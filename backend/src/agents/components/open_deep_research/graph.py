import functools
import json
import re
import time
import uuid
from typing import Any, List, Literal, Optional, Tuple

import langsmith as ls
import requests
import structlog

# We import our data models
from agents.api.data_types import DeepCitation, DeepResearchSection
from agents.api.utils import generate_report_pdf
from agents.components.compound.data_types import LLMType
from agents.components.compound.timing_aggregator import WorkflowTimingAggregator
from agents.components.open_deep_research.configuration import Configuration, SearchAPI
from agents.components.open_deep_research.prompts import (
    final_section_writer_instructions,
    query_writer_instructions,
    report_planner_instructions,
    report_planner_query_writer_instructions,
    section_grader_instructions,
    section_writer_instructions,
)
from agents.components.open_deep_research.state import (
    Feedback,
    Queries,
    ReportState,
    ReportStateInput,
    ReportStateOutput,
    SectionOutputState,
    Sections,
    SectionState,
)
from agents.components.open_deep_research.utils import (
    deduplicate_and_format_sources,
    format_sections,
    perplexity_search,
    tavily_search_async,
)
from agents.registry.model_registry import model_registry
from agents.storage.redis_storage import RedisStorage
from agents.utils.logging_utils import setup_logging_context
from agents.utils.message_interceptor import MessageInterceptor
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_fireworks import ChatFireworks
from langchain_openai import ChatOpenAI
from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph
from langgraph.types import Checkpointer, Command, interrupt

logger = structlog.get_logger(__name__)


class CleanContentParser(BaseOutputParser):
    """
    Extract only the content field from AIMessage, removing any reasoning artifacts.

    This parser is used to clean up output from reasoning models that may include
    chain-of-thought reasoning, confidence scores, or meta-commentary in their responses.
    """

    def parse(self, text: str) -> str:
        """
        Parse the output and remove reasoning artifacts wrapped in <step> and <count> tags.
        When chained after an AIMessage, this extracts just the .content field.
        """
        # Remove <step>...</step> blocks (multiline)
        # Pattern: **<step>** or **<step> ** ... </step> or </step>**
        # More flexible to handle variations from different reasoning models
        text = re.sub(r'\*\*<step>(?:\s?\*\*)?.*?</step>(?:\*\*)?', '', text, flags=re.DOTALL)

        # Also remove standalone </step> tags that might be left over
        text = re.sub(r'</step>', '', text, flags=re.IGNORECASE)

        # Remove <count>...</count> lines
        # Pattern: **<count> N </count>**
        text = re.sub(r'\*\*<count>.*?</count>\*\*', '', text)

        # Remove standalone number lines (artifacts left over)
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Skip lines that are just numbers (including decimals like 0.9, 0.8)
            if stripped and re.match(r'^\d+\.?\d*$', stripped):
                continue

            # Skip leftover "Sources" headers without content
            # These should have been extracted already, so any remaining are artifacts
            lower_stripped = stripped.lower()
            if lower_stripped in ['sources', 'sources:', '### sources', '## sources']:
                continue

            cleaned_lines.append(line)

        cleaned_text = '\n'.join(cleaned_lines).strip()

        return cleaned_text

    @property
    def _type(self) -> str:
        return "clean_content"


class LLMTimeoutError(Exception):
    """Custom exception for LLM timeout."""

    def __init__(self, message="LLM request timed out after the specified duration"):
        self.message = message
        super().__init__(self.message)


def get_model_name(llm):
    if hasattr(llm, "model_name"):
        return llm.model_name
    elif hasattr(llm, "model"):
        return llm.model
    else:
        return "Unknown Model"


def parse_reference_line(line: str) -> DeepCitation:
    """
    If the line has an http/https link, store that as url, everything before is "title".
    If no URL found, return a citation with empty url => skip it upstream.
    """
    # remove bullet chars
    line = line.lstrip("*-0123456789. ").strip()
    # find a link
    match = re.search(r"(https?://[^\s]+)", line)
    if not match:
        # no link => skip
        return DeepCitation(title="", url="")  # no URL
    url = match.group(1)
    # everything prior to the url is the title
    idx = line.find(url)
    title = line[:idx].strip(" :")
    return DeepCitation(title=title, url=url)


def extract_sources_block(section_text: str) -> Tuple[str, List[DeepCitation]]:
    """
    If there's a block after ### Sources or ## Sources or 'Sources:'
    parse them line by line.
    Remove that block from the text. Return cleaned text + references array.
    """
    lines = section_text.split("\n")
    cleaned_lines = []
    citations: List[DeepCitation] = []

    in_sources = False

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        lower_line = line.lower().strip()
        # detect the start
        if not in_sources and (
            lower_line == "### sources"
            or lower_line == "## sources"
            or lower_line == "sources:"
        ):
            # from next line onward => references
            in_sources = True
            i += 1
            continue

        if in_sources:
            # if blank or new heading => end
            if not line.strip() or re.match(r"#+\s", line):
                # end
                in_sources = False
                # do not add line to cleaned
                i += 1
                continue
            # parse the line
            ref = parse_reference_line(line)
            # if no url => skip
            if ref.url:
                citations.append(ref)
        else:
            cleaned_lines.append(line)
        i += 1

    new_text = "\n".join(cleaned_lines).strip()
    return new_text, citations


