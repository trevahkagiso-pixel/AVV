# Order Block (OB) Strategy Documentation

## Overview

The Order Block strategy implements a **price-action based trading system** that identifies bullish and bearish order blocks using 3-bar fractals and break of structure (BOS) detection.

**Strategy Type**: Intrabar Entry with Partial Risk Management  
**Timeframe**: Daily (adjustable)  
**Asset Classes**: Forex, Stocks, Commodities  
**Risk/Reward Profile**: Conservative 1R partials → Breakeven → 2R remaining

---

## 🎯 Core Logic

### 1. Order Block Detection

An **Order Block (OB)** is identified through:

**Bullish OB**:
- A 3-bar pivot high is established (bar with highest high between its neighbors)
- New bar breaks above this pivot high (Break of Structure)
- The most recent bearish candle (close < open) within the last 10 bars is marked as the OB
- OB mid-body = (OB_open + OB_close) / 2

**Bearish OB**:
- A 3-bar pivot low is established (bar with lowest low between its neighbors)
- New bar breaks below this pivot low
- The most recent bullish candle (close > open) within the last 10 bars is marked as the OB
- OB mid-body = (OB_open + OB_close) / 2

### 2. Entry Conditions

After BOS detection, the strategy waits up to 60 bars for a **mitigation entry**:

**Bullish Entry**:
- Price touches (lows <= OB mid-body) → "Mitigates" the order block
- Closes with bullish confirmation (close > open, close > OB mid-body)
- EMA(50) > Close (uptrend confirmation)
- ATR(14) >= threshold (0.0060 in price units, ~60 pips for GBP/USD)

**Bearish Entry**:
- Price touches (highs >= OB mid-body) → "Mitigates" the order block
- Closes with bearish confirmation (close < open, close < OB mid-body)
- EMA(50) < Close (downtrend confirmation)
- ATR(14) >= threshold

### 3. Risk Management

**Stop Loss**:
- Bullish: OB low
- Bearish: OB high

**Initial Risk (R)**:
- R = Entry - Stop (bullish) or Stop - Entry (bearish)

**Profit Targets**:
1. **First Target (1R)**: Entry + 1.0×R → Close 50% position, move stop to breakeven
2. **Second Target (2R)**: Entry + 2.0×R → Close remaining 50%

**Stop-First Rule**:
- If stop and target are both touched in the same bar, stop is executed first (conservative)

---

## 📊 Implementation

### Core Files

| File | Purpose |
|------|---------|
| `ob_refined_strategy.py` | Core OB detection + backtest engine |
| `ob_ui.py` | Flask dashboard for OB analysis |
| `database.py` | SQLite data loading |
| `plotting.py` | Plotly chart rendering |

### Key Functions

#### `detect_order_blocks(df, lookback=10) → DataFrame`
Identifies all order blocks in a price series.

**Input**:
- `df`: DataFrame with columns ['high', 'low', 'open', 'close']
- `lookback`: bars to search for OB candle after BOS

**Output**:
- DataFrame with columns:
  - `type`: 'Bullish' or 'Bearish'
  - `ob_date`: Date of the OB candle
  - `bos_date`: Date of the break of structure
  - `ob_open`, `ob_close`, `ob_high`, `ob_low`: OHLC of OB candle

#### `refined_backtest(df, ob, entry_wait_bars=60, atr_threshold=0.0060) → DataFrame`
Executes backtest with entry, exit, and position management.

**Input**:
- `df`: DataFrame with ['high', 'low', 'open', 'close', 'ema', 'atr']
- `ob`: DataFrame from `detect_order_blocks()`
- `entry_wait_bars`: Max bars to wait for mitigation entry
- `atr_threshold`: Minimum ATR for trade qualification (in price units)

**Output**:
- DataFrame with trade records:
  - `type`: Bullish/Bearish
  - `ob_date`, `bos_date`, `entry_date`: Timestamp columns
  - `entry`, `stop`, `R`: Entry price, stop price, risk in price units
  - `outcome_R`: Final P&L in risk multiples

#### `compute_indicators(df, ema_span=50, atr_span=14) → DataFrame`
Adds EMA and ATR to the price data.

**Calculations**:
- EMA: Exponential moving average with span parameter
- ATR: Average True Range using true range components

---

## 📈 Performance Metrics

The backtest returns these statistics:

```python
{
    "trades": 15,           # Total number of trades
    "wins": 9,              # Trades with outcome_R > 0
    "losses": 6,            # Trades with outcome_R <= 0
    "total_pnl": 6.5,       # Sum of all outcome_R (in R)
    "win_rate": 60.0,       # wins / trades * 100
    "avg_r": 0.433,         # total_pnl / trades
}
```

