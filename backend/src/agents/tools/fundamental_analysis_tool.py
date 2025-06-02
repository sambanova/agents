from datetime import datetime
import yfinance as yf
from typing import Dict, Any, List
from crewai.tools import tool

from tools.financial_data import get_fundamental_data, get_fundamental_data_insightsentry, get_ticker_balance_sheet_yfinance, get_ticker_cashflow_yfinance, get_ticker_dividends_yfinance, get_ticker_financials_yfinance, get_ticker_info_yfinance, get_ticker_quarterly_financials_yfinance, get_ticker_yfinance
from utils.logging import logger
###################### FUNDAMENTAL ANALYSIS TOOL ######################

def _generate_quarterly_data_with_labels(total_revenue_values: List[Any], net_income_values: List[Any]) -> List[Dict[str, Any]]:
    """
    Generates a list of quarterly financial data with date labels starting
    from the previous quarter and going backwards.
    """
    quarterly_csv = []
    num_quarters_to_generate = len(total_revenue_values)

    if num_quarters_to_generate > 0:
        now = datetime.now()
        current_label_year = now.year
        
        if now.month <= 3:
            pq_label_num = 4
            current_label_year -= 1
        elif now.month <= 6:
            pq_label_num = 1
        elif now.month <= 9:
            pq_label_num = 2
        else:
            pq_label_num = 3
        
        for i in range(num_quarters_to_generate):
            quarter_label = f"Q{pq_label_num} {current_label_year}"
            
            current_total_rev = total_revenue_values[i] if i < len(total_revenue_values) else None
            current_net_inc = net_income_values[i] if i < len(net_income_values) else None

            quarterly_csv.append({
                "date": quarter_label,
                "total_revenue": str(current_total_rev) if current_total_rev is not None else None,
                "net_income": str(current_net_inc) if current_net_inc is not None else None
            })

            pq_label_num -= 1
            if pq_label_num == 0:
                pq_label_num = 4
                current_label_year -= 1
                
    quarterly_csv.reverse()
    return quarterly_csv

