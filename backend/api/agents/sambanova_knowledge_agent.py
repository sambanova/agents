########## sambanova_knowledge_agent.py (llamastack) ##########
import json
import time
import uuid

import asyncio

from api.services.redis_service import SecureRedisService

from autogen_core import (
    RoutedAgent,
    type_subscription,
    MessageContext,
    DefaultTopicId,
    message_handler,
)

from api.data_types import (
    AgentRequest,
    AgentStructuredResponse,
    APIKeys,
    AgentEnum,
    SambaKnowledgeResult,
)


from config.model_registry import model_registry
from utils.logging import logger

from .sambanova_knowledge import llamastack_sambanova_knowledge

@type_subscription(topic_type="sambanova_knowledge")
class SambaKnowledgeAgent(RoutedAgent):
    def __init__(
        self, api_keys: APIKeys, redis_client: SecureRedisService = None
    ):
        super().__init__("SambaKnowledgeAgent")
        self.api_keys = api_keys
        self.redis_client = redis_client
        logger.info(
            logger.format_message(
                None, f"Initializing DeepResearchAgent with ID: {self.id}"
            )
        )
        self._session_threads = {}
        
        #Init Agent
    
    def _get_or_create_thread_config(
        self,
        session_id: str,
        message_id: str,
        model: str,
        provider: str,
    ) -> dict:
        if session_id not in self._session_threads:
            user_id, conversation_id = session_id.split(":")
            thread_id = str(uuid.uuid4())
            self._session_threads[session_id] = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "agent_name":"sambanova_knowledge",
                    "workflow_name":"sambanova_knowledge",
                    "model":model,
                    "provider":provider,
                    "redis_client":self.redis_client
                }
            }
        
        return self._session_threads[session_id]
     
    @message_handler
    async def handle_sambanova_knowledge_request(
        self, message: AgentRequest, ctx: MessageContext
    ) -> None:
        
        logger.info(
                logger.format_message(
                    ctx.topic_id.source,
                    f"Processing request: '{message.parameters.sambaknowledge_query[:100]}...'",
                )
            )
        
        session_id = ctx.topic_id.source
        user_text = message.parameters.sambaknowledge_query.strip()
        docs = message.docs
        files_b64 = message.files_b64
        provider = message.provider
        
        #get model id
        if provider not in ["sambanova"]:
            raise ValueError(f"Sambanova Knowledge agent doesn't have support for provider {provider}")
        model_info = model_registry.get_model_info(
            model_key="llama-3.3-70b", 
            provider=provider
        )
        if not model_info:
            raise ValueError(f"No model configuration found for provider {provider}")
        
        model = f"{model_info['crewai_prefix']}/{model_info['model']}"
        
        #get thread
        thread_config = self._get_or_create_thread_config(session_id, message.message_id, model, provider)
        
        #call 
        thread = asyncio.to_thread(
            llamastack_sambanova_knowledge.call,
            thread_config,
            user_text,
            docs,
            files_b64,
            api_key=getattr(self.api_keys, model_registry.get_api_key_env(provider=message.provider))
        )
        thread_response = await asyncio.gather(thread)
        text_response, metadata = thread_response[0]
        
        response = AgentStructuredResponse(
            agent_type=AgentEnum.SambaKnowledge,
            data=SambaKnowledgeResult(response=text_response),
            message="Sambanova Knowledge flow completed.",
            metadata=metadata,
            message_id=message.message_id
        )
        
        await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )