import base64
import json
import re
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, List, Optional

import markdown
import structlog
from agents.api.session_state import SessionStateManager
from agents.components.compound.code_execution_subgraph import (
    create_code_execution_graph,
)
from agents.components.compound.data_types import LiberalFunctionMessage
from agents.components.datagen.tools.persistent_daytona import PersistentDaytonaManager
from agents.storage.redis_service import SecureRedisService
from agents.storage.redis_storage import RedisStorage
from agents.tools.langgraph_tools import load_static_tools
from requests_cache import Dict
from weasyprint import HTML

logger = structlog.get_logger(__name__)

session_state_manager = SessionStateManager()


class DocumentContextLengthError(Exception):
    """Exception raised when document(s) exceed the maximum context length."""

    def __init__(self, total_tokens: int, max_tokens: int):
        self.total_tokens = total_tokens
        self.max_tokens = max_tokens
        super().__init__(
            f"Combined documents exceed maximum context window size of {max_tokens} tokens (got {total_tokens} tokens). Please reduce the number or size of documents."
        )


def estimate_tokens_regex(text: str) -> int:
    return len(re.findall(r"\w+|\S", text))


def load_documents(
    user_id: str,
    document_ids: List[str],
    redis_client: SecureRedisService,
    context_length_summariser: int,
) -> List[str]:
    documents = []
    total_tokens = 0

    for doc_id in document_ids:
        # Verify document exists and belongs to user
        user_docs_key = f"user_documents:{user_id}"
        if not redis_client.sismember(user_docs_key, doc_id):
            continue  # Skip if document doesn't belong to user

        chunks_key = f"document_chunks:{doc_id}"
        chunks_data = redis_client.get(chunks_key, user_id)

        if chunks_data:
            chunks = json.loads(chunks_data)
            doc_text = "\n".join([chunk["text"] for chunk in chunks])
            token_count = estimate_tokens_regex(doc_text)

            # Update total token count and check if it would exceed the limit
            if total_tokens + token_count > context_length_summariser:
                raise DocumentContextLengthError(
                    total_tokens + token_count, context_length_summariser
                )

            total_tokens += token_count
            documents.append(doc_text)

    return documents


