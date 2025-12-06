# How to Run the Ichimoku Trading Backtest Application

## Overview

This is a complete Flask-based web application for backtesting the Ichimoku trading strategy on multiple FX currency pairs. It includes:

- 📊 Interactive backtest dashboard
- 📈 Equity curves and price charts
- ☁️ Ichimoku cloud analysis
- 💡 AI-powered strategy analysis
- 🎯 Risk management with stop-loss and take-profit
- 📱 Responsive web interface

---

## Quick Start (60 seconds)

### 1. Activate Virtual Environment

```bash
cd /workspaces/AV
source .venv/bin/activate
```

### 2. Start the Application

```bash
python web_ui.py
```

### 3. Open in Browser

Navigate to: **http://localhost:5000**

That's it! 🚀

---

## Detailed Setup Guide

### Prerequisites

- Python 3.8+
- Virtual environment (`.venv`) already set up
- Required packages installed (pandas, backtesting, plotly, flask, etc.)

### Step 1: Navigate to Project Directory

```bash
cd /workspaces/AV
```

### Step 2: Activate Virtual Environment

**On Linux/Mac:**
```bash
source .venv/bin/activate
```

**On Windows:**
```bash
.venv\Scripts\activate
```

You should see `(.venv)` prefix in your terminal.

### Step 3: Start the Web Server

```bash
python web_ui.py
```

Expected output:
```
Starting web server on http://127.0.0.1:5000
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

### Step 4: Open Application

Open your web browser and navigate to:

```
http://localhost:5000
```

---

## Web Interface Features

### Dashboard (Home Page)

**URL:** `http://localhost:5000/`

- 📈 Summary table of all backtest results across currency pairs
- 💹 Equity curve charts for all pairs
- ✅ System status indicator
- 🔄 Real-time build status

**Currency Pairs Included:**
- EUR/USD
- GBP/USD
- USD/JPY
- AUD/USD
- USD/CAD

### Pair Details Page

**URL:** `http://localhost:5000/pair/<PAIR>` (e.g., `/pair/EUR_USD_daily`)

**Features:**
1. **📈 Performance Metrics** - Key statistics (Return %, Max Drawdown, Win Rate, Trades, Exposure)
2. **📊 Charts** (click to expand):
   - 💰 **Equity Curve** - Strategy account balance over time
   - 📊 **Candlestick Chart** - Price action visualization
   - ☁️ **Ichimoku Analysis** - Cloud, Tenkan, Kijun, signals
3. **💡 AI Analysis & Insights**:
   - Overall performance rating (Excellent/Good/Fair/Poor)
   - Risk analysis (drawdown, volatility, Sharpe ratio)
   - Trade quality assessment
   - Prioritized improvement suggestions

### Viewing Full Charts

**New Feature:** Click on any chart to expand to full screen
- Modal popup displays full-sized chart
- Press `Escape` or click outside to close
- Use browser zoom (Ctrl/Cmd + scroll) for more detail

---

## Advanced Usage

### Custom Port

To run on a different port:

```bash
python web_ui.py --port 8080
```

Then access: `http://localhost:8080`

### Custom Host

To allow remote connections:

```bash
python web_ui.py --host 0.0.0.0 --port 5000
```

**Note:** Only use on trusted networks.

### Build Cache

To pre-build all backtests and save results:

```bash
python web_ui.py --build
```

This creates `backtest_summary.csv` and saves HTML charts.

---

## Strategy Parameters

### Current Settings

The strategy uses these parameters (configurable in code):

| Parameter | Value | Purpose |
|-----------|-------|---------|
| ATR Multiplier (SL) | 1.5 | Stop-loss distance = ATR × 1.5 |
| Risk-Reward Ratio | 2.0 | Take-profit = SL distance × 2.0 |
| EMA Length | 100 | Trend filter period |
| Ichimoku Tenkan | 9 | Fast line period |
| Ichimoku Kijun | 26 | Slow line period |
| Ichimoku Senkou B | 52 | Cloud span period |

### Modifying Parameters

Edit `ichimoku_backtest.py`:

```python
# Change these values
stats = bt.run(
    atr_mult_sl=1.5,      # Stop-loss multiplier
    rr_mult_tp=2.0,       # Risk-reward ratio
)
```

Or when running individual backtests:

```python
from ichimoku_backtest import run_backtest_from_database

stats, df, bt = run_backtest_from_database(
    "EUR_USD_daily",
    atr_mult_sl=2.0,      # Wider stops
    rr_mult_tp=3.0,       # Higher profit targets
    ema_length=50,        # Shorter trend filter
)
```

---

## Data Management

### Database Location

All currency pair data is stored in SQLite database:

```
/workspaces/AV/av_data.sqlite3
```

### Data Tables

- `EUR_USD_daily` - Euro/US Dollar daily prices
- `GBP_USD_daily` - British Pound/US Dollar daily prices
- `USD_JPY_daily` - US Dollar/Japanese Yen daily prices
- `AUD_USD_daily` - Australian Dollar/US Dollar daily prices
- `USD_CAD_daily` - US Dollar/Canadian Dollar daily prices

### Updating Data

To refresh price data:

```python
from ichimoku import fetch_data_yfinance, save_to_database
from config import DATABASE_PATH

df = fetch_data_yfinance("EURUSD=X", period="5y")
save_to_database(df, "EUR_USD_daily", DATABASE_PATH)
```

---

## File Structure

