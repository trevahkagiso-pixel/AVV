"""
Strategy Framework - Base classes and interfaces for trading strategies.

This module provides the foundation for creating and managing multiple trading strategies
in a modular, extensible way. All strategies inherit from BaseStrategy and implement
the required methods.

Usage:
    from strategy_framework import BaseStrategy, StrategyRegistry, run_backtest_with_strategy
    
    class MyStrategy(BaseStrategy):
        def add_indicators(self, df):
            # Add custom indicators
            return df
        
        def generate_signals(self, df):
            # Generate trading signals
            return df
    
    registry = StrategyRegistry()
    registry.register('my_strategy', MyStrategy())
    results = run_backtest_with_strategy(df, 'my_strategy')
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, Any
import pandas as pd
import numpy as np
from backtesting import Backtest


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Subclasses must implement:
    - add_indicators(): Add technical indicators to the dataframe
    - generate_signals(): Generate trading signals (1=long, -1=short, 0=none)
    - get_parameters(): Return strategy parameters
    - get_description(): Return strategy description
    """
    
    def __init__(self, name: str, description: str = ""):
        """
        Initialize base strategy.
        
        Args:
            name: Strategy identifier (e.g., 'ichimoku', 'rsi', 'macd')
            description: Human-readable description
        """
        self.name = name
        self.description = description or f"Strategy: {name}"
    
    @abstractmethod
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add technical indicators to the dataframe.
        
        Args:
            df: DataFrame with columns: Open, High, Low, Close, (Volume)
        
        Returns:
            DataFrame with added indicator columns
        """
        pass
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on indicators.
        
        Args:
            df: DataFrame with indicators already added
        
        Returns:
            DataFrame with 'signal' column (1=long, -1=short, 0=none)
        """
        pass
    
    def add_atr(self, df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
        """
        Add Average True Range (ATR) for risk management.
        
        Args:
            df: DataFrame with Open, High, Low, Close
            length: ATR period (default 14)
        
        Returns:
            DataFrame with ATR column
        """
        import pandas_ta as ta
        df['ATR'] = ta.atr(high=df['High'], low=df['Low'], close=df['Close'], length=length)
        return df
    
    def add_ema(self, df: pd.DataFrame, column: str, length: int, name: str = None) -> pd.DataFrame:
        """
        Add Exponential Moving Average.
        
        Args:
            df: DataFrame
            column: Column to calculate EMA on (e.g., 'Close')
            length: EMA period
            name: Name of output column (default: f'EMA_{length}')
        
        Returns:
            DataFrame with EMA column
        """
        import pandas_ta as ta
        col_name = name or f'EMA_{length}'
        df[col_name] = ta.ema(df[column], length=length)
        return df
    
    def add_sma(self, df: pd.DataFrame, column: str, length: int, name: str = None) -> pd.DataFrame:
        """
        Add Simple Moving Average.
        
        Args:
            df: DataFrame
            column: Column to calculate SMA on
            length: SMA period
            name: Name of output column (default: f'SMA_{length}')
        
        Returns:
            DataFrame with SMA column
        """
        import pandas_ta as ta
        col_name = name or f'SMA_{length}'
        df[col_name] = ta.sma(df[column], length=length)
        return df
    
    def add_rsi(self, df: pd.DataFrame, column: str = 'Close', length: int = 14, name: str = None) -> pd.DataFrame:
        """
        Add Relative Strength Index.
        
        Args:
            df: DataFrame
            column: Column to calculate RSI on
            length: RSI period
            name: Name of output column (default: 'RSI')
        
        Returns:
            DataFrame with RSI column
        """
        import pandas_ta as ta
        col_name = name or 'RSI'
        df[col_name] = ta.rsi(df[column], length=length)
        return df
    
    def get_parameters(self) -> Dict[str, Any]:
        """
        Get strategy parameters as a dictionary.
        
        Returns:
            Dictionary of parameter names and values
        """
        return {}
    
    def get_description(self) -> str:
        """Get strategy description."""
        return self.description
    
    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(name='{self.name}')"


class StrategyRegistry:
    """
    Registry for managing multiple strategies.
    
    Allows registration, retrieval, and listing of available strategies.
    """
    
    def __init__(self):
        """Initialize the strategy registry."""
        self._strategies: Dict[str, BaseStrategy] = {}
    
    def register(self, strategy_id: str, strategy: BaseStrategy) -> None:
        """
        Register a strategy.
        
        Args:
            strategy_id: Unique identifier for the strategy
            strategy: BaseStrategy instance
        
        Raises:
            ValueError: If strategy_id already registered or invalid
            TypeError: If strategy is not BaseStrategy instance
        """
        if not isinstance(strategy, BaseStrategy):
            raise TypeError(f"Strategy must be BaseStrategy instance, got {type(strategy)}")
        
        if strategy_id in self._strategies:
            print(f"⚠️  Overwriting existing strategy: {strategy_id}")
        
        self._strategies[strategy_id] = strategy
        print(f"✅ Registered strategy: {strategy_id}")
    
    def get(self, strategy_id: str) -> Optional[BaseStrategy]:
        """
        Get a strategy by ID.
        
        Args:
            strategy_id: Strategy identifier
        
        Returns:
            BaseStrategy instance or None if not found
        """
        return self._strategies.get(strategy_id)
    
    def list_strategies(self) -> Dict[str, str]:
        """
        List all registered strategies with descriptions.
        
        Returns:
            Dictionary of {strategy_id: description}
        """
        return {
            sid: strategy.get_description()
            for sid, strategy in self._strategies.items()
        }
    
    def remove(self, strategy_id: str) -> bool:
        """
        Remove a strategy from registry.
        
        Args:
            strategy_id: Strategy identifier
        
        Returns:
            True if removed, False if not found
        """
        if strategy_id in self._strategies:
            del self._strategies[strategy_id]
            return True
        return False
    
    def __len__(self) -> int:
        """Number of registered strategies."""
        return len(self._strategies)
    
    def __repr__(self) -> str:
        """String representation."""
        strats = ", ".join(self._strategies.keys())
        return f"StrategyRegistry({strats})"


def run_backtest_with_strategy(
    df: pd.DataFrame,
    strategy: BaseStrategy,
    cash: float = 1_000_000,
    commission: float = 0.0002,
    atr_mult_sl: float = 1.5,
    rr_mult_tp: float = 2.0,
) -> Tuple[Any, pd.DataFrame, Any]:
    """
    Run a backtest with a given strategy.
    
    Args:
        df: DataFrame with OHLC data (Open, High, Low, Close)
        strategy: BaseStrategy instance
        cash: Initial cash for backtest
        commission: Commission per trade (decimal)
        atr_mult_sl: ATR multiplier for stop-loss
        rr_mult_tp: Risk-reward ratio for take-profit
    
    Returns:
        tuple: (stats, df_with_signals, bt) where
            - stats: Backtest statistics
            - df_with_signals: DataFrame with all indicators and signals
            - bt: Backtest object
    """
    from strategy import SignalStrategy
    
    print(f"\n{'='*70}")
    print(f"Running Backtest: {strategy.name}")
    print(f"{'='*70}")
    
    # Add indicators
    print(f"📈 Adding indicators...")
    df = strategy.add_indicators(df.copy())
    
    # Generate signals
    print(f"📊 Generating signals...")
    df = strategy.generate_signals(df)
    
    # Drop NaN rows
    df = df.dropna()
    print(f"   {len(df)} valid data points")
    
    # Run backtest
    print(f"🎯 Running backtest...")
    bt = Backtest(
        df,
        SignalStrategy,
        cash=cash,
        commission=commission,
        exclusive_orders=True
    )
    
    # Set strategy parameters
    bt.run(atr_mult_sl=atr_mult_sl, rr_mult_tp=rr_mult_tp)
    stats = bt.optimize(
        atr_mult_sl=[atr_mult_sl],
        rr_mult_tp=[rr_mult_tp],
        maximize='Return [%]',
        constraint=None,
        verbose=False
    )
    
    print(f"\n✅ Backtest Results for {strategy.name}:")
    print(f"   Return: {stats._stats['Return [%]']:.2f}%")
    print(f"   Max Drawdown: {stats._stats['Max. Drawdown [%]']:.2f}%")
    print(f"   Win Rate: {stats._stats['Win Rate [%]']:.2f}%")
    print(f"   # Trades: {int(stats._stats['# Trades'])}")
    print(f"   Exposure Time: {stats._stats['Exposure Time [%]']:.2f}%")
    
    return stats, df, bt


# Global registry instance
_global_registry = StrategyRegistry()


def get_registry() -> StrategyRegistry:
    """Get the global strategy registry."""
    return _global_registry