async def generate_report_pdf(content: str, header: str) -> Optional[str]:
    """
    Generate a PDF from deep research markdown content and return the file ID.

    Args:
        content: The markdown content to convert to PDF

    Returns:
        Optional[str]: The file ID if successful, None if failed
    """
    try:
        logger.info("Generating PDF from report content")

        # Convert markdown to HTML
        html_content = markdown.markdown(content, extensions=["tables", "fenced_code"])

        # Create professional HTML document
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: A4;
                    margin: 1in 0.75in;
                    @bottom-center {{
                        content: "Page " counter(page) " of " counter(pages);
                        font-size: 9pt;
                        color: #666;
                    }}
                }}
                
                body {{
                    font-family: Georgia, 'Times New Roman', serif;
                    font-size: 11pt;
                    line-height: 1.5;
                    color: #212529;
                    margin: 0;
                    padding: 0;
                }}
                
                .report-header {{
                    text-align: center;
                    margin-bottom: 2em;
                    padding-bottom: 0.5em;
                    border-bottom: 2px solid #343a40;
                    page-break-after: avoid;
                }}
                
                .report-header h1 {{
                    font-size: 24pt;
                    margin-bottom: 0.5em;
                    font-weight: 700;
                }}
                
                .report-header .date {{
                    font-size: 10pt;
                    color: #666;
                }}
                
                h1, h2, h3, h4, h5, h6 {{
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    font-weight: 700;
                    color: #000;
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                    line-height: 1.2;
                    page-break-after: avoid;
                }}
                
                h1 {{ font-size: 20pt; }}
                h2 {{ font-size: 16pt; }}
                h3 {{ font-size: 14pt; }}
                
                p {{
                    margin-bottom: 1em;
                    text-align: justify;
                    orphans: 3;
                    widows: 3;
                }}
                
                a {{
                    color: #ee7624;
                    text-decoration: none;
                }}
                
                a:hover {{
                    text-decoration: underline;
                }}
                
                strong {{
                    font-weight: 700;
                }}
                
                ul, ol {{
                    padding-left: 2em;
                    margin-bottom: 1em;
                }}
                
                li {{
                    margin-bottom: 0.5em;
                    page-break-inside: avoid;
                }}
                
                blockquote {{
                    border-left: 4px solid #dee2e6;
                    padding: 0.5em 1em;
                    margin: 1.5em 0;
                    color: #6c757d;
                    page-break-inside: avoid;
                }}
                
                pre, code {{
                    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
                    font-size: 9.5pt;
                }}
                
                pre {{
                    background-color: #f8f9fa;
                    border: 1px solid #e9ecef;
                    border-radius: 4px;
                    padding: 1em;
                    overflow-x: auto;
                    page-break-inside: avoid;
                }}
                
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 1.5em 0;
                    page-break-inside: avoid;
                }}
                
                th, td {{
                    border: 1px solid #dee2e6;
                    padding: 0.75em;
                    text-align: left;
                }}
                
                th {{
                    background-color: #f8f9fa;
                    font-weight: 700;
                }}
            </style>
        </head>
        <body>
            <div class="report-header">
                <h1>{header}</h1>
                <p class="date">Generated on {datetime.now().strftime('%B %d, %Y')}</p>
            </div>
            <div class="report-content">
                {html_content}
            </div>
        </body>
        </html>
        """

        # Generate PDF using WeasyPrint
        pdf_buffer = BytesIO()
        HTML(string=full_html).write_pdf(pdf_buffer)
        pdf_data = pdf_buffer.getvalue()
        pdf_buffer.close()

        # Generate unique file ID and filename
        file_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.pdf"

        logger.info("PDF generated successfully", file_size=len(pdf_data))

        return file_id, filename, pdf_data

    except Exception as e:
        logger.error("Failed to generate PDF from report content", error=str(e))
        return None


def to_agent_thinking(payload: dict) -> Optional[dict]:
    """
    Convert deep research markdown content to agent thinking content.
    """

    event_to_agent_name_mapping = {
        "deep_research_search_queries_plan": "Search Agent",
        "deep_research_search_queries_plan_fixed": "Search Agent",
        "deep_research_search_sections": "Planner Agent",
        "deep_research_search_queries_section": "Search Queries Agent",
        "deep_research_search_queries_section_fixed": "Search Queries Agent",
        "deep_research_writer": "Writer Agent",
        "deep_research_grader": "Grader Agent",
        "data_science_hypothesis_agent": "Hypothesis Agent",
        "data_science_process_agent": "Supervisor Agent",
        "data_science_code_agent": "Code Agent",
        "data_science_quality_review_agent": "Quality Review Agent",
        "data_science_note_agent": "Note Taker Agent",
        "data_science_report_agent": "Report Agent",
        "data_science_visualization_agent": "Visualization Agent",
        "data_science_human_choice": "Human Choice",
    }

    try:
        if payload.get("event") == "agent_completion" and payload.get(
            "additional_kwargs", {}
        ).get("agent_type") in [
            "deep_research_search_queries_plan",
            "deep_research_search_queries_plan_fixed",
            "deep_research_search_sections",
            "deep_research_search_queries_section",
            "deep_research_search_queries_section_fixed",
            "deep_research_writer",
            "deep_research_grader",
            "data_science_hypothesis_agent",
            "data_science_process_agent",
            "data_science_code_agent",
            "data_science_quality_review_agent",
            "data_science_note_agent",
            "data_science_report_agent",
            "data_science_visualization_agent",
            "data_science_human_choice",
        ]:
            return {
                "event": "think",
                "data": json.dumps(
                    {
                        "user_id": payload["user_id"],
                        "message_id": payload["message_id"],
                        "agent_name": event_to_agent_name_mapping.get(
                            payload["additional_kwargs"]["agent_type"],
                            "Agent",
                        ),
                        "text": payload["content"],
                        "task": payload["additional_kwargs"]["agent_type"],
                        "metadata": {
                            "workflow_name": "deep_research",
                            "agent_name": event_to_agent_name_mapping.get(
                                payload["additional_kwargs"]["agent_type"],
                                "Agent",
                            ),
                            "llm_name": payload["response_metadata"]["model_name"],
                            "duration": payload["response_metadata"]["usage"][
                                "total_latency"
                            ],
                        },
                    }
                ),
                "user_id": payload["user_id"],
                "conversation_id": payload["conversation_id"],
                "message_id": payload["message_id"],
                "timestamp": payload["timestamp"],
            }
    except Exception as e:
        logger.error("Failed to convert deep research to agent thinking", error=str(e))
        return None

    return None


def replace_redis_chart(files_content, match):
    alt_text = match.group(1)
    combined_id = match.group(2)
    file_id = combined_id.split(":")[0]

    if file_id in files_content:
        file_data = files_content[file_id]
        if isinstance(file_data, bytes):
            encoded_data = base64.b64encode(file_data).decode("utf-8")
            return f'<img src="data:image/png;base64,{encoded_data}" alt="{alt_text}" style="max-width: 100%; max-height: 600px; height: auto;" />'

    # Return original markdown if file not found
    return f"![{alt_text}](redis-chart:{combined_id})"


async def process_data_science_report(
    markdown_report: str,
    files_from_report: list[str],
    redis_storage: RedisStorage,
    user_id: str,
):
    files_content = {}
    for file_id in files_from_report:
        file_data, metadata = await redis_storage.get_file(user_id, file_id)
        if metadata and "filename" in metadata:
            files_content[metadata["filename"]] = file_data

    html_report = markdown.markdown(
        markdown_report, extensions=["tables", "fenced_code"]
    )

    def replace_chart_placeholder(match):
        alt_text = match.group(1)
        filename = match.group(2)
        if filename in files_content:
            file_data = files_content[filename]
            if isinstance(file_data, bytes):
                encoded_data = base64.b64encode(file_data).decode("utf-8")
                return f'<img src="data:image/png;base64,{encoded_data}" alt="{alt_text}" style="max-width: 100%; max-height: 600px; height: auto;" />'
        return match.group(0)

    final_html = re.sub(
        r'<img alt="([^"]+)" src="([^"]+)"\s*/?>',
        replace_chart_placeholder,
        html_report,
    )

    def replace_reference_placeholder(match):
        filename = match.group(1)
        link_text = match.group(3)

        if filename in files_content:
            file_data = files_content[filename]
            if isinstance(file_data, bytes):
                encoded_data = base64.b64encode(file_data).decode("utf-8")
                return f'<a href="data:image/png;base64,{encoded_data}" download="{filename}" title="Download {filename}">{link_text}</a>'
        return match.group(0)

    final_html = re.sub(
        r'<a href="\[([^\]]+)\]\(([^)]+)\)">([^<]+)</a>',
        replace_reference_placeholder,
        final_html,
    )

    return final_html


async def create_coding_agent_config(
    user_id: str,
    thread_id: str,
    api_key: str,
    message_id: str,
    llm_type: str,
    doc_ids: Dict[str, Any],
    redis_storage: RedisStorage,
    daytona_manager: PersistentDaytonaManager,
):

    data_analysis_doc_ids = []
    directory_content = []
    for doc_id in doc_ids:
        if doc_id["format"] == "text/csv":
            data_analysis_doc_ids.append(doc_id["id"])
            directory_content.append(doc_id["filename"])

    tools_config = [
        {
            "type": "search_tavily",
            "config": {},
        },
    ]

    config = {
        "configurable": {
            "type==default/user_id": user_id,
            "type==default/llm_type": llm_type,
            "thread_id": thread_id,
            "user_id": user_id,
            "api_key": api_key,
            "message_id": message_id,
        },
        "recursion_limit": 50,
    }

    config["configurable"][
        "type==default/system_message"
    ] = f"""
