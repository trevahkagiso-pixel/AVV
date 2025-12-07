#!/usr/bin/env python3
"""
Adapter to expose the `ob_refined_strategy` implementation as a `BaseStrategy`
so it can be used by the existing backtest runner / registry.

This module intentionally keeps the adapter small: it re-uses
`compute_indicators`, `detect_order_blocks`, and `refined_backtest` to
produce trade entry points and then marks `signal` on the corresponding
entry bar so the existing `SignalStrategy` backtester can execute trades.
"""
from typing import Dict, Any
import pandas as pd

from strategy_framework import BaseStrategy

# re-use functions provided by the user's OB implementation
from ob_refined_strategy import compute_indicators, detect_order_blocks, refined_backtest


class OBRefinedAdapter(BaseStrategy):
    """Wraps the refined Order Block logic into a BaseStrategy-compatible adapter.

    Notes:
    - `add_indicators` will compute EMA and ATR used by the OB implementation.
    - `generate_signals` will call the refined backtest helper to discover entries
      and then mark the `signal` column at each entry timestamp (+1 long, -1 short).
    """

    def __init__(
        self,
        name: str = "ob_refined",
        ema_span: int = 50,
        atr_span: int = 14,
        atr_threshold: float = 0.0060,
        entry_wait_bars: int = 60,
        lookback: int = 10,
    ):
        super().__init__(name=name, description="Refined Order Block (3-bar fractal) strategy")
        self.ema_span = ema_span
        self.atr_span = atr_span
        self.atr_threshold = atr_threshold
        self.entry_wait_bars = entry_wait_bars
        self.lookback = lookback

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        # The OB module expects lower-case column names: open, high, low, close
        df2 = df.copy()
        # Normalize input column names for the OB helper
        col_map = {c: c.lower() for c in df2.columns}
        df2 = df2.rename(columns=col_map)

        # Ensure required columns are present in lower-case
        required = {"open", "high", "low", "close"}
        if not required.issubset(set(df2.columns)):
            # Try to map Title-case Open/High/Low/Close
            df2 = df2.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close'
            })

        # Compute indicators using the OB helper (adds 'atr' and 'ema' lower-case)
        df2 = compute_indicators(df2, ema_span=self.ema_span, atr_span=self.atr_span)

        # Back to the expected capitalized columns used by the backtesting framework
        rename_back = {}
        if 'open' in df2.columns:
            rename_back['open'] = 'Open'
        if 'high' in df2.columns:
            rename_back['high'] = 'High'
        if 'low' in df2.columns:
            rename_back['low'] = 'Low'
        if 'close' in df2.columns:
            rename_back['close'] = 'Close'
        if 'atr' in df2.columns:
            rename_back['atr'] = 'ATR'
        if 'ema' in df2.columns:
            # keep a lowercase 'ema' too, but expose EMA_signal later if needed
            rename_back['ema'] = 'ema'

        df2 = df2.rename(columns=rename_back)

        return df2

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # Work on a lower-case copy for the OB helpers
        df_lower = df.copy()
        # Create a lower-case view without losing the original index
        df_lower.columns = [c.lower() for c in df_lower.columns]

        # Detect OBs and run the refined backtest helper to find entries
        ob = detect_order_blocks(df_lower, lookback=self.lookback)

        # refined_backtest returns a trades DataFrame with entry_date and type
        trades = refined_backtest(
            df_lower,
            ob,
            entry_wait_bars=self.entry_wait_bars,
            atr_threshold=self.atr_threshold,
            stop_on_tie=True,
        )

        # Prepare signals column for the backtesting framework
        df_out = df.copy()
        df_out['signal'] = 0

        if trades is not None and not trades.empty:
            for _, tr in trades.iterrows():
                ed = pd.to_datetime(tr['entry_date'])
                # Mark the entry bar with +1 / -1
                mask = df_out.index == ed
                if tr['type'] == 'Bullish':
                    df_out.loc[mask, 'signal'] = 1
                else:
                    df_out.loc[mask, 'signal'] = -1

        return df_out

    def get_parameters(self) -> Dict[str, Any]:
        return {
            'ema_span': self.ema_span,
            'atr_span': self.atr_span,
            'atr_threshold': self.atr_threshold,
            'entry_wait_bars': self.entry_wait_bars,
            'lookback': self.lookback,
        }

    def get_description(self) -> str:
        return "Refined Order Block strategy (3-bar fractals, mitigation entries, partials)"


__all__ = ['OBRefinedAdapter']
