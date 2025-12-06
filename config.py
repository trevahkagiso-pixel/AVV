"""
Configuration settings for the Alpha Vantage data pipeline and Ichimoku backtest.
"""

import os

# ══════════════════════════════════════════════════════════════════════════════
# API Configuration
# ══════════════════════════════════════════════════════════════════════════════
API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "74M88OXCGWTNUIV9")

# Database Configuration
DATABASE_PATH = "sqlite:///forex.db"
STOCKS_DB_PATH = "sqlite:///stocks.db"
COMMODITIES_DB_PATH = "sqlite:///commodities.db"

# Currency Pairs to fetch
CURRENCY_PAIRS = [
    ("EUR", "USD"),
    ("GBP", "USD"),
    ("USD", "JPY"),
    ("AUD", "USD"),
    ("USD", "CAD")
]

# Stock symbols to fetch - Big Five US Tech Stocks
STOCK_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

# Commodity symbols - Big Five commodities (via yfinance)
# Gold (GC=F), Crude Oil (CL=F), Natural Gas (NG=F), Copper (HG=F), Silver (SI=F)
COMMODITY_SYMBOLS = ["GC=F", "CL=F", "NG=F", "HG=F", "SI=F"]
COMMODITY_NAMES = {"GC=F": "Gold", "CL=F": "Crude Oil", "NG=F": "Natural Gas", "HG=F": "Copper", "SI=F": "Silver"}

# API Rate limiting (requests per minute = 5, so wait 12 seconds between requests)
API_RATE_LIMIT_SECONDS = 12

# ══════════════════════════════════════════════════════════════════════════════
# Ichimoku Cloud Configuration
# ══════════════════════════════════════════════════════════════════════════════

# Ichimoku indicator parameters
ICHIMOKU_TENKAN = 9        # Tenkan-sen (Conversion Line) period
ICHIMOKU_KIJUN = 26        # Kijun-sen (Base Line) period
ICHIMOKU_SENKOU_B = 52     # Senkou Span B period

# Risk management (ATR-based)
ATR_LENGTH = 14
ATR_MULT_SL = 1.5          # Stop-loss distance = ATR * this multiplier
ATR_MULT_TP = 2.0          # Take-profit distance = SL distance * this multiplier (risk-reward ratio)

# EMA trend filter
EMA_LENGTH = 100           # EMA period for trend confirmation
EMA_BACK_CANDLES = 7       # Number of lookback candles for EMA signal

# Ichimoku signal generation
ICHIMOKU_LOOKBACK = 10     # Lookback window for cloud confirmation
ICHIMOKU_MIN_CONFIRM = 5   # Minimum bars required above/below cloud

# Backtest parameters
BACKTEST_CASH = 1_000_000          # Initial account cash
BACKTEST_COMMISSION = 0.0002       # Commission per trade (0.02%)
BACKTEST_TRADE_ON_CLOSE = True     # Execute at close price
BACKTEST_MARGIN = 1/10             # Margin (1:10 leverage)
