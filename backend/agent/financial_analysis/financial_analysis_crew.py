import os
import sys
import uuid
import json
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
from api.services.redis_service import SecureRedisService
import yfinance as yf

from agent.crewai_llm import CustomLLM
from services.structured_output_parser import CustomConverter

# Ensure our parent directories are in sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
parent_of_parent_dir = os.path.abspath(os.path.join(parent_dir, ".."))
if parent_of_parent_dir not in sys.path:
    sys.path.insert(0, parent_of_parent_dir)

from dotenv import load_dotenv

# Only import and initialize langtrace if API key is set
if os.getenv("LANGTRACE_API_KEY"):
    from langtrace_python_sdk import langtrace
    langtrace.init(api_key=os.getenv("LANGTRACE_API_KEY"))

# crewai imports
from crewai import Agent, Task, Crew, LLM, Process
from utils.agent_thought import RedisConversationLogger
from crewai.tools import tool
from crewai_tools import SerperDevTool
from tools.competitor_analysis_tool import competitor_analysis_tool
from tools.fundamental_analysis_tool import fundamental_analysis_tool
from tools.technical_analysis_tool import yf_tech_analysis
from tools.risk_assessment_tool import risk_assessment_tool
from config.model_registry import model_registry


###################### NEWS MODELS & (SERPER) WRAPPER ######################
from pydantic import BaseModel, Field
from pydantic import field_validator
from datetime import datetime, timedelta

class NewsItem(BaseModel):
    title: str
    content: str
    link: str
    published_time: str
    named_entities: List[str] = []

class YahooNewsData(BaseModel):
    news_items: List[NewsItem]

########################## Additional Pydantic Models for aggregator ###############
class QuarterlyFundamentals(BaseModel):
    date: str
    total_revenue: Optional[str] = None
    net_income: Optional[str] = None

class FundamentalData(BaseModel):
    company_name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: str = ""
    pe_ratio: str = ""
    forward_pe: str = ""
    peg_ratio: str = ""
    ps_ratio: str = ""
    price_to_book: str = ""
    dividend_yield: str = ""
    beta: str = ""
    year_high: str = ""
    year_low: str = ""
    analyst_recommendation: str = ""
    target_price: str = ""
    earnings_per_share: str = ""
    profit_margins: str = ""
    operating_margins: str = ""
    ebitda_margins: str = ""
    short_ratio: str = ""
    current_ratio: str = ""
    debt_to_equity: str = ""
    return_on_equity: str = ""
    return_on_assets: str = ""
    revenue_growth: str = ""
    net_income_growth: str = ""
    free_cash_flow: str = ""
    quarterly_fundamentals: List[QuarterlyFundamentals] = []
    advanced_fundamentals: Dict[str, str] = {}
    dividend_history: List[Dict[str,Any]] = []

class TechnicalChartData(BaseModel):
    date: str
    open: str
    high: str
    low: str
    close: str
    volume: str

class TechnicalData(BaseModel):
    moving_averages: Dict[str, Optional[str]] = {}
    rsi: Optional[str] = None
    macd: Dict[str, Optional[str]] = {}
    bollinger_bands: Dict[str, Optional[str]] = {}
    volatility: Optional[str] = None
    momentum: Optional[str] = None
    support_levels: List[str] = []
    resistance_levels: List[str] = []
    detected_patterns: List[str] = []
    chart_data: List[TechnicalChartData] = []
    stock_price_data: List[TechnicalChartData] = []

class RiskDailyReturns(BaseModel):
    date: str
    daily_return: Union[str, float]

class RiskData(BaseModel):
    beta: float
    sharpe_ratio: str
    value_at_risk_95: str
    max_drawdown: str
    volatility: str
    daily_returns: List[RiskDailyReturns] = Field(default_factory=list)

    @field_validator('daily_returns', mode='before')
    @classmethod
    def validate_daily_returns(cls, v):
        try:
            if not v:
                return []
            if all(isinstance(x, dict) for x in v):
                return [RiskDailyReturns(**x) for x in v]
            return []
        except:
            return []

class CompetitorInfo(BaseModel):
    ticker: str
    name: str
    market_cap: str
    pe_ratio: str
    ps_ratio: str
    ebitda_margins: str
    profit_margins: str
    revenue_growth: str
    earnings_growth: str
    short_ratio: str
    industry: str
    sector: str

class CompetitorBlock(BaseModel):
    competitor_tickers: List[str] = []
    competitor_details: List[CompetitorInfo] = []

