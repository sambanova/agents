import yfinance as yf
import pandas as pd
import numpy as np
# import matplotlib.pyplot as plt  # For potential plotting if desired
from datetime import datetime, timedelta
from crewai.tools import tool
from typing import Dict, Any

from tools.financial_data import get_historical_ohlcv_data_insightsentry, get_price_data, get_price_data_yfinance, get_ticker_yfinance
from utils.logging import logger


###################### TECHNICAL ANALYSIS TOOL (3mo weekly) #####
@tool('Technical Analysis Tool')
def yf_tech_analysis(ticker: str) -> Dict[str, Any]:
    """
    Get 3-month weekly intervals from yfinance for the ticker, returning standard fields plus stock_price_data.
    """

    try:
        period: str = "3mo"
        interval: str = "1wk"

        ticker_yfinance = get_ticker_yfinance(ticker)
        hist = get_price_data_yfinance(ticker_yfinance, period=period, interval=interval)
        stock_price_data = []
        for dt, row in hist.iterrows():
            date_str = dt.strftime("%Y-%m-%d")
            stock_price_data.append({
                "date": date_str,
                "open": str(row["Open"]),
                "high": str(row["High"]),
                "low": str(row["Low"]),
                "close": str(row["Close"]),
                "volume": str(row["Volume"])
            })
        return {
            "moving_averages": {"ma50": None,"ma200": None},
            "rsi": None,
            "macd": {"macd_line": None,"signal_line": None},
            "bollinger_bands": {"upper": None,"middle": None,"lower": None},
            "volatility": None,
            "momentum": None,
            "support_levels": [],
            "resistance_levels": [],
            "detected_patterns": [],
            "chart_data": [],
            "stock_price_data": stock_price_data
        }
    except Exception as e:
        logger.error(f"Error fetching technical analysis data for {ticker}: {e}")
        return {}


def yf_tech_analysis_rapidapi(ticker: str, period: str = "3mo") -> Dict[str, Any]:
    """
    Get price data from yfinance for the ticker, returning standard fields plus stock_price_data.
    """

    interval = "1wk"
    hist = get_price_data(symbol=ticker, interval=interval, period=period)

    stock_price_data = []
    for dt, row in hist.iterrows():
        date_str = dt.strftime("%Y-%m-%d")
        stock_price_data.append({
            "date": date_str,
            "open": str(row["Open"]),
            "high": str(row["High"]),
            "low": str(row["Low"]),
            "close": str(row["Close"]),
            "volume": str(row["Volume"])
        })
    return {
        "moving_averages": {"ma50": None,"ma200": None},
        "rsi": None,
        "macd": {"macd_line": None,"signal_line": None},
        "bollinger_bands": {"upper": None,"middle": None,"lower": None},
        "volatility": None,
        "momentum": None,
        "support_levels": [],
        "resistance_levels": [],
        "detected_patterns": [],
        "chart_data": [],
        "stock_price_data": stock_price_data
    }


def tech_analysis_insightsentry(ticker: str) -> Dict[str, Any]:
    """
    Get price data from InsightsEntry for the ticker, returning standard fields plus stock_price_data. Use the format 'EXCHANGE:TICKER'.
    """

    hist = get_historical_ohlcv_data_insightsentry(ticker, period="3mo")

    stock_price_data = []
    for dt, row in hist.iterrows():
        date_str = dt.strftime("%Y-%m-%d")
        stock_price_data.append({
            "date": date_str,
            "open": str(row["Open"]),
            "high": str(row["High"]),
            "low": str(row["Low"]),
            "close": str(row["Close"]),
            "volume": str(row["Volume"])
        })
    return {
        "moving_averages": {"ma50": None,"ma200": None},
        "rsi": None,
        "macd": {"macd_line": None,"signal_line": None},
        "bollinger_bands": {"upper": None,"middle": None,"lower": None},
        "volatility": None,
        "momentum": None,
        "support_levels": [],
        "resistance_levels": [],
        "detected_patterns": [],
        "chart_data": [],
        "stock_price_data": stock_price_data
    }