You are a helpful coding assistant. Today's date is {datetime.now().strftime('%Y-%m-%d')}.
CRITICAL: Use DaytonaCodeSandbox subgraph ONLY when code execution is required (running scripts, data processing, file operations, creating visualizations). For code explanations, examples, or discussions, respond directly without routing to subgraphs.
"""

    config["configurable"]["type==default/subgraphs"] = {
        "DaytonaCodeSandbox": {
            "description": "This subgraph executes Python code in a secure sandbox environment. Use for: data exploration, basic analysis, code debugging, file operations, simple calculations, data visualization, and any general programming tasks. Perfect for examining datasets, creating plots, or running straightforward code snippets.",
            "next_node": "agent",
            "graph": create_code_execution_graph(
                user_id=user_id,
                sambanova_api_key=api_key,
                redis_storage=redis_storage,
                daytona_manager=daytona_manager,
            ),
            "state_input_mapper": lambda x: {
                "code": x,
                "current_retry": 0,
                "max_retries": 5,
                "steps_taken": [],
                "error_detected": False,
                "final_result": "",
                "corrections_proposed": [],
                "files": [],
            },
            "state_output_mapper": lambda x: LiberalFunctionMessage(
                name="DaytonaCodeSandbox",
                content="\n".join(x["steps_taken"]),
                additional_kwargs={
                    "agent_type": "tool_response",
                    "timestamp": datetime.now().isoformat(),
                    "files": x["files"],
                },
                result={"usage": {"total_latency": 0.0}},
            ),
        },
    }
    all_tools = await load_static_tools(tools_config)
    config["configurable"]["type==default/tools"] = all_tools
    config["configurable"]["agent_type"] = "default"

    return config
