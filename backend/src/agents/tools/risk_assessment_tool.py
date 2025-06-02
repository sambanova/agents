import yfinance as yf
import numpy as np
from typing import Dict, Any
from crewai.tools import tool

from tools.financial_data import get_historical_ohlcv_data_insightsentry, get_price_data, get_price_data_yfinance, get_ticker_yfinance
from utils.logging import logger

###################### RISK ASSESSMENT TOOL ######################
@tool('Risk Assessment Tool')
def risk_assessment_tool(ticker: str) -> Dict[str, Any]:
    """
    Compute Beta, Sharpe, VaR, Max Drawdown, Volatility, plus monthly-averaged daily_returns for plotting.
    """

    try:
        benchmark: str = "^GSPC"
        period: str = "1y"
        interval: str = "1d"

        ticker_yfinance = get_ticker_yfinance(ticker)
        benchmark_yfinance = get_ticker_yfinance(benchmark)
        stock_close = get_price_data_yfinance(ticker_yfinance, period=period, interval=interval)['Close']
        bench_close = get_price_data_yfinance(benchmark_yfinance, period=period, interval=interval)['Close']

        if stock_close.empty or bench_close.empty:
            return {"error": "Insufficient data for risk metrics."}

        stock_returns = stock_close.pct_change().dropna()
        bench_returns = bench_close.pct_change().dropna()

        # Align indexes
        common_idx = stock_returns.index.intersection(bench_returns.index)
        stock_returns = stock_returns.loc[common_idx]
        bench_returns = bench_returns.loc[common_idx]

        # Beta
        cov = np.cov(stock_returns, bench_returns)[0][1]
        var_bench = np.var(bench_returns)
        beta = float(cov / var_bench) if var_bench != 0 else 0.0

        # Sharpe
        risk_free_annual = 0.02
        risk_free_daily = risk_free_annual / 252
        excess = stock_returns - risk_free_daily
        if excess.std() == 0:
            sharpe = 0.0
        else:
            sharpe = float(np.sqrt(252) * excess.mean() / excess.std())

        # VaR
        var_95 = float(np.percentile(stock_returns, 5))

        # Max Drawdown
        cumul = (1 + stock_returns).cumprod()
        peak = cumul.cummax()
        dd = (cumul - peak) / peak
        max_dd = float(dd.min())

        # annual vol
        vol = float(stock_returns.std() * np.sqrt(252))

        # monthly average
        monthly_group = stock_returns.groupby([stock_returns.index.year, stock_returns.index.month]).mean()
        returns_csv = []
        for (year, month), ret in monthly_group.items():
            date_str = f"{year}-{month:02d}"
            returns_csv.append({
                "date": date_str,
                "daily_return": str(ret)
            })

        return {
            "beta": f"{beta:.4f}",
            "sharpe_ratio": f"{sharpe:.4f}",
            "value_at_risk_95": f"{var_95:.4f}",
            "max_drawdown": f"{max_dd:.4f}",
            "volatility": f"{vol:.4f}",
            "daily_returns": returns_csv
        }
    except Exception as e:
        logger.error(f"Error fetching risk assessment data for {ticker}: {e}")
        return {}

