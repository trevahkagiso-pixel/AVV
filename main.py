"""
Main script for fetching and storing financial data from Alpha Vantage API.
Handles both stock and forex data with automatic rate limiting.
"""

import time
from config import CURRENCY_PAIRS, STOCK_SYMBOLS, API_RATE_LIMIT_SECONDS, DATABASE_PATH, STOCKS_DB_PATH
from data_fetcher import fetch_stock_data, fetch_fx_daily_data, fetch_fx_intraday_data
from database import save_to_database, save_to_csv


def fetch_and_store_stocks():
    """
    Fetch stock data for all configured symbols and store in database and CSV.
    """
    print("\n" + "="*60)
    print("FETCHING STOCK DATA")
    print("="*60)
    
    for symbol in STOCK_SYMBOLS:
        try:
            print(f"\n📊 Fetching data for {symbol}...")
            df = fetch_stock_data(symbol)
            
            # Store in database
            save_to_database(df, f"{symbol}_daily", STOCKS_DB_PATH)
            
            # Store as CSV
            save_to_csv(df, f"{symbol}_daily.csv")
            
            print(f"✅ {symbol} data fetched and stored successfully!")
            time.sleep(API_RATE_LIMIT_SECONDS)
            
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {str(e)}")
            time.sleep(API_RATE_LIMIT_SECONDS)


def fetch_and_store_forex_daily():
    """
    Fetch daily forex data for all configured currency pairs and store in database and CSV.
    """
    print("\n" + "="*60)
    print("FETCHING DAILY FOREX DATA")
    print("="*60)
    
    for from_symbol, to_symbol in CURRENCY_PAIRS:
        try:
            print(f"\n💱 Fetching daily data for {from_symbol}/{to_symbol}...")
            df = fetch_fx_daily_data(from_symbol, to_symbol)
            
            # Store in database
            table_name = f"{from_symbol}_{to_symbol}_daily"
            save_to_database(df, table_name, DATABASE_PATH)
            
            # Store as CSV
            save_to_csv(df, f"{table_name}.csv")
            
            print(f"✅ {from_symbol}/{to_symbol} daily data fetched and stored!")
            time.sleep(API_RATE_LIMIT_SECONDS)
            
        except Exception as e:
            print(f"❌ Error fetching {from_symbol}/{to_symbol}: {str(e)}")
            time.sleep(API_RATE_LIMIT_SECONDS)


def fetch_and_store_forex_intraday():
    """
    Fetch intraday forex data for all configured currency pairs and store in database and CSV.
    """
    print("\n" + "="*60)
    print("FETCHING INTRADAY FOREX DATA")
    print("="*60)
    
    for from_symbol, to_symbol in CURRENCY_PAIRS:
        try:
            print(f"\n💱 Fetching intraday data for {from_symbol}/{to_symbol}...")
            df = fetch_fx_intraday_data(from_symbol, to_symbol, interval="60min")
            
            # Store in database
            table_name = f"{from_symbol}_{to_symbol}_hourly"
            save_to_database(df, table_name, DATABASE_PATH)
            
            # Store as CSV
            save_to_csv(df, f"{table_name}.csv")
            
            print(f"✅ {from_symbol}/{to_symbol} intraday data fetched and stored!")
            time.sleep(API_RATE_LIMIT_SECONDS)
            
        except Exception as e:
            print(f"❌ Error fetching intraday {from_symbol}/{to_symbol}: {str(e)}")
            time.sleep(API_RATE_LIMIT_SECONDS)


def main():
    """
    Main entry point for data fetching pipeline.
    """
    print("\n🚀 Starting Financial Data Pipeline...")
    print("="*60)
    
    # Fetch stocks
    fetch_and_store_stocks()
    
    # Fetch forex daily data
    fetch_and_store_forex_daily()
    
    # Fetch forex intraday data
    fetch_and_store_forex_intraday()
    
    print("\n" + "="*60)
    print("✅ ALL DATA FETCHED AND STORED SUCCESSFULLY!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
