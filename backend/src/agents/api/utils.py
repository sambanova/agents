import json
import os
import re
import uuid
from datetime import datetime
from io import BytesIO
from typing import List, Optional

import markdown
import structlog
from agents.api.data_types import APIKeys
from agents.api.session_state import SessionStateManager
from agents.api.websocket_interface import WebSocketInterface
from agents.components.routing.assistant import AssistantAgentWrapper
from agents.components.routing.deep_research_agent import DeepResearchAgent
from agents.components.routing.educational_content import EducationalContentAgent
from agents.components.routing.financial_analysis import FinancialAnalysisAgent
from agents.components.routing.route import SemanticRouterAgent
from agents.components.routing.sales_leads import SalesLeadsAgent
from agents.components.routing.user_proxy import UserProxyAgent
from agents.storage.redis_service import SecureRedisService
from autogen_core import DefaultSubscription, SingleThreadedAgentRuntime
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


async def initialize_agent_runtime(
    redis_client: SecureRedisService,
    api_keys: APIKeys,
    user_id: str,
    conversation_id: str,
    websocket_manager: WebSocketInterface,
) -> SingleThreadedAgentRuntime:
    """
    Initializes the agent runtime with the required agents and tools.

    Returns:
        SingleThreadedAgentRuntime: The initialized runtime for managing agents.
    """
    global session_state_manager, aoai_model_client

    # load back session state
    session_state_manager.init_conversation(redis_client, user_id, conversation_id)

    agent_runtime = SingleThreadedAgentRuntime(tracer_provider=tracer)

    # Add subscriptions
    logger.info("Adding user proxy subscription")
    await agent_runtime.add_subscription(
        DefaultSubscription(topic_type="user_proxy", agent_type="user_proxy")
    )

    # Register Semantic Router Agent
    await SemanticRouterAgent.register(
        agent_runtime,
        "router",
        lambda: SemanticRouterAgent(
            name="SemanticRouterAgent",
            session_manager=session_state_manager,
            websocket_manager=websocket_manager,
            redis_client=redis_client,
            api_keys=api_keys,
        ),
    )

    await FinancialAnalysisAgent.register(
        agent_runtime,
        "financial_analysis",
        lambda: FinancialAnalysisAgent(api_keys=api_keys, redis_client=redis_client),
    )

    # Keep old educational content agent for "basic" usage
    await EducationalContentAgent.register(
        agent_runtime,
        "educational_content",
        lambda: EducationalContentAgent(api_keys=api_keys),
    )

    await SalesLeadsAgent.register(
        agent_runtime,
        "sales_leads",
        lambda: SalesLeadsAgent(api_keys=api_keys, redis_client=redis_client),
    )

    await AssistantAgentWrapper.register(
        agent_runtime,
        "assistant",
        lambda: AssistantAgentWrapper(api_keys=api_keys, redis_client=redis_client),
    )

    # Register the new deep research agent:
    await DeepResearchAgent.register(
        agent_runtime,
        "deep_research",
        lambda: DeepResearchAgent(
            api_keys=api_keys,
            redis_client=redis_client,
        ),
    )

    # Register the UserProxyAgent instance with the AgentRuntime
    await UserProxyAgent.register(
        agent_runtime,
        "user_proxy",
        lambda: UserProxyAgent(
            session_manager=session_state_manager,
            websocket_manager=websocket_manager,
            redis_client=redis_client,
        ),
    )

    # Start the runtime
    agent_runtime.start()

    logger.info("Agent runtime initialized successfully.")

    return agent_runtime


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


async def generate_deep_research_pdf(content: str) -> Optional[str]:
    """
    Generate a PDF from deep research markdown content and return the file ID.

    Args:
        content: The markdown content to convert to PDF

    Returns:
        Optional[str]: The file ID if successful, None if failed
    """
    try:
        logger.info("Generating PDF from deep research content")

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
                <h1>Deep Research Report</h1>
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
        filename = f"deep_research_report_{timestamp}.pdf"

        logger.info("PDF generated successfully", file_size=len(pdf_data))

        return file_id, filename, pdf_data

    except Exception as e:
        logger.error("Failed to generate PDF from deep research content", error=str(e))
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
