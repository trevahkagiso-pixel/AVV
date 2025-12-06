"""
Ichimoku Backtest Runner.
Pulls data from local database or yfinance, applies Ichimoku signals, and backtests the strategy.
"""

import numpy as np
import pandas as pd
from backtesting import Backtest

from ichimoku import (
    fetch_data_from_database,
    fetch_data_yfinance,
    add_ichimoku,
    add_ema_signal,
    create_ichimoku_signal,
    TENKAN, KIJUN, SENKOU_B, ATR_LEN
)
from strategy import SignalStrategy, SimpleSignalStrategy
from config import CURRENCY_PAIRS, DATABASE_PATH
from config import STOCKS_DB_PATH, STOCK_SYMBOLS, COMMODITY_SYMBOLS, COMMODITY_NAMES, COMMODITIES_DB_PATH


def run_backtest_from_database(
    table_name: str,
    db_path: str = DATABASE_PATH,
    cash: float = 1_000_000,
    commission: float = 0.0002,
    atr_mult_sl: float = 1.5,
    rr_mult_tp: float = 2.0,
    ema_length: int = 100,
    ema_back_candles: int = 7,
    ichimoku_lookback: int = 10,
    ichimoku_min_confirm: int = 5,
    show_plot: bool = False,
    strategy_class = None,
):
    """
    Run a complete Ichimoku backtest using data from local database.
    
    Args:
        table_name: Database table name (e.g., 'EUR_USD_daily')
        db_path: Path to database
        cash: Initial cash for backtest
        commission: Commission per trade (decimal, e.g., 0.0002 = 0.02%)
        atr_mult_sl: ATR multiplier for stop-loss
        rr_mult_tp: Risk-reward ratio for take-profit
        ema_length: EMA period for trend filter
        ema_back_candles: Number of lookback candles for EMA signal
        ichimoku_lookback: Lookback window for cloud confirmation
        ichimoku_min_confirm: Min bars above/below cloud required
        strategy_class: Strategy class to use (default: SignalStrategy; use SimpleSignalStrategy for EMA-only)
        show_plot: If True, render Plotly interactive plot
    
    Returns:
        tuple: (stats, df, bt) where
            - stats: Backtest statistics
            - df: DataFrame with all indicators and signals
            - bt: Backtest object
    """
    print(f"\n{'='*70}")
    print(f"Running Ichimoku Backtest: {table_name}")
    print(f"{'='*70}")
    
    # Use provided strategy class or default to SignalStrategy
    if strategy_class is None:
        strategy_class = SignalStrategy
    
    # Fetch and prepare data
    print(f"📊 Fetching {table_name} from database...")
    df = fetch_data_from_database(table_name, db_path)
    print(f"   Loaded {len(df)} rows")
    
    # Add Ichimoku indicators
    print(f"📈 Adding Ichimoku Cloud indicators...")
    df = add_ichimoku(df, tenkan=TENKAN, kijun=KIJUN, senkou_b=SENKOU_B)
    
    # Add EMA trend filter
    print(f"📈 Adding EMA trend filter (length={ema_length})...")
    df = add_ema_signal(df, ema_length=ema_length, back_candles=ema_back_candles)
    
    # Create trading signals
    print(f"📊 Creating Ichimoku + EMA signals...")
    df = create_ichimoku_signal(
        df,
        lookback_window=ichimoku_lookback,
        min_confirm=ichimoku_min_confirm
    )
    
    # Drop NaN rows
    df = df.dropna(subset=["signal", "ATR"])
    print(f"   {len(df)} rows after dropping NaN")
    
    # Run backtest
    print(f"🎯 Running backtest with {len(df)} candles...")
    bt = Backtest(
        df,
        strategy_class,
        cash=cash,
        commission=commission,
        trade_on_close=True,
        exclusive_orders=True,
        margin=1/10,
    )
    
    # Customize strategy parameters
    stats = bt.run(atr_mult_sl=atr_mult_sl, rr_mult_tp=rr_mult_tp)
    
    # Print results
    print(f"\n✅ Backtest Results for {table_name}:")
    print(f"   Return: {stats['Return [%]']:.2f}%")
    print(f"   Max Drawdown: {stats['Max. Drawdown [%]']:.2f}%")
    print(f"   Win Rate: {stats['Win Rate [%]']:.2f}%")
    print(f"   # Trades: {stats['# Trades']}")
    print(f"   Exposure Time: {stats['Exposure Time [%]']:.2f}%")
    
    if show_plot:
        print(f"📊 Rendering interactive Plotly chart...")
        bt.plot(open_browser=False)

    # Attach richer artifacts to stats for downstream use (equity curve and trades)
    try:
        # stats._equity_curve is a DataFrame created by Backtesting lib
        equity_df = getattr(stats, '_equity_curve', None)
        if equity_df is not None:
            # attach for convenience
            stats._equity_df = equity_df
            # also expose a simple equity series
            try:
                stats._equity_series = equity_df['Equity']
            except Exception:
                stats._equity_series = None
    except Exception:
        pass

    try:
        trades = getattr(stats, '_trades', None)
        if trades is not None:
            stats._trades_df = trades
    except Exception:
        pass

    return stats, df, bt


def run_all_pairs_backtest(
    pairs: list = CURRENCY_PAIRS,
    db_path: str = DATABASE_PATH,
    data_type: str = "daily",
    cash: float = 1_000_000,
    commission: float = 0.0002,
    show_plot: bool = False,
):
    """
    Run Ichimoku backtest for multiple currency pairs.
    
    Args:
        pairs: List of (from_symbol, to_symbol) tuples
        db_path: Path to database
        data_type: Data type suffix ('daily' or 'hourly')
        cash: Initial cash per backtest
        commission: Commission per trade
        show_plot: If True, render plots
    
    Returns:
        pd.DataFrame: Summary table with backtest results for all pairs
    """
    print(f"\n{'='*70}")
    print(f"🚀 Running Multi-Pair Ichimoku Backtest")
    print(f"{'='*70}")
    
    def safe_get(stats, key, default=np.nan):
        """Safely extract backtest statistic."""
        try:
            return float(stats.get(key, default))
        except Exception:
            return default
    
    rows = []
    for from_sym, to_sym in pairs:
        table_name = f"{from_sym}_{to_sym}_{data_type}"
        
        try:
            stats, _, _ = run_backtest_from_database(
                table_name,
                db_path=db_path,
                cash=cash,
                commission=commission,
                show_plot=show_plot
            )
            
            rows.append({
                "Pair": f"{from_sym}/{to_sym}",
                "Return [%]": safe_get(stats, "Return [%]"),
                "Max DD [%]": safe_get(stats, "Max. Drawdown [%]"),
                "Avg DD [%]": safe_get(stats, "Avg. Drawdown [%]"),
                "Win Rate [%]": safe_get(stats, "Win Rate [%]"),
                "# Trades": safe_get(stats, "# Trades"),
                "Exposure [%]": safe_get(stats, "Exposure Time [%]"),
            })
        except Exception as e:
            print(f"   ⚠️ Error: {str(e)}")
            rows.append({
                "Pair": f"{from_sym}/{to_sym}",
                "Return [%]": np.nan,
                "Max DD [%]": np.nan,
                "Avg DD [%]": np.nan,
                "Win Rate [%]": np.nan,
                "# Trades": np.nan,
                "Exposure [%]": np.nan,
            })
    
    # Create summary DataFrame
    df_summary = pd.DataFrame(rows)
    
    # Add average row
    avg_row = {"Pair": "AVERAGE"}
    for col in ["Return [%]", "Max DD [%]", "Avg DD [%]", "Win Rate [%]", "# Trades", "Exposure [%]"]:
        avg_row[col] = df_summary[col].mean(skipna=True)
    
    df_summary = pd.concat([df_summary, pd.DataFrame([avg_row])], ignore_index=True)
    
    # Print summary
    print(f"\n{'='*70}")
    print("📊 Multi-Pair Backtest Summary")
    print(f"{'='*70}")
    with pd.option_context("display.float_format", "{:,.2f}".format):
        print(df_summary)
    
    return df_summary


def optimize_strategy(
    table_name: str,
    db_path: str = DATABASE_PATH,
    cash: float = 1_000_000,
    commission: float = 0.0002,
    atr_range: list = None,
    rr_range: list = None,
    maximize: str = "Return [%]",
):
    """
    Optimize SignalStrategy parameters using grid search.
    
    Args:
        table_name: Database table name
        db_path: Path to database
        cash: Initial cash
        commission: Commission per trade
        atr_range: List of ATR multiplier values to test (default: 1.0 to 2.5 step 0.1)
        rr_range: List of risk-reward ratio values to test (default: 1.0 to 3.0 step 0.1)
        maximize: Metric to optimize ('Return [%]', 'Sharpe Ratio', etc.)
    
    Returns:
        tuple: (stats, heatmap_df)
    """
    if atr_range is None:
        atr_range = list(np.arange(1.0, 2.5, 0.1))
    if rr_range is None:
        rr_range = list(np.arange(1.0, 3.0, 0.1))
    
    print(f"\n{'='*70}")
    print(f"🔍 Optimizing strategy for {table_name}")
    print(f"   ATR range: {atr_range[0]:.1f} to {atr_range[-1]:.1f}")
    print(f"   RR range: {rr_range[0]:.1f} to {rr_range[-1]:.1f}")
    print(f"{'='*70}")
    
    # Fetch and prepare data
    df = fetch_data_from_database(table_name, db_path)
    df = add_ichimoku(df, tenkan=TENKAN, kijun=KIJUN, senkou_b=SENKOU_B)
    df = add_ema_signal(df, ema_length=100, back_candles=7)
    df = create_ichimoku_signal(df, lookback_window=10, min_confirm=5)
    df = df.dropna(subset=["signal", "ATR"])
    
    # Run optimization
    bt = Backtest(
        df,
        SignalStrategy,
        cash=cash,
        commission=commission,
        trade_on_close=True,
        exclusive_orders=True,
        margin=1/10,
    )
    
    stats, heatmap = bt.optimize(
        atr_mult_sl=atr_range,
        rr_mult_tp=rr_range,
        maximize=maximize,
        return_heatmap=True,
    )
    
    print(f"\n✅ Optimization Complete")
    print(f"   Best ATR multiplier: {stats._strategy.atr_mult_sl:.2f}")
    print(f"   Best RR multiplier: {stats._strategy.rr_mult_tp:.2f}")
    print(f"   {maximize}: {stats[maximize]:.2f}")
    
    return stats, heatmap


if __name__ == "__main__":
    # Example: Run backtest on all available pairs
    summary = run_all_pairs_backtest(show_plot=False)
