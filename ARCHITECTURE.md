# Complete Architecture Guide

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Ichimoku Backtest System                  │
│                      (Modular Design)                         │
└──────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
    ┌─────────────┐  ┌──────────────┐  ┌─────────────┐
    │   Strategy  │  │  Data Layer  │  │     Web     │
    │  Framework  │  │              │  │    UI/API   │
    ├─────────────┤  ├──────────────┤  ├─────────────┤
    │ Base Classes│  │ Fetch Data   │  │  Dashboard  │
    │ Registry    │  │ Database     │  │  Charts     │
    │ Helpers     │  │ yfinance     │  │  Results    │
    └─────────────┘  └──────────────┘  └─────────────┘
          │
    ┌─────┴──────┬────────────┬────────────┐
    │            │            │            │
    ▼            ▼            ▼            ▼
┌───────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
│ Ichimoku  │ │  RSI   │ │  MACD    │ │  Custom  │
│ Strategy  │ │Strategy│ │ Strategy │ │ Strategy │
└───────────┘ └────────┘ └──────────┘ └──────────┘
    │            │            │            │
    └─────┬──────┴────────────┴────────────┘
          │
          ▼
    ┌──────────────────────┐
    │  Backtest Engine     │
    │  (Backtesting lib)   │
    └──────────────────────┘
          │
          ▼
    ┌──────────────────────┐
    │    Test Results      │
    │   (Stats, Trades)    │
    └──────────────────────┘
```

## Component Details

### 1. Strategy Framework (`strategy_framework.py`)

Core abstraction layer for all strategies:

```python
BaseStrategy (abstract)
├── add_indicators()      # Add technical indicators
├── generate_signals()    # Generate trading signals
├── get_parameters()      # Return strategy params
└── Helper Methods
    ├── add_atr()
    ├── add_ema()
    ├── add_sma()
    └── add_rsi()

StrategyRegistry
├── register(id, strategy)
├── get(id)
├── list_strategies()
└── remove(id)

run_backtest_with_strategy(df, strategy, ...)
```

### 2. Strategy Implementations

#### Ichimoku Strategy (`ichimoku_strategy.py`)
```
IchimokuStrategy(BaseStrategy)
├── Parameters:
│   ├── tenkan: 9
│   ├── kijun: 26
│   ├── senkou_b: 52
│   ├── ema_length: 100
│   ├── ichimoku_lookback: 10
│   └── ichimoku_min_confirm: 5
├── Indicators:
│   ├── Ichimoku Cloud
│   ├── EMA Trend Filter
│   ├── ATR (Risk Management)
│   └── Chikou Confirmation
└── Signals:
    ├── Long: Price > Cloud + EMA + Chikou
    └── Short: Price < Cloud + EMA + Chikou
```

#### RSI Strategy (`rsi_strategy.py`)
```
RSIStrategy(BaseStrategy)
├── Parameters:
│   ├── rsi_length: 14
│   ├── oversold: 30
│   └── overbought: 70
├── Indicators:
│   ├── RSI
│   └── ATR
└── Signals:
    ├── Long: RSI crosses above oversold
    └── Short: RSI crosses below overbought
```

### 3. Data Flow

```
User Request
    │
    ▼
┌─────────────────────────┐
│ Load Strategy from      │
│ Registry / Create New   │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Fetch Data from DB      │
│ (fetch_data_from_db)    │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Add Indicators          │
│ (strategy.add_ind...()) │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Generate Signals        │
│ (strategy.generate...)  │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Run Backtest            │
│ (Backtesting library)   │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Return Results          │
│ (stats, df, bt)         │
└─────────────────────────┘
```

### 4. File Dependencies

```
strategy_framework.py
│
├── ichimoku_strategy.py ──────┐
├── rsi_strategy.py ───────────┤
└── (other strategies)          │
                                ▼
                        backtest_runner.py
                                │
                                ├── strategy.py (SignalStrategy)
                                ├── ichimoku.py (indicators)
                                ├── config.py (settings)
                                └── database.py (data loading)
                                
web_ui.py
├── backtest_runner.py
├── ichimoku_strategy.py
├── rsi_strategy.py
├── strategy_framework.py
└── plotting.py
```

### 5. Execution Modes

#### Mode 1: Direct Strategy Execution
```python
from ichimoku_strategy import create_ichimoku_strategy
from backtest_runner import run_backtest_with_custom_strategy

strategy = create_ichimoku_strategy()
stats, df, bt = run_backtest_with_custom_strategy('EUR_USD_daily', strategy)
```

#### Mode 2: Registry-Based Execution
```python
from strategy_framework import get_registry

registry = get_registry()
registry.register('my_ichimoku', create_ichimoku_strategy())
strategy = registry.get('my_ichimoku')
```

#### Mode 3: Batch Execution
```python
from backtest_runner import run_all_pairs_with_strategy

summary = run_all_pairs_with_strategy(strategy)
# Tests on all 5 FX pairs
```

#### Mode 4: Comparative Analysis
```python
from backtest_runner import run_multiple_strategies

results = run_multiple_strategies('EUR_USD_daily', {
    'ichimoku': ichimoku_strategy,
    'rsi': rsi_strategy,
    'macd': macd_strategy,
})
```

## Adding a New Strategy - Step by Step

### Step 1: Create Strategy Class
```python
# File: my_awesome_strategy.py
from strategy_framework import BaseStrategy
import pandas as pd

class MyAwesomeStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name='my_awesome', description='...')
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        # Add your indicators
        df = self.add_atr(df)
        # Add more indicators
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Generate signals
        df['signal'] = 0
        # Your logic
        return df
    
    def get_parameters(self):
        return {...}
```

### Step 2: Test It
```python
from my_awesome_strategy import MyAwesomeStrategy
from backtest_runner import run_backtest_with_custom_strategy

strategy = MyAwesomeStrategy()
stats, df, bt = run_backtest_with_custom_strategy('EUR_USD_daily', strategy)
```

### Step 3: Register (Optional)
```python
from strategy_framework import get_registry
from my_awesome_strategy import MyAwesomeStrategy

registry = get_registry()
registry.register('my_awesome', MyAwesomeStrategy())
```

**That's it! No other code modifications needed.**

## Configuration & Parameters

### Strategy Parameters
Each strategy can be customized:
```python
# Ichimoku with custom parameters
strategy = create_ichimoku_strategy(
    tenkan=7,
    kijun=22,
    senkou_b=44,
    ema_length=50,
)

# RSI with custom parameters
strategy = create_rsi_strategy(
    rsi_length=21,
    oversold=25,
    overbought=75,
)
```

### Backtest Parameters
```python
stats, df, bt = run_backtest_with_custom_strategy(
    table_name='EUR_USD_daily',
    strategy=strategy,
    cash=1_000_000,              # Initial capital
    commission=0.0002,           # 0.02% per trade
    atr_mult_sl=1.5,            # Stop-loss distance
    rr_mult_tp=2.0,             # Risk-reward ratio
)
```

## Testing & Validation

### Verify Framework
```bash
python run_strategy.py  # Run demos
```

### Test Single Strategy
```python
from ichimoku_strategy import create_ichimoku_strategy
from backtest_runner import run_backtest_with_custom_strategy

strategy = create_ichimoku_strategy()
stats, df, bt = run_backtest_with_custom_strategy('EUR_USD_daily', strategy)

assert stats._stats['# Trades'] > 0, "No trades executed"
assert len(df) > 0, "No data returned"
```

### Test All Strategies
```python
from backtest_runner import register_and_run_all_strategies

register_and_run_all_strategies()  # Runs all registered strategies on all pairs
```

## Performance Characteristics

| Operation | Time | Memory |
|-----------|------|--------|
| Load strategy | <1ms | ~5MB |
| Add indicators | 50-200ms | ~50MB |
| Generate signals | 10-50ms | ~10MB |
| Run backtest | 500ms-5s | ~100MB |
| Total per pair | 1-10s | ~200MB |

## Backward Compatibility

### Old Code (Still Works!)
```python
from ichimoku_backtest import run_backtest_from_database
stats, df, bt = run_backtest_from_database('EUR_USD_daily')
```

### New Code (Recommended)
```python
from ichimoku_strategy import create_ichimoku_strategy
from backtest_runner import run_backtest_with_custom_strategy

strategy = create_ichimoku_strategy()
stats, df, bt = run_backtest_with_custom_strategy('EUR_USD_daily', strategy)
```

## Design Principles

1. **Separation of Concerns**
   - Strategies are independent modules
   - Data loading is separate
   - Backtesting is abstracted

2. **Open/Closed Principle**
   - Open for extension (add strategies)
   - Closed for modification (no core changes)

3. **DRY (Don't Repeat Yourself)**
   - Common functionality in BaseStrategy
   - Helper methods for indicators

4. **Single Responsibility**
   - Each class has one purpose
   - Clear, focused interfaces

5. **Easy to Test**
   - Strategies are easily unit testable
   - No global state

## Future Extensions

Potential additions without core changes:

```python
# Walk-forward analysis
from backtest_runner import walk_forward_backtest

# Portfolio optimization
from portfolio import optimize_strategies

# Monte Carlo simulation
from analysis import monte_carlo_analysis

# Parameter optimization
from optimization import grid_search_optimize

# Real-time trading
from trading import LiveTrader
```

All can be added as new modules without touching existing code!

## Summary

- **Framework**: Clean abstraction for all strategies
- **Registry**: Centralized strategy management
- **Execution**: Flexible modes (direct, batch, comparative)
- **Extension**: Add strategies without modifying core
- **Testing**: Built-in demos and validation
- **Documentation**: Comprehensive guides and examples

This architecture enables rapid strategy development while maintaining stability and backward compatibility.

---

**Ready to build your trading empire!** 🚀
