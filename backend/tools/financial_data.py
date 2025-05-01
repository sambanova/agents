import os
import pandas as pd
import httpx
import yfinance as yf
from typing import Dict, Any, List
from cachetools import cached, TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.logging import logger

rapidapi_key = os.getenv("RAPIDAPI_KEY")

# Create a cache that expires after 12 hours (12 * 60 * 60 seconds)
cache = TTLCache(maxsize=1024, ttl=12 * 60 * 60)

# Define a shared timeout configuration
# total cap 15s, connect 5s, read 10s
timeout_config = httpx.Timeout(15.0, connect=5.0, read=10.0)

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
        # Use logger for errors
        logger.error(f"Invalid period value provided: {period}")
        raise ValueError(f"Invalid period: {period}")
    
    return start_date, today


@cached(cache)
def get_ticker_yfinance(symbol):
    """
    Fetches a given stock symbol using yfinance.
    """
    logger.info(f"Fetching ticker for {symbol}")
    return yf.Ticker(symbol)

@cached(cache)
def get_ticker_info_yfinance(symbol):
    """
    Fetches ticker info for a given stock symbol using yfinance.
    """
    logger.info(f"Fetching ticker info for {symbol}")
    return get_ticker_yfinance(symbol).info

@cached(cache)
def get_ticker_financials_yfinance(symbol):
    """
    Fetches financials for a given stock symbol using yfinance.
    """
    logger.info(f"Fetching financials for {symbol}")
    return get_ticker_yfinance(symbol).financials

@cached(cache)
def get_ticker_balance_sheet_yfinance(symbol):
    """
    Fetches balance sheet for a given stock symbol using yfinance.
    """
    logger.info(f"Fetching balance sheet for {symbol}")
    return get_ticker_yfinance(symbol).balance_sheet

@cached(cache)
def get_ticker_cashflow_yfinance(symbol):
    """
    Fetches cash flow for a given stock symbol using yfinance.
    """
    logger.info(f"Fetching cash flow for {symbol}")
    return get_ticker_yfinance(symbol).cashflow

@cached(cache)
def get_ticker_quarterly_financials_yfinance(symbol):
    """
    Fetches quarterly financials for a given stock symbol using yfinance.
    """
    logger.info(f"Fetching quarterly financials for {symbol}")
    return get_ticker_yfinance(symbol).quarterly_financials

@cached(cache)
def get_ticker_dividends_yfinance(symbol):
    """
    Fetches dividends for a given stock symbol using yfinance.
    """
    logger.info(f"Fetching dividends for {symbol}")
    return get_ticker_yfinance(symbol).dividends

@cached(cache)
def get_price_data_yfinance(symbol, interval, period):
    """
    Fetches price data for a given stock symbol using yfinance.
    """
    logger.info(f"Fetching price data for {symbol} (interval={interval}, period={period})")
    return get_ticker_yfinance(symbol).history(interval=interval, period=period)

@cached(cache)
def get_price_data(symbol, interval="1wk", period="3mo"):
    """
    Fetches daily close prices for `symbol` (US stocks only),
    returns a pandas Series indexed by date.
    """
    logger.info(f"Fetching price data for {symbol} (interval={interval}, period={period})")
    url = "https://yahoo-finance15.p.rapidapi.com/api/v1/markets/stock/history"

    querystring = {"symbol":symbol,"interval":interval,"diffandsplits":"false"}

    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "yahoo-finance15.p.rapidapi.com"
    }

    try:
        # Use httpx.Client with the defined timeout
        with httpx.Client(timeout=timeout_config) as client:
            response = client.get(url, headers=headers, params=querystring)
            response.raise_for_status() # raise_for_status works similarly in httpx
            hist = response.json().get("body", [])
            if not hist:
                logger.warning(f"No price history data found for {symbol} in the response body.")
                return pd.DataFrame() # Return empty DataFrame if no data

        df = pd.DataFrame(hist.values())

        start_date, _ = get_date_range(period)
        start_date_str = start_date.strftime("%Y-%m-%d")
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df[start_date_str:].rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
        logger.info(f"Successfully fetched and processed price data for {symbol}")
        return df.sort_index()
    except httpx.RequestError as e:
        logger.error(f"Error fetching price data for {symbol}: {e}")
        return pd.DataFrame() # Return empty DataFrame on error
    except ValueError as e: # Catch potential errors from get_date_range
        logger.error(f"Error processing date range for {symbol}: {e}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Unexpected error processing price data for {symbol}: {e}")
        return pd.DataFrame()

