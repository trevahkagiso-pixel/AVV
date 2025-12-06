# Quick Start Guide - Strategy Framework

## 1. Verify Installation

```bash
source .venv/bin/activate
python run_strategy.py
```

## 2. Run Single Backtest

```python
from ichimoku_strategy import create_ichimoku_strategy
from backtest_runner import run_backtest_with_custom_strategy

strategy = create_ichimoku_strategy()
stats, df, bt = run_backtest_with_custom_strategy('EUR_USD_daily', strategy)
print(f"Return: {stats._stats['Return [%]']:.2f}%")
```

## 3. Test All Pairs

```python
from ichimoku_strategy import create_ichimoku_strategy
from backtest_runner import run_all_pairs_with_strategy

strategy = create_ichimoku_strategy()
summary = run_all_pairs_with_strategy(strategy)
print(summary)
```

## 4. Compare Strategies

```python
from backtest_runner import run_multiple_strategies
from ichimoku_strategy import create_ichimoku_strategy
from rsi_strategy import create_rsi_strategy

strategies = {
    'ichimoku': create_ichimoku_strategy(),
    'rsi': create_rsi_strategy(),
}

results = run_multiple_strategies('EUR_USD_daily', strategies)
```

## 5. Create Your Own Strategy

### File: my_strategy.py
```python
from strategy_framework import BaseStrategy
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name='my_strategy')
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self.add_atr(df)
        df = self.add_rsi(df)
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        # Your signal logic
        return df
```

### Use It:
```python
from my_strategy import MyStrategy
from backtest_runner import run_backtest_with_custom_strategy

strategy = MyStrategy()
stats, df, bt = run_backtest_with_custom_strategy('EUR_USD_daily', strategy)
```

## 6. Using the Registry

```python
from strategy_framework import get_registry
from ichimoku_strategy import create_ichimoku_strategy

registry = get_registry()
registry.register('ichimoku', create_ichimoku_strategy())

# Later...
strategy = registry.get('ichimoku')
```

## Files Overview

| File | Purpose |
|------|---------|
| `strategy_framework.py` | Core framework (BaseStrategy, Registry) |
| `ichimoku_strategy.py` | Ichimoku as a reusable strategy |
| `rsi_strategy.py` | RSI strategy (example) |
| `backtest_runner.py` | High-level backtest orchestration |
| `run_strategy.py` | Quick-start demos |
| `STRATEGY_FRAMEWORK.md` | Full documentation |
| `IMPROVEMENTS.md` | Detailed improvements & architecture |

## Key Features

✅ **Modular** - Each strategy is independent  
✅ **Extensible** - Easy to add new strategies  
✅ **Backward Compatible** - Old code still works  
✅ **Well Documented** - Comprehensive guides  
✅ **Easy to Test** - Quick-start demos included  

---

For detailed documentation, see `STRATEGY_FRAMEWORK.md`