class WeeklyPriceData(BaseModel):
    date: str
    open: Union[str, float]
    high: Union[str, float]
    low: Union[str, float]
    close: Union[str, float]
    volume: Union[str, float]


class NewsItem(BaseModel):
    title: str
    link: str

class News(BaseModel):
    news_items: List[NewsItem] = []
    news_summary: str = ""

class FinancialAnalysisResult(BaseModel):
    ticker: str
    company_name: str
    competitor: CompetitorBlock
    fundamental: FundamentalData
    risk: RiskData
    stock_price_data: List[WeeklyPriceData] = []
    news: News
    comprehensive_summary: str = ""

########################### The Main Crew Class ###########################
load_dotenv()

class FinancialAnalysisCrew:
    """
    Multi-agent pipeline for advanced financial analysis:
      1) Enhanced competitor (LLM fallback if needed)
      2) Competitor analysis
      3) Fundamentals
      4) Technical (3mo weekly)
      5) Risk (1y)
      6) News
      7) Aggregator => merges all into final JSON, at least 700 words in summary.
    Using partial concurrency to speed up tasks that do not depend on each other.
    """

    def __init__(
        self,
        llm_api_key: str,
        provider: str,
        serper_key: str,
        user_id: str = "",
        run_id: str = "",
        docs_included: bool = False,
        redis_client: SecureRedisService = None,
        message_id: str = None,
        verbose: bool = True
    ):
        competitor_finder_model_info = model_registry.get_model_info(model_key="llama-3.1-8b", provider=provider)
        self.competitor_finder_llm = CustomLLM(
            model=competitor_finder_model_info["crewai_prefix"] + "/" + competitor_finder_model_info["model"],
            temperature=0.0,
            max_tokens=8192,
            api_key=llm_api_key,
            base_url=competitor_finder_model_info["url"],
        )
        model_info = model_registry.get_model_info(model_key="llama-3.1-8b", provider=provider)
        self.llm = CustomLLM(
            model=model_info["crewai_prefix"] + "/" + model_info["model"],
            temperature=0.0,
            max_tokens=8192,
            api_key=llm_api_key,
            base_url=model_info["url"],
        )
        aggregator_model_info = model_registry.get_model_info(model_key="llama-3.3-70b", provider=provider)
        self.aggregator_llm = CustomLLM(
            model=aggregator_model_info["crewai_prefix"] + "/" + aggregator_model_info["model"],
            temperature=0.0,
            max_tokens=8192,
            api_key=llm_api_key,
            base_url=aggregator_model_info["url"],
        )
        self.serper_key = serper_key
        self.user_id = user_id
        self.run_id = run_id
        self.docs_included = docs_included
        self.verbose = verbose
        self.redis_client = redis_client
        self.message_id = message_id
        self._init_agents()
        self._init_tasks()

    def _init_agents(self):
        # 1) competitor finder
        self.enhanced_competitor_agent = Agent(
            role="Enhanced Competitor Finder",
            goal="Identify 3 closest competitor tickers for the same industry and sector as {ticker}.",
            backstory="Expert in analyzing sector, fallback to LLM guess if yfinance fails. No extraneous calls needed.",
            llm=self.competitor_finder_llm,
            allow_delegation=False,
            verbose=self.verbose,
        )

        # 2) competitor analysis
        self.competitor_analysis_agent = Agent(
            role="Competitor Analysis Agent",
            goal="Given competitor_tickers, produce competitor_details from yfinance fundamentals.",
            backstory="Focus on market_cap, margins, growth, short_ratio, etc. Must be quick and direct.",
            llm=self.llm,
            tools=[competitor_analysis_tool],
            allow_delegation=False,
            verbose=self.verbose,
        )

        # 3) fundamental
        self.fundamental_agent = Agent(
            role="Fundamental Analysis Agent",
            goal="Retrieve fundamental data from yfinance including advanced_fundamentals, dividend_history. for {ticker}",
            backstory="Focus on a single pass to avoid overhead. Return structured data quickly.",
            llm=self.llm,
            tools=[fundamental_analysis_tool],
            allow_delegation=False,
            verbose=self.verbose,
        )

        # 4) technical
        self.technical_agent = Agent(
            role="Technical Analysis Agent",
            goal="Gather 3-month weekly price data plus standard technical fields from yfinance. for {ticker}",
            backstory="No repeated calls. Provide stock_price_data for front-end charting.",
            llm=self.llm,
            tools=[yf_tech_analysis],
            allow_delegation=False,
            verbose=self.verbose,
        )

        # 5) risk
        self.risk_agent = Agent(
            role="Risk Assessment Agent",
            goal="Compute Beta, Sharpe, VaR, Max Drawdown, Volatility over 1 year for {ticker}.",
            backstory="Return monthly-averaged daily returns quickly. No extraneous calls.",
            llm=self.llm,
            tools=[risk_assessment_tool],
            allow_delegation=False,
            verbose=self.verbose,
        )

        # 6) news
        os.environ["SERPER_API_KEY"] = self.serper_key
        self.news_agent = Agent(
            role="Financial News Agent",
            goal="Gather recent news for {ticker}, focusing on recent events that could affect stock price. Must be quick.",
            backstory="Search for top ~10 items, do minimal overhead. Summaries used by aggregator. No re-calls.",
            llm=self.aggregator_llm,
            tools=[SerperDevTool()],
            allow_delegation=False,
            verbose=self.verbose,
            max_iter=2
        )

        if self.docs_included:
            # 6.5) document summarizer
            self.document_summarizer_agent = Agent(
                role="Document Summarization Agent",
                goal="Analyze and summarize any provided documents related to {ticker}, extracting key financial insights.",
                backstory="Expert at distilling complex financial documents into actionable insights. Focuses on material information that could impact investment decisions.",
                llm=self.aggregator_llm,
                allow_delegation=False,
                verbose=self.verbose,
                max_iter=1,
            )

        # 7) aggregator
        self.aggregator_agent = Agent(
            role="Aggregator Agent",
            goal=(
                "Combine competitor, fundamental, technical, risk, and news into final JSON. Summaries must be at least 700 words referencing all tasks."
            ),
            backstory="One-pass aggregator. Minimizes tokens by being succinct. Output must match FinancialAnalysisResult pydantic exactly.",
            llm=self.aggregator_llm,
            allow_delegation=False,
            verbose=self.verbose,
        )

        # Redis logs

        self.enhanced_competitor_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Enhanced Competitor Finder Agent",
            workflow_name="Financial Analysis",
            llm_name=self.enhanced_competitor_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id
        )
        self.competitor_analysis_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Competitor Analysis Agent",
            workflow_name="Financial Analysis",
            llm_name=self.competitor_analysis_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id
        )
        self.fundamental_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Fundamental Analysis Agent",
            workflow_name="Financial Analysis",
            llm_name=self.fundamental_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id
        )
        self.technical_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Technical Analysis Agent",
            workflow_name="Financial Analysis",
            llm_name=self.technical_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id
        )
        self.risk_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Risk Assessment Agent",
            workflow_name="Financial Analysis",
            llm_name=self.risk_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id
        )
        self.news_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Financial News Agent",
            workflow_name="Financial Analysis",
            llm_name=self.news_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id
        )
        if self.docs_included:
            self.document_summarizer_agent.step_callback = RedisConversationLogger(
                user_id=self.user_id,
                run_id=self.run_id,
                agent_name="Document Summarizer Agent",
                workflow_name="Financial Analysis",
                llm_name=self.document_summarizer_agent.llm.model,
                redis_client=self.redis_client,
                message_id=self.message_id
            )
        self.aggregator_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Aggregator Agent",
            workflow_name="Financial Analysis",
            llm_name=self.aggregator_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id
            )

    def _init_tasks(self):
        # 1) competitor tasks => sequential
        self.enhanced_competitor_task = Task(
            description="Find competitor tickers for {ticker} with EnhancedCompetitorTool. Return competitor_tickers plus competitor_details=[].",
            agent=self.enhanced_competitor_agent,
            expected_output="competitor_tickers[] + competitor_details[] (empty).",
            max_iterations=1
        )
        self.competitor_analysis_task = Task(
            description="Analyze competitor fundamentals for those tickers with competitor_analysis_tool. Return competitor_details array.",
            agent=self.competitor_analysis_agent,
            context=[self.enhanced_competitor_task],
            expected_output="competitor_tickers plus competitor_details array with fundamentals.",
            max_iterations=1
        )

        # 2) fundamentals + technical + risk + news => parallel
        self.fundamental_task = Task(
            description="Get fundamental data from fundamental_analysis_tool for {ticker}. Return FundamentalData quickly.",
            agent=self.fundamental_agent,
            expected_output="FundamentalData object including advanced_fundamentals, etc.",
            async_execution=True,
            max_iterations=1
        )
        self.technical_task = Task(
            description="Use yf_tech_analysis with period='3mo' to get stock_price_data. Return TechnicalData.",
            agent=self.technical_agent,
            expected_output="TechnicalData with stock_price_data.",
            async_execution=True,
            max_iterations=1
        )
        self.risk_task = Task(
            description="Compute risk metrics from risk_assessment_tool for {ticker}, period='1y'. Return RiskData.",
            agent=self.risk_agent,
            expected_output="Beta, Sharpe, VaR, Max Drawdown, Volatility, daily_returns array",
            async_execution=True,
            max_iterations=1
        )
        self.news_task = Task(
            description="Get ~10 recent news items for {ticker} via SerperDevTool. Return them quickly.",
            agent=self.news_agent,
            expected_output="List of news items with title, content, link, published_time, named_entities.",
            async_execution=True,
            max_iterations=1
        )

        if self.docs_included:
            self.document_summarizer_task = Task(
                description="Summarize any provided documents related to {ticker}, extracting key financial insights. \n\nDocuments: \n\n{docs}",
                agent=self.document_summarizer_agent,
                expected_output="Summary of the document.",
                async_execution=True,
                max_iterations=1,
            )

        # 3) aggregator => sequential
        self.aggregator_task = Task(
            description=(
                "Aggregate all previous steps => final JSON with fields: ticker, company_name, competitor, fundamental, risk, stock_price_data, comprehensive_summary. Comprehensive Summary should be ~700 words referencing everything. For the news section, you must include the title, the link and the summary of the news. Must match FinancialAnalysisResult exactly. You MUST focus on recent news and events that may affect the stock price or metrics of {ticker} not just financial data. Name entities that are mentioned in the news."
            ),
            agent=self.aggregator_agent,
            context=[
                self.competitor_analysis_task, 
                self.fundamental_task, 
                self.technical_task, 
                self.risk_task, 
                self.news_task,
            ] + ([self.document_summarizer_task] if self.docs_included else []),
            expected_output="Valid JSON with ticker, company_name, competitor, fundamental, risk, stock_price_data, news, comprehensive_summary",
            max_iterations=1,
            output_pydantic=FinancialAnalysisResult,
            converter_cls=CustomConverter
        )

    def execute_financial_analysis(self, inputs: Dict[str,Any]) -> Tuple[str, Dict[str,Any]]:
        """
        1) Competitor tasks => sequential
        2) Fundamentals + Technical + Risk + News => parallel
        3) Aggregator => merges
        Return final JSON as string (pydantic).
        """
        # Parallel after competitor tasks => speeds up
        crew = Crew(
            agents=[
                self.enhanced_competitor_agent,
                self.competitor_analysis_agent,
                self.fundamental_agent,
                self.technical_agent,
                self.risk_agent,
                self.news_agent,
            ]
            + ([self.document_summarizer_agent] if self.docs_included else [])
            + [self.aggregator_agent],
            tasks=[
                self.enhanced_competitor_task,
                self.competitor_analysis_task,
                # concurrency on these four
                self.fundamental_task,
                self.technical_task,
                self.risk_task,
                self.news_task,
            ]
            + ([self.document_summarizer_task] if self.docs_included else [])
            +
            # aggregator last
            [self.aggregator_task],
            process=Process.sequential,  # now we use parallel for tasks, aggregator last
            verbose=self.verbose,
        )
        final = crew.kickoff(inputs=inputs)
        return final.pydantic.model_dump_json(), dict(final.token_usage)

########## EXAMPLE MAIN ##############
def main():
    load_dotenv()
    sambanova_key = os.getenv("SAMBANOVA_API_KEY")
    exa_key = os.getenv("EXA_API_KEY") 
    serper_key = os.getenv("SERPAPI_API_KEY")
    langtrace_key = os.getenv("LANGTRACE_API_KEY")
    user_id = "demo_user"
    run_id = str(uuid.uuid4())

    inputs = {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "docs": "NVIDIA Corporation is a company that makes GPUs. It is a good company."
    }

    fac = FinancialAnalysisCrew(
        sambanova_key=sambanova_key,
        exa_key=exa_key,
        serper_key=serper_key,
        user_id=user_id,
        run_id=run_id,
        docs_included=True
    )
    result_json = fac.execute_financial_analysis(inputs)
    print("FINAL FINANCIAL ANALYSIS JSON:\n")
    print(result_json)

if __name__=="__main__":
    main()