# Define the logging function for tenacity retries
def log_retry_attempt(retry_state):
    """Log the retry attempt information."""
    logger.warning(
        f"Retrying request due to {retry_state.outcome.exception()} "
        f"(Attempt {retry_state.attempt_number}, waiting {retry_state.next_action.sleep:.2f}s)..."
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
    before_sleep=log_retry_attempt # Log before sleeping on retry
)
def _fetch_yahoo_module_data_with_retry(symbol: str, module: str, rapidapi_key: str) -> Dict[str, Any]:
    """Helper function to fetch data for a specific module from Yahoo Finance API with retries."""
    url = "https://yahoo-finance15.p.rapidapi.com/api/v1/markets/stock/modules"
    querystring = {"ticker": symbol, "module": module}
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "yahoo-finance15.p.rapidapi.com"
    }
    # Use httpx.Client with the defined timeout within the retried function
    with httpx.Client(timeout=timeout_config) as client:
        response = client.get(url, headers=headers, params=querystring)
        response.raise_for_status() # Raises HTTPStatusError for bad responses (4xx or 5xx) in httpx
        return response.json().get("body", {})

def _fetch_yahoo_module_data(symbol: str, module: str, rapidapi_key: str) -> Dict[str, Any]:
    """Wrapper function to handle exceptions from the retrying fetcher and log appropriately."""
    try:
        return _fetch_yahoo_module_data_with_retry(symbol, module, rapidapi_key)
    except RetryError as retry_err:
        # This catches the error after all retries have failed
        logger.error(f"Max retries exceeded for {module} ({symbol}). Last exception: {retry_err.last_attempt.exception()}")
        return {}
    except Exception as e:
         # Catch any other unexpected exceptions that weren't retried or occurred outside the retry loop
        logger.error(f"Unexpected error fetching {module} for {symbol}: {e}")
        return {}

@cached(cache)
def get_fundamental_data(symbol: str, include_income_statement: bool = False) -> Dict[str, Any]:
    """
    Fetches fundamental data for a given stock symbol by calling the Yahoo Finance API
    for different modules in parallel.
    """
    logger.info(f"Starting fundamental data fetch for {symbol} (include_income_statement={include_income_statement})")
    modules_to_fetch = ["asset-profile", "statistics", "financial-data"]
    if include_income_statement:
        modules_to_fetch.append("income-statement")

    combined_data = {}
    futures = {}
    # Use ThreadPoolExecutor to fetch modules in parallel
    with ThreadPoolExecutor() as executor:
        # Submit tasks for each module
        for module in modules_to_fetch:
            logger.info(f"Submitting task for module: {module} for {symbol}...")
            future = executor.submit(_fetch_yahoo_module_data, symbol, module, rapidapi_key)
            futures[future] = module # Store module name to identify results/errors

        # Process completed futures as they finish
        for future in as_completed(futures):
            module = futures[future]
            try:
                module_data = future.result() # Get result from the future
                if module_data: # Check if data was actually returned
                    combined_data.update(module_data)
                    logger.info(f"Successfully processed module: {module} for {symbol}.")
                else:
                    # Log if a module returned no data after processing (incl. retries)
                    logger.warning(f"No data received for module {module} ({symbol}) after processing.")
            except Exception as exc:
                # Log exceptions raised during the execution of the future
                logger.error(f'Error processing module {module} for {symbol}: {exc}')

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

    logger.info(f"Finished fundamental data fetch for {symbol}.")
    return processed_data
