########## NEW CODE ##########
import json
import os
import re
from typing import List
from autogen_core import SingleThreadedAgentRuntime, TypeSubscription
from autogen_core import DefaultSubscription
from fastapi import WebSocket
from fastapi.responses import JSONResponse
import redis

from api.agents.financial_analysis import FinancialAnalysisAgent
from api.agents.educational_content import EducationalContentAgent
from api.agents.sales_leads import SalesLeadsAgent
from api.agents.deep_research_agent import DeepResearchAgent
from api.agents.sambanova_knowledge_agent import SambaKnowledgeAgent
from api.agents.assistant import AssistantAgentWrapper
from api.agents.route import SemanticRouterAgent

from autogen_agentchat.agents import AssistantAgent

from api.otlp_tracing import configure_oltp_tracing
from api.websocket_interface import WebSocketInterface
from api.services.redis_service import SecureRedisService
from utils.logging import logger
from api.session_state import SessionStateManager
from api.agents.user_proxy import UserProxyAgent

from api.data_types import APIKeys


session_state_manager = SessionStateManager()

# Make tracer optional based on environment variable
tracer = None
if os.getenv("ENABLE_TRACING", "false").lower() == "true":
    tracer = configure_oltp_tracing()

class DocumentContextLengthError(Exception):
    """Exception raised when document(s) exceed the maximum context length."""
    def __init__(self, total_tokens: int, max_tokens: int):
        self.total_tokens = total_tokens
        self.max_tokens = max_tokens
        super().__init__(f"Combined documents exceed maximum context window size of {max_tokens} tokens (got {total_tokens} tokens). Please reduce the number or size of documents.")

async def initialize_agent_runtime(
    redis_client: SecureRedisService,
    api_keys: APIKeys,
    user_id: str,
    conversation_id: str,
    websocket_manager: WebSocketInterface
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
        agent_runtime, "assistant", lambda: AssistantAgentWrapper(api_keys=api_keys, redis_client=redis_client)
    )

    await DeepResearchAgent.register(
        agent_runtime,
        "deep_research",
        lambda: DeepResearchAgent(
            api_keys=api_keys,
            redis_client=redis_client,
        ),
    )
    
    await SambaKnowledgeAgent.register(
        agent_runtime,
        "sambanova_knowledge",
        lambda: SambaKnowledgeAgent(
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


def load_documents(user_id: str, document_ids: List[str], redis_client: SecureRedisService, context_length_summarizer: int) -> List[str]:
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
            doc_text = "\n".join([chunk['text'] for chunk in chunks])
            token_count = estimate_tokens_regex(doc_text)
            
            files_b64 = {
                chunk["metadata"]["source"]:chunk["metadata"]['base_64_url'] 
                for chunk in chunks 
                if chunk["metadata"].get('base_64_url') is not None
            }
            
            # Update total token count and check if it would exceed the limit
            if total_tokens + token_count > context_length_summarizer:
                raise DocumentContextLengthError(total_tokens + token_count, context_length_summarizer)
            
            total_tokens += token_count
            documents.append(doc_text)

    return documents, files_b64