import functools
import re
import time
from typing import Any, List, Literal, Optional, Tuple

import requests
import structlog

# We import our data models
from agents.api.data_types import DeepCitation, DeepResearchReport, DeepResearchSection
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
    Section,
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
from agents.utils.custom_sambanova import CustomChatSambaNovaCloud
from agents.utils.logging_utils import setup_logging_context
from langchain.output_parsers import OutputFixingParser, PydanticOutputParser
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_fireworks import ChatFireworks
from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

logger = structlog.get_logger(__name__)


class MessageInterceptor:
    def __init__(self):
        self.captured_messages = []

    def capture_and_pass(self, message):
        """Capture the message and pass it through"""
        if isinstance(message, AIMessage):
            self.captured_messages.append(message)
        return message


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


async def generate_report_plan(
    writer_model, planner_model, state: ReportState, config: RunnableConfig
):
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
    fixing_interceptor = MessageInterceptor()

    # Create an intercepted version of the writer model for the fixing parser
    fixing_writer_model = writer_model | RunnableLambda(
        fixing_interceptor.capture_and_pass
    )

    structured_llm = (
        writer_model
        | RunnableLambda(search_queries_interceptor.capture_and_pass)
        | OutputFixingParser.from_llm(
            llm=fixing_writer_model,  # Use the intercepted model
            parser=PydanticOutputParser(pydantic_object=Queries),
        )
    )

    system_instructions_query = report_planner_query_writer_instructions.format(
        topic=topic,
        report_organization=report_structure,
        number_of_queries=configurable.number_of_queries,
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

    logger.info("Generating final report sections plan")
    system_instructions_sections = report_planner_instructions.format(
        topic=topic,
        report_organization=report_structure,
        context=source_str,
        feedback=feedback,
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

    for m in fixing_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_search_queries_plan_fixed"
        captured_messages.append(m)

    for m in search_sections_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_search_sections"
        captured_messages.append(m)

    return {"sections": sections, "messages": captured_messages}


async def human_feedback(
    state: ReportState, config: RunnableConfig
) -> Command[
    Literal[
        "generate_report_plan", "build_section_with_web_research", "summarize_documents"
    ]
]:
    sections = state["sections"]
    sec_str = "\n\n".join(
        f"<b>Section {i+1}:</b> {s.name} - {s.description}\n"
        for i, s in enumerate(sections)
    )
    logger.info("Interrupting for human feedback", sections=sec_str)
    fb = interrupt(sec_str)
    if isinstance(fb, bool):
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
    elif isinstance(fb, str):
        return Command(
            goto="generate_report_plan", update={"feedback_on_report_plan": fb}
        )
    else:
        raise ValueError("interrupt unknown")


async def generate_queries(writer_model, state: SectionState, config: RunnableConfig):
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
    fixing_interceptor = MessageInterceptor()

    # Create an intercepted version of the writer model for the fixing parser
    fixing_writer_model = writer_model | RunnableLambda(
        fixing_interceptor.capture_and_pass
    )

    structured_llm = (
        writer_model
        | RunnableLambda(search_queries_interceptor.capture_and_pass)
        | OutputFixingParser.from_llm(
            llm=fixing_writer_model,  # Use the intercepted model
            parser=PydanticOutputParser(pydantic_object=Queries),
        )
    )

    sys_inst = query_writer_instructions.format(
        section_topic=sec.description, number_of_queries=configurable.number_of_queries
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

    for m in fixing_interceptor.captured_messages:
        m.additional_kwargs["agent_type"] = "deep_research_search_queries_section_fixed"
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


async def write_section(
    writer_model, state: SectionState, config: RunnableConfig
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
    writer_model_with_interceptor = writer_model | RunnableLambda(
        writer_interceptor.capture_and_pass
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

    sec.content = content.content
    logger.info("Generated content for section", section_name=sec.name)

    # now we grade
    logger.info("Grading section", section_name=sec.name)
    grader_inst = section_grader_instructions.format(
        section_topic=sec.description, section=sec.content
    )

    grader_interceptor = MessageInterceptor()
    structured_llm = (
        writer_model
        | RunnableLambda(grader_interceptor.capture_and_pass)
        | OutputFixingParser.from_llm(
            llm=writer_model, parser=PydanticOutputParser(pydantic_object=Feedback)
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
    writer_model_with_interceptor = writer_model | RunnableLambda(
        writer_interceptor.capture_and_pass
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

    sec.content = content.content
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


async def compile_final_report(state: ReportState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    setup_logging_context(config, node="compile_final_report", session_id=session_id)

    sections = state["sections"]
    logger.info("Compiling final report", num_sections=len(sections))
    completed_map = {s.name: s.content for s in state["completed_sections"]}

    deep_sections: List[DeepResearchSection] = []
    all_citations: List[DeepCitation] = []

    for sec in sections:
        content = completed_map.get(sec.name, sec.content or "")

        # 1) strip any sources block
        cleaned, block_refs = extract_sources_block(content)
        # 2) optionally remove bullet lines that contain URLs but are not in sources block
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
    report = DeepResearchReport(
        sections=deep_sections, final_report=final_text, citations=all_citations
    )
    return {"final_report": final_text, "deep_research_report": report}


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


def create_deep_research_graph(api_key: str, provider: str, request_timeout: int = 120):
    """
    Create and configure the graph for deep research.

    Args:
        api_key: The API key for the LLM provider
        provider: The LLM provider to use (fireworks or sambanova)
        documents: Optional list of documents to process
    """
    logger.info(
        "Creating deep research graph",
        provider=provider,
        request_timeout=request_timeout,
    )
    model_name = "llama-3.3-70b"
    planner_model_config: str = model_registry.get_model_info(
        model_key=model_name, provider=provider
    )
    writer_model_config: str = model_registry.get_model_info(
        model_key=model_name, provider=provider
    )
    summary_model_config: str = model_registry.get_model_info(
        model_key=model_name, provider=provider
    )

    if provider == "fireworks":
        writer_model = ChatFireworks(
            base_url=writer_model_config["url"],
            model=writer_model_config["model"],
            temperature=0,
            max_tokens=8192,
            api_key=api_key,
        )
        planner_model = ChatFireworks(
            base_url=planner_model_config["url"],
            model=planner_model_config["model"],
            temperature=0,
            max_tokens=8192,
            api_key=api_key,
        )
        summary_model = ChatFireworks(
            base_url=summary_model_config["url"],
            model=summary_model_config["model"],
            temperature=0,
            max_tokens=8192,
            api_key=api_key,
        )
    elif provider == "sambanova":
        writer_model = CustomChatSambaNovaCloud(
            sambanova_url=writer_model_config["long_url"],
            model=writer_model_config["model"],
            temperature=0,
            max_tokens=8192,
            sambanova_api_key=api_key,
            timeout=request_timeout,
        )
        planner_model = CustomChatSambaNovaCloud(
            sambanova_url=planner_model_config["long_url"],
            model=planner_model_config["model"],
            temperature=0,
            max_tokens=8192,
            sambanova_api_key=api_key,
            timeout=request_timeout,
        )
        summary_model = CustomChatSambaNovaCloud(
            sambanova_url=summary_model_config["long_url"],
            model=summary_model_config["model"],
            temperature=0,
            max_tokens=8192,
            sambanova_api_key=api_key,
            timeout=request_timeout,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    section_builder = StateGraph(SectionState, output=SectionOutputState)
    section_builder.add_node(
        "generate_queries", functools.partial(generate_queries, writer_model)
    )
    section_builder.add_node("search_web", search_web)
    section_builder.add_node(
        "write_section", functools.partial(write_section, writer_model)
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
        functools.partial(generate_report_plan, writer_model, planner_model),
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
    builder.add_node("compile_final_report", compile_final_report)

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

    return builder.compile()
