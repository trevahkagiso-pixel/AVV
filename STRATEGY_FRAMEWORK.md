# Strategy Framework & Backtesting Architecture

## Overview

This module provides a **modular, extensible framework** for building and testing trading strategies without modifying existing code. It separates concerns and makes it trivial to add new strategies.

## Architecture

### Core Components

```
strategy_framework.py          - Abstract base class and registry
├── BaseStrategy              - Abstract class for all strategies
├── StrategyRegistry          - Manages registered strategies
└── run_backtest_with_strategy() - Unified backtest runner

ichimoku_strategy.py           - Ichimoku Cloud strategy implementation
rsi_strategy.py                - RSI strategy (example)
backtest_runner.py             - High-level backtest orchestration
```

## Key Concepts

### 1. **BaseStrategy**
All strategies inherit from `BaseStrategy` and must implement:
- `add_indicators(df)` - Add technical indicators to dataframe
- `generate_signals(df)` - Generate trading signals (1=long, -1=short, 0=none)
- `get_parameters()` - Return strategy parameters

### 2. **StrategyRegistry**
Centralized registry for managing strategies:
- Register multiple strategies
- Retrieve strategies by ID
- List all available strategies

### 3. **Modular Design**
- Strategies are completely isolated
- Adding a new strategy does **NOT** modify existing code
- All strategies use the same backtest engine

## Usage Examples

### Example 1: Run Backtest with Ichimoku Strategy

```python
from ichimoku_strategy import create_ichimoku_strategy
from backtest_runner import run_backtest_with_custom_strategy

# Create strategy
strategy = create_ichimoku_strategy()

# Run backtest on a single pair
stats, df, bt = run_backtest_with_custom_strategy(
    table_name='EUR_USD_daily',
    strategy=strategy,
)

print(f"Return: {stats._stats['Return [%]']:.2f}%")
print(f"Win Rate: {stats._stats['Win Rate [%]']:.2f}%")
```

### Example 2: Run All Pairs with RSI Strategy

```python
from rsi_strategy import create_rsi_strategy
from backtest_runner import run_all_pairs_with_strategy

# Create strategy
strategy = create_rsi_strategy(rsi_length=21, oversold=25, overbought=75)

# Run on all currency pairs
df_summary = run_all_pairs_with_strategy(strategy)
print(df_summary)
```

### Example 3: Compare Multiple Strategies

```python
from ichimoku_strategy import create_ichimoku_strategy
from rsi_strategy import create_rsi_strategy
from backtest_runner import run_multiple_strategies

strategies = {
    'ichimoku': create_ichimoku_strategy(),
    'rsi': create_rsi_strategy(),
}

results = run_multiple_strategies('EUR_USD_daily', strategies)
# results['ichimoku'] -> (stats, df, bt)
# results['rsi'] -> (stats, df, bt)
```

### Example 4: Register and Use Strategy Registry

```python
from strategy_framework import get_registry
from ichimoku_strategy import create_ichimoku_strategy
from rsi_strategy import create_rsi_strategy

# Get global registry
registry = get_registry()

# Register strategies
registry.register('ichimoku', create_ichimoku_strategy())
registry.register('ichimoku_aggressive', create_ichimoku_strategy(ema_length=50))
registry.register('rsi', create_rsi_strategy())

# List strategies
for sid, desc in registry.list_strategies().items():
    print(f"{sid}: {desc}")

# Retrieve strategy
strategy = registry.get('ichimoku')
```

## Creating a New Strategy

Adding a new strategy is **simple and non-intrusive**:

### Step 1: Create Strategy File (e.g., `macd_strategy.py`)

```python
from strategy_framework import BaseStrategy
import pandas as pd

class MACDStrategy(BaseStrategy):
    """MACD-based trading strategy."""
    
    def __init__(self, fast=12, slow=26, signal=9):
        super().__init__(
            name='macd',
            description=f'MACD strategy ({fast}/{slow}/{signal})'
        )
        self.fast = fast
        self.slow = slow
        self.signal = signal
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add MACD indicators."""
        import pandas_ta as ta
        
        df['MACD'] = ta.macd(df['Close'], fast=self.fast, slow=self.slow)[0]
        df['MACD_Signal'] = ta.macd(df['Close'], fast=self.fast, slow=self.slow)[1]
        df = self.add_atr(df)  # Add ATR for risk management
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate MACD crossover signals."""
        df['signal'] = 0
        
        for i in range(1, len(df)):
            macd_prev = df['MACD'].iloc[i-1]
            signal_prev = df['MACD_Signal'].iloc[i-1]
            macd_curr = df['MACD'].iloc[i]
            signal_curr = df['MACD_Signal'].iloc[i]
            
            # Long: MACD crosses above signal
            if macd_prev < signal_prev and macd_curr > signal_curr:
                df.loc[df.index[i], 'signal'] = 1
            
            # Short: MACD crosses below signal
            elif macd_prev > signal_prev and macd_curr < signal_curr:
                df.loc[df.index[i], 'signal'] = -1
        
        return df
    
    def get_parameters(self):
        return {'fast': self.fast, 'slow': self.slow, 'signal': self.signal}
```