@tool('Fundamental Analysis Tool')
def fundamental_analysis_tool(ticker: str) -> Dict[str, Any]:
    """
    Retrieve fundamentals from yfinance: 
    - standard fields
    - advanced_fundamentals
    - dividend_history
    - quarterly_fundamentals
    """

    try:
        ticker_yfinance = get_ticker_yfinance(ticker)
        info = get_ticker_info_yfinance(ticker_yfinance)

        result = {
            "ticker": ticker,
            "company_name": info.get("longName",""),
            "sector": info.get("sector",""),
            "industry": info.get("industry",""),
            "market_cap": str(info.get("marketCap","")),
            "pe_ratio": str(info.get("trailingPE","")),
            "forward_pe": str(info.get("forwardPE","")),
            "peg_ratio": str(info.get("pegRatio","")),
            "ps_ratio": str(info.get("priceToSalesTrailing12Months","")),
            "price_to_book": str(info.get("priceToBook","")),
            "dividend_yield": str(info.get("dividendYield","")),
            "beta": str(info.get("beta","")),
            "year_high": str(info.get("fiftyTwoWeekHigh","")),
            "year_low": str(info.get("fiftyTwoWeekLow","")),
            "analyst_recommendation": info.get("recommendationKey",""),
            "target_price": str(info.get("targetMeanPrice","")),
            "earnings_per_share": str(info.get("trailingEps","")),
            "profit_margins": str(info.get("profitMargins","")),
            "operating_margins": str(info.get("operatingMargins","")),
            "ebitda_margins": str(info.get("ebitdaMargins","")),
            "short_ratio": str(info.get("shortRatio","")),
        }
    except Exception as e:
        logger.error(f"Error fetching fundamental analysis data for {ticker}: {e}")
        results = {}

    # Attempt advanced statement analysis
    fin = get_ticker_financials_yfinance(ticker_yfinance)
    bs = get_ticker_balance_sheet_yfinance(ticker_yfinance)
    cf = get_ticker_cashflow_yfinance(ticker_yfinance)

    current_ratio = None
    debt_to_equity = None
    roe = None
    roa = None
    revenue_growth = None
    net_income_growth = None
    free_cash_flow = None

    try:
        if bs is not None and not bs.empty:
            if "Total Current Assets" in bs.index and "Total Current Liabilities" in bs.index:
                ca = bs.loc["Total Current Assets"].iloc[0]
                cl = bs.loc["Total Current Liabilities"].iloc[0]
                if cl != 0:
                    current_ratio = float(ca)/float(cl)
            if "Total Liabilities" in bs.index and "Total Stockholder Equity" in bs.index:
                tl = bs.loc["Total Liabilities"].iloc[0]
                te = bs.loc["Total Stockholder Equity"].iloc[0]
                if te != 0:
                    debt_to_equity = float(tl)/float(te)

        if fin is not None and not fin.empty:
            if "Net Income" in fin.index and "Total Revenue" in fin.index:
                ni = fin.loc["Net Income"]
                tr = fin.loc["Total Revenue"]
                if len(ni) >= 2:
                    prev = ni.iloc[1]
                    curr = ni.iloc[0]
                    if abs(prev) > 0:
                        net_income_growth = (curr - prev)/abs(prev)
                if len(tr) >= 2:
                    prev = tr.iloc[1]
                    curr = tr.iloc[0]
                    if abs(prev) > 0:
                        revenue_growth = (curr - prev)/abs(prev)

            if "Net Income" in fin.index and "Total Stockholder Equity" in bs.index:
                neti_latest = fin.loc["Net Income"].iloc[0]
                eq_latest = bs.loc["Total Stockholder Equity"].iloc[0]
                if eq_latest != 0:
                    roe = float(neti_latest)/float(eq_latest)
            if "Net Income" in fin.index and "Total Assets" in bs.index:
                neti_latest = fin.loc["Net Income"].iloc[0]
                assets_latest = bs.loc["Total Assets"].iloc[0]
                if assets_latest != 0:
                    roa = float(neti_latest)/float(assets_latest)

        if cf is not None and not cf.empty:
            if "Operating Cash Flow" in cf.index and "Capital Expenditures" in cf.index:
                ocf = cf.loc["Operating Cash Flow"].iloc[0]
                capex = cf.loc["Capital Expenditures"].iloc[0]
                free_cash_flow = float(ocf) - float(capex)
    except Exception as e:
        logger.error(f"Error fetching advanced statement analysis data for {ticker}: {e}")

    result["current_ratio"] = str(current_ratio if current_ratio else "")
    result["debt_to_equity"] = str(debt_to_equity if debt_to_equity else "")
    result["return_on_equity"] = str(roe if roe else "")
    result["return_on_assets"] = str(roa if roa else "")
    result["revenue_growth"] = str(revenue_growth if revenue_growth else "")
    result["net_income_growth"] = str(net_income_growth if net_income_growth else "")
    result["free_cash_flow"] = str(free_cash_flow if free_cash_flow else "")

    quarterly_csv = []
    try:
        qfin = get_ticker_quarterly_financials_yfinance(ticker_yfinance)
        if qfin is not None and not qfin.empty:
            for date_col in qfin.columns:
                col_str = str(date_col.date()) if hasattr(date_col, "date") else str(date_col)
                total_rev = None
                net_inc = None
                if "Total Revenue" in qfin.index:
                    total_rev = qfin.loc["Total Revenue", date_col]
                if "Net Income" in qfin.index:
                    net_inc = qfin.loc["Net Income", date_col]
                quarterly_csv.append({
                    "date": col_str,
                    "total_revenue": str(total_rev) if total_rev else None,
                    "net_income": str(net_inc) if net_inc else None
                })
            # Sort the quarterly data by date (oldest to newest)
            quarterly_csv.sort(key=lambda x: x["date"])
    except Exception as e:
        logger.error(f"Error fetching quarterly fundamentals data for {ticker}: {e}")

    result["quarterly_fundamentals"] = quarterly_csv

    adv_data = {}
    adv_data["shares_outstanding"] = str(info.get("sharesOutstanding",""))
    adv_data["float_shares"] = str(info.get("floatShares",""))
    adv_data["enterprise_value"] = str(info.get("enterpriseValue",""))
    adv_data["book_value"] = str(info.get("bookValue",""))

    div_hist = []
    try:
        dividends = get_ticker_dividends_yfinance(ticker_yfinance)
        # Check if dividends Series is valid and non-empty before processing
        if dividends is not None and not dividends.empty:
            div_hist = [
                {"date": str(dt.date()), "dividend": float(val)}
                for dt, val in dividends.items()
            ]
    except Exception as e:
        logger.error(f"Error fetching dividend history data for {ticker}: {e}")

    return {
        "ticker": ticker,
        **result,
        "advanced_fundamentals": adv_data,
        "dividend_history": div_hist
    }

