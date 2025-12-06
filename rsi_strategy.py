"""
RSI Strategy Implementation.

A simple RSI-based trading strategy as an example of how to add new strategies
to the framework without modifying existing code.

Usage:
    from rsi_strategy import RSIStrategy
    from strategy_framework import run_backtest_with_strategy
    
    df = load_data(...)
    strategy = RSIStrategy(rsi_length=14, oversold=30, overbought=70)
    stats, df, bt = run_backtest_with_strategy(df, strategy)
"""

from typing import Dict, Any
import pandas as pd
import pandas_ta as ta

from strategy_framework import BaseStrategy


class RSIStrategy(BaseStrategy):
    """
    Simple RSI (Relative Strength Index) overbought/oversold strategy.
    
    Entry Rules:
    - Long: RSI crosses above oversold level
    - Short: RSI crosses below overbought level
    
    Exit Rules:
    - Long: RSI reaches overbought level or ATR stop-loss
    - Short: RSI reaches oversold level or ATR stop-loss
    
    Parameters:
    - rsi_length: RSI period (default 14)
    - oversold: Oversold threshold (default 30)
    - overbought: Overbought threshold (default 70)
    """
    
    def __init__(
        self,
        rsi_length: int = 14,
        oversold: float = 30,
        overbought: float = 70,
        atr_length: int = 14,
    ):
        """
        Initialize RSI strategy.
        
        Args:
            rsi_length: RSI period
            oversold: Oversold threshold (0-100)
            overbought: Overbought threshold (0-100)
            atr_length: ATR period for risk management
        """
        super().__init__(
            name='rsi',
            description=f'RSI strategy (period={rsi_length}, OS={oversold}, OB={overbought})'
        )
        
        self.rsi_length = rsi_length
        self.oversold = oversold
        self.overbought = overbought
        self.atr_length = atr_length
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add RSI and ATR indicators.
        
        Args:
            df: DataFrame with OHLC
        
        Returns:
            DataFrame with RSI and ATR
        """
        print(f"   📊 Adding RSI (length={self.rsi_length})")
        df = self.add_rsi(df, column='Close', length=self.rsi_length)
        
        print(f"   ⚠️  Adding ATR (length={self.atr_length})")
        df = self.add_atr(df, length=self.atr_length)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate RSI-based signals.
        
        Signal logic:
        - Long (1): RSI crosses above oversold
        - Short (-1): RSI crosses below overbought
        - None (0): Default
        
        Args:
            df: DataFrame with RSI already added
        
        Returns:
            DataFrame with 'signal' column
        """
        print(f"   🎯 Generating RSI signals (OS={self.oversold}, OB={self.overbought})")
        
        df['signal'] = 0
        
        for i in range(1, len(df)):
            rsi_prev = df['RSI'].iloc[i-1]
            rsi_curr = df['RSI'].iloc[i]
            
            # Long: RSI crosses above oversold
            if rsi_prev <= self.oversold and rsi_curr > self.oversold:
                df.loc[df.index[i], 'signal'] = 1
            
            # Short: RSI crosses below overbought
            elif rsi_prev >= self.overbought and rsi_curr < self.overbought:
                df.loc[df.index[i], 'signal'] = -1
        
        return df
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        return {
            'rsi_length': self.rsi_length,
            'oversold': self.oversold,
            'overbought': self.overbought,
            'atr_length': self.atr_length,
        }


def create_rsi_strategy(**kwargs) -> RSIStrategy:
    """
    Factory function to create RSI strategy.
    
    Args:
        **kwargs: Any RSIStrategy parameter
    
    Returns:
        RSIStrategy instance
    
    Example:
        strategy = create_rsi_strategy(rsi_length=21, oversold=25)
    """
    return RSIStrategy(**kwargs)
