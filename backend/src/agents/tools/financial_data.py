import os
import pandas as pd
import httpx
import requests_cache
import yfinance as yf
from typing import Dict, Any, List
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    RetryError,
    retry_if_exception,
)
from concurrent.futures import ThreadPoolExecutor, as_completed

import structlog

logger = structlog.get_logger(__name__)

rapidapi_key = os.getenv("RAPIDAPI_KEY")
insightsentry_api_key = os.getenv("INSIGHTSENTRY_API_KEY")

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


def get_ticker_yfinance(symbol):
    """
    Fetches ticker info for a given stock symbol using yfinance.
    """
    logger.info(f"Fetching ticker info for {symbol}")
    return yf.Ticker(symbol)


def get_ticker_info_yfinance(ticker: yf.Ticker):
    """
    Fetches ticker info for a given stock symbol using yfinance.
    """
    with requests_cache.enabled(backend="memory", expire_after=3600):
        logger.info(f"Fetching ticker info for {ticker}")
        return ticker.info


def get_ticker_financials_yfinance(ticker: yf.Ticker):
    """
    Fetches financials for a given stock symbol using yfinance.
    """
    with requests_cache.enabled(backend="memory", expire_after=3600):
        logger.info(f"Fetching financials for {ticker}")
        return ticker.financials


def get_ticker_balance_sheet_yfinance(ticker: yf.Ticker):
    """
    Fetches balance sheet for a given stock symbol using yfinance.
    """
    with requests_cache.enabled(backend="memory", expire_after=3600):
        logger.info(f"Fetching balance sheet for {ticker}")
        return ticker.balance_sheet


def get_ticker_cashflow_yfinance(ticker: yf.Ticker):
    """
    Fetches cash flow for a given stock symbol using yfinance.
    """
    with requests_cache.enabled(backend="memory", expire_after=3600):
        logger.info(f"Fetching cash flow for {ticker}")
        return ticker.cashflow


def get_ticker_quarterly_financials_yfinance(ticker: yf.Ticker):
    """
    Fetches quarterly financials for a given stock symbol using yfinance.
    """
    with requests_cache.enabled(backend="memory", expire_after=3600):
        logger.info(f"Fetching quarterly financials for {ticker}")
        return ticker.quarterly_financials


def get_ticker_dividends_yfinance(ticker: yf.Ticker):
    """
    Fetches dividends for a given stock symbol using yfinance.
    """
    with requests_cache.enabled(backend="memory", expire_after=3600):
        logger.info(f"Fetching dividends for {ticker}")
        return ticker.dividends


def get_price_data_yfinance(ticker: yf.Ticker, interval, period):
    """
    Fetches price data for a given stock symbol using yfinance.
    """
    with requests_cache.enabled(backend="memory", expire_after=3600):
        logger.info(
            f"Fetching price data for {ticker} (interval={interval}, period={period})"
        )
        return ticker.history(interval=interval, period=period)


def get_price_data(symbol, interval="1wk", period="3mo"):
    """
    Fetches daily close prices for `symbol` (US stocks only),
    returns a pandas Series indexed by date.
    """
    logger.info(
        f"Fetching price data for {symbol} (interval={interval}, period={period})"
    )
    url = "https://yahoo-finance15.p.rapidapi.com/api/v1/markets/stock/history"

    querystring = {"symbol": symbol, "interval": interval, "diffandsplits": "false"}

    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "yahoo-finance15.p.rapidapi.com",
    }

    try:
        # Use httpx.Client with the defined timeout
        with httpx.Client(timeout=timeout_config) as client:
            response = client.get(url, headers=headers, params=querystring)
            response.raise_for_status()  # raise_for_status works similarly in httpx
            hist = response.json().get("body", [])
            if not hist:
                logger.warning(
                    f"No price history data found for {symbol} in the response body."
                )
                return pd.DataFrame()  # Return empty DataFrame if no data

        df = pd.DataFrame(hist.values())

        start_date, _ = get_date_range(period)
        start_date_str = start_date.strftime("%Y-%m-%d")
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        df = df[start_date_str:].rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        logger.info(f"Successfully fetched and processed price data for {symbol}")
        return df.sort_index()
    except httpx.RequestError as e:
        logger.error(f"Error fetching price data for {symbol}: {e}")
        return pd.DataFrame()  # Return empty DataFrame on error
    except ValueError as e:  # Catch potential errors from get_date_range
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