def risk_assessment_tool_rapidapi(ticker: str) -> Dict[str, Any]:
    """
    Compute Beta, Sharpe, VaR, Max Drawdown, Volatility, plus monthly-averaged daily_returns for plotting.
    """

    benchmark: str = "^GSPC"
    period: str = "1y"

    stock = get_price_data(ticker, period=period)
    bench = get_price_data(benchmark, period=period)
    
    if stock.empty or bench.empty:
        return {
            "beta": "",
            "sharpe_ratio": "",
            "value_at_risk_95": "",
            "max_drawdown": "",
            "volatility": "",
            "daily_returns": []
        }
    
    stock_close = stock["Close"]
    bench_close = bench["Close"]

    stock_returns = stock_close.pct_change().dropna()
    bench_returns = bench_close.pct_change().dropna()

    # Align indexes
    common_idx = stock_returns.index.intersection(bench_returns.index)
    stock_returns = stock_returns.loc[common_idx]
    bench_returns = bench_returns.loc[common_idx]

    # Beta
    cov = np.cov(stock_returns, bench_returns)[0][1]
    var_bench = np.var(bench_returns)
    beta = float(cov / var_bench) if var_bench != 0 else 0.0

    # Sharpe
    risk_free_annual = 0.02
    risk_free_daily = risk_free_annual / 252
    excess = stock_returns - risk_free_daily
    if excess.std() == 0:
        sharpe = 0.0
    else:
        sharpe = float(np.sqrt(252) * excess.mean() / excess.std())

    # VaR
    var_95 = float(np.percentile(stock_returns, 5))

    # Max Drawdown
    cumul = (1 + stock_returns).cumprod()
    peak = cumul.cummax()
    dd = (cumul - peak) / peak
    max_dd = float(dd.min())

    # annual vol
    vol = float(stock_returns.std() * np.sqrt(252))

    # monthly average
    monthly_group = stock_returns.groupby([stock_returns.index.year, stock_returns.index.month]).mean()
    returns_csv = []
    for (year, month), ret in monthly_group.items():
        date_str = f"{year}-{month:02d}"
        returns_csv.append({
            "date": date_str,
            "daily_return": str(ret)
        })

    return {
        "beta": f"{beta:.4f}",
        "sharpe_ratio": f"{sharpe:.4f}",
        "value_at_risk_95": f"{var_95:.4f}",
        "max_drawdown": f"{max_dd:.4f}",
        "volatility": f"{vol:.4f}",
        "daily_returns": returns_csv
    }


def risk_assessment_tool_insightsentry(ticker: str) -> Dict[str, Any]:
    """
    Compute Beta, Sharpe, VaR, Max Drawdown, Volatility, plus monthly-averaged daily_returns for plotting.
    """

    benchmark: str = "SPCFD:SPX"
    period: str = "1y"

    stock = get_historical_ohlcv_data_insightsentry(ticker, period=period)
    bench = get_historical_ohlcv_data_insightsentry(benchmark, period=period)
    
    if stock.empty or bench.empty:
        return {
            "beta": "",
            "sharpe_ratio": "",
            "value_at_risk_95": "",
            "max_drawdown": "",
            "volatility": "",
            "daily_returns": [
                {
                    "date": "",
                    "daily_return": ""
                }
            ]
        }
    
    stock_close = stock["Close"]
    bench_close = bench["Close"]

    stock_returns = stock_close.pct_change().dropna()
    bench_returns = bench_close.pct_change().dropna()

    # Align indexes
    common_idx = stock_returns.index.intersection(bench_returns.index)
    stock_returns = stock_returns.loc[common_idx]
    bench_returns = bench_returns.loc[common_idx]

    # Beta
    cov = np.cov(stock_returns, bench_returns)[0][1]
    var_bench = np.var(bench_returns)
    beta = float(cov / var_bench) if var_bench != 0 else 0.0

    # Sharpe
    risk_free_annual = 0.02
    risk_free_daily = risk_free_annual / 252
    excess = stock_returns - risk_free_daily
    if excess.std() == 0:
        sharpe = 0.0
    else:
        sharpe = float(np.sqrt(252) * excess.mean() / excess.std())

    # VaR
    var_95 = float(np.percentile(stock_returns, 5))

    # Max Drawdown
    cumul = (1 + stock_returns).cumprod()
    peak = cumul.cummax()
    dd = (cumul - peak) / peak
    max_dd = float(dd.min())

    # annual vol
    vol = float(stock_returns.std() * np.sqrt(252))

    # monthly average
    monthly_group = stock_returns.groupby([stock_returns.index.year, stock_returns.index.month]).mean()
    returns_csv = []
    for (year, month), ret in monthly_group.items():
        date_str = f"{year}-{month:02d}"
        returns_csv.append({
            "date": date_str,
            "daily_return": str(ret)
        })

    return {
        "beta": f"{beta:.4f}",
        "sharpe_ratio": f"{sharpe:.4f}",
        "value_at_risk_95": f"{var_95:.4f}",
        "max_drawdown": f"{max_dd:.4f}",
        "volatility": f"{vol:.4f}",
        "daily_returns": returns_csv
    }