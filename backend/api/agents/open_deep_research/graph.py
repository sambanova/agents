########## graph.py (UPDATED CODE) ##########
import functools
import json
import time
from typing import Literal, List, Optional, Tuple, Any, Callable
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langchain_sambanova import ChatSambaNovaCloud
from langchain_fireworks import ChatFireworks
from langchain_core.callbacks import BaseCallbackHandler

from langgraph.constants import Send
from langgraph.graph import START, END, StateGraph
from langgraph.types import interrupt, Command
from api.services.redis_service import SecureRedisService

from config.model_registry import model_registry

# We import our data models from the api module

from .state import (
    ReportStateInput,
    ReportStateOutput,
    Sections,
    ReportState,
    SectionState,
    SectionOutputState,
    Queries,
    Feedback,
)
from .prompts import (
    report_planner_query_writer_instructions,
    report_planner_instructions,
    query_writer_instructions,
    section_writer_instructions,
    final_section_writer_instructions,
    section_grader_instructions,
)
from .configuration import Configuration, SearchAPI
from .utils import APIKeyRotator, tavily_search_async, deduplicate_and_format_sources, format_sections, perplexity_search

# We import our data models
from api.data_types import (
    DeepResearchReport,
    DeepResearchSection,
    DeepCitation
)

from utils.logging import logger

class UsageCallback(BaseCallbackHandler):
    def __init__(self, provider: str):
        self.usage = []
        self.provider = provider
        
    def on_llm_end(self, response, **kwargs):
        if self.provider == "sambanova":
            if hasattr(response, 'generations'):
                for generation_list in response.generations:
                    for generation in generation_list:
                        if hasattr(generation.message, 'response_metadata'):
                            metadata_usage = generation.message.response_metadata.get('usage', {})
                            if metadata_usage:
                                self.usage.append(metadata_usage)
        elif self.provider == "fireworks":
            if hasattr(response, 'generations'):
                for generation_list in response.generations:
                    for generation in generation_list:
                        if hasattr(generation.message, 'response_metadata'):
                            metadata_usage = generation.message.response_metadata.get('token_usage', {})
                            if metadata_usage:
                                self.usage.append(metadata_usage)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

def get_model_name(llm):
    if hasattr(llm, 'model_name'):
        return llm.model_name
    elif hasattr(llm, 'model'):
        return llm.model
    else:
        return "Unknown Model"