**Interpretation**:
- **Win Rate**: % of profitable trades (ideally >50%)
- **Avg R**: Average R-multiple per trade (ideally >1.0 for positive expectancy)
- **Total P&L**: Cumulative R gained/lost across all trades

---

## 🎨 Visualization

### OB Detection Chart

The `plot_ob_signals()` function renders:
- **Candlesticks**: OHLC price action
- **EMA(50)**: Blue dashed line for trend confirmation
- **Bullish OBs**: Green triangle markers at OB low
- **Bearish OBs**: Red triangle markers at OB high

This helps visually confirm the strategy logic.

---

## ⚙️ Configuration

### Adjustable Parameters

```python
# In ob_ui.py run_ob_backtest_for_pair()
trades = refined_backtest(
    df, ob,
    entry_wait_bars=60,     # Increase to wait longer for entry
    atr_threshold=0.0060,   # Increase to be more selective
    stop_on_tie=True        # Keep True for conservative exits
)
```

### EMA & ATR Spans

```python
# In ob_ui.py run_ob_backtest_for_pair()
df = compute_indicators(df, ema_span=50, atr_span=14)
```

### OB Lookback

```python
# In ob_ui.py run_ob_backtest_for_pair()
ob = detect_order_blocks(df, lookback=10)  # Increase to find older OBs
```

---

## 🔍 Common Adjustments

### To Be More Selective (Fewer Trades)
- Increase `atr_threshold` (e.g., 0.0080)
- Decrease `entry_wait_bars` (e.g., 30)
- Increase `lookback` (e.g., 15)

### To Be More Aggressive (More Trades)
- Decrease `atr_threshold` (e.g., 0.0040)
- Increase `entry_wait_bars` (e.g., 90)
- Decrease `lookback` (e.g., 5)

### To Reduce Whipsaws
- Increase EMA span (e.g., 100 instead of 50)
- Increase ATR span (e.g., 21 instead of 14)
- Tighten entry confirmation (require 2+ bars above OB mid)

---

## 📊 Historical Context

**Order Blocks** are based on the **Smart Money Concept (SMC)** framework:
- Identifies where institutional liquidity may have been swept
- Uses fractals + BOS for objective entry triggers
- Combines with trend bias (EMA) for directional confirmation
- Implements risk-managed position sizing (partials + BE + 2R)

This strategy is suited for traders who:
- Prefer price-action over indicators
- Like clear, objective entry/exit rules
- Want controlled risk with defined R-multiples
- Trade daily or longer timeframes

---

## 🚀 Running OB Backtest

### Via UI Dashboard
1. Go to http://127.0.0.1:5001
2. Click "View Details" on any pair
3. See trade log, P&L, and detection chart

### Via Python Script
```python
from ob_refined_strategy import (
    compute_indicators,
    detect_order_blocks,
    refined_backtest
)
from database import load_from_database

# Load data
df = load_from_database("EUR_USD_daily", "sqlite:///forex.db")
df.columns = ['o', 'h', 'l', 'c'] = df.columns.str.lower()
df = df[['open', 'high', 'low', 'close']]

# Add indicators
df = compute_indicators(df)

# Detect OBs
ob = detect_order_blocks(df, lookback=10)

# Run backtest
trades = refined_backtest(df, ob)

# Analyze
print(f"Total trades: {len(trades)}")
print(f"Win rate: {(trades['outcome_R'] > 0).sum() / len(trades) * 100:.1f}%")
print(f"Total P&L: {trades['outcome_R'].sum():.2f}R")
```

---

## 📝 Example Trade

**Bullish OB Trade**:
1. **2024-08-15**: 3-bar pivot high formed at 1.1250
2. **2024-08-20**: New candle breaks above 1.1250 → BOS detected
3. **2024-08-20 to 2024-09-10**: Look for mitigation within 60 bars
4. **2024-09-05**: Price pulls back, touches OB mid-body (1.1100)
5. **2024-09-06**: Bullish candle closes above mid-body, EMA filter OK, ATR OK → **Entry at 1.1100**
6. **Stop**: OB low = 1.1050 → **Risk = 50 pips**
7. **Target 1**: 1.1100 + 50 = 1.1150 → Close 50%, move stop to 1.1100
8. **Target 2**: 1.1100 + 100 = 1.1200 → Close remaining 50%
9. **Result**: +1R on first half, +2R on second half = **+1.5R total**

---

## 🎓 Further Reading

- **Smart Money Concepts (SMC)**: Institutional order flow analysis
- **3-Bar Fractals**: Classic swing point identification
- **Break of Structure (BOS)**: Entry trigger for institutional traders
- **Risk/Reward Ratios**: Position sizing based on R-multiples
- **EMA Trend Bias**: Simple trend confirmation filter

Enjoy your Order Block strategy dashboard! 📈
