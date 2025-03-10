import sys
import os
import uuid

from agent.crewai_llm import CustomLLM
from api.services.redis_service import SecureRedisService

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# load dotenv
from dotenv import load_dotenv
load_dotenv()

# Only import and initialize langtrace if API key is set
if os.getenv("LANGTRACE_API_KEY"):
    from langtrace_python_sdk import langtrace
    langtrace.init(api_key=os.getenv("LANGTRACE_API_KEY"))

from crewai import Agent, Task, Crew, Process
from tools.company_intelligence_tool import CompanyIntelligenceTool
from tools.market_research_tool import MarketResearchTool
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from utils.agent_thought import RedisConversationLogger
from config.model_registry import model_registry

class Outreach(BaseModel):
    company_name: str
    website: str
    headquarters: str
    key_contacts: str
    funding_status: str
    funding_amount: str
    product: str
    relevant_trends: str
    opportunities: str
    challenges: str
    email_subject: str
    email_body: str


class OutreachList(BaseModel):
    outreach_list: List[Outreach] = []


class ExtractedCompany(BaseModel):
    name: str
    website: str
    headquarters: str
    funding_stage: str
    funding_amount: str
    product: str
    detailed_description: str
    key_contacts: str


class ExtractedCompanyList(BaseModel):
    companies: List[ExtractedCompany]


class ExtractedMarketTrend(BaseModel):
    company_name: str
    relevant_trends: str
    opportunities: str
    challenges: str


class ExtractedMarketTrendList(BaseModel):
    market_trends: List[ExtractedMarketTrend]


