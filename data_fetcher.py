"""
Data fetching module for Alpha Vantage API.
Handles fetching stock and forex data from Alpha Vantage API.
"""

import requests
import pandas as pd
import time
from config import API_KEY, API_RATE_LIMIT_SECONDS


def fetch_stock_data(symbol: str) -> pd.DataFrame:
    """
    Fetch daily stock data from Alpha Vantage API.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
    
    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={API_KEY}"
    
    response = requests.get(url)
    data = response.json()
    
    # Parse JSON into DataFrame
    time_series = data.get("Time Series (Daily)", {})
    if not time_series:
        raise ValueError(f"No data returned for symbol {symbol}")
    
    df = pd.DataFrame.from_dict(time_series, orient="index")
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # Convert columns to numeric
    df = df.apply(pd.to_numeric)
    
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
    
    response = requests.get(url)
    data = response.json()
    
    # Parse JSON into DataFrame
    time_series = data.get("Time Series FX (Daily)", {})
    if not time_series:
        raise ValueError(f"No data returned for {from_symbol}/{to_symbol}")
    
    df = pd.DataFrame.from_dict(time_series, orient="index")
    df.columns = ["open", "high", "low", "close"]
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # Convert columns to numeric
    df = df.apply(pd.to_numeric)
    
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
    
    response = requests.get(url)
    data = response.json()
    
    # Parse JSON into DataFrame
    key = f"Time Series FX ({interval})"
    time_series = data.get(key, {})
    if not time_series:
        raise ValueError(f"No data returned for {from_symbol}/{to_symbol} at {interval}")
    
    df = pd.DataFrame.from_dict(time_series, orient="index")
    df.columns = ["open", "high", "low", "close"]
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    
    # Convert columns to numeric
    df = df.apply(pd.to_numeric)
    
    return df