def create_publish_callback(
    user_id: str,
    conversation_id: str,
    message_id: str,
    agent_name: str,
    workflow_name: str,
    redis_client: SecureRedisService,
    token_usage_callback: Callable[[dict], None] = None,
):
   
    def callback(message: str, llm_name: str, task: str, usage: dict, llm_provider: str, duration: float):
        response_duration = usage.get("end_time", 0) - usage.get("start_time", 0)
        if response_duration > 0:
            duration = response_duration

        # Track token usage if callback provided
        if token_usage_callback and usage:
            token_usage = {
                "total_tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }
            token_usage_callback(token_usage)

        message_data = {
            "user_id": user_id,
            "run_id": conversation_id,
            "message_id": message_id,
            "agent_name": agent_name,
            "text": message,
            "timestamp": time.time(),
            "metadata": {
                "workflow_name": workflow_name,
                "agent_name": agent_name,
                "llm_name": llm_name,
                "llm_provider": llm_provider,
                "task": task,
                "total_tokens": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "acceptance_rate": usage.get("acceptance_rate", 0),
                "completion_tokens_after_first_per_sec": usage.get("completion_tokens_after_first_per_sec", 0),
                "completion_tokens_after_first_per_sec_first_ten": usage.get("completion_tokens_after_first_per_sec_first_ten", 0),
                "completion_tokens_per_sec": usage.get("completion_tokens_per_sec", 0),
                "time_to_first_token": usage.get("time_to_first_token", 0),
                "total_latency": usage.get("total_latency", 0),
                "total_tokens_per_sec": usage.get("total_tokens_per_sec", 0),
                "duration": duration
            },
        }
        channel = f"agent_thoughts:{user_id}:{conversation_id}"
        redis_client.publish(channel, json.dumps(message_data))
    
    return callback


###############################################################################
# 1) Utility: parse a reference line from the sources block
###############################################################################
def parse_reference_line(line: str) -> DeepCitation:
    """
    If the line has an http/https link, store that as url, everything before is "title".
    If no URL found, return a citation with empty url => skip it upstream.
    """
    # remove bullet chars
    line = line.lstrip("*-0123456789. ").strip()
    # find a link
    match = re.search(r'(https?://[^\s]+)', line)
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
        if not in_sources and (lower_line == "### sources" or lower_line == "## sources" or lower_line == "sources:"):
            # from next line onward => references
            in_sources = True
            i += 1
            continue

        if in_sources:
            # if blank or new heading => end
            if not line.strip() or re.match(r'#+\s', line):
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

###############################################################################
# 2) Optional remove inline references with a pattern
###############################################################################
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
        if re.match(r'^(\*|-)\s+', trimmed):
            # check for a url
            match = re.search(r'(https?://[^\s]+)', trimmed)
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

###############################################################################
# The normal nodes
###############################################################################

def get_session_id_from_config(config: Configuration) -> Optional[str]:
    """
    Extract and format session ID from RunnableConfig.
    Returns None if user_id or conversation_id is missing.
    """
    if config.user_id and config.conversation_id:
        return f"{config.user_id}:{config.conversation_id}"
    return None

async def generate_report_plan(writer_model, planner_model, state: ReportState, config: RunnableConfig):
    topic = state["topic"]
    feedback = state.get("feedback_on_report_plan", None)

    configurable = Configuration.from_runnable_config(config)
    usage_handler_report_planner = UsageCallback(provider=configurable.provider)
    usage_handler_query_generation = UsageCallback(provider=configurable.provider)

    report_structure = configurable.report_structure
    number_of_queries = configurable.number_of_queries 
    session_id = get_session_id_from_config(configurable)

    logger.info(logger.format_message(session_id, f"Generating report plan for topic: {topic}"))
    if feedback:
        logger.info(logger.format_message(session_id, f"Incorporating feedback: {feedback}"))

    if isinstance(report_structure, dict):
        report_structure = str(report_structure)

    structured_llm = writer_model.with_structured_output(Queries)
    
    system_instructions_query = report_planner_query_writer_instructions.format(
        topic=topic,
        report_organization=report_structure,
        number_of_queries=number_of_queries
    )
    
    llm_config_query = RunnableConfig(callbacks=[usage_handler_query_generation], tags=["query_generation"])
    logger.info(logger.format_message(session_id, "Generating initial search queries for planning"))
    
    results = invoke_llm_with_tracking(
        llm=structured_llm,
        messages=[
            SystemMessage(content=system_instructions_query),
            HumanMessage(content="Generate search queries that will help with planning the sections of the report.")
        ],
        task="Generate initial planning queries",
        config=llm_config_query,
        usage_handler=usage_handler_query_generation,
        configurable=configurable,
        session_id=session_id,
        llm_name=get_model_name(writer_model)
    )

    query_list = [q.search_query for q in results.queries]
    logger.info(logger.format_message(session_id, f"Generated {len(query_list)} search queries"))

    logger.info(logger.format_message(session_id, f"Using search API: {configurable.search_api}"))
    if configurable.search_api == SearchAPI.TAVILY:
        logger.info(logger.format_message(session_id, f"Using Tavily API with key rotation for {len(query_list)} queries"))
        search_results = await tavily_search_async(query_list, configurable.api_key_rotator)
        source_str = deduplicate_and_format_sources(search_results, max_tokens_per_source=1500, include_raw_content=False)
    elif configurable.search_api == SearchAPI.PERPLEXITY:
        search_results = perplexity_search(query_list, configurable.api_key_rotator)
        source_str = deduplicate_and_format_sources(search_results, max_tokens_per_source=1000, include_raw_content=False)
    else:
        logger.error(logger.format_message(session_id, f"Unsupported search API: {configurable.search_api}"))
        raise ValueError(f"Unsupported search API: {configurable.search_api}")

    logger.info(logger.format_message(session_id, "Generating final report sections plan"))
    system_instructions_sections = report_planner_instructions.format(
        topic=topic,
        report_organization=report_structure,
        context=source_str,
        feedback=feedback
    )

    structured_llm = planner_model.with_structured_output(Sections)
    llm_config_sections = RunnableConfig(callbacks=[usage_handler_report_planner], tags=["report_planning"])
    
    report_sections = invoke_llm_with_tracking(
        llm=structured_llm,
        messages=[
            SystemMessage(content=system_instructions_sections),
            HumanMessage(content="Generate the sections of the report. Your response must include a 'sections' field containing a list of sections. Each section must have: name, description, plan, research, and content fields.")
        ],
        task="Generate report sections plan",
        config=llm_config_sections,
        usage_handler=usage_handler_report_planner,
        configurable=configurable,
        session_id=session_id,
        llm_name=get_model_name(planner_model)
    )

    sections = report_sections.sections
    logger.info(logger.format_message(session_id, f"Generated plan with {len(sections)} sections"))
    return {"sections": sections}

def human_feedback(state: ReportState, config: RunnableConfig) -> Command[Literal["generate_report_plan","build_section_with_web_research", "summarize_documents"]]:
    sections = state["sections"]
    sec_str = "\n\n".join(
        f"<b>Section {i+1}:</b> {s.name} - {s.description}\n"
        for i, s in enumerate(sections)
    )
    fb = interrupt(sec_str)
    if isinstance(fb, bool):
        if state.get("document"):
            return Command(goto="summarize_documents")
        else:
            return Command(goto=[
                Send("build_section_with_web_research", {"section": s, "search_iterations": 0})
                for s in sections
                if s.research
            ])
    elif isinstance(fb, str):
        return Command(goto="generate_report_plan", update={"feedback_on_report_plan": fb})
    else:
        raise ValueError("interrupt unknown")

def generate_queries(writer_model, state: SectionState, config: RunnableConfig):
    sec = state["section"]
    configurable = Configuration.from_runnable_config(config)
    usage_handler = UsageCallback(provider=configurable.provider)
    session_id = get_session_id_from_config(configurable)

    logger.info(logger.format_message(session_id, f"Generating queries for section: {sec.name}"))

    structured_llm = writer_model.with_structured_output(Queries)
    sys_inst = query_writer_instructions.format(
        section_topic=sec.description,
        number_of_queries=configurable.number_of_queries
    )
    llm_config = RunnableConfig(
        callbacks=[usage_handler],
        tags=["query_generation"]
    )
    
    queries = invoke_llm_with_tracking(
        llm=structured_llm,
        messages=[
            SystemMessage(content=sys_inst),
            HumanMessage(content="Generate search queries.")
        ],
        task="Generate search queries",
        config=llm_config,
        usage_handler=usage_handler,
        configurable=configurable,
        session_id=session_id,
        llm_name=get_model_name(writer_model)
    )
    
    logger.info(
        logger.format_message(
            session_id,
            f"Generated {len(queries.queries)} queries for section {sec.name}."
        )
    )
    return {"search_queries": queries.queries}

async def search_web(state: SectionState, config: RunnableConfig):
    sq = state["search_queries"]
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    
    query_list = [q.search_query for q in sq]
    logger.info(logger.format_message(session_id, f"Executing web search with {len(query_list)} queries"))

    logger.info(logger.format_message(session_id, f"Using search API: {configurable.search_api}"))
    if configurable.search_api == SearchAPI.TAVILY:
        logger.info(logger.format_message(session_id, f"Using Tavily API with key rotation for {len(query_list)} queries"))
        search_results = await tavily_search_async(query_list, configurable.api_key_rotator)
        src_str = deduplicate_and_format_sources(search_results, max_tokens_per_source=1500, include_raw_content=True)
    elif configurable.search_api == SearchAPI.PERPLEXITY:
        search_results = perplexity_search(query_list, configurable.api_key_rotator)
        src_str = deduplicate_and_format_sources(search_results, max_tokens_per_source=5000, include_raw_content=False)
    else:
        logger.error(logger.format_message(session_id, f"Unsupported search API: {configurable.search_api}"))
        raise ValueError(f"Unsupported search API: {configurable.search_api}")

    logger.info(logger.format_message(session_id, "Successfully completed web search"))
    return {
        "source_str": src_str,
        "search_iterations": state["search_iterations"] + 1
    }

def invoke_llm_with_tracking(
    llm,
    messages: List[Any],
    task: str,
    llm_name: str,
    config: RunnableConfig,
    usage_handler: UsageCallback,
    configurable: Configuration,
    session_id: Optional[str] = None
) -> Any:
    """Helper function to invoke LLM with timing and usage tracking.
    
    Args:
        llm: The LLM to invoke
        messages: List of messages to send to the LLM
        task: Description of the task being performed
        config: RunnableConfig for the LLM
        usage_handler: UsageCallback instance to track usage
        configurable: Configuration instance
        session_id: Optional session ID for logging
    
    Returns:
        The LLM response
    """
    start_time = time.time()
    response = llm.invoke(messages, config=config)
    duration = time.time() - start_time
    if duration > 10:
        logger.warning(logger.format_message(session_id, f"Deep Research - LLM {llm_name} took {duration:.2f} seconds to complete task {task}"))

    if len(usage_handler.usage) > 1:
        logger.warning(logger.format_message(session_id, f"Multiple usage objects found in callback. Using the first one."))

    if isinstance(response, AIMessage):
        text = response.content
    else:
        text = response.model_dump()
    
    configurable.callback(
        message=text,
        task=task,
        llm_name=llm_name,
        llm_provider=configurable.provider,
        usage=usage_handler.usage[0],
        duration=duration
    )

    return response

def write_section(
    writer_model, state: SectionState, config: RunnableConfig
) -> Command[Literal["__end__", "search_web"]]:
    sec = state["section"]
    configurable = Configuration.from_runnable_config(config)
    usage_handler_section_writing = UsageCallback(provider=configurable.provider)
    usage_handler_section_grading = UsageCallback(provider=configurable.provider)
    session_id = get_session_id_from_config(configurable)

    logger.info(logger.format_message(session_id, f"Writing section: {sec.name}"))
    src = state["source_str"]
    doc_summary = state.get("document_summary", "")
    sys_inst = section_writer_instructions.format(
        section_title=sec.name,
        section_topic=sec.description,
        context=src,
        section_content=sec.content,
        document_summary=doc_summary
    )

    llm_config_section_writing = RunnableConfig(callbacks=[usage_handler_section_writing], tags=["section_writing"])
    
    content = invoke_llm_with_tracking(
        llm=writer_model,
        messages=[SystemMessage(content=sys_inst), HumanMessage(content="Write the section.")],
        task=f"Write section - {sec.name}",
        config=llm_config_section_writing,
        usage_handler=usage_handler_section_writing,
        configurable=configurable,
        session_id=session_id,
        llm_name=get_model_name(writer_model)
    )
    
    sec.content = content.content
    logger.info(
        logger.format_message(session_id, f"Generated content for section: {sec.name}")
    )

    # now we grade
    logger.info(logger.format_message(session_id, f"Grading section: {sec.name}"))
    grader_inst = section_grader_instructions.format(
        section_topic=sec.description, section=sec.content
    )
    llm_config_section_grading = RunnableConfig(callbacks=[usage_handler_section_grading], tags=["section_grading"])
    structured_llm = writer_model.with_structured_output(Feedback)

    fb = invoke_llm_with_tracking(
        llm=structured_llm,
        messages=[SystemMessage(content=grader_inst), HumanMessage(content="Grade it")],
        task=f"Grade section - {sec.name}",
        config=llm_config_section_grading,
        usage_handler=usage_handler_section_grading,
        configurable=configurable,
        session_id=session_id,
        llm_name=get_model_name(writer_model)
    )

    if fb.grade == "pass":
        logger.info(logger.format_message(session_id, f"Section {sec.name} passed grading"))
        return Command(update={"completed_sections": [sec]}, goto=END)
    elif state["search_iterations"] >= Configuration.from_runnable_config(config).max_search_depth:
        logger.warning(logger.format_message(session_id, f"Section {sec.name} reached max iterations, moving on"))
        return Command(update={"completed_sections": [sec]}, goto=END)
    else:
        logger.info(logger.format_message(session_id, f"Section {sec.name} needs revision, doing another search iteration"))
        return Command(
            update={"search_queries": fb.follow_up_queries, "section": sec},
            goto="search_web"
        )


def write_final_sections(writer_model, state: SectionState, config: RunnableConfig):
    sec = state["section"]
    configurable = Configuration.from_runnable_config(config)
    usage_handler = UsageCallback(provider=configurable.provider)
    session_id = get_session_id_from_config(configurable)

    logger.info(logger.format_message(session_id, f"Writing final section: {sec.name}"))
    rep = state["report_sections_from_research"]

    sys_inst = final_section_writer_instructions.format(
        section_title=sec.name, section_topic=sec.description, context=rep
    )
    llm_config = RunnableConfig(
        callbacks=[usage_handler], tags=["final_section_writing"]
    )

    content = invoke_llm_with_tracking(
        llm=writer_model,
        messages=[SystemMessage(content=sys_inst), HumanMessage(content="Write final section.")],
        task="Write final section",
        config=llm_config,
        usage_handler=usage_handler,
        configurable=configurable,
        session_id=session_id,
        llm_name=get_model_name(writer_model)
    )

    sec.content = content.content
    logger.info(logger.format_message(session_id, f"Completed final section: {sec.name}"))
    return {"completed_sections": [sec]}

def gather_completed_sections(state: ReportState, config: RunnableConfig):
    comps = state["completed_sections"]
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    
    logger.info(logger.format_message(session_id, f"Gathering {len(comps)} completed sections"))
    rep = format_sections(comps)
    return {"report_sections_from_research": rep}

def initiate_final_section_writing(state: ReportState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    
    non_research_sections = [s for s in state["sections"] if not s.research]
    logger.info(logger.format_message(session_id, f"Initiating writing of {len(non_research_sections)} final sections"))
    return [
        Send("write_final_sections", {"section": s, "report_sections_from_research": state["report_sections_from_research"]})
        for s in non_research_sections
    ]

def compile_final_report(state: ReportState, config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    session_id = get_session_id_from_config(configurable)
    
    sections = state["sections"]
    logger.info(logger.format_message(session_id, "Compiling final report"))
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
                citations=[]  # we skip local citations array
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

    logger.info(logger.format_message(session_id, f"Completed report compilation with {len(deep_sections)} sections and {len(all_citations)} citations"))
    report = DeepResearchReport(
        sections=deep_sections,
        final_report=final_text,
        citations=all_citations
    )
    return {"final_report": final_text, "deep_research_report": report}

def summarize_documents(summary_model, state: ReportState, config: RunnableConfig):
    """
    Summarize provided documents if they exist.
    """
    configurable = Configuration.from_runnable_config(config)
    usage_handler = UsageCallback(provider=configurable.provider)
    session_id = get_session_id_from_config(configurable)
    
    document = state.get("document", None)
    if not document:
        logger.info(logger.format_message(session_id, "No documents provided for summarization"))
        return {"document_summary": ""}
        
    logger.info(logger.format_message(session_id, f"Summarizing a {len(document)} word document"))
    
    
    sys_inst = """You are a document summarizer. Your task is to:
    1. Read through the provided documents
    2. Extract the key information, main points, and important findings
    3. Create a comprehensive but concise summary that captures the essential information
    4. Focus on factual information that would be relevant for research
    5. Maintain objectivity and accuracy
    
    Format your response as a clear, well-structured summary."""

    llm_config = RunnableConfig(callbacks=[usage_handler], tags=["document_summarization"])
    
    summary = invoke_llm_with_tracking(
        llm=summary_model,
        messages=[
            SystemMessage(content=sys_inst),
            HumanMessage(content=f"Please summarize the following document:\n\n{document}")
        ],
        task="Summarize provided document",
        config=llm_config,
        usage_handler=usage_handler,
        configurable=configurable,
        session_id=session_id,
        llm_name=get_model_name(summary_model)
    )

    # After summarization, initiate section building
    sections = state.get("sections", [])
    return Command(goto=[
                Send("build_section_with_web_research", {"section": s, "search_iterations": 0, "document_summary": summary.content})
                for s in sections
                if s.research
    ])

def get_graph(api_key: str, provider: str):
    """
    Create and configure the graph for deep research.
    
    Args:
        api_key: The API key for the LLM provider
        provider: The LLM provider to use (fireworks or sambanova)
        documents: Optional list of documents to process
    """
    model_name = "llama-3.3-70b"
    planner_model_config: str = model_registry.get_model_info(model_key=model_name, provider=provider)
    writer_model_config: str = model_registry.get_model_info(model_key=model_name, provider=provider)
    summary_model_config: str = model_registry.get_model_info(model_key=model_name, provider=provider)

    if provider == "fireworks":    
        writer_model = ChatFireworks(base_url=writer_model_config["url"], model=writer_model_config["model"], temperature=0, max_tokens=8192, api_key=api_key)
        planner_model = ChatFireworks(base_url=planner_model_config["url"], model=planner_model_config["model"], temperature=0, max_tokens=8192, api_key=api_key)
        summary_model = ChatFireworks(base_url=summary_model_config["url"], model=summary_model_config["model"], temperature=0, max_tokens=8192, api_key=api_key)
    elif provider == "sambanova":
        writer_model = ChatSambaNovaCloud(sambanova_url=writer_model_config["long_url"], model=writer_model_config["model"], temperature=0, max_tokens=8192, sambanova_api_key=api_key)
        planner_model = ChatSambaNovaCloud(sambanova_url=planner_model_config["long_url"], model=planner_model_config["model"], temperature=0, max_tokens=8192, sambanova_api_key=api_key)
        summary_model = ChatSambaNovaCloud(sambanova_url=summary_model_config["long_url"], model=summary_model_config["model"], temperature=0, max_tokens=8192, sambanova_api_key=api_key)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    section_builder = StateGraph(SectionState, output=SectionOutputState)
    section_builder.add_node("generate_queries", functools.partial(generate_queries, writer_model))
    section_builder.add_node("search_web", search_web)
    section_builder.add_node("write_section", functools.partial(write_section, writer_model))

    section_builder.add_edge(START, "generate_queries")
    section_builder.add_edge("generate_queries", "search_web")
    section_builder.add_edge("search_web", "write_section")

    builder = StateGraph(ReportState, input=ReportStateInput, output=ReportStateOutput, config_schema=Configuration)
    builder.add_node("generate_report_plan", functools.partial(generate_report_plan, writer_model, planner_model))
    builder.add_node("human_feedback", human_feedback)
    builder.add_node("summarize_documents", functools.partial(summarize_documents, summary_model))
    builder.add_node("build_section_with_web_research", section_builder.compile())
    builder.add_node("gather_completed_sections", gather_completed_sections)
    builder.add_node("write_final_sections", functools.partial(write_final_sections, writer_model))
    builder.add_node("compile_final_report", compile_final_report)

    builder.add_edge(START, "generate_report_plan")
    builder.add_edge("generate_report_plan", "human_feedback")
    builder.add_edge("build_section_with_web_research", "gather_completed_sections")
    builder.add_conditional_edges("gather_completed_sections", initiate_final_section_writing, ["write_final_sections"])
    builder.add_edge("write_final_sections", "compile_final_report")
    builder.add_edge("compile_final_report", END)

    return builder
