import asyncio
import json
from typing import Dict, List, Any, Tuple

from autogen_core import MessageContext
from autogen_core import (
    DefaultTopicId,
    RoutedAgent,
    message_handler,
    type_subscription,
)
from autogen_core.models import LLMMessage, SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

from agent.financial_analysis.financial_analysis_crew import (
    FinancialAnalysisCrew,
    FinancialAnalysisResult,
)
from config.model_registry import model_registry
from services.financial_user_prompt_extractor_service import FinancialPromptExtractor

from ..data_types import (
    AgentRequest,
    AgentStructuredResponse,
    APIKeys,
)
from utils.logging import logger


@type_subscription(topic_type="financial_analysis")
class FinancialAnalysisAgent(RoutedAgent):
    def __init__(
        self,
        api_keys: APIKeys,
    ) -> None:
        super().__init__("FinancialAnalysisAgent")
        logger.info(logger.format_message(None, f"Initializing FinancialAnalysisAgent with ID: {self.id}"))
        self.api_keys = api_keys

    async def execute_financial(
        self, crew: FinancialAnalysisCrew, parameters: Dict[str, Any]
    ) -> Tuple[str, Dict[str,Any]]:
        logger.info(logger.format_message(None, f"Extracting financial information from query: '{parameters.get('query_text', '')[:100]}...'"))
        fextractor = FinancialPromptExtractor(getattr(self.api_keys, model_registry.get_api_key_env()))
        query_text = parameters.get("query_text", "")
        extracted_ticker, extracted_company = fextractor.extract_info(query_text)

        if not extracted_ticker:
            extracted_ticker = parameters.get("ticker", "")
        if not extracted_company:
            extracted_company = parameters.get("company_name", "")

        if not extracted_ticker:
            extracted_ticker = "AAPL"
        if not extracted_company:
            extracted_company = "Apple Inc"

        logger.info(logger.format_message(None, f"Analyzing company: {extracted_company} (ticker: {extracted_ticker})"))
        inputs = {"ticker": extracted_ticker, "company_name": extracted_company}

        if "docs" in parameters:
            inputs["docs"] = parameters["docs"]
            logger.info(logger.format_message(None, "Including additional document analysis in financial analysis"))

        # Run the synchronous function in a thread pool
        raw_result, usage_stats = await asyncio.to_thread(crew.execute_financial_analysis, inputs)
        return raw_result, usage_stats

    @message_handler
    async def handle_financial_analysis_request(self, message: AgentRequest, ctx: MessageContext) -> None:
        try:
            user_id, conversation_id = ctx.topic_id.source.split(":")
            logger.info(logger.format_message(
                ctx.topic_id.source,
                f"Processing financial analysis request for company: '{message.parameters.company_name}'"
            ))

            # Initialize crew
            crew = FinancialAnalysisCrew(
                llm_api_key=getattr(self.api_keys, model_registry.get_api_key_env()),
                exa_key=self.api_keys.exa_key,
                serper_key=self.api_keys.serper_key,
                user_id=user_id,
                run_id=conversation_id,
                docs_included=False,
                verbose=False
            )

            # Execute analysis
            raw_result, usage_stats = await self.execute_financial(
                crew, message.parameters.model_dump()
            )

            financial_analysis_result = FinancialAnalysisResult.model_validate(
                json.loads(raw_result)
            )
            logger.info(logger.format_message(
                ctx.topic_id.source,
                "Successfully parsed financial analysis result"
            ))

        except Exception as e:
            logger.error(logger.format_message(
                ctx.topic_id.source,
                f"Failed to process financial analysis request: {str(e)}"
            ), exc_info=True)
            financial_analysis_result = FinancialAnalysisResult()

        try:
            # Send response back
            response = AgentStructuredResponse(
                agent_type=self.id.type,
                data=financial_analysis_result,
                message=message.parameters.model_dump_json(),
                metadata=usage_stats
            )
            logger.info(logger.format_message(
                ctx.topic_id.source,
                "Publishing financial analysis to user_proxy"
            ))
            await self.publish_message(
                response,
                DefaultTopicId(type="user_proxy", source=ctx.topic_id.source),
            )
        except Exception as e:
            logger.error(logger.format_message(
                ctx.topic_id.source,
                f"Failed to publish response: {str(e)}"
            ), exc_info=True)