def should_retry_http_error(exception: BaseException) -> bool:
    """Return True if we should retry, False otherwise."""
    if isinstance(exception, httpx.HTTPStatusError):
        # Do not retry on 4xx client errors
        if 400 <= exception.response.status_code < 500:
            logger.warning(
                f"Not retrying due to client error: {exception.response.status_code}"
            )
            return False
    # Retry on other errors (e.g., 5xx server errors, connection errors)
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry_error_callback=should_retry_http_error,
    reraise=True,
    before_sleep=log_retry_attempt,  # Log before sleeping on retry
)
def _fetch_yahoo_module_data_with_retry(
    symbol: str, module: str, rapidapi_key: str
) -> Dict[str, Any]:
    """Helper function to fetch data for a specific module from Yahoo Finance API with retries."""
    url = "https://yahoo-finance15.p.rapidapi.com/api/v1/markets/stock/modules"
    querystring = {"ticker": symbol, "module": module}
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "yahoo-finance15.p.rapidapi.com",
    }
    # Use httpx.Client with the defined timeout within the retried function
    with httpx.Client(timeout=timeout_config) as client:
        response = client.get(url, headers=headers, params=querystring)
        response.raise_for_status()  # Raises HTTPStatusError for bad responses (4xx or 5xx) in httpx
        return response.json().get("body", {})


def _fetch_yahoo_module_data(
    symbol: str, module: str, rapidapi_key: str
) -> Dict[str, Any]:
    """Wrapper function to handle exceptions from the retrying fetcher and log appropriately."""
    try:
        return _fetch_yahoo_module_data_with_retry(symbol, module, rapidapi_key)
    except RetryError as retry_err:
        # This catches the error after all retries have failed
        logger.error(
            f"Max retries exceeded for {module} ({symbol}). Last exception: {retry_err.last_attempt.exception()}"
        )
        return {}
    except Exception as e:
        # Catch any other unexpected exceptions that weren't retried or occurred outside the retry loop
        logger.error(f"Unexpected error fetching {module} for {symbol}: {e}")
        return {}


def get_fundamental_data(
    symbol: str, include_income_statement: bool = False
) -> Dict[str, Any]:
    """
    Fetches fundamental data for a given stock symbol by calling the Yahoo Finance API
    for different modules in parallel.
    """
    logger.info(
        f"Starting fundamental data fetch for {symbol} (include_income_statement={include_income_statement})"
    )
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
            future = executor.submit(
                _fetch_yahoo_module_data, symbol, module, rapidapi_key
            )
            futures[future] = module  # Store module name to identify results/errors

        # Process completed futures as they finish
        for future in as_completed(futures):
            module = futures[future]
            try:
                module_data = future.result()  # Get result from the future
                if module_data:  # Check if data was actually returned
                    combined_data.update(module_data)
                    logger.info(
                        f"Successfully processed module: {module} for {symbol}."
                    )
                else:
                    # Log if a module returned no data after processing (incl. retries)
                    logger.warning(
                        f"No data received for module {module} ({symbol}) after processing."
                    )
            except Exception as exc:
                # Log exceptions raised during the execution of the future
                logger.error(f"Error processing module {module} for {symbol}: {exc}")

    processed_data = {}
    for key, value in combined_data.items():
        if isinstance(value, dict) and "raw" in value and "fmt" in value:
            processed_data[key] = value["raw"]
        else:
            if isinstance(value, dict) and "raw" in value:
                processed_data[key] = value["raw"]
            elif isinstance(value, dict) and "fmt" in value:
                processed_data[key] = value["fmt"]
            else:
                processed_data[key] = value

    logger.info(f"Finished fundamental data fetch for {symbol}.")
    return processed_data


#### INSIGHTSENTRY ####


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(should_retry_http_error),
    reraise=True,
    before_sleep=log_retry_attempt,
)
def _fetch_insightsentry_data_with_retry(
    url: str, insightsentry_api_key: str, query_string: Dict = {}
) -> Dict[str, Any]:
    """Helper function to fetch data from InsightsEntry API with retries, avoiding retries on 4xx errors."""
    headers = {
        "x-rapidapi-key": insightsentry_api_key,
        "x-rapidapi-host": "insightsentry.p.rapidapi.com",
    }
    # Use httpx.Client with the defined timeout within the retried function
    with httpx.Client(timeout=timeout_config) as client:
        if query_string:
            response = client.get(url, headers=headers, params=query_string)
        else:
            response = client.get(url, headers=headers)
        response.raise_for_status()  # Raises HTTPStatusError for bad responses (4xx or 5xx) in httpx
        return response.json()


