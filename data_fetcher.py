"""
Data fetching module for Alpha Vantage API and yfinance.
Handles fetching stock, forex, and commodity data with logging and timeouts.
"""

import logging
import requests
import pandas as pd
import time
from config import API_KEY, API_RATE_LIMIT_SECONDS

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# HTTP request timeout in seconds
REQUEST_TIMEOUT = 30


def fetch_stock_data(symbol: str) -> pd.DataFrame:
    """
    Fetch daily stock data from Alpha Vantage API.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
    
    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={API_KEY}"
    logger.info(f"Fetching stock data for {symbol}...")
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout while fetching {symbol} (>{REQUEST_TIMEOUT}s)")
        raise ValueError(f"Request timeout for {symbol}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching {symbol}: {e}")
        raise ValueError(f"Network error for {symbol}: {e}")
    
    data = response.json()
    
    # Check for API errors (e.g., rate limit, invalid API key)
    if "Error Message" in data:
        logger.error(f"API error for {symbol}: {data['Error Message']}")
        raise ValueError(f"API error for {symbol}: {data['Error Message']}")
    
    if "Note" in data:
        logger.warning(f"API rate limit reached: {data['Note']}")
        raise ValueError(f"API rate limit: {data['Note']}")
    
    # Parse JSON into DataFrame
    time_series = data.get("Time Series (Daily)", {})
    if not time_series:
        logger.error(f"No data returned for symbol {symbol}")
        raise ValueError(f"No data returned for symbol {symbol}")
    
    df = pd.DataFrame.from_dict(time_series, orient="index")
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # Convert columns to numeric
    df = df.apply(pd.to_numeric)
    logger.info(f"Successfully fetched {len(df)} rows for {symbol}")
    
    return df


def fetch_fx_daily_data(from_symbol: str, to_symbol: str) -> pd.DataFrame:
    """
    Fetch daily forex data from Alpha Vantage API.
    
    Args:
        from_symbol: Base currency (e.g., 'EUR')
        to_symbol: Quote currency (e.g., 'USD')
    
    Returns:
        DataFrame with columns: open, high, low, close
    """
    url = f"https://www.alphavantage.co/query?function=FX_DAILY&from_symbol={from_symbol}&to_symbol={to_symbol}&apikey={API_KEY}&outputsize=full"
    logger.info(f"Fetching daily forex data for {from_symbol}/{to_symbol}...")
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout for {from_symbol}/{to_symbol} (>{REQUEST_TIMEOUT}s)")
        raise ValueError(f"Request timeout for {from_symbol}/{to_symbol}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching {from_symbol}/{to_symbol}: {e}")
        raise ValueError(f"Network error for {from_symbol}/{to_symbol}: {e}")
    
    data = response.json()
    
    # Check for API errors
    if "Error Message" in data:
        logger.error(f"API error for {from_symbol}/{to_symbol}: {data['Error Message']}")
        raise ValueError(f"API error for {from_symbol}/{to_symbol}: {data['Error Message']}")
    
    if "Note" in data:
        logger.warning(f"API rate limit reached: {data['Note']}")
        raise ValueError(f"API rate limit: {data['Note']}")
    
    # Parse JSON into DataFrame
    time_series = data.get("Time Series FX (Daily)", {})
    if not time_series:
        logger.error(f"No data returned for {from_symbol}/{to_symbol}")
        raise ValueError(f"No data returned for {from_symbol}/{to_symbol}")
    
    df = pd.DataFrame.from_dict(time_series, orient="index")
    df.columns = ["open", "high", "low", "close"]
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # Convert columns to numeric
    df = df.apply(pd.to_numeric)
    logger.info(f"Successfully fetched {len(df)} rows for {from_symbol}/{to_symbol}")
    
    return df


def fetch_fx_intraday_data(from_symbol: str, to_symbol: str, interval: str = "60min") -> pd.DataFrame:
    """
    Fetch intraday forex data from Alpha Vantage API.
    
    Args:
        from_symbol: Base currency (e.g., 'EUR')
        to_symbol: Quote currency (e.g., 'USD')
        interval: Time interval (e.g., '60min', '30min', '15min', '5min', '1min')
    
    Returns:
        DataFrame with columns: open, high, low, close
    """
    url = f"https://www.alphavantage.co/query?function=FX_INTRADAY&from_symbol={from_symbol}&to_symbol={to_symbol}&interval={interval}&apikey={API_KEY}&outputsize=full"
    logger.info(f"Fetching intraday forex data for {from_symbol}/{to_symbol} @ {interval}...")
    
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout for {from_symbol}/{to_symbol} @ {interval} (>{REQUEST_TIMEOUT}s)")
        raise ValueError(f"Request timeout for {from_symbol}/{to_symbol} @ {interval}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching {from_symbol}/{to_symbol} @ {interval}: {e}")
        raise ValueError(f"Network error for {from_symbol}/{to_symbol} @ {interval}: {e}")
    
    data = response.json()
    
    # Check for API errors
    if "Error Message" in data:
        logger.error(f"API error for {from_symbol}/{to_symbol} @ {interval}: {data['Error Message']}")
        raise ValueError(f"API error for {from_symbol}/{to_symbol} @ {interval}: {data['Error Message']}")
    
    if "Note" in data:
        logger.warning(f"API rate limit reached: {data['Note']}")
        raise ValueError(f"API rate limit: {data['Note']}")
    
    # Parse JSON into DataFrame
    key = f"Time Series FX ({interval})"
    time_series = data.get(key, {})
    if not time_series:
        logger.error(f"No data returned for {from_symbol}/{to_symbol} at {interval}")
        raise ValueError(f"No data returned for {from_symbol}/{to_symbol} at {interval}")
    
    df = pd.DataFrame.from_dict(time_series, orient="index")
    df.columns = ["open", "high", "low", "close"]
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # Convert columns to numeric
    df = df.apply(pd.to_numeric)
    logger.info(f"Successfully fetched {len(df)} rows for {from_symbol}/{to_symbol} @ {interval}")
    
    return df


def fetch_commodity_data(symbol: str, period: str = "5y") -> pd.DataFrame:
    """
    Fetch daily commodity data from yfinance.
    
    Args:
        symbol: Commodity ticker (e.g., 'GC=F' for Gold, 'CL=F' for Crude Oil)
        period: Historical period ('5y', '10y', 'max', etc.)
    
    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume (standardized to lowercase)
    """
    logger.info(f"Fetching commodity data for {symbol} (period={period})...")
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed")
        raise ImportError("yfinance not installed. Install with: pip install yfinance")
    
    try:
        df = yf.download(symbol, period=period, progress=False, threads=False)
        
        if df.empty:
            logger.error(f"No data returned for commodity {symbol}")
            raise ValueError(f"No data returned for commodity {symbol}")
        
        # Handle yfinance MultiIndex format (flatten if needed)
        if isinstance(df.columns, pd.MultiIndex):
            try:
                df = df.xs(symbol, axis=1, level=1)
            except (KeyError, TypeError):
                # If xs fails, just take first level
                df.columns = df.columns.get_level_values(0)
        
        # Standardize column names to lowercase
        df.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in df.columns]
        
        # Ensure we have OHLC columns
        required_cols = ['open', 'high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing OHLC columns for {symbol}")
            raise ValueError(f"Missing OHLC columns for {symbol}")
        
        logger.info(f"Successfully fetched {len(df)} rows for commodity {symbol}")
        return df.dropna()
    
    except Exception as e:
        logger.error(f"Error fetching commodity {symbol}: {str(e)}")
        raise ValueError(f"Error fetching commodity {symbol}: {str(e)}")
