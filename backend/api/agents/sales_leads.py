import asyncio
from typing import Any, Dict
from autogen_core import DefaultTopicId, RoutedAgent, message_handler, type_subscription
from autogen_core import MessageContext
from api.data_types import AgentEnum, AgentRequest, AgentStructuredResponse, ErrorResponse, SalesLeads, APIKeys
from agent.lead_generation_crew import OutreachList, ResearchCrew
from config.model_registry import model_registry
from services.user_prompt_extractor_service import UserPromptExtractor
from utils.logging import logger
from api.services.redis_service import SecureRedisService

@type_subscription(topic_type="sales_leads")
class SalesLeadsAgent(RoutedAgent):
    def __init__(self, api_keys: APIKeys, redis_client: SecureRedisService):
        super().__init__("SalesLeadsAgent")
        logger.info(logger.format_message(None, f"Initializing SalesLeadsAgent with ID: {self.id}"))
        self.api_keys = api_keys
        self.redis_client = redis_client

    @message_handler
    async def handle_sales_leads_request(
        self, message: AgentRequest, ctx: MessageContext
    ) -> None:
        try:
            user_id, conversation_id = ctx.topic_id.source.split(":")   
            logger.info(logger.format_message(
                ctx.topic_id.source,
                "Processing sales leads request"
            ))
            
            crew = ResearchCrew(
                llm_api_key=getattr(self.api_keys, model_registry.get_api_key_env(provider=message.provider)),
                exa_key=self.api_keys.exa_key,
                user_id=user_id,
                run_id=conversation_id,
                verbose=False,
                provider=message.provider,
                message_id=message.message_id,
                extra_headers=self.api_keys.extra_headers,
                redis_client=self.redis_client
            )
            parameters_dict = {k: v if v is not None else "" for k, v in message.parameters.model_dump().items()}
            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Starting lead research with parameters: {parameters_dict}"
            ))

            raw_result, usage_stats = await asyncio.to_thread(crew.execute_research, parameters_dict)
            logger.info(logger.format_message(
                ctx.topic_id.source,
                "Successfully generated sales leads"
            ))
            outreach_list = OutreachList.model_validate_json(raw_result)

            # Send response back
            response = AgentStructuredResponse(
                agent_type=self.id.type,
                data=outreach_list,
                message=message.parameters.model_dump_json(),
                metadata=usage_stats,
                message_id=message.message_id
            )
            logger.info(logger.format_message(
                ctx.topic_id.source,
                "Publishing sales leads to user_proxy"
            ))
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )
        except Exception as e:
            logger.error(logger.format_message(
                ctx.topic_id.source,
                f"Error processing sales leads request: {str(e)}"
            ), exc_info=True)
            response = AgentStructuredResponse(
                agent_type=AgentEnum.Error,
                data=ErrorResponse(error=f"Unable to assist with sales leads, try again later."),
                message=f"Error processing sales leads request: {str(e)}",
                message_id=message.message_id
            )
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )