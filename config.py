"""
Configuration settings for the Alpha Vantage data pipeline.
"""

# API Configuration
API_KEY = "74M88OXCGWTNUIV9"

# Database Configuration
DATABASE_PATH = "sqlite:///forex.db"
STOCKS_DB_PATH = "sqlite:///stocks.db"

# Currency Pairs to fetch
CURRENCY_PAIRS = [
    ("EUR", "USD"),
    ("GBP", "USD"),
    ("USD", "JPY"),
    ("AUD", "USD"),
    ("USD", "CAD")
]

# Stock symbols to fetch
STOCK_SYMBOLS = ["AAPL"]

# API Rate limiting (requests per minute = 5, so wait 12 seconds between requests)
API_RATE_LIMIT_SECONDS = 12
