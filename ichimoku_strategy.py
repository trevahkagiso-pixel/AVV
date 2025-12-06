"""
Ichimoku Strategy Implementation.

A trading strategy based on the Ichimoku Cloud indicator with EMA trend filter.
Easily integrable with the strategy framework for modular backtesting.
"""

from typing import Dict, Any
import pandas as pd
import pandas_ta as ta

from strategy_framework import BaseStrategy
from ichimoku import (
    add_ichimoku,
    add_ema_signal,
    create_ichimoku_signal,
    TENKAN, KIJUN, SENKOU_B, ATR_LEN
)


class IchimokuStrategy(BaseStrategy):
    """
    Trading strategy using Ichimoku Cloud with EMA trend filter.
    
    Parameters:
    - tenkan: Tenkan line period (default 9)
    - kijun: Kijun line period (default 26)
    - senkou_b: Senkou B line period (default 52)
    - ema_length: EMA trend filter period (default 100)
    - ema_back_candles: Lookback candles for EMA signal (default 7)
    - ichimoku_lookback: Cloud confirmation lookback (default 10)
    - ichimoku_min_confirm: Min bars required above/below cloud (default 5)
    """
    
    def __init__(
        self,
        tenkan: int = TENKAN,
        kijun: int = KIJUN,
        senkou_b: int = SENKOU_B,
        ema_length: int = 100,
        ema_back_candles: int = 7,
        ichimoku_lookback: int = 10,
        ichimoku_min_confirm: int = 5,
        atr_length: int = ATR_LEN,
    ):
        """
        Initialize Ichimoku strategy.
        
        Args:
            tenkan: Tenkan line period
            kijun: Kijun line period
            senkou_b: Senkou B line period
            ema_length: EMA trend filter length
            ema_back_candles: Lookback candles for EMA
            ichimoku_lookback: Cloud confirmation lookback
            ichimoku_min_confirm: Minimum cloud confirmation bars
            atr_length: ATR period for risk management
        """
        super().__init__(
            name='ichimoku',
            description='Ichimoku Cloud strategy with EMA trend filter'
        )
        
        self.tenkan = tenkan
        self.kijun = kijun
        self.senkou_b = senkou_b
        self.ema_length = ema_length
        self.ema_back_candles = ema_back_candles
        self.ichimoku_lookback = ichimoku_lookback
        self.ichimoku_min_confirm = ichimoku_min_confirm
        self.atr_length = atr_length
    
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add Ichimoku Cloud indicators and ATR to the dataframe.
        
        Args:
            df: DataFrame with Open, High, Low, Close
        
        Returns:
            DataFrame with Ichimoku indicators
        """
        print(f"   📈 Adding Ichimoku Cloud indicators (T={self.tenkan}, K={self.kijun}, B={self.senkou_b})")
        df = add_ichimoku(
            df,
            tenkan=self.tenkan,
            kijun=self.kijun,
            senkou_b=self.senkou_b
        )
        
        print(f"   📊 Adding EMA trend filter (length={self.ema_length})")
        df = add_ema_signal(
            df,
            ema_length=self.ema_length,
            back_candles=self.ema_back_candles
        )
        
        print(f"   ⚠️  Adding ATR for risk management (length={self.atr_length})")
        df = self.add_atr(df, length=self.atr_length)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate trading signals based on Ichimoku + EMA.
        
        Signal logic:
        - Long: Price above cloud, EMA bullish, Chikou confirmation
        - Short: Price below cloud, EMA bearish, Chikou confirmation
        
        Args:
            df: DataFrame with Ichimoku indicators already added
        
        Returns:
            DataFrame with 'signal' column (1=long, -1=short, 0=none)
        """
        print(f"   🎯 Generating Ichimoku signals (lookback={self.ichimoku_lookback}, min_confirm={self.ichimoku_min_confirm})")
        df = create_ichimoku_signal(
            df,
            lookback_window=self.ichimoku_lookback,
            min_confirm=self.ichimoku_min_confirm
        )
        return df
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        return {
            'tenkan': self.tenkan,
            'kijun': self.kijun,
            'senkou_b': self.senkou_b,
            'ema_length': self.ema_length,
            'ema_back_candles': self.ema_back_candles,
            'ichimoku_lookback': self.ichimoku_lookback,
            'ichimoku_min_confirm': self.ichimoku_min_confirm,
            'atr_length': self.atr_length,
        }


def create_ichimoku_strategy(**kwargs) -> IchimokuStrategy:
    """
    Factory function to create Ichimoku strategy with custom parameters.
    
    Args:
        **kwargs: Any IchimokuStrategy parameter
    
    Returns:
        IchimokuStrategy instance
    
    Example:
        strategy = create_ichimoku_strategy(ema_length=50, tenkan=7)
    """
    return IchimokuStrategy(**kwargs)
