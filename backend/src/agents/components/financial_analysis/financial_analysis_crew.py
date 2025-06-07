import os
from typing import Dict, Any, List, Optional, Tuple, Union
from agents.storage.redis_service import SecureRedisService

from agents.components.crewai_llm import CustomLLM
from agents.services.structured_output_parser import CustomConverter

# crewai imports
from crewai import Agent, Task, Crew, Process
from agents.utils.agent_thought import RedisConversationLogger
from crewai_tools import SerperDevTool
from agents.tools.competitor_analysis_tool import competitor_analysis_tool
from agents.tools.fundamental_analysis_tool import fundamental_analysis_tool
from agents.tools.technical_analysis_tool import yf_tech_analysis
from agents.tools.risk_assessment_tool import risk_assessment_tool
from agents.registry.model_registry import model_registry


###################### NEWS MODELS & (SERPER) WRAPPER ######################
from pydantic import BaseModel, Field
from pydantic import field_validator


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
    dividend_history: List[Dict[str, Any]] = []


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

    @field_validator("daily_returns", mode="before")
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
        user_id: str = "",
        run_id: str = "",
        docs_included: bool = False,
        redis_client: SecureRedisService = None,
        message_id: str = None,
        verbose: bool = True,
    ):
        competitor_finder_model_info = model_registry.get_model_info(
            model_key="llama-3.1-8b", provider=provider
        )
        self.competitor_finder_llm = CustomLLM(
            model=competitor_finder_model_info["crewai_prefix"]
            + "/"
            + competitor_finder_model_info["model"],
            temperature=0.0,
            max_tokens=8192,
            api_key=llm_api_key,
            base_url=competitor_finder_model_info["url"],
        )
        model_info = model_registry.get_model_info(
            model_key="llama-3.1-8b", provider=provider
        )
        self.llm = CustomLLM(
            model=model_info["crewai_prefix"] + "/" + model_info["model"],
            temperature=0.0,
            max_tokens=8192,
            api_key=llm_api_key,
            base_url=model_info["url"],
        )
        aggregator_model_info = model_registry.get_model_info(
            model_key="llama-3.3-70b", provider=provider
        )
        self.aggregator_llm = CustomLLM(
            model=aggregator_model_info["crewai_prefix"]
            + "/"
            + aggregator_model_info["model"],
            temperature=0.0,
            max_tokens=8192,
            api_key=llm_api_key,
            base_url=aggregator_model_info["url"],
        )
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
            goal="Identify the top 3 competitor tickers for {ticker} within the same industry and sector.",
            backstory="Expert market analyst focused on direct competitor identification. Uses provided ticker information efficiently.",
            llm=self.competitor_finder_llm,
            allow_delegation=False,
            verbose=self.verbose,
            max_iter=1,
        )

        # 2) competitor analysis
        self.competitor_analysis_agent = Agent(
            role="Competitor Analysis Agent",
            goal="Fetch fundamental details (market cap, margins, growth, short ratio) for the given `competitor_tickers` using the 'Competitor Analysis Tool'.",
            backstory="Data retrieval specialist. Executes the 'Competitor Analysis Tool' once per ticker and returns structured data.",
            llm=self.llm,
            tools=[competitor_analysis_tool],
            allow_delegation=False,
            verbose=self.verbose,
            max_iter=1,
        )

        # 3) fundamental
        self.fundamental_agent = Agent(
            role="Fundamental Analysis Agent",
            goal="Retrieve comprehensive fundamental data (including `advanced_fundamentals` and `dividend_history`) for {ticker} using the 'Fundamental Analysis Tool'.",
            backstory="Financial data specialist. Executes the `fundamental_analysis_tool` once for {ticker} and returns the complete `FundamentalData` object.",
            llm=self.llm,
            tools=[fundamental_analysis_tool],
            allow_delegation=False,
            verbose=self.verbose,
        )

        # 4) technical
        self.technical_agent = Agent(
            role="Technical Analysis Agent",
            goal="Obtain 3-month weekly technical data (including price data for charting) for {ticker} using the 'Technical Analysis Tool'.",
            backstory="Technical data specialist. Executes `yf_tech_analysis` once with period='3mo' for {ticker}. Returns `TechnicalData`, ensuring `stock_price_data` is populated.",
            llm=self.llm,
            tools=[yf_tech_analysis],
            allow_delegation=False,
            verbose=self.verbose,
            max_iter=1,
        )

        # 5) risk
        self.risk_agent = Agent(
            role="Risk Assessment Agent",
            goal="Calculate key risk metrics (Beta, Sharpe, VaR, Max Drawdown, Volatility) for {ticker} using the 'Risk Assessment Tool'.",
            backstory="Risk analysis specialist. Executes `risk_assessment_tool` once for {ticker}. Returns `RiskData`, including monthly-averaged daily returns.",
            llm=self.llm,
            tools=[risk_assessment_tool],
            allow_delegation=False,
            verbose=self.verbose,
            max_iter=1,
        )

        # 6) news
        self.news_agent = Agent(
            role="Financial News Agent",
            goal="Fetch the top ~10 recent news articles relevant to {ticker}'s stock price using the 'SerperDevTool'.",
            backstory="News retrieval specialist. Executes `SerperDevTool` once for {ticker}. Returns a concise list of news items (title, link, summary, time, entities).",
            llm=self.aggregator_llm,
            tools=[SerperDevTool()],
            allow_delegation=False,
            verbose=self.verbose,
            max_iter=2,
        )

        if self.docs_included:
            # 6.5) document summarizer
            self.document_summarizer_agent = Agent(
                role="Document Summarization Agent",
                goal="Summarize the provided financial documents related to {ticker}, extracting key insights impacting investment decisions.",
                backstory="Financial document analysis expert. Distills complex information into a concise, actionable summary focusing on material impact.",
                llm=self.aggregator_llm,
                allow_delegation=False,
                verbose=self.verbose,
                max_iter=1,
            )

        # 7) aggregator
        self.aggregator_agent = Agent(
            role="Aggregator Agent",
            goal=(
                "Compile all analysis results (competitor, fundamental, technical, risk, news, optional docs) into the `FinancialAnalysisResult` JSON format. Generate a comprehensive summary (~700 words)."
            ),
            backstory="Master report compiler. Synthesizes inputs into the precise `FinancialAnalysisResult` Pydantic structure. Writes a detailed, integrated summary referencing all data points, including recent news impact and named entities.",
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
            message_id=self.message_id,
        )
        self.competitor_analysis_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Competitor Analysis Agent",
            workflow_name="Financial Analysis",
            llm_name=self.competitor_analysis_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id,
        )
        self.fundamental_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Fundamental Analysis Agent",
            workflow_name="Financial Analysis",
            llm_name=self.fundamental_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id,
        )
        self.technical_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Technical Analysis Agent",
            workflow_name="Financial Analysis",
            llm_name=self.technical_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id,
        )
        self.risk_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Risk Assessment Agent",
            workflow_name="Financial Analysis",
            llm_name=self.risk_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id,
        )
        self.news_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Financial News Agent",
            workflow_name="Financial Analysis",
            llm_name=self.news_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id,
        )
        if self.docs_included:
            self.document_summarizer_agent.step_callback = RedisConversationLogger(
                user_id=self.user_id,
                run_id=self.run_id,
                agent_name="Document Summarizer Agent",
                workflow_name="Financial Analysis",
                llm_name=self.document_summarizer_agent.llm.model,
                redis_client=self.redis_client,
                message_id=self.message_id,
            )
        self.aggregator_agent.step_callback = RedisConversationLogger(
            user_id=self.user_id,
            run_id=self.run_id,
            agent_name="Aggregator Agent",
            workflow_name="Financial Analysis",
            llm_name=self.aggregator_agent.llm.model,
            redis_client=self.redis_client,
            message_id=self.message_id,
        )

    def _init_tasks(self):
        # 1) competitor tasks => sequential
        self.enhanced_competitor_task = Task(
            description="Find 3 competitor tickers for {ticker}. Return competitor_tickers",
            agent=self.enhanced_competitor_agent,
            expected_output="competitor_tickers[]",
            max_iterations=1,
        )
        self.competitor_analysis_task = Task(
            description="Extract the list of `competitor_tickers` from the context provided by the enhanced competitor task. Using the `competitor_analysis_tool`, analyze the fundamentals for each ticker in this list. Ensure the `tickers` argument passed to the tool is a `List[str]`. Return the full output dictionary containing `competitor_tickers` and `competitor_details`.",
            agent=self.competitor_analysis_agent,
            context=[self.enhanced_competitor_task],
            expected_output="competitor_tickers plus competitor_details array with fundamentals.",
            max_iterations=1,
        )

        # 2) fundamentals + technical + risk + news => parallel
        self.fundamental_task = Task(
            description="Execute the `fundamental_analysis_tool` for {ticker}. Output the structured `FundamentalData` object.",
            agent=self.fundamental_agent,
            expected_output="FundamentalData object including advanced_fundamentals, etc.",
            async_execution=True,
            max_iterations=1,
        )
        self.technical_task = Task(
            description="Execute `tech_analysis_insightsentry` for {ticker}. Output the structured `TechnicalData` object, including `stock_price_data`.",
            agent=self.technical_agent,
            expected_output="TechnicalData with stock_price_data.",
            async_execution=True,
            max_iterations=1,
        )
        self.risk_task = Task(
            description="Execute `risk_assessment_tool` for {ticker}. Output the structured `RiskData` object, including `daily_returns`.",
            agent=self.risk_agent,
            expected_output="Beta, Sharpe, VaR, Max Drawdown, Volatility, daily_returns array",
            async_execution=True,
            max_iterations=1,
        )
        self.news_task = Task(
            description="Use `SerperDevTool` to find ~10 recent news items for {ticker}. Output a list of news items including title, link, published_time, and named_entities.",
            agent=self.news_agent,
            expected_output="List of news items with title, content, link, published_time, named_entities.",
            async_execution=True,
            max_iterations=1,
        )

        if self.docs_included:
            self.document_summarizer_task = Task(
                description="Analyze the provided {docs} for {ticker}. Output a concise summary of key financial insights.",
                agent=self.document_summarizer_agent,
                expected_output="Summary of the document.",
                async_execution=True,
                max_iterations=1,
            )

        # 3) aggregator => sequential
        self.aggregator_task = Task(
            description=(
                "Aggregate results from all previous tasks into the `FinancialAnalysisResult` format. Ensure `ticker`, `company_name`, `competitor`, `fundamental`, `risk`, `stock_price_data`, and `news` (with title, link, summary) are populated. Write a comprehensive summary (~700 words) integrating all findings, highlighting recent news/events and named entities affecting {ticker}. Output must strictly match the `FinancialAnalysisResult` Pydantic model."
            ),
            agent=self.aggregator_agent,
            context=[
                self.competitor_analysis_task,
                self.fundamental_task,
                self.technical_task,
                self.risk_task,
                self.news_task,
            ]
            + ([self.document_summarizer_task] if self.docs_included else []),
            expected_output="Valid JSON with ticker, company_name, competitor, fundamental, risk, stock_price_data, news, comprehensive_summary",
            max_iterations=1,
            output_pydantic=FinancialAnalysisResult,
            converter_cls=CustomConverter,
        )

    async def execute_financial_analysis(
        self, inputs: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
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
        final = await crew.kickoff_async(inputs=inputs)
        return final.pydantic, dict(final.token_usage)