def get_fundamental_data_insightsentry(
    symbol: str, extended: bool = False
) -> Dict[str, Any]:
    """
    Fetches fundamental data for a given stock symbol by calling the InsightsEntry API.
    Returns an empty dictionary if data fetching fails.
    """
    logger.info(f"Starting fundamental data fetch for {symbol} (extended={extended})")
    response_data = {}

    try:
        # Fetch base info
        url = f"https://insightsentry.p.rapidapi.com/v2/symbols/{symbol}/info"
        info_response = _fetch_insightsentry_data_with_retry(url, insightsentry_api_key)
        if info_response:  # Check if response is not empty/None
            response_data.update(info_response)
            logger.info(f"Successfully fetched base info for {symbol}.")
        else:
            logger.warning(f"Received empty base info response for {symbol}.")

        # Fetch extended financials if requested
        if extended:
            try:
                url = f"https://insightsentry.p.rapidapi.com/v2/symbols/{symbol}/financials"
                financials_response = _fetch_insightsentry_data_with_retry(
                    url, insightsentry_api_key
                )
                if financials_response:  # Check if response is not empty/None
                    response_data.update(financials_response)
                    logger.info(
                        f"Successfully fetched extended financials for {symbol}."
                    )
                else:
                    logger.warning(
                        f"Received empty extended financials response for {symbol}."
                    )
            except (RetryError, httpx.HTTPError, Exception) as e:
                logger.error(
                    f"Error fetching extended financials for {symbol}: {e}. Proceeding with base info."
                )
                # We don't return here, just log the error and continue with base data if available

    except (RetryError, httpx.HTTPError, Exception) as e:
        logger.error(f"Error fetching fundamental data for {symbol}: {e}")
        return {}  # Return empty dict if the initial 'info' call fails

    if not response_data:
        logger.warning(f"No fundamental data could be fetched for {symbol}.")

    logger.info(
        f"Finished fundamental data fetch for {symbol}. Returning {'partial' if extended and 'financials' not in response_data else 'complete'} data."
    )
    return response_data


def get_historical_ohlcv_data_insightsentry(
    symbol: str, period: str = "3mo"
) -> pd.DataFrame:
    """
    Fetches historical OHLCV data for a given stock symbol using InsightsEntry API.
    Returns an empty DataFrame if data fetching fails.
    """
    logger.info(f"Fetching historical OHLCV data for {symbol} (period={period})")
    querystring = {
        "bar_interval": "1",
        "bar_type": "week",
        "extended": "false",
        "badj": "true",
        "dadj": "false",
    }
    try:
        url = f"https://insightsentry.p.rapidapi.com/v2/symbols/{symbol}/history"
        response = _fetch_insightsentry_data_with_retry(
            url, insightsentry_api_key, querystring
        )

        # Check if 'series' key exists and is not empty
        if not response or "series" not in response or not response["series"]:
            logger.warning(f"No historical data found for {symbol} in the response.")
            return pd.DataFrame()

        df = pd.DataFrame(response["series"])

        start_date, _ = get_date_range(period)
        start_date_str = start_date.strftime("%Y-%m-%d")
        # Ensure 'time' column exists before processing
        if "time" not in df.columns:
            logger.error(f"'time' column missing in historical data for {symbol}.")
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("date", inplace=True)
        df = df[start_date_str:].rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        logger.info(
            f"Successfully fetched and processed historical OHLCV data for {symbol}"
        )
        return df.sort_index()

    except (RetryError, httpx.HTTPError, ValueError, KeyError, Exception) as e:
        logger.error(
            f"Error fetching or processing historical OHLCV data for {symbol}: {e}"
        )
        return pd.DataFrame()


def search_symbol_insightsentry(query: str) -> Dict[str, Any]:
    """
    Searches InsightsEntry API for a given query.
    """
    try:
        logger.info(f"Searching InsightsEntry for {query}")
        url = f"https://insightsentry.p.rapidapi.com/v2/symbols/search"
        querystring = {"query": query, "type": "stocks"}
        search_response = _fetch_insightsentry_data_with_retry(
            url, insightsentry_api_key, querystring
        )
        return search_response[0]["code"]
    except (RetryError, httpx.HTTPError, ValueError, KeyError, Exception) as e:
        logger.error(f"Error searching InsightsEntry for {query}: {e}")
        return None
