from datetime import datetime, timezone
from agents.components.financial_analysis.financial_analysis_crew import (
    FinancialAnalysisCrew,
)
from agents.services.financial_user_prompt_extractor_service import (
    FinancialPromptExtractor,
)
from agents.storage.redis_service import SecureRedisService
from langchain_core.messages import AIMessage
from agents.components.compound.util import extract_api_key
from langgraph.graph import END
from langgraph.graph.message import MessageGraph
from langchain_core.runnables import RunnableConfig


def create_financial_analysis_graph(redis_client: SecureRedisService):
    """Create a simple subgraph with just one node that greets the user."""

    async def financial_analysis_node(messages, *, config: RunnableConfig = None):

        api_key = extract_api_key(config)

        fextractor = FinancialPromptExtractor(llm_api_key=api_key, provider="sambanova")
        extracted_ticker, extracted_company = fextractor.extract_info(
            messages[-1].content
        )

        # Initialize crew
        crew = FinancialAnalysisCrew(
            llm_api_key=api_key,
            provider="sambanova",
            user_id=config["metadata"]["user_id"],
            run_id=config["metadata"]["thread_id"],
            docs_included=False,
            verbose=False,
            message_id=config["metadata"]["message_id"],
            redis_client=redis_client,
        )

        inputs = {"ticker": extracted_ticker, "company_name": extracted_company}

        result = await crew.execute_financial_analysis(inputs)

        return AIMessage(
            content=result[0],
            additional_kwargs={
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_type": "financial_analysis_end",
                "token_usage": result[1],
            },
        )

    # Create the workflow with just one node
    workflow = MessageGraph()

    # Add the single greeter node
    workflow.add_node("greeter", financial_analysis_node)

    # Set entry point
    workflow.set_entry_point("greeter")

    # Go directly to END after the greeter node
    workflow.add_edge("greeter", END)

    # Compile and return
    return workflow.compile()
