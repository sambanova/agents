import asyncio
import json
from typing import Dict, List, Any

from autogen_core import MessageContext
from autogen_core import (
    DefaultTopicId,
    RoutedAgent,
    message_handler,
    type_subscription,
)

from agent.samba_research_flow.crews.edu_research.edu_research_crew import EducationalPlan
from agent.samba_research_flow.samba_research_flow import SambaResearchFlow
from config.model_registry import model_registry

from api.data_types import (
    AgentEnum,
    AgentRequest,
    AgentStructuredResponse,
    EducationalPlanResult,
    APIKeys,
    ErrorResponse,
)
from utils.logging import logger

@type_subscription(topic_type="educational_content")
class EducationalContentAgent(RoutedAgent):
    def __init__(self, api_keys: APIKeys):
        super().__init__("EducationalContentAgent")
        logger.info(logger.format_message(None, f"Initializing EducationalContentAgent with ID: {self.id}"))
        self.api_keys = api_keys

    @message_handler
    async def handle_educational_content_request(self, message: AgentRequest, ctx: MessageContext) -> None:
        try:
            user_id, conversation_id = ctx.topic_id.source.split(":")
            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Processing educational content request for topic: '{message.parameters.topic}'"
            ))
            
            edu_flow = SambaResearchFlow(
                    llm_api_key=getattr(self.api_keys, model_registry.get_api_key_env(provider=message.provider)),
                    provider=message.provider,
                    serper_key=self.api_keys.serper_key,
                    user_id=user_id,
                    run_id=conversation_id,
                    docs_included=True if message.docs else False,
                    verbose=False
                )
            edu_inputs = {
                "topic": message.parameters.topic,
                "audience_level": message.parameters.audience_level if message.parameters.audience_level else "",
                "additional_context": message.parameters.focus_areas if message.parameters.focus_areas else ""
            }
            if message.docs:
                edu_inputs["docs"] = message.docs
            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Starting educational content flow with inputs: {edu_inputs}"
            ))
            edu_flow.input_variables = edu_inputs
            result = await asyncio.to_thread(edu_flow.kickoff, edu_inputs)

            usage_stats = [edu_flow.research_usage] + edu_flow.content_usage + ([edu_flow.summariser_usage] if edu_flow.summariser_usage else [])

            # Sum up usage statistics
            total_usage = {
                'total_tokens': 0,
                'prompt_tokens': 0, 
                'cached_prompt_tokens': 0,
                'completion_tokens': 0,
                'successful_requests': 0
            }
            
            for usage in usage_stats:
                for key in total_usage:
                    total_usage[key] += usage.get(key, 0)

            logger.info(logger.format_message(
                ctx.topic_id.source,
                "Successfully generated educational content"
            ))
            sections_with_content = EducationalPlanResult.model_validate({"sections": result})
            
            # Send response back
            response = AgentStructuredResponse(
                agent_type=self.id.type,
                data=sections_with_content,
                message=message.parameters.model_dump_json(),
                metadata=total_usage,
                message_id=message.message_id
            )
            logger.info(logger.format_message(
                ctx.topic_id.source,
                "Publishing educational content to user_proxy"
            ))
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )
        except Exception as e:
            logger.error(logger.format_message(
                ctx.topic_id.source,
                f"Failed to process educational content request: {str(e)}"
            ), exc_info=True)

            error_message = str(e).lower()
            if "rate limit exceeded" in error_message or "too many requests" in error_message:
                error_response = "Rate limit exceeded. Please try again later."
            else:
                error_response = "Unable to assist with research content, try again later."

            response = AgentStructuredResponse(
                agent_type=AgentEnum.Error,
                data=ErrorResponse(error=error_response),
                message=f"Error processing research content request: {str(e)}",
                message_id=message.message_id
            )
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )
