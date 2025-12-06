"""
Background tasks for builds (RQ worker-friendly).

This module exposes `build_summary` which runs the multi-pair backtest
and writes `backtest_summary.csv`. It is intentionally standalone so an
RQ worker can import and execute it without importing the Flask app.
"""
import pandas as pd
from ichimoku_backtest import run_all_pairs_backtest


def build_summary(cache_path: str = "backtest_summary.csv") -> pd.DataFrame:
    """Run multi-pair backtests and save summary CSV to cache_path.

    Returns the summary DataFrame.
    """
    print("[build_tasks] Running multi-pair backtests (worker)")
    df_summary = run_all_pairs_backtest(show_plot=False)
    df_summary.to_csv(cache_path, index=False)
    print(f"[build_tasks] Summary saved to {cache_path}")
    return df_summary