def remove_inline_citation_lines(text: str) -> Tuple[str, List[DeepCitation]]:
    """
    If you want to forcibly remove lines that look like a bullet with 'http'
    but are not in the sources block, you can parse them here.
    We'll only remove lines that start with "* " or "- " or some bullet + a link.
    """
    lines = text.split("\n")
    new_lines = []
    found: List[DeepCitation] = []

    for line in lines:
        trimmed = line.strip()
        # check if it starts with bullet
        if re.match(r"^(\*|-)\s+", trimmed):
            # check for a url
            match = re.search(r"(https?://[^\s]+)", trimmed)
            if match:
                # parse
                ref = parse_reference_line(trimmed)
                if ref.url:  # store
                    found.append(ref)
                # skip line
                continue
        # else keep
        new_lines.append(line)
    return "\n".join(new_lines), found


def get_session_id_from_config(config: Configuration) -> Optional[str]:
    """
    Extract and format session ID from RunnableConfig.
    Returns None if user_id or conversation_id is missing.
    """
    if config.user_id and config.conversation_id:
        return f"{config.user_id}:{config.conversation_id}"
    return None


@ls.traceable(
    metadata={
        "agent_type": "deep_research_agent",
        "llm_type": LLMType.SN_LLAMA_MAVERICK.value,
    },
    process_inputs=lambda x: None,
)
async def generate_report_plan(
    writer_model, planner_model, summary_model, state: ReportState, config: RunnableConfig
):
    # Capture workflow start time at the very beginning
    workflow_start_time = state.get("workflow_start_time") or time.time()

    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(config, node="generate_report_plan", session_id=session_id)
    topic = state["topic"]
    feedback = state.get("feedback_on_report_plan", None)

    logger.info("Generating report plan", topic=topic)
    if feedback:
        logger.info("Incorporating feedback on report plan", feedback=feedback)

    if isinstance(configurable.report_structure, dict):
        report_structure = str(configurable.report_structure)
    else:
        report_structure = configurable.report_structure

    search_queries_interceptor = MessageInterceptor()

    structured_llm = (
        writer_model
        | RunnableLambda(search_queries_interceptor.capture_and_pass)
        | OutputFixingParser.from_llm(
            llm=summary_model,  # Use summary model for fixing
            parser=PydanticOutputParser(pydantic_object=Queries),
        )
    )

    schema = Queries.model_json_schema()
    report_planner_schema = json.dumps(schema, indent=2)

    system_instructions_query = report_planner_query_writer_instructions.format(
        topic=topic,
        report_organization=report_structure,
        number_of_queries=configurable.number_of_queries,
        report_planner_schema=report_planner_schema,
    )

    logger.info("Generating initial search queries for planning")

    results = await invoke_llm_with_tracking(
        llm=structured_llm,
        messages=[
            SystemMessage(content=system_instructions_query),
            HumanMessage(
                content="Generate search queries that will help with planning the sections of the report."
            ),
        ],
        task="Generate initial planning queries",
        config=configurable,
        llm_name=get_model_name(writer_model),
    )

    query_list = [q.search_query for q in results.queries]
    logger.info("Generated initial search queries", num_queries=len(query_list))

    logger.info("Starting web search for planning", search_api=configurable.search_api)
    start_time = time.time()
    if configurable.search_api == SearchAPI.TAVILY:
        logger.info("Using Tavily API for search", num_queries=len(query_list))
        search_results = await tavily_search_async(
            query_list, configurable.api_key_rotator
        )
        source_str = deduplicate_and_format_sources(
            search_results, max_tokens_per_source=1500, include_raw_content=False
        )
    elif configurable.search_api == SearchAPI.PERPLEXITY:
        search_results = perplexity_search(query_list, configurable.api_key_rotator)
        source_str = deduplicate_and_format_sources(
            search_results, max_tokens_per_source=1000, include_raw_content=False
        )
    else:
        logger.error("Unsupported search API", search_api=configurable.search_api)
        raise ValueError(f"Unsupported search API: {configurable.search_api}")

    duration = time.time() - start_time
    logger.info(
        "Web search for planning completed", duration_ms=round(duration * 1000, 2)
    )

    schema = Sections.model_json_schema()
    report_planner_schema = json.dumps(schema, indent=2)

    logger.info("Generating final report sections plan")
    system_instructions_sections = report_planner_instructions.format(
        topic=topic,
        report_organization=report_structure,
        context=source_str,
        feedback=feedback,
        report_planner_schema=report_planner_schema,
    )

    search_sections_interceptor = MessageInterceptor()
    structured_llm = (
        planner_model
        | RunnableLambda(search_sections_interceptor.capture_and_pass)
        | OutputFixingParser.from_llm(
            llm=planner_model, parser=PydanticOutputParser(pydantic_object=Sections)
        )
    )

    report_sections = await invoke_llm_with_tracking(
        llm=structured_llm,
        messages=[
            SystemMessage(content=system_instructions_sections),
            HumanMessage(
                content="Generate the sections of the report. Your response must include a 'sections' field containing a list of sections. Each section must have: name, description, plan, research, and content fields."
            ),
        ],
        task="Generate report sections plan",
        config=configurable,
        llm_name=get_model_name(planner_model),
    )

    sections = report_sections.sections
    logger.info("Generated report plan", num_sections=len(sections))

    # tag and concatenate the captured messages
    captured_messages = []

    for m in search_queries_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_search_queries_plan"
        captured_messages.append(m)

    for m in search_sections_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_search_sections"
        captured_messages.append(m)

    return {
        "sections": sections,
        "messages": captured_messages,
        "workflow_start_time": workflow_start_time,
    }


