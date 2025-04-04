########## sambanova_knowledge_agent.py (llamastack) ##########
import json
import time
import uuid

import asyncio

async def wait_ten_seconds():
    print("Waiting for 10 seconds...")
    await asyncio.sleep(10)
    print("Done waiting!")
    return "Finished!"

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
        message_id: str
    ) -> dict:
        if session_id not in self._session_threads:
            user_id, conversation_id = session_id.split(":")
            thread_id = str(uuid.uuid4())
            self._session_threads[session_id] = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "mesage_id": message_id,
                    "agent_name":"sambanova_knowledge",
                    "workflow_name":"sambanova_knowledge",
                    "redis_client":self.redis_client
                }
            }
        
        # TODO create client with api key
        
        return self._session_threads[session_id]
     
    @message_handler
    async def handle_sambanova_knowledge_request(
        self, message: AgentRequest, ctx: MessageContext
    ) -> None:
        
        logger.info(
                logger.format_message(
                    ctx.topic_id.source,
                    f"Processing request: '{message.parameters.sambanova_question[:100]}...'",
                )
            )
        
        session_id = ctx.topic_id.source
        user_id, conversation_id = session_id.split(":")
        user_text = message.query.strip()
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
        
        model = model_info["model"]
        
        #get thread
        thread_config = self._get_or_create_thread_config(session_id, message.message_id)
        
        # TODO main call to agent passing client of the current user
        # and using the thread config params 
        
        #publish intermediate thoughts / steps
        
        assistant_metadata = {
                "duration": 1,
                "llm_name": "llama3.3",
                "llm_provider": "sambanova",
                "workflow": "Sambanova Knowledge",
                "agent_name": "Sambanova Knowledge",
                "task": "assistant",
                "total_tokens": 10,
                "prompt_tokens": 10,
                "completion_tokens": 10,
            }
        
        intermediate_message = {
                "user_id": user_id,
                "run_id": conversation_id,
                "message_id": message.message_id,
                "agent_name": "sambanova_knowledge",
                "text": "this is a dummy thought",
                "timestamp": time.time(),
                "metadata": assistant_metadata,
            }
        
        channel = f"agent_thoughts:{user_id}:{conversation_id}"
        self.redis_client.publish(channel, json.dumps(intermediate_message))
        await asyncio.sleep(5)
        self.redis_client.publish(channel, json.dumps(intermediate_message))
        await asyncio.sleep(5)
        
        #publish dummy response 
        text_response = f"this is a response from sambanova knowledge agent for: {user_text}"
        
        token_usage = {
                "total_tokens": 10,
                "prompt_tokens": 10,
                "completion_tokens": 10,
            }
        
        response = AgentStructuredResponse(
            agent_type=AgentEnum.SambaKnowledge,
            data=SambaKnowledgeResult(response=text_response),
            message="Sambanova Knowledge flow completed.",
            metadata=token_usage,
            message_id=message.message_id
        )
        
        await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )