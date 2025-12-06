"""
Main script for fetching and storing financial data from Alpha Vantage API and yfinance.
Handles stock, forex, and commodity data with automatic rate limiting and logging.
"""

import logging
import time
from config import CURRENCY_PAIRS, STOCK_SYMBOLS, COMMODITY_SYMBOLS, COMMODITY_NAMES, API_RATE_LIMIT_SECONDS, DATABASE_PATH, STOCKS_DB_PATH, COMMODITIES_DB_PATH
from data_fetcher import fetch_stock_data, fetch_fx_daily_data, fetch_fx_intraday_data, fetch_commodity_data
from database import save_to_database, save_to_csv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('data_pipeline.log')  # File output
    ]
)

logger = logging.getLogger(__name__)


def fetch_and_store_stocks():
    """
    Fetch stock data for all configured symbols and store in database and CSV.
    """
    logger.info("="*60)
    logger.info("FETCHING STOCK DATA")
    logger.info("="*60)
    
    for symbol in STOCK_SYMBOLS:
        try:
            logger.info(f"Fetching data for {symbol}...")
            df = fetch_stock_data(symbol)
            
            # Store in database
            save_to_database(df, f"{symbol}_daily", STOCKS_DB_PATH)
            
            # Store as CSV
            save_to_csv(df, f"{symbol}_daily.csv")
            
            logger.info(f"✅ {symbol} data fetched and stored successfully!")
            time.sleep(API_RATE_LIMIT_SECONDS)
            
        except Exception as e:
            logger.error(f"❌ Error fetching {symbol}: {str(e)}")
            time.sleep(API_RATE_LIMIT_SECONDS)


def fetch_and_store_forex_daily():
    """
    Fetch daily forex data for all configured currency pairs and store in database and CSV.
    """
    logger.info("="*60)
    logger.info("FETCHING DAILY FOREX DATA")
    logger.info("="*60)
    
    for from_symbol, to_symbol in CURRENCY_PAIRS:
        try:
            logger.info(f"Fetching daily data for {from_symbol}/{to_symbol}...")
            df = fetch_fx_daily_data(from_symbol, to_symbol)
            
            # Store in database
            table_name = f"{from_symbol}_{to_symbol}_daily"
            save_to_database(df, table_name, DATABASE_PATH)
            
            # Store as CSV
            save_to_csv(df, f"{table_name}.csv")
            
            logger.info(f"✅ {from_symbol}/{to_symbol} daily data fetched and stored!")
            time.sleep(API_RATE_LIMIT_SECONDS)
            
        except Exception as e:
            logger.error(f"❌ Error fetching {from_symbol}/{to_symbol}: {str(e)}")
            time.sleep(API_RATE_LIMIT_SECONDS)


def fetch_and_store_forex_intraday():
    """
    Fetch intraday forex data for all configured currency pairs and store in database and CSV.
    """
    logger.info("="*60)
    logger.info("FETCHING INTRADAY FOREX DATA")
    logger.info("="*60)
    
    for from_symbol, to_symbol in CURRENCY_PAIRS:
        try:
            logger.info(f"Fetching intraday data for {from_symbol}/{to_symbol}...")
            df = fetch_fx_intraday_data(from_symbol, to_symbol, interval="60min")
            
            # Store in database
            table_name = f"{from_symbol}_{to_symbol}_hourly"
            save_to_database(df, table_name, DATABASE_PATH)
            
            # Store as CSV
            save_to_csv(df, f"{table_name}.csv")
            
            logger.info(f"✅ {from_symbol}/{to_symbol} intraday data fetched and stored!")
            time.sleep(API_RATE_LIMIT_SECONDS)
            
        except Exception as e:
            logger.error(f"❌ Error fetching intraday {from_symbol}/{to_symbol}: {str(e)}")
            time.sleep(API_RATE_LIMIT_SECONDS)


def fetch_and_store_commodities():
    """
    Fetch commodity data for all configured symbols and store in database and CSV.
    """
    logger.info("="*60)
    logger.info("FETCHING COMMODITY DATA")
    logger.info("="*60)
    
    for symbol in COMMODITY_SYMBOLS:
        try:
            name = COMMODITY_NAMES.get(symbol, symbol)
            logger.info(f"Fetching data for {name} ({symbol})...")
            df = fetch_commodity_data(symbol)
            
            # Use symbol as table name (e.g., 'GC=F' -> 'GC_F')
            table_name = symbol.replace("=", "_") + "_daily"
            
            # Store in database
            save_to_database(df, table_name, COMMODITIES_DB_PATH)
            
            # Store as CSV
            save_to_csv(df, f"{table_name}.csv")
            
            logger.info(f"✅ {name} data fetched and stored successfully!")
            time.sleep(API_RATE_LIMIT_SECONDS)
            
        except Exception as e:
            logger.error(f"❌ Error fetching {symbol}: {str(e)}")
            time.sleep(API_RATE_LIMIT_SECONDS)


def main():
    """
    Main entry point for data fetching pipeline.
    """
    logger.info("\n🚀 Starting Financial Data Pipeline...")
    logger.info("="*60)
    
    # Fetch stocks
    fetch_and_store_stocks()
    
    # Fetch forex daily data
    fetch_and_store_forex_daily()
    
    # Fetch forex intraday data
    fetch_and_store_forex_intraday()
    
    # Fetch commodities
    fetch_and_store_commodities()
    
    logger.info("="*60)
    logger.info("✅ ALL DATA FETCHED AND STORED SUCCESSFULLY!")
    logger.info("="*60)


if __name__ == "__main__":
    main()
