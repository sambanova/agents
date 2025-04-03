########## sambanova_knowledge_agent.py (llamastack) ##########

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
    APIKeys,
    SambaKnowledge,
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
        
    @message_handler
    async def handle_deep_research_request(
        self, message: AgentRequest, ctx: MessageContext
    ) -> None:
        
        response = f"this is a response from sambanova knowledge agent for {message}"
        
        await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )