# Financial Data Pipeline

A Python-based financial data pipeline for fetching, storing, and visualizing forex and stock data from Alpha Vantage API.

## Project Structure

```
.
├── config.py              # Configuration settings (API keys, database paths, symbols)
├── data_fetcher.py        # Data fetching module (Alpha Vantage API interactions)
├── database.py            # Database operations module (SQLite storage/retrieval)
├── plotting.py            # Visualization module (Plotly charts)
├── main.py                # Main data fetching pipeline
├── plot_main.py           # Main plotting pipeline
├── requirements.txt       # Project dependencies
└── README.md              # This file
```

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure your API key:**
   - Edit `config.py` and ensure `API_KEY` is set correctly
   - The default API key is already configured

## Usage

### 1. Fetch Data

Run the main data fetching pipeline to collect stock and forex data:

```bash
python main.py
```

This will:
- Fetch stock data (AAPL by default)
- Fetch daily forex data for all configured currency pairs
- Fetch intraday (hourly) forex data for all configured currency pairs
- Store data in SQLite databases and CSV files

**Data Output:**
- `forex.db` - SQLite database with forex data
- `stocks.db` - SQLite database with stock data
- `*.csv` files - CSV exports of all data

### 2. Generate Plots

Run the plotting pipeline to visualize the stored data:

```bash
python plot_main.py
```

This will:
- Display database structure information
- Generate interactive candlestick charts for all currency pairs
- Save charts as HTML files for offline viewing

**Plot Output:**
- Interactive Plotly charts in browser
- `*_daily.html` - HTML files with candlestick charts

## Module Documentation

### `config.py`
Contains all configuration settings:
- `API_KEY` - Alpha Vantage API key
- `CURRENCY_PAIRS` - List of forex pairs to fetch
- `STOCK_SYMBOLS` - List of stock symbols to fetch
- `DATABASE_PATH` - Forex database location
- `STOCKS_DB_PATH` - Stock database location

### `data_fetcher.py`
Functions for fetching data from Alpha Vantage:
- `fetch_stock_data(symbol)` - Fetch daily stock data
- `fetch_fx_daily_data(from_symbol, to_symbol)` - Fetch daily forex data
- `fetch_fx_intraday_data(from_symbol, to_symbol, interval)` - Fetch intraday forex data

### `database.py`
Functions for database operations:
- `save_to_database(df, table_name, db_path)` - Save DataFrame to SQLite
- `save_to_csv(df, filename)` - Save DataFrame to CSV
- `load_from_database(table_name, db_path)` - Load DataFrame from SQLite
- `list_tables(db_path)` - List all tables in database
- `get_database_info(db_path)` - Get detailed database structure info

### `plotting.py`
Functions for data visualization:
- `plot_candlestick(df, title)` - Interactive candlestick chart
- `plot_price_line(df, title)` - Line chart of closing prices
- `plot_ohlc(df, title)` - OHLC bar chart
- `plot_multiple_candlesticks(data_dict, title)` - Multiple charts in subplots
- `save_candlestick_html(df, filename, title)` - Save chart as HTML file

### `main.py`
Entry point for data fetching pipeline with functions:
- `fetch_and_store_stocks()` - Process all stock symbols
- `fetch_and_store_forex_daily()` - Process daily forex data
- `fetch_and_store_forex_intraday()` - Process intraday forex data
- `main()` - Execute full pipeline

### `plot_main.py`
Entry point for plotting pipeline with functions:
- `plot_single_pair(from_symbol, to_symbol, data_type)` - Plot single currency pair
- `plot_all_daily_pairs()` - Plot all currency pairs (daily)
- `plot_all_hourly_pairs()` - Plot all currency pairs (hourly)
- `plot_price_lines()` - Plot price line charts
- `save_charts_as_html()` - Save all charts as HTML files
- `show_database_tables()` - Display available tables
- `show_database_info()` - Display database structure

## Customization

### Add More Currency Pairs

Edit `config.py`:
```python
CURRENCY_PAIRS = [
    ("EUR", "USD"),
    ("GBP", "USD"),
    ("USD", "JPY"),
    ("AUD", "USD"),
    ("USD", "CAD"),
    ("CHF", "USD"),  # Add new pair
]
```

### Add More Stock Symbols

Edit `config.py`:
```python
STOCK_SYMBOLS = ["AAPL", "MSFT", "GOOGL"]  # Add more symbols
```

### Change API Rate Limiting

Edit `config.py`:
```python
API_RATE_LIMIT_SECONDS = 12  # Adjust based on API plan
```

### Create Custom Plots

Use the `plotting.py` functions in your own scripts:
```python
from database import load_from_database
from plotting import plot_candlestick

df = load_from_database("EUR_USD_daily", "sqlite:///forex.db")
plot_candlestick(df, title="EUR/USD Daily")
```

## API Documentation

- **Alpha Vantage API**: https://www.alphavantage.co/
- **Rate Limit**: 5 requests per minute (free tier)
- **Data Functions**:
  - `TIME_SERIES_DAILY` - Daily stock data
  - `FX_DAILY` - Daily forex data
  - `FX_INTRADAY` - Intraday forex data

## Dependencies

- **requests** - HTTP requests library
- **pandas** - Data manipulation and analysis
- **sqlalchemy** - Database ORM
- **plotly** - Interactive visualization library

## License

MIT License

## Author

Financial Data Pipeline Project