def fundamental_analysis_tool_rapidapi(ticker: str) -> Dict[str, Any]:
    """
    Retrieve fundamentals from yfinance: 
    - standard fields
    - advanced_fundamentals
    - dividend_history
    - quarterly_fundamentals
    """

    info = get_fundamental_data(ticker, include_income_statement=True)

    result = {
        "ticker": ticker,
        "company_name": info.get("longName",""),
        "sector": info.get("sector",""),
        "industry": info.get("industry",""),
        "market_cap": str(info.get("priceToBook",0.0) * info.get("bookValue",0.0) * info.get("sharesOutstanding", 0.0)),
        "pe_ratio": str(info.get("forwardPE","")),
        "forward_pe": str(info.get("forwardPE","")),
        "peg_ratio": str(info.get("pegRatio","")),
        "ps_ratio": str(info.get("priceToSalesTrailing12Months","")),
        "price_to_book": str(info.get("priceToBook","")),
        "dividend_yield": str(info.get("dividendYield","")),
        "beta": str(info.get("beta","")),
        "year_high": str(info.get("fiftyTwoWeekHigh","")),
        "year_low": str(info.get("fiftyTwoWeekLow","")),
        "analyst_recommendation": info.get("recommendationKey",""),
        "target_price": str(info.get("targetMeanPrice","")),
        "earnings_per_share": str(info.get("trailingEps","")),
        "profit_margins": str(info.get("profitMargins","")),
        "operating_margins": str(info.get("operatingMargins","")),
        "ebitda_margins": str(info.get("ebitdaMargins","")),
        "short_ratio": str(info.get("shortRatio","")),
        "current_ratio": str(info.get("currentRatio","")),
        "debt_to_equity": str(info.get("debtToEquity","")),
        "return_on_equity": str(info.get("returnOnEquity","")),
        "return_on_assets": str(info.get("returnOnAssets","")),
        "revenue_growth": str(info.get("revenueGrowth","")),
        "free_cash_flow": str(info.get("freeCashflow","")),     
    }

    quarterly_csv = []
    if "incomeStatementHistoryQuarterly" in info and "incomeStatementHistory" in info["incomeStatementHistoryQuarterly"]:
        for quarter in info["incomeStatementHistoryQuarterly"]["incomeStatementHistory"]:
            quarterly_csv.append({
                "date": quarter["endDate"]["fmt"],
                "total_revenue": quarter["totalRevenue"]["raw"],
                "net_income": quarter["netIncome"]["raw"]
            })

    result["quarterly_fundamentals"] = quarterly_csv

    adv_data = {}
    adv_data["shares_outstanding"] = str(info.get("sharesOutstanding", ""))
    adv_data["float_shares"] = str(info.get("floatShares", ""))
    adv_data["enterprise_value"] = str(info.get("enterpriseValue", ""))
    adv_data["book_value"] = str(info.get("bookValue", ""))

    div_hist = []
    # TODO: add dividend history (not available in current data)

    return {
        "ticker": ticker,
        **result,
        "advanced_fundamentals": adv_data,
        "dividend_history": div_hist
    }


