import yfinance as yf
import numpy as np
from typing import Dict, Any
from crewai.tools import tool

from tools.financial_data import get_price_data


###################### RISK ASSESSMENT TOOL ######################
@tool('Risk Assessment Tool')
def risk_assessment_tool_yfinance(ticker: str, benchmark: str = "^GSPC", period: str = "1y") -> Dict[str, Any]:
    """
    Compute Beta, Sharpe, VaR, Max Drawdown, Volatility, plus monthly-averaged daily_returns for plotting.
    """
    stock = yf.Ticker(ticker)
    bench = yf.Ticker(benchmark)

    stock_close = stock.history(period=period)['Close']
    bench_close = bench.history(period=period)['Close']

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

@tool('Risk Assessment Tool')
def risk_assessment_tool(ticker: str, benchmark: str = "^GSPC", period: str = "1y") -> Dict[str, Any]:
    """
    Compute Beta, Sharpe, VaR, Max Drawdown, Volatility, plus monthly-averaged daily_returns for plotting.
    """

    stock_close = get_price_data(ticker, period=period)["Close"]
    bench_close = get_price_data(benchmark, period=period)["Close"]

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