class ResearchCrew:
    def __init__(
        self,
        llm_api_key: str,
        provider: str,
        exa_key: str,
        user_id: str = "",
        run_id: str = "",
        message_id: str = "",
        extra_headers: Optional[Dict[str, str]] = None,
        redis_client: SecureRedisService = None,
        verbose: bool = True,
    ):

        model_info = model_registry.get_model_info(model_key="llama-3.3-70b", provider=provider)
        self.llm =  CustomLLM(
            model=model_info["crewai_prefix"] + "/" + model_info["model"],
            temperature=0.0,
            max_tokens=8192,
            api_key=llm_api_key,
            extra_headers=extra_headers
        )
        self.exa_key = exa_key
        self.user_id = user_id
        self.run_id = run_id
        self.message_id = message_id
        self.verbose = verbose
        self.redis_client = redis_client

        self._initialize_agents()
        self._initialize_tasks()

    def _initialize_agents(self) -> None:
        """We define aggregator_agent, data_extraction_agent, market_trends_agent, outreach_agent."""

        # 1) aggregator_agent
        self.aggregator_agent = Agent(
            role="Aggregator Search Agent",
            goal="Perform aggregator search for user's query using CompanyIntelligenceTool",
            backstory="You retrieve top-level aggregator results from Exa using the tool.",
            llm=self.llm,
            allow_delegation=False,
            verbose=self.verbose,
            tools=[CompanyIntelligenceTool(api_key=self.exa_key)]
        )

        # 2) data_extraction_agent
        self.data_extraction_agent = Agent(
            role="Data Extraction Agent",
            goal="Parse aggregator snippet text with the LLM for detailed data, do optional enrichment.",
            backstory="You parse aggregator text with the LLM to produce structured data.",
            llm=self.llm,
            allow_delegation=False,
            verbose=self.verbose
        )

        # 3) market_trends_agent
        self.market_trends_agent = Agent(
            role="Market Trends Analyst",
            goal="Analyze current market trends and opportunities",
            backstory="You are an experienced market research analyst ...",
            llm=self.llm,
            allow_delegation=False,
            verbose=self.verbose,
            tools=[MarketResearchTool(api_key=self.exa_key)]
        )

        # 4) outreach_agent
        self.outreach_agent = Agent(
            role="Outreach Specialist",
            goal="Create compelling, personalized outreach emails",
            backstory="You craft personalized outreach messages ...",
            llm=self.llm,
            allow_delegation=False,
            verbose=self.verbose
        )

        # Hook them in
        self.aggregator_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Aggregator Search Agent",
            workflow_name="Lead Generation",
            llm_name=self.llm.model,
            message_id=self.message_id,
            redis_client=self.redis_client
        )
        self.data_extraction_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Data Extraction Agent",
            workflow_name="Lead Generation",
            llm_name=self.llm.model,
            message_id=self.message_id,
            redis_client=self.redis_client
        )
        self.market_trends_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Market Trends Analyst",
            workflow_name="Lead Generation",
            llm_name=self.llm.model,
            message_id=self.message_id,
            redis_client=self.redis_client
        )
        self.outreach_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Outreach Specialist",
            workflow_name="Lead Generation",
            llm_name=self.llm.model,
            message_id=self.message_id,
            redis_client=self.redis_client
        )

    def _initialize_tasks(self) -> None:
        """
        5 tasks in sequential order:
          1) aggregator_search_task
          2) data_extraction_task
          3) data_enrichment_task
          4) market_trends_task
          5) outreach_task
        """

        # 1) aggregator_search_task
        self.aggregator_search_task = Task(
            description=(
                "Step 1: aggregator_agent calls CompanyIntelligenceTool.run(...) with:\n"
                "  industry={industry}\n"
                "  company_stage={company_stage}\n"
                "  geography={geography}\n"
                "  funding_stage={funding_stage}\n"
                "  product={product}\n\n"
                "Return aggregator JSON with 'companies' etc."
            ),
            expected_output=(
                "A JSON with 'companies', each having fields like name, website, description."
            ),
            agent=self.aggregator_agent
        )

        # 2) data_extraction_task
        self.data_extraction_task = Task(
            description=(
                "Step 2: data_extraction_agent reads aggregator_search_task's 'companies'. "
                "For each company's 'description' aggregator snippet, parse with LLM output to get detailed fields. "
                "If the 'text' field is available parse information from that field as well."
                "Remember some of these links will be to articles and NOT companies. You should not include these."
                "If within the text field of such articles there are companies mentioned you should include them if they are relevant."
                "Store partial results in data_manager. Return the new list of companies."
                "Remember to get the most relevant companies for the user's query, as well as the most relevant products and services."
                "These should be named products and services, not just categories. This is very important."
            ),
            expected_output=(
                "[\n"
                "  {\n"
                "    'name': '...', 'website': '...', 'headquarters': '...', "
                "    'funding_stage': '...', 'employee_count': '...', "
                "'funding_amount': '...', 'product_list': '...', ...\n"
                "    'detailed_description': '...', ...\n"
                "  }\n"
                "]"
            ),
            agent=self.data_extraction_agent,
            context=[self.aggregator_search_task],
            output_pydantic=ExtractedCompanyList
        )

        # 3) data_enrichment_task
        self.data_enrichment_task = Task(
            description=(
                "Step 3: For each partial company, if missing fields, do an extra aggregator query, parse again.  "
                "The data should be as enriched as possible. Listing all named products and services from that company."
                "As well as the key contacts and their titles for outreach."
                "For key contacts, you should return as many as possible not just CEO etc."
                "Then return the final enriched array."
            ),
            expected_output=(
                "[\n"
                "  {\n"
                "    'name': '...', 'website': '...', 'headquarters': '...', "
                "    'funding_stage': '...', 'employee_count': '...', 'product': '...', ...\n"
                "    'funding_amount': '...', ...\n"
                "    'detailed_description': '...', ...\n"
                "    'key_contacts': '...', ...\n"
                "  }\n"
                "]"
            ),
            agent=self.data_extraction_agent,
            context=[self.data_extraction_task],
            output_pydantic=ExtractedCompanyList
        )

        # 4) market_trends_task
        self.market_trends_task = Task(
            description=(
                "Use Market Research Intelligence with:\n"
                "  industry={industry}\n"
                "  product={product}\n\n"
                "Then map findings to the final companies from data_enrichment_task."
            ),
            expected_output=(
                "[\n"
                "  {\n"
                "    'company_name': '...', 'relevant_trends': '...', "
                "    'opportunities': '...', 'challenges': '...'\n"
                "  }\n"
                "]"
            ),
            agent=self.market_trends_agent,
            context=[self.data_enrichment_task],
            output_pydantic=ExtractedMarketTrendList
        )

        # 5) outreach_task
        self.outreach_task = Task(
            description=(
                "Create a JSON array of personalized emails for the final companies. "
                "company_name, website, headquarters, funding_status, email_subject, email_body. "
                "Body must start 'Dear [Company]' (100-150 words). Return ONLY a JSON array. "
                "Be sure to mention the company's product or service by NAME in the email body and use all relevant information."
                "We should map ALL fields collected in the data_enrichment_task and market_trends_task to the response json"
                "To create a hyper-personalized email based on relevant current information."
                "The email should be tailored to the company's named product or service, and the market trends."
            ),
            expected_output=(
                "[\n"
                "  {\n"
                "    'company_name': '...', "
                "    'website': '...', "
                "    'headquarters': '...', "
                "    'funding_status': '...', "
                "    'funding_amount': '...', "
                "    'product': '...', "
                "    'relevant_trends': '...', "
                "    'opportunities': '...', "
                "    'challenges': '...', "
                "    'email_subject': '...', "
                "    'email_body': '...'\n"
                "  }\n"
                "]"
            ),
            agent=self.outreach_agent,
            context=[self.market_trends_task, self.data_enrichment_task],
            output_pydantic=OutreachList
        )

    def execute_research(self, inputs: dict) -> Tuple[str, Dict[str,Any]]:
        """
        Run the 5-step pipeline with 4 agents in sequential order.
        """
        crew = Crew(
            agents=[
                self.aggregator_agent,
                self.data_extraction_agent,
                self.market_trends_agent,
                self.outreach_agent
            ],
            tasks=[
                self.aggregator_search_task,
                self.data_extraction_task,
                self.data_enrichment_task,
                self.market_trends_task,
                self.outreach_task
            ],
            process=Process.sequential,
            verbose=self.verbose,
            memory=False
        )
        results = crew.kickoff(inputs=inputs)
        return results.pydantic.model_dump_json(), dict(results.token_usage)


def main():
    # Example usage with dummy keys
    example_samba_key = "test_samba_key"
    example_exa_key = "test_exa_key"

    # Random run_id
    example_run_id = str(uuid.uuid4())
    # Hard-coded user for demonstration
    example_user_id = "test_user_123"

    crew = ResearchCrew(
        sambanova_key=example_samba_key,
        exa_key=example_exa_key,
        user_id=example_user_id,
        run_id=example_run_id
    )
    example_inputs = {
        "industry": "ai hardware chip",
        "geography": "silicon valley",
        "funding_stage": "series d",
        "company_stage": "",
        "product": ""
    }

    final_output, _ = crew.execute_research(example_inputs)
    print("Crew Output:")
    print(final_output)


if __name__ == "__main__":
    main()