def fundamental_analysis_tool_insightsentry(ticker: str) -> Dict[str, Any]:
    """
    Retrieve fundamentals from InsightsEntry: 
    - standard fields
    - advanced_fundamentals
    - dividend_history
    - quarterly_fundamentals
    """

    info = get_fundamental_data_insightsentry(ticker, extended=True)
    ebitda_margin = info.get("data", {}).get("profitability", {}).get("ebitda_margin_current", "")
    if ebitda_margin != "":
        ebitda_margin = str(ebitda_margin / 100)
    result = {
        "ticker": ticker,
        "company_name": info.get("description",""),
        "sector": info.get("data", {}).get("company_info", {}).get("sector", ""),
        "industry": info.get("data", {}).get("company_info", {}).get("industry", ""),
        "market_cap": str(info.get("market_cap", "")),
        "pe_ratio": str(info.get("data", {}).get("valuation_ratios", {}).get("price_earnings", "")),
        "forward_pe": str(info.get("data", {}).get("valuation_ratios", {}).get("price_earnings_fy", "")),
        "peg_ratio": "",
        "ps_ratio": str(info.get("data", {}).get("valuation_ratios", {}).get("price_sales_current", "")),
        "price_to_book": str(info.get("data", {}).get("valuation_ratios", {}).get("price_book_current", "")),
        "dividend_yield": str(info.get("data", {}).get("dividends", {}).get("dividends_yield_current", "")),
        "beta": "",
        "year_high": "",
        "year_low": "",
        "analyst_recommendation": "",
        "target_price": str(info.get("data", {}).get("price_targets", {}).get("price_target_average", "")),
        "earnings_per_share": str(info.get("earnings_per_share_basic_ttm","")),
        "profit_margins": str(info.get("data", {}).get("profitability", {}).get("net_margin", "")),
        "operating_margins": str(info.get("data", {}).get("profitability", {}).get("operating_margin", "")),
        "ebitda_margins": ebitda_margin,
        "short_ratio": "",
        "current_ratio": str(info.get("data", {}).get("balance_sheet", {}).get("current_ratio", "")),
        "debt_to_equity": str(info.get("data", {}).get("balance_sheet", {}).get("debt_to_equity_fy", "")),
        "return_on_equity": str(info.get("data", {}).get("profitability", {}).get("return_on_equity", "")),
        "return_on_assets": str(info.get("data", {}).get("profitability", {}).get("return_on_assets", "")),
        "revenue_growth": "",
        "free_cash_flow": str(info.get("data", {}).get("cash_flow", {}).get("free_cash_flow_ttm", "")),
    }


    total_revenue_values = info.get("data", {}).get("income_statement", {}).get("total_revenue_fq_h", [])
    net_income_values = info.get("data", {}).get("income_statement", {}).get("net_income_fq_h", [])
    
    quarterly_csv = _generate_quarterly_data_with_labels(total_revenue_values, net_income_values)
                
    result["quarterly_fundamentals"] = quarterly_csv

    adv_data = {}
    adv_data["shares_outstanding"] = str(info.get("data", {}).get("income_statement", {}).get("basic_shares_outstanding_fy", ""))
    adv_data["float_shares"] = ""
    adv_data["enterprise_value"] = ""
    adv_data["book_value"] = str(info.get("data", {}).get("valuation_ratios", {}).get("book_per_share_fy", ""))

    div_hist = []
    dividend_ex_date_h = info.get("data", {}).get("dividends", {}).get("dividend_ex_date_h", [])
    dividend_amount_h = info.get("data", {}).get("dividends", {}).get("dividend_amount_h", [])
    for dt, val in zip(dividend_ex_date_h, dividend_amount_h):
        dt = datetime.fromtimestamp(dt)
        div_hist.append({"date": str(dt.date()), "dividend": float(val)})

    return {
        "ticker": ticker,
        **result,
        "advanced_fundamentals": adv_data,
        "dividend_history": div_hist
    }
