import os
import pandas as pd
import requests
import yfinance as yf
from typing import Dict, Any, List
from crewai.tools import tool
from cachetools import cached, TTLCache
import time
import concurrent.futures

rapidapi_key = os.getenv("RAPIDAPI_KEY")

# Create a cache that expires after 12 hours (12 * 60 * 60 seconds)
cache = TTLCache(maxsize=1024, ttl=12 * 60 * 60)

def get_date_range(period):
        # Convert period to date range
    today = pd.Timestamp.today()
    if period == "1d":
        start_date = today - pd.Timedelta(days=1)
    elif period == "5d":
        start_date = today - pd.Timedelta(days=5) 
    elif period == "1mo":
        start_date = today - pd.Timedelta(days=30)
    elif period == "3mo":
        start_date = today - pd.Timedelta(days=90)
    elif period == "6mo":
        start_date = today - pd.Timedelta(days=180)
    elif period == "1y":
        start_date = today - pd.Timedelta(days=365)
    else:
        raise ValueError(f"Invalid period: {period}")
    
    return start_date, today

@cached(cache)
def get_price_data(symbol, interval="1wk", period="3mo"):
    """
    Fetches daily close prices for `symbol` (US stocks only),
    returns a pandas Series indexed by date.
    """
    url = "https://yahoo-finance15.p.rapidapi.com/api/v1/markets/stock/history"

    querystring = {"symbol":symbol,"interval":interval,"diffandsplits":"false"}

    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "yahoo-finance15.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    hist = response.json().get("body", [])
    df = pd.DataFrame(hist.values())

    start_date, _ = get_date_range(period)
    start_date_str = start_date.strftime("%Y-%m-%d")
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df = df[start_date_str:].rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    return df.sort_index()

def _fetch_yahoo_module_data(symbol: str, module: str, rapidapi_key: str) -> Dict[str, Any]:
    """Helper function to fetch data for a specific module from Yahoo Finance API."""
    url = "https://yahoo-finance15.p.rapidapi.com/api/v1/markets/stock/modules"
    querystring = {"ticker": symbol, "module": module}
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "yahoo-finance15.p.rapidapi.com"
    }
    retries = 3
    backoff_factor = 1.0  # Start with a 1-second delay

    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=10)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            return response.json().get("body", {})
        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 429:
                if i < retries - 1:  # Don't wait on the last attempt
                    wait_time = backoff_factor * (2 ** i)
                    print(f"Rate limit hit for {module} ({symbol}). Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Rate limit hit for {module} ({symbol}). Max retries exceeded.")
                    return {}  # Return empty dict after max retries for 429
            else:
                # Re-raise other HTTP errors immediately
                print(f"HTTP error fetching {module} for {symbol}: {http_err}")
                return {}
        except requests.exceptions.RequestException as e:
            # Handle other request exceptions (timeout, connection error, etc.)
            print(f"Error fetching {module} for {symbol}: {e}")
            return {} # Return empty dict for other request errors

    # Should not be reached if retries exhausted, but as a fallback
    return {}

@cached(cache)
def get_fundamental_data(symbol: str, include_income_statement: bool = False) -> Dict[str, Any]:
    """
    Fetches fundamental data for a given stock symbol by calling the Yahoo Finance API
    for different modules in parallel.
    """
    modules_to_fetch = ["asset-profile", "statistics", "financial-data"]
    if include_income_statement:
        modules_to_fetch.append("income-statement")

    combined_data = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_module = {
            executor.submit(_fetch_yahoo_module_data, symbol, module, rapidapi_key): module
            for module in modules_to_fetch
        }
        for future in concurrent.futures.as_completed(future_to_module):
            module = future_to_module[future]
            try:
                module_data = future.result()
                combined_data.update(module_data)
            except Exception as exc:
                print(f'{module} generated an exception: {exc}')

    processed_data = {}
    for key, value in combined_data.items():
        if isinstance(value, dict) and 'raw' in value and 'fmt' in value:
            processed_data[key] = value['raw']
        else:
            if isinstance(value, dict) and 'raw' in value:
                processed_data[key] = value['raw']
            elif isinstance(value, dict) and 'fmt' in value:
                processed_data[key] = value['fmt']
            else:
                processed_data[key] = value

    return processed_data