### Step 2: Use It Immediately

```python
from macd_strategy import MACDStrategy
from backtest_runner import run_backtest_with_custom_strategy

strategy = MACDStrategy(fast=12, slow=26, signal=9)
stats, df, bt = run_backtest_with_custom_strategy('EUR_USD_daily', strategy)
```

**No changes needed to existing code!**

## Helper Methods in BaseStrategy

All strategies inherit these convenience methods:

```python
# Add technical indicators
df = strategy.add_atr(df, length=14)
df = strategy.add_ema(df, column='Close', length=50, name='EMA_50')
df = strategy.add_sma(df, column='Close', length=200)
df = strategy.add_rsi(df, column='Close', length=14)
```

## File Structure

```
.
├── strategy_framework.py       # Core framework (BaseStrategy, StrategyRegistry)
├── ichimoku_strategy.py        # Ichimoku implementation
├── rsi_strategy.py             # RSI implementation (example)
├── macd_strategy.py            # (optional) MACD implementation
├── backtest_runner.py          # High-level orchestration
├── strategy.py                 # SignalStrategy (do not modify)
├── ichimoku_backtest.py        # Legacy (for backward compatibility)
├── web_ui.py                   # Web dashboard (uses strategies)
└── requirements.txt
```

## Migration Guide

### Old Code (Ichimoku-only)
```python
from ichimoku_backtest import run_backtest_from_database

stats, df, bt = run_backtest_from_database('EUR_USD_daily')
```

### New Code (Flexible, framework-based)
```python
from ichimoku_strategy import create_ichimoku_strategy
from backtest_runner import run_backtest_with_custom_strategy

strategy = create_ichimoku_strategy()
stats, df, bt = run_backtest_with_custom_strategy('EUR_USD_daily', strategy)
```

Both still work! The framework is backward compatible.

## Best Practices

1. **One strategy per file** - Easier to maintain and understand
2. **Inherit from BaseStrategy** - Ensures consistent interface
3. **Use factory functions** - Makes instantiation cleaner
4. **Add comprehensive docstrings** - Help future developers
5. **Test on multiple pairs** - Ensure robustness
6. **Version your strategies** - Create variants (aggressive, conservative)

## Advanced Usage

### Multiple Strategies on Web UI

```python
# In web_ui.py
from strategy_framework import get_registry
from ichimoku_strategy import create_ichimoku_strategy
from rsi_strategy import create_rsi_strategy

registry = get_registry()
registry.register('ichimoku', create_ichimoku_strategy())
registry.register('rsi', create_rsi_strategy())

# Web UI automatically discovers and runs all registered strategies
```

### Optimization

```python
from ichimoku_strategy import create_ichimoku_strategy
from backtest_runner import run_backtest_with_custom_strategy

# Create strategy with custom parameters
strategy = create_ichimoku_strategy(
    ema_length=50,
    tenkan=7,
    kijun=22,
)

# Backtest with specific parameters
stats, df, bt = run_backtest_with_custom_strategy(
    'EUR_USD_daily',
    strategy,
    atr_mult_sl=2.0,  # Custom risk management
    rr_mult_tp=3.0,
)
```

## Troubleshooting

### Q: My strategy doesn't work!
A: Check that:
- `add_indicators()` adds required columns (especially 'signal')
- `generate_signals()` sets 'signal' column (1, -1, or 0)
- All NaN values are handled before backtest

### Q: How do I add a custom indicator?
A: Use `pandas_ta` or raw pandas operations in `add_indicators()`:
```python
import pandas_ta as ta
df['CustomIndicator'] = ta.your_indicator(...)
```

### Q: Can I run multiple strategies in parallel?
A: Yes, use `run_multiple_strategies()` or implement threading externally.

## See Also

- `strategy_framework.py` - Core classes and utilities
- `ichimoku_strategy.py` - Reference implementation
- `rsi_strategy.py` - Simple example
- `backtest_runner.py` - Orchestration and examples

---

**Happy strategy building!** 🚀