```
/workspaces/AV/
├── web_ui.py                          # Main Flask application
├── ichimoku_backtest.py              # Backtest runner
├── ichimoku.py                        # Ichimoku indicators
├── strategy.py                        # Trading strategy
├── backtest_analysis.py              # Analysis & insights
├── plotting.py                        # Chart generation
├── config.py                          # Configuration
├── strategy_framework.py              # Strategy framework
├── ichimoku_strategy.py              # Strategy class
├── rsi_strategy.py                   # RSI example strategy
├── backtest_runner.py                # Multi-strategy runner
├── .venv/                             # Virtual environment
├── av_data.sqlite3                   # Price data database
├── backtest_summary.csv              # Cached results (auto-generated)
└── *_equity.html                     # Chart files (auto-generated)
```

---

## Troubleshooting

### Port 5000 Already in Use

Kill the existing process:

```bash
# Linux/Mac
lsof -i :5000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Or use different port
python web_ui.py --port 8080
```

### Missing Dependencies

Install missing packages:

```bash
pip install -r requirements.txt
```

### Charts Not Loading

Clear browser cache:
- Chrome: Ctrl+Shift+Delete
- Firefox: Ctrl+Shift+Delete
- Safari: Cmd+Option+E

Then refresh the page.

### Slow Backtest

- First run takes longer (backtests all pairs)
- Results are cached in `backtest_summary.csv`
- Subsequent runs use cache (much faster)
- To refresh: Delete `backtest_summary.csv` and reload

### ModuleNotFoundError

Ensure virtual environment is activated:

```bash
# Check if activated (should show (.venv) prefix)
which python
# Should output: /workspaces/AV/.venv/bin/python

# If not, activate it
source .venv/bin/activate
```

---

## Monitoring Backtests

### View Console Output

The Flask server shows real-time backtest progress:

```
Running Ichimoku Backtest: EUR_USD_daily
📊 Fetching EUR_USD_daily from database...
   Loaded 5000 rows
📈 Adding Ichimoku Cloud indicators...
📊 Creating Ichimoku + EMA signals...
   4949 rows after dropping NaN
🎯 Running backtest with 4949 candles...

✅ Backtest Results for EUR_USD_daily:
   Return: -75.43%
   Max Drawdown: -87.67%
   Win Rate: 35.06%
   # Trades: 77
```

### Build Status

Check `/build_status` endpoint for background build progress:

```
http://localhost:5000/build_status
```

---

## Performance Tips

1. **First Load**: 
   - Takes 30-60 seconds (backtests all pairs)
   - Results are cached

2. **Subsequent Loads**:
   - Instant (uses cache)
   - Delete `backtest_summary.csv` to force refresh

3. **Chart Loading**:
   - Charts are HTML files (fast loading)
   - Stored locally in project directory
   - No external dependencies

4. **Memory**:
   - Each backtest: ~50-100MB
   - Total with all pairs: ~500MB
   - Manageable on any modern system

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Escape` | Close expanded chart modal |
| `Ctrl/Cmd + +` | Zoom in on chart |
| `Ctrl/Cmd + -` | Zoom out on chart |
| `Ctrl/Cmd + 0` | Reset chart zoom |

---

## Configuration Files

### `config.py`

Main configuration:

```python
DATABASE_PATH = "av_data.sqlite3"
CURRENCY_PAIRS = ["EUR_USD_daily", "GBP_USD_daily", "USD_JPY_daily", "AUD_USD_daily", "USD_CAD_daily"]
```

### `requirements.txt`

All dependencies:

```
pandas
numpy
backtesting
plotly
flask
scikit-learn
pandas-ta
yfinance
redis
rq
```

---

## Stop/Restart Application

### Stop Server

In terminal, press:
```
Ctrl + C
```

### Restart Server

```bash
# Kill any running instances
pkill -f "python web_ui.py"

# Restart
python web_ui.py
```

---

## Production Deployment

For production use (not development):

### Use WSGI Server

Instead of Flask development server:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web_ui:APP
```

### Enable HTTPS

Use nginx as reverse proxy with SSL certificate.

### Background Task Queue

For heavy backtests, use RQ (Redis Queue):

```bash
# Start Redis
redis-server

# Start RQ worker
rq worker

# App will automatically use Redis if available
```

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Dashboard with summary |
| `/pair/<pair>` | GET | Detailed analysis for pair |
| `/chart/<filename>` | GET | Serve HTML chart file |
| `/build_status` | GET | Build progress status |

---

## Support & Documentation

### Documentation Files

- **QUICK_START.md** - 5-minute quick reference
- **ANALYSIS_FEATURE.md** - Analysis feature guide
- **STRATEGY_FRAMEWORK.md** - Strategy framework details
- **ARCHITECTURE.md** - System architecture
- **IMPROVEMENTS.md** - Recent improvements

### Code Documentation

All modules have docstrings:

```python
from ichimoku_backtest import run_backtest_from_database
help(run_backtest_from_database)
```

---

## Example Session

```bash
# 1. Start terminal and navigate to project
cd /workspaces/AV

# 2. Activate environment
source .venv/bin/activate

# 3. Start app
python web_ui.py

# Output:
# Starting web server on http://127.0.0.1:5000
# * Running on http://127.0.0.1:5000

# 4. Open browser to http://localhost:5000

# 5. Click "View Details →" on EUR/USD
# 6. Click on any chart to expand
# 7. Read AI analysis and suggestions
# 8. Press Escape to close expanded chart

# 9. Stop server when done (Ctrl+C)
```

---

## Next Steps

1. ✅ Run the app
2. 🔍 Explore the dashboard
3. 📊 View detailed analysis on a pair
4. 💡 Read AI improvement suggestions
5. 🎯 Modify strategy parameters and re-run
6. 📈 Track improvements in metrics

---

**Happy Backtesting!** 🚀

---

*Documentation created: December 6, 2025*
*Application: Ichimoku Trading Backtest System*
*Version: 1.0 (with chart expansion & analysis)*
