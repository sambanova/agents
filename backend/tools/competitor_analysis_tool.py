import yfinance as yf
from typing import Dict, Any, List
from crewai.tools import tool

from tools.financial_data import get_fundamental_data, get_fundamental_data_insightsentry, get_ticker_info_yfinance


###################### COMPETITOR TOOL WITH PROMPT ENGINEERING ######################
@tool('EnhancedCompetitorTool')
def enhanced_competitor_tool(company_name: str, ticker: str) -> Dict[str, Any]:
    """
    Attempt to find 3 best competitor tickers from yfinance, fallback LLM guess if not found.
    Return: competitor_tickers[], competitor_details[] = []
    """
    fallback_competitors = []
    y = yf.Ticker(ticker)
    inf = y.info
    sector = inf.get("sector","")

    if sector and "Tech" in sector:
        fallback_competitors = ["AMD","INTC","MSFT"]
    elif sector and "Energy" in sector:
        fallback_competitors = ["XOM","CVX","BP"]
    else:
        fallback_competitors = ["GOOGL","AMZN","META"]

    return {
      "competitor_tickers": fallback_competitors[:3],
      "competitor_details": []
    }

###################### COMPETITOR ANALYSIS TOOL ######################
def competitor_analysis_tool(tickers: List[str]) -> Dict[str, Any]:
    """
    For each competitor ticker in 'tickers', fetch fundamental info from yfinance.
    Return competitor_tickers plus competitor_details[] with fields:
    {ticker, name, market_cap, pe_ratio, ps_ratio, ebitda_margins, profit_margins, revenue_growth, earnings_growth, short_ratio, industry, sector}.
    """
    details = []
    for t in tickers:
        info = get_ticker_info_yfinance(t)
        details.append({
            "ticker": t,
            "name": info.get("longName",""),
            "market_cap": str(info.get("marketCap","")),
            "pe_ratio": str(info.get("trailingPE","")),
            "ps_ratio": str(info.get("priceToSalesTrailing12Months","")),
            "ebitda_margins": str(info.get("ebitdaMargins","")),
            "profit_margins": str(info.get("profitMargins","")),
            "revenue_growth": str(info.get("revenueGrowth","")),
            "earnings_growth": str(info.get("earningsGrowth","")),
            "short_ratio": str(info.get("shortRatio","")),
            "industry": info.get("industry",""),
            "sector": info.get("sector","")
        })
    return {
      "competitor_tickers": tickers,
      "competitor_details": details
    }

def competitor_analysis_tool_rapidapi(tickers: List[str]) -> Dict[str, Any]:
    """
    For each competitor ticker in 'tickers', fetch fundamental info from yfinance.
    Return competitor_tickers plus competitor_details[] with fields:
    {ticker, name, market_cap, pe_ratio, ps_ratio, ebitda_margins, profit_margins, revenue_growth, earnings_growth, short_ratio, industry, sector}.
    """
    details = []
    for t in tickers:
        info = get_fundamental_data(t, include_income_statement=False)
        details.append({
            "ticker": t,
            "name": info.get("longName",""),
            "market_cap": str(info.get("priceToBook",0.0) * info.get("bookValue",0.0) * info.get("sharesOutstanding", 0.0)),
            "pe_ratio": str(info.get("forwardPE","")),
            "ps_ratio": str(info.get("priceToSalesTrailing12Months","")),
            "ebitda_margins": str(info.get("ebitdaMargins","")),
            "profit_margins": str(info.get("profitMargins","")),
            "revenue_growth": str(info.get("revenueGrowth","")),
            "earnings_growth": str(info.get("earningsGrowth","")),
            "short_ratio": str(info.get("shortRatio","")),
            "industry": info.get("industry",""),
            "sector": info.get("sector","")
        })
    return {
      "competitor_tickers": tickers,
      "competitor_details": details
    }

@tool('Competitor Analysis Tool')
def competitor_analysis_tool_insightsentry(tickers: List[str]) -> Dict[str, Any]:
    """
    For each competitor ticker in 'tickers', fetch fundamental info from InsightsEntry.
    Return competitor_tickers plus competitor_details[] with fields:
    {ticker, name, market_cap, pe_ratio, ps_ratio, ebitda_margins, profit_margins, revenue_growth, earnings_growth, short_ratio, industry, sector}.
    """
    details = []
    #TODO: remove this once we have a way to handle the large response from InsightsEntry
    for t in tickers:
        info = get_fundamental_data_insightsentry(t, extended=False)
        details.append({
            "ticker": t,
            "name": info.get("description",""),
            "market_cap": str(info.get("market_cap",0.0)),
            "pe_ratio": str(info.get("price_earnings_ttm","")),
            "ps_ratio": "",
            "ebitda_margins": "",
            "profit_margins": "",
            "revenue_growth": "",
            "earnings_growth": "",
            "short_ratio": "",
            "industry": "",
            "sector": ""
        })
    return {
      "competitor_tickers": tickers,
      "competitor_details": details
    }