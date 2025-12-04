"""
Main script for plotting financial data.
Generates candlestick charts and other visualizations for stored data.
"""

from config import CURRENCY_PAIRS, DATABASE_PATH
from database import load_from_database, list_tables, get_database_info
from plotting import plot_candlestick, plot_price_line, plot_ohlc, save_candlestick_html


def plot_single_pair(from_symbol: str, to_symbol: str, data_type: str = "daily"):
    """
    Plot a single currency pair.
    
    Args:
        from_symbol: Base currency (e.g., 'EUR')
        to_symbol: Quote currency (e.g., 'USD')
        data_type: Type of data - 'daily' or 'hourly'
    """
    table_name = f"{from_symbol}_{to_symbol}_{data_type}"
    
    try:
        print(f"\n📈 Loading {table_name}...")
        df = load_from_database(table_name, DATABASE_PATH)
        
        print(f"📊 Plotting candlestick chart for {from_symbol}/{to_symbol} ({data_type})...")
        title = f"{from_symbol}/{to_symbol} - {data_type.capitalize()} Candlestick Chart"
        plot_candlestick(df, title=title)
        
    except Exception as e:
        print(f"❌ Error plotting {table_name}: {str(e)}")


def plot_all_daily_pairs():
    """
    Plot candlestick charts for all configured currency pairs (daily data).
    """
    print("\n" + "="*60)
    print("PLOTTING ALL DAILY FOREX PAIRS")
    print("="*60)
    
    for from_symbol, to_symbol in CURRENCY_PAIRS:
        plot_single_pair(from_symbol, to_symbol, data_type="daily")


def plot_all_hourly_pairs():
    """
    Plot candlestick charts for all configured currency pairs (hourly data).
    """
    print("\n" + "="*60)
    print("PLOTTING ALL HOURLY FOREX PAIRS")
    print("="*60)
    
    for from_symbol, to_symbol in CURRENCY_PAIRS:
        plot_single_pair(from_symbol, to_symbol, data_type="hourly")


def plot_price_lines():
    """
    Plot line charts of closing prices for all pairs.
    """
    print("\n" + "="*60)
    print("PLOTTING PRICE LINES")
    print("="*60)
    
    for from_symbol, to_symbol in CURRENCY_PAIRS:
        table_name = f"{from_symbol}_{to_symbol}_daily"
        
        try:
            print(f"\n📈 Loading {table_name}...")
            df = load_from_database(table_name, DATABASE_PATH)
            
            print(f"📊 Plotting price line for {from_symbol}/{to_symbol}...")
            title = f"{from_symbol}/{to_symbol} - Closing Price"
            plot_price_line(df, title=title)
            
        except Exception as e:
            print(f"❌ Error plotting {table_name}: {str(e)}")


def save_charts_as_html():
    """
    Save candlestick charts as HTML files for all pairs.
    """
    print("\n" + "="*60)
    print("SAVING CHARTS AS HTML")
    print("="*60)
    
    for from_symbol, to_symbol in CURRENCY_PAIRS:
        table_name = f"{from_symbol}_{to_symbol}_daily"
        
        try:
            print(f"\n📈 Loading {table_name}...")
            df = load_from_database(table_name, DATABASE_PATH)
            
            print(f"💾 Saving HTML chart for {from_symbol}/{to_symbol}...")
            filename = f"{from_symbol}_{to_symbol}_daily.html"
            title = f"{from_symbol}/{to_symbol} - Daily Candlestick Chart"
            save_candlestick_html(df, filename, title=title)
            
        except Exception as e:
            print(f"❌ Error saving chart for {table_name}: {str(e)}")


def show_database_tables():
    """
    Display all available tables in the database.
    """
    print("\n" + "="*60)
    print("DATABASE TABLES")
    print("="*60)
    
    try:
        tables = list_tables(DATABASE_PATH)
        print("\nAvailable tables:")
        for table in tables:
            print(f"  - {table}")
        print(f"\nTotal: {len(tables)} tables")
    except Exception as e:
        print(f"❌ Error listing tables: {str(e)}")


def show_database_info():
    """
    Display detailed information about database structure.
    """
    print("\n" + "="*60)
    print("DATABASE STRUCTURE")
    print("="*60)
    
    try:
        info = get_database_info(DATABASE_PATH)
        for table, columns in info.items():
            print(f"\n📊 {table}:")
            for col in columns:
                print(f"    - {col}")
    except Exception as e:
        print(f"❌ Error getting database info: {str(e)}")


def main():
    """
    Main entry point for plotting pipeline.
    """
    print("\n🎨 Starting Plotting Pipeline...")
    print("="*60)
    
    # Show database information
    show_database_tables()
    show_database_info()
    
    # Plot all daily pairs
    plot_all_daily_pairs()
    
    # Save charts as HTML
    save_charts_as_html()
    
    print("\n" + "="*60)
    print("✅ ALL CHARTS GENERATED SUCCESSFULLY!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