async def human_feedback(
    state: ReportState, config: RunnableConfig
) -> Command[
    Literal[
        "generate_report_plan", "build_section_with_web_research", "summarize_documents"
    ]
]:
    sections = state["sections"]
    sec_str = (
        "Please <b>provide feedback</b> on the following plan or <b>type 'approve'.</b>\n"
        + "\n".join(
            f"<b>Section {i+1}:</b> {s.name} - {s.description}"
            for i, s in enumerate(sections)
        )
    )
    logger.info("Interrupting for human feedback", sections=sec_str)
    fb = interrupt(sec_str)
    if fb == "APPROVE":
        if state.get("document"):
            return Command(goto="summarize_documents")
        else:
            return Command(
                goto=[
                    Send(
                        "build_section_with_web_research",
                        {"section": s, "search_iterations": 0},
                    )
                    for s in sections
                    if s.research
                ]
            )
    else:
        return Command(
            goto="generate_report_plan", update={"feedback_on_report_plan": fb}
        )


@ls.traceable(
    metadata={
        "agent_type": "deep_research_agent",
        "llm_type": LLMType.SN_LLAMA_MAVERICK.value,
    },
    process_inputs=lambda x: None,
)
async def generate_queries(writer_model, summary_model, state: SectionState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    sec = state["section"]
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(
        config,
        node="generate_queries",
        session_id=session_id,
        section_name=sec.name,
    )

    logger.info("Generating queries for section")

    search_queries_interceptor = MessageInterceptor()

    structured_llm = (
        writer_model
        | RunnableLambda(search_queries_interceptor.capture_and_pass)
        | OutputFixingParser.from_llm(
            llm=summary_model,  # Use summary model for fixing
            parser=PydanticOutputParser(pydantic_object=Queries),
        )
    )

    schema = Queries.model_json_schema()
    queries_schema = json.dumps(schema, indent=2)

    sys_inst = query_writer_instructions.format(
        section_topic=sec.description,
        number_of_queries=configurable.number_of_queries,
        queries_schema=queries_schema,
    )

    queries = await invoke_llm_with_tracking(
        llm=structured_llm,
        messages=[
            SystemMessage(content=sys_inst),
            HumanMessage(content="Generate search queries."),
        ],
        task="Generate search queries",
        config=configurable,
        llm_name=get_model_name(writer_model),
    )

    logger.info("Generated queries", num_queries=len(queries.queries))

    captured_message = []
    for m in search_queries_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_search_queries_section"
        captured_message.append(m)

    return {"search_queries": queries.queries, "messages": captured_message}


async def search_web(state: SectionState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    sq = state["search_queries"]
    session_id = get_session_id_from_config(configurable)
    section_name = state["section"].name if state.get("section") else "N/A"
    setup_logging_context(
        config,
        node="search_web",
        session_id=session_id,
        section_name=section_name,
    )

    query_list = [q.search_query for q in sq]
    logger.info("Executing web search", num_queries=len(query_list))

    logger.info("Starting web search", search_api=configurable.search_api)
    start_time = time.time()
    if configurable.search_api == SearchAPI.TAVILY:
        logger.info("Using Tavily API for search", num_queries=len(query_list))
        search_results = await tavily_search_async(
            query_list, configurable.api_key_rotator
        )
        src_str = deduplicate_and_format_sources(
            search_results, max_tokens_per_source=1500, include_raw_content=True
        )
    elif configurable.search_api == SearchAPI.PERPLEXITY:
        search_results = perplexity_search(query_list, configurable.api_key_rotator)
        src_str = deduplicate_and_format_sources(
            search_results, max_tokens_per_source=5000, include_raw_content=False
        )
    else:
        logger.error("Unsupported search API", search_api=configurable.search_api)
        raise ValueError(f"Unsupported search API: {configurable.search_api}")

    duration = time.time() - start_time
    logger.info("Web search completed", duration_ms=round(duration * 1000, 2))
    return {"source_str": src_str, "search_iterations": state["search_iterations"] + 1}


async def invoke_llm_with_tracking(
    llm,
    messages: List[Any],
    task: str,
    llm_name: str,
    config: RunnableConfig,
) -> Any:
    """Helper function to invoke LLM with timing and usage tracking.

    Args:
        llm: The LLM to invoke
        messages: List of messages to send to the LLM
        task: Description of the task being performed
        config: RunnableConfig for the LLM
        usage_handler: UsageCallback instance to track usage
        configurable: Configuration instance
        timeout_seconds: Maximum time in seconds to wait for LLM response

    Returns:

    Raises:
        LLMTimeoutError: If the LLM request exceeds the timeout duration
    """
    logger.info("Invoking LLM", task=task, llm_name=llm_name)
    start_time = time.time()
    try:
        response = await llm.ainvoke(messages)
    except requests.exceptions.ReadTimeout as e:
        logger.error("LLM invocation ReadTimeout", error=str(e), exc_info=True)
        raise LLMTimeoutError(f"Request timed out: {str(e)}") from e

    duration = time.time() - start_time

    logger.info(
        "LLM invocation completed",
        task=task,
        duration_ms=round(duration * 1000, 2),
        model=llm_name,
    )
    return response


@ls.traceable(
    metadata={
        "agent_type": "deep_research_agent",
        "llm_type": LLMType.SN_LLAMA_MAVERICK.value,
    },
    process_inputs=lambda x: None,
)
async def write_section(
    writer_model, summary_model, state: SectionState, config: RunnableConfig
) -> Command[Literal["__end__", "search_web"]]:
    configurable = Configuration.from_runnable_config(config)
    sec = state["section"]
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(
        config,
        node="write_section",
        session_id=session_id,
        section_name=sec.name,
    )

    logger.info("Writing section")
    src = state["source_str"]
    doc_summary = state.get("document_summary", "")
    sys_inst = section_writer_instructions.format(
        section_title=sec.name,
        section_topic=sec.description,
        context=src,
        section_content=sec.content,
        document_summary=doc_summary,
    )
    writer_interceptor = MessageInterceptor()
    writer_model_with_interceptor = (
        writer_model
        | RunnableLambda(writer_interceptor.capture_and_pass)
    )

    content = await invoke_llm_with_tracking(
        llm=writer_model_with_interceptor,
        messages=[
            SystemMessage(content=sys_inst),
            HumanMessage(content="Write the section."),
        ],
        task=f"Write section - {sec.name}",
        config=configurable,
        llm_name=get_model_name(writer_model),
    )

    sec.content = content.content if hasattr(content, 'content') else content
    logger.info("Generated content for section", section_name=sec.name)

    schema = Feedback.model_json_schema()
    section_grader_schema = json.dumps(schema, indent=2)

    # now we grade - use summary model (stronger) for grading
    logger.info("Grading section", section_name=sec.name)
    grader_inst = section_grader_instructions.format(
        section_topic=sec.description,
        section=sec.content,
        section_grader_schema=section_grader_schema,
    )

    grader_interceptor = MessageInterceptor()

    structured_llm = (
        summary_model
        | RunnableLambda(grader_interceptor.capture_and_pass)
        | OutputFixingParser.from_llm(
            llm=summary_model, parser=PydanticOutputParser(pydantic_object=Feedback)
        )
    )

    fb = await invoke_llm_with_tracking(
        llm=structured_llm,
        messages=[SystemMessage(content=grader_inst), HumanMessage(content="Grade it")],
        task=f"Grade section - {sec.name}",
        config=configurable,
        llm_name=get_model_name(writer_model),
    )

    captured_messages = []
    for m in writer_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_writer"
        captured_messages.append(m)

    for m in grader_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_grader"
        captured_messages.append(m)

    # Clean reasoning artifacts from section content before adding to completed_sections
    # This ensures the UI displays clean content as sections stream in
    if sec.content:
        parser = CleanContentParser()
        sec.content = parser.parse(sec.content)

    if fb.grade == "pass":
        logger.info("Section passed grading", section_name=sec.name)
        return Command(
            update={"completed_sections": [sec], "messages": captured_messages},
            goto=END,
        )
    elif (
        state["search_iterations"]
        >= Configuration.from_runnable_config(config).max_search_depth
    ):
        logger.warning(
            "Section reached max search iterations, moving on",
            section_name=sec.name,
            max_iterations=state["search_iterations"],
        )
        return Command(
            update={"completed_sections": [sec], "messages": captured_messages},
            goto=END,
        )
    else:
        logger.info(
            "Section needs revision, doing another search iteration",
            section_name=sec.name,
            feedback=fb.feedback,
            queries=fb.follow_up_queries,
        )
        return Command(
            update={
                "search_queries": fb.follow_up_queries,
                "section": sec,
                "messages": captured_messages,
            },
            goto="search_web",
        )


@ls.traceable(
    metadata={
        "agent_type": "deep_research_agent",
        "llm_type": LLMType.SN_LLAMA_MAVERICK.value,
    },
    process_inputs=lambda x: None,
)
async def write_final_sections(
    writer_model, state: SectionState, config: RunnableConfig
):
    configurable = Configuration.from_runnable_config(config)
    sec = state["section"]
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(
        config,
        node="write_final_sections",
        session_id=session_id,
        section_name=sec.name,
    )

    logger.info("Writing final section")
    rep = state["report_sections_from_research"]

    sys_inst = final_section_writer_instructions.format(
        section_title=sec.name, section_topic=sec.description, context=rep
    )

    writer_interceptor = MessageInterceptor()
    writer_model_with_interceptor = (
        writer_model
        | RunnableLambda(writer_interceptor.capture_and_pass)
    )

    content = await invoke_llm_with_tracking(
        llm=writer_model_with_interceptor,
        messages=[
            SystemMessage(content=sys_inst),
            HumanMessage(content="Write final section."),
        ],
        task="Write final section",
        config=configurable,
        llm_name=get_model_name(writer_model),
    )

    sec.content = content.content if hasattr(content, 'content') else content

    # Clean reasoning artifacts from final section content before adding to completed_sections
    # This ensures the UI displays clean content as sections stream in
    if sec.content:
        parser = CleanContentParser()
        sec.content = parser.parse(sec.content)

    logger.info("Completed final section", section_name=sec.name)

    captured_messages = []
    for m in writer_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_final_section_writer"
        captured_messages.append(m)

    return {"completed_sections": [sec], "messages": captured_messages}


async def gather_completed_sections(state: ReportState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(
        config, node="gather_completed_sections", session_id=session_id
    )
    comps = state["completed_sections"]

    logger.info("Gathering completed sections", num_sections=len(comps))
    rep = format_sections(comps)
    return {"report_sections_from_research": rep}


async def initiate_final_section_writing(state: ReportState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(
        config, node="initiate_final_section_writing", session_id=session_id
    )
    non_research_sections = [s for s in state["sections"] if not s.research]
    logger.info(
        "Initiating writing of final sections",
        num_sections=len(non_research_sections),
    )
    return [
        Send(
            "write_final_sections",
            {
                "section": s,
                "report_sections_from_research": state["report_sections_from_research"],
            },
        )
        for s in non_research_sections
    ]


async def compile_final_report(
    state: ReportState,
    config: RunnableConfig,
    redis_storage: RedisStorage,
    user_id: str,
    workflow_start_time: float = None,
):
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(config, node="compile_final_report", session_id=session_id)

    # Track workflow timing - get from state if not passed as parameter
    if workflow_start_time is None:
        workflow_start_time = state.get("workflow_start_time") or time.time()
        logger.info(
            "Using workflow_start_time from state",
            workflow_start_time=workflow_start_time,
            from_state=state.get("workflow_start_time") is not None,
        )

    sections = state["sections"]
    logger.info("Compiling final report", num_sections=len(sections))
    completed_map = {s.name: s.content for s in state["completed_sections"]}

    deep_sections: List[DeepResearchSection] = []
    all_citations: List[DeepCitation] = []

    for sec in sections:
        content = completed_map.get(sec.name, sec.content or "")

        # 1) strip any sources block (extract BEFORE cleaning reasoning artifacts)
        cleaned, block_refs = extract_sources_block(content)

        # 2) clean reasoning artifacts from content (after sources extracted)
        parser = CleanContentParser()
        cleaned = parser.parse(cleaned)

        # 3) optionally remove bullet lines that contain URLs but are not in sources block
        # if we want to keep inline links in the text, skip this step or tweak it
        final_cleaned, inline_refs = remove_inline_citation_lines(cleaned)

        # combine
        # only keep references that have a valid url
        block_refs = [r for r in block_refs if r.url.strip()]
        inline_refs = [r for r in inline_refs if r.url.strip()]
        all_citations.extend(block_refs)
        all_citations.extend(inline_refs)

        deep_sections.append(
            DeepResearchSection(
                name=sec.name,
                description=sec.description,
                content=final_cleaned.strip(),
                citations=[],  # we skip local citations array
            )
        )

    # Deduplicate citations by URL (keep first occurrence)
    # This prevents the same source appearing hundreds of times
    original_citation_count = len(all_citations)
    seen_urls = {}
    for citation in all_citations:
        if citation.url not in seen_urls:
            seen_urls[citation.url] = citation
    all_citations = list(seen_urls.values())

    logger.info(
        "Deduplicated citations",
        original_count=original_citation_count,
        unique_count=len(all_citations)
    )

    # build final text
    lines = []
    for ds in deep_sections:
        lines.append(f"# {ds.name}\n{ds.content}\n")

    # final citations at end
    if all_citations:
        lines.append("## Citations\n")
        for c in all_citations:
            title = c.title.strip() or "Untitled"
            url = c.url.strip()
            lines.append(f"- [{title}]({url})")

    final_text = "\n".join(lines).strip()

    logger.info(
        "Completed report compilation",
        num_sections=len(deep_sections),
        num_citations=len(all_citations),
    )
    pdf_report_file_id = None
    try:
        # Generate PDF
        if final_text:
            pdf_result = await generate_report_pdf(final_text, "Deep Research Report")
            if pdf_result:
                pdf_report_file_id, filename, pdf_data = pdf_result

                # Store the PDF file in Redis
                await redis_storage.put_file(
                    user_id=user_id,
                    file_id=pdf_report_file_id,
                    data=pdf_data,
                    filename=filename,
                    format="application/pdf",
                    upload_timestamp=time.time(),
                    indexed=False,
                    source="deep_research_pdf",
                    vector_ids=[],
                )

                logger.info(
                    "PDF generated and attached to deep research message",
                    file_id=pdf_report_file_id,
                    filename=filename,
                )

    except Exception as e:
        logger.error(
            "Failed to generate PDF for deep research report",
            error=str(e),
        )
        # Continue without PDF - don't fail the message sending

    # Build hierarchical timing structure
    # CRITICAL: Capture workflow end time IMMEDIATELY to ensure accurate duration
    workflow_end_time = time.time()
    workflow_duration = workflow_end_time - workflow_start_time

    logger.info(
        "Deep research workflow timing captured",
        workflow_start_time=workflow_start_time,
        workflow_end_time=workflow_end_time,
        workflow_duration=round(workflow_duration, 2),
    )

    # Collect all captured messages from state
    all_messages_raw = state.get("messages", [])

    # DEBUG: Check for potential message duplication BEFORE deduplication
    logger.info(
        "[DUPLICATION_DEBUG] Messages BEFORE deduplication",
        total_messages=len(all_messages_raw),
        message_types=[type(msg).__name__ for msg in all_messages_raw],
        message_ids=[getattr(msg, 'id', 'NO_ID') for msg in all_messages_raw],
        num_unique_ids=len(set(getattr(msg, 'id', f'no_id_{i}') for i, msg in enumerate(all_messages_raw))),
    )

    # CRITICAL FIX: Deduplicate messages by ID before aggregating timing
    # This fixes the issue where parallel Send() branches cause message duplication
    seen_message_ids = set()
    all_messages = []
    for msg in all_messages_raw:
        msg_id = getattr(msg, 'id', None)
        if msg_id and msg_id not in seen_message_ids:
            seen_message_ids.add(msg_id)
            all_messages.append(msg)
        elif not msg_id:
            # Keep messages without IDs
            all_messages.append(msg)

    logger.info(
        "[DUPLICATION_DEBUG] Messages AFTER deduplication",
        total_messages_before=len(all_messages_raw),
        total_messages_after=len(all_messages),
        duplicates_removed=len(all_messages_raw) - len(all_messages),
    )

    # Create timing aggregator with correct workflow start time
    timing_aggregator = WorkflowTimingAggregator()
    timing_aggregator.workflow_start_time = workflow_start_time

    # Extract main agent timing from config metadata
    main_agent_calls = []
    if config and "metadata" in config and "main_agent_timing" in config["metadata"]:
        main_timing = config["metadata"]["main_agent_timing"]
        logger.info("Retrieved main agent timing from config metadata", main_timing=main_timing)

        timing_aggregator.add_main_agent_call(
            node_name=main_timing.get("node_name", "agent_node"),
            agent_name=main_timing.get("agent_name", "XML Agent"),
            model_name=main_timing.get("model_name", "unknown"),
            duration=main_timing.get("duration", 0),
            start_time=main_timing.get("start_time", workflow_start_time),
        )
    else:
        logger.warning(
            "Main agent timing not found in config metadata",
            has_config=config is not None,
            has_metadata=config and "metadata" in config,
            metadata_keys=list(config["metadata"].keys()) if config and "metadata" in config else None,
        )

    # Aggregate timing from all captured messages
    agent_timing_map = {}  # agent_name -> {duration, num_calls, model, calls: []}
    agent_call_counters = {}  # Track call indices per agent
    model_breakdown = []

    # Track actual message timestamps to capture concurrency
    earliest_timestamp = None
    messages_with_timestamps = []

    # First pass: collect all messages with timestamps
    for msg in all_messages:
        if hasattr(msg, 'response_metadata') and msg.response_metadata:
            usage = msg.response_metadata.get('usage', {})
            total_latency = usage.get('total_latency', 0)

            # Try to get timestamp from message
            # Check additional_kwargs for timing data from MessageInterceptor
            timestamp = None
            if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs:
                timing = msg.additional_kwargs.get('timing', {})
                if timing and 'end_time' in timing:
                    # Use end_time from interceptor and calculate start from duration
                    timestamp = timing['end_time'] - total_latency

            # If no timestamp from interceptor, estimate based on workflow progression
            # This is less accurate but better than nothing
            if timestamp is None:
                timestamp = None  # Will use position-based offset as fallback

            messages_with_timestamps.append({
                'msg': msg,
                'timestamp': timestamp,
                'duration': total_latency,
            })

            if timestamp is not None and (earliest_timestamp is None or timestamp < earliest_timestamp):
                earliest_timestamp = timestamp

    # If we have no timestamps, fall back to workflow start time
    if earliest_timestamp is None:
        earliest_timestamp = workflow_start_time
        logger.warning(
            "No message timestamps found, using workflow start time as baseline",
            workflow_start_time=workflow_start_time,
        )
    else:
        logger.info(
            "Found message timestamps for concurrency tracking",
            earliest_timestamp=earliest_timestamp,
            num_messages_with_timestamps=sum(1 for m in messages_with_timestamps if m['timestamp'] is not None),
            total_messages=len(messages_with_timestamps),
        )

    # Sort messages by timestamp (start time) to preserve execution order for waterfall
    # Messages with timestamps come first (sorted by time), then messages without timestamps
    messages_with_timestamps.sort(key=lambda x: (x['timestamp'] is None, x['timestamp'] if x['timestamp'] else 0))

    logger.info(
        "[CONCURRENCY_DEBUG] Messages sorted by timestamp",
        num_with_timestamps=sum(1 for m in messages_with_timestamps if m['timestamp'] is not None),
        first_3_timestamps=[m['timestamp'] for m in messages_with_timestamps[:3] if m['timestamp']],
    )

    # Second pass: aggregate with proper start_offset based on timestamps
    for i, msg_data in enumerate(messages_with_timestamps):
        msg = msg_data['msg']
        timestamp = msg_data['timestamp']
        total_latency = msg_data['duration']

        # Calculate start_offset relative to earliest message
        if timestamp is not None:
            start_offset = timestamp - earliest_timestamp
        else:
            # Fallback: use position-based estimate (assumes sequential execution)
            # This is used when MessageInterceptor timing is not available
            if i == 0:
                start_offset = 0
            else:
                # Use previous message's end time
                prev_start = messages_with_timestamps[i-1].get('calculated_start', 0)
                prev_duration = messages_with_timestamps[i-1]['duration']
                start_offset = prev_start + prev_duration

        # Store calculated start for next iteration
        msg_data['calculated_start'] = start_offset

        usage = msg.response_metadata.get('usage', {})
        agent_type = msg.additional_kwargs.get('agent_type', 'unknown') if hasattr(msg, 'additional_kwargs') else 'unknown'
        model_name = msg.response_metadata.get('model_name', 'unknown')

        # Track call index for this agent
        if agent_type not in agent_call_counters:
            agent_call_counters[agent_type] = 0
        agent_call_counters[agent_type] += 1

        # Aggregate by agent
        if agent_type not in agent_timing_map:
            agent_timing_map[agent_type] = {
                'agent_name': agent_type,
                'total_duration': 0,
                'num_calls': 0,
                'model_name': model_name,
                'calls': [],  # Store individual calls for this agent
                'start_time': start_offset,  # Track when this agent first appeared
            }

        agent_timing_map[agent_type]['total_duration'] += total_latency
        agent_timing_map[agent_type]['num_calls'] += 1

        # Update agent's start_time if this call started earlier
        if start_offset < agent_timing_map[agent_type]['start_time']:
            agent_timing_map[agent_type]['start_time'] = start_offset

        # Create individual call entry with actual timestamp-based offset
        call_entry = {
            'model_name': model_name,
            'provider': model_name.split('/')[0] if '/' in model_name else 'sambanova',
            'duration': total_latency,
            'start_offset': start_offset,  # Use actual timestamp for concurrency visualization
            'call_index': agent_call_counters[agent_type],
        }

        # Add to agent's calls array
        agent_timing_map[agent_type]['calls'].append(call_entry)

        # Add to model breakdown with actual start_offset
        model_breakdown.append({
            'agent_name': agent_type,
            'model_name': model_name,
            'provider': model_name.split('/')[0] if '/' in model_name else 'sambanova',
            'duration': total_latency,
            'start_offset': start_offset,  # Use actual timestamp for concurrency visualization
            'call_index': agent_call_counters[agent_type],
        })

    # Calculate total duration for percentage calculations
    total_duration = sum(m['duration'] for m in model_breakdown)

    # Add percentage to model breakdown entries
    for entry in model_breakdown:
        entry['percentage'] = (entry['duration'] / total_duration * 100) if total_duration > 0 else 0

    # Add percentage to each call in agent_timing_map
    for agent_data in agent_timing_map.values():
        for call in agent_data['calls']:
            call['percentage'] = (call['duration'] / total_duration * 100) if total_duration > 0 else 0

    # Convert agent timing map to list with start_offset, percentage, and calls array
    agent_breakdown = [
        {
            'agent_name': v['agent_name'],
            'num_calls': v['num_calls'],
            'total_duration': v['total_duration'],
            'model_name': v['model_name'],
            'start_offset': v['start_time'],  # Use tracked start time for waterfall
            'percentage': (v['total_duration'] / total_duration * 100) if total_duration > 0 else 0,
            'calls': v['calls'],  # Include individual calls array for frontend drill-down
        }
        for v in agent_timing_map.values()
    ]

    logger.info(
        "Aggregated timing from messages (AFTER deduplication)",
        num_messages_deduplicated=len(all_messages),
        num_agents=len(agent_breakdown),
        num_model_calls=len(model_breakdown),
        total_duration=round(total_duration, 2),
    )

    # DEBUG: Log breakdown details with call counts per agent
    logger.info(
        "[DUPLICATION_DEBUG] Message aggregation complete (deduplicated counts)",
        messages_with_timing=sum(1 for msg in all_messages if hasattr(msg, 'response_metadata') and msg.response_metadata and msg.response_metadata.get('usage', {}).get('total_latency')),
        model_breakdown_count=len(model_breakdown),
        agent_breakdown_summary={agent['agent_name']: agent['num_calls'] for agent in agent_breakdown},
        total_llm_calls_in_subgraph=len(model_breakdown),
    )

    # Add subgraph timing
    if agent_breakdown or model_breakdown:
        subgraph_start_offset = timing_aggregator.main_agent_calls[0]['duration'] if timing_aggregator.main_agent_calls else 0
        timing_aggregator.add_subgraph_timing(
            subgraph_name="Deep Research",
            subgraph_duration=workflow_duration,
            subgraph_start_time=workflow_start_time,
            agent_breakdown=agent_breakdown,
            model_breakdown=model_breakdown,
        )

    # Get final hierarchical timing structure with explicit end time to prevent recalculation
    # CRITICAL: Pass workflow_end_time to prevent get_hierarchical_timing() from recalculating
    hierarchical_timing = timing_aggregator.get_hierarchical_timing(workflow_end_time=workflow_end_time)

    logger.info(
        "Created hierarchical timing structure for deep research",
        total_llm_calls=hierarchical_timing["total_llm_calls"],
        num_levels=len(hierarchical_timing["levels"]),
        workflow_duration_calculated=round(hierarchical_timing["workflow_duration"], 2),
        workflow_duration_actual=round(workflow_duration, 2),
        duration_match=abs(hierarchical_timing["workflow_duration"] - workflow_duration) < 0.1,
    )

    # CRITICAL DEBUG: Log the exact contents before returning to verify it's non-empty
    logger.info(
        "[COMPILE_DEBUG] About to return state with workflow_timing",
        workflow_timing_keys=list(hierarchical_timing.keys()) if hierarchical_timing else "EMPTY",
        workflow_timing_is_dict=isinstance(hierarchical_timing, dict),
        workflow_timing_bool=bool(hierarchical_timing),
        total_llm_calls=hierarchical_timing.get("total_llm_calls", "MISSING") if hierarchical_timing else "EMPTY_DICT",
    )

    # Create timing message to carry workflow_timing to frontend (matches financial analysis pattern)
    # This message will be added to state["messages"] and streamed to frontend with timing data
    # IMPORTANT: Do NOT include model_name in response_metadata - that causes frontend to count this as an LLM call
    timing_message = AIMessage(
        content="",  # Empty content, just carrying timing metadata
        id=str(uuid.uuid4()),
        additional_kwargs={
            "agent_type": "deep_research_timing",
            "workflow_timing": hierarchical_timing,
        },
        response_metadata={
            # Do not include model_name here - frontend counts messages with model_name as LLM calls
            "usage": {
                "total_latency": workflow_duration
            },
        },
    )

    logger.info(
        "[COMPILE_DEBUG] Created timing message for deep research",
        has_workflow_timing="workflow_timing" in timing_message.additional_kwargs,
        workflow_timing_is_empty=not bool(timing_message.additional_kwargs.get("workflow_timing", {})),
        total_llm_calls=hierarchical_timing.get("total_llm_calls", 0),
        agent_type=timing_message.additional_kwargs.get("agent_type"),
        message_id=timing_message.id,
    )

    logger.info(
        "[LIVE_COUNT_FIX] Timing message contains authoritative LLM count",
        total_llm_calls_deduplicated=hierarchical_timing.get("total_llm_calls", 0),
        agent_type_for_frontend_filter="deep_research_timing",
        message_will_stream_to_frontend=True,
    )

    return {
        "final_report": final_text,
        "pdf_report": pdf_report_file_id,
        "workflow_timing": hierarchical_timing,
        "messages": [timing_message],  # Add timing message to state messages
    }


async def summarize_documents(
    summary_model, state: ReportState, config: RunnableConfig
):
    """
    Summarize provided documents if they exist.
    """
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(config, node="summarize_documents", session_id=session_id)

    document = state.get("document", None)

    if not document:
        logger.warning("No document found to summarize.")

    sys_inst = """You are a document summarizer. Your task is to:
    1. Read through the provided documents
    2. Extract the key information, main points, and important findings
    3. Create a comprehensive but concise summary that captures the essential information
    4. Focus on factual information that would be relevant for research
    5. Maintain objectivity and accuracy
    
    Format your response as a clear, well-structured summary."""

    summary = await invoke_llm_with_tracking(
        llm=summary_model,
        messages=[
            SystemMessage(content=sys_inst),
            HumanMessage(
                content=f"Please summarize the following document:\n\n{document}"
            ),
        ],
        task="Summarize provided document",
        config=configurable,
        llm_name=get_model_name(summary_model),
    )

    # After summarization, initiate section building
    sections = state.get("sections", [])
    return Command(
        goto=[
            Send(
                "build_section_with_web_research",
                {
                    "section": s,
                    "search_iterations": 0,
                    "document_summary": summary.content,
                },
            )
            for s in sections
            if s.research
        ]
    )


def create_deep_research_graph(
    api_key: str,
    provider: str,
    redis_storage: RedisStorage,
    user_id: str,
    request_timeout: int = 120,
    checkpointer: Checkpointer = None,
    api_keys: dict = None,
):
    """
    Create and configure the graph for deep research.

    Args:
        api_key: The API key for the LLM provider (for backward compatibility)
        provider: The LLM provider to use (fireworks or sambanova)
        redis_storage: Redis storage for persistence
        user_id: User ID for configuration lookup
        request_timeout: Request timeout in seconds
        checkpointer: Optional checkpointer
        api_keys: Dictionary of API keys by provider (preferred over api_key)
    """
    logger.info(
        "Creating deep research graph",
        provider=provider,
        request_timeout=request_timeout,
        user_id=user_id[:8] if user_id else "None",
    )

    # Import config manager
    from agents.config.llm_config_manager import get_config_manager
    from agents.utils.llm_provider import get_llm_for_task

    config_manager = get_config_manager()

    # If api_keys dict is not provided, create it from single api_key for backward compatibility
    if api_keys is None:
        api_keys = {provider: api_key}
        logger.info(f"Using backward-compatible single API key for provider: {provider}")

    # Get LLM instances using config manager for task-specific models
    try:
        writer_model = get_llm_for_task(
            task="deep_research_writer",
            api_keys=api_keys,
            config_manager=config_manager,
            user_id=user_id
        )
        logger.info(f"Deep research writer model initialized from config")

        planner_model = get_llm_for_task(
            task="deep_research_planner",
            api_keys=api_keys,
            config_manager=config_manager,
            user_id=user_id
        )
        logger.info(f"Deep research planner model initialized from config")

        summary_model = get_llm_for_task(
            task="deep_research_summary",
            api_keys=api_keys,
            config_manager=config_manager,
            user_id=user_id
        )
        logger.info(f"Deep research summary model initialized from config")
    except Exception as e:
        logger.error(f"Failed to initialize deep research models from config: {e}", exc_info=True)
        raise

    section_builder = StateGraph(SectionState, output=SectionOutputState)
    section_builder.add_node(
        "generate_queries", functools.partial(generate_queries, writer_model, summary_model)
    )
    section_builder.add_node("search_web", search_web)
    section_builder.add_node(
        "write_section", functools.partial(write_section, writer_model, summary_model)
    )

    section_builder.add_edge(START, "generate_queries")
    section_builder.add_edge("generate_queries", "search_web")
    section_builder.add_edge("search_web", "write_section")

    builder = StateGraph(
        ReportState,
        input=ReportStateInput,
        output=ReportStateOutput,
        config_schema=Configuration,
    )
    builder.add_node(
        "generate_report_plan",
        functools.partial(generate_report_plan, writer_model, planner_model, summary_model),
    )
    builder.add_node("human_feedback", human_feedback)
    builder.add_node(
        "summarize_documents", functools.partial(summarize_documents, summary_model)
    )
    builder.add_node("build_section_with_web_research", section_builder.compile())
    builder.add_node("gather_completed_sections", gather_completed_sections)
    builder.add_node(
        "write_final_sections", functools.partial(write_final_sections, writer_model)
    )
    builder.add_node(
        "compile_final_report",
        functools.partial(
            compile_final_report, redis_storage=redis_storage, user_id=user_id
        ),
    )

    builder.add_edge(START, "generate_report_plan")
    builder.add_edge("generate_report_plan", "human_feedback")
    builder.add_edge("build_section_with_web_research", "gather_completed_sections")
    builder.add_conditional_edges(
        "gather_completed_sections",
        initiate_final_section_writing,
        ["write_final_sections"],
    )
    builder.add_edge("write_final_sections", "compile_final_report")
    builder.add_edge("compile_final_report", END)

    return builder.compile(checkpointer=checkpointer)
