"""
Modular Backtest Runner.

Runs backtests with any strategy from the registry without modification.
Supports multiple strategies in parallel, easy to extend.
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional, Any

from strategy_framework import BaseStrategy, get_registry, run_backtest_with_strategy
from ichimoku import fetch_data_from_database
from config import CURRENCY_PAIRS, DATABASE_PATH


def run_backtest_with_custom_strategy(
    table_name: str,
    strategy: BaseStrategy,
    db_path: str = DATABASE_PATH,
    cash: float = 1_000_000,
    commission: float = 0.0002,
    atr_mult_sl: float = 1.5,
    rr_mult_tp: float = 2.0,
    show_plot: bool = False,
) -> Tuple[Any, pd.DataFrame, Any]:
    """
    Run backtest with a custom strategy (replaces ichimoku_backtest.run_backtest_from_database).
    
    Args:
        table_name: Database table name (e.g., 'EUR_USD_daily')
        strategy: BaseStrategy instance
        db_path: Database path
        cash: Initial cash
        commission: Commission per trade
        atr_mult_sl: ATR multiplier for stop-loss
        rr_mult_tp: Risk-reward ratio for take-profit
        show_plot: Whether to plot results
    
    Returns:
        tuple: (stats, df, bt)
    """
    # Fetch data
    df = fetch_data_from_database(table_name, db_path)
    
    # Run backtest with strategy
    stats, df, bt = run_backtest_with_strategy(
        df,
        strategy,
        cash=cash,
        commission=commission,
        atr_mult_sl=atr_mult_sl,
        rr_mult_tp=rr_mult_tp,
    )
    
    return stats, df, bt


def run_all_pairs_with_strategy(
    strategy: BaseStrategy,
    db_path: str = DATABASE_PATH,
    cash: float = 1_000_000,
    commission: float = 0.0002,
    atr_mult_sl: float = 1.5,
    rr_mult_tp: float = 2.0,
) -> pd.DataFrame:
    """
    Run backtest for all currency pairs with a single strategy.
    
    Args:
        strategy: BaseStrategy instance
        db_path: Database path
        cash: Initial cash per backtest
        commission: Commission per trade
        atr_mult_sl: ATR multiplier for stop-loss
        rr_mult_tp: Risk-reward ratio for take-profit
    
    Returns:
        DataFrame with summary statistics for all pairs
    """
    results = []
    
    for base, quote in CURRENCY_PAIRS:
        table_name = f"{base}_{quote}_daily"
        try:
            stats, df, bt = run_backtest_with_custom_strategy(
                table_name,
                strategy,
                db_path=db_path,
                cash=cash,
                commission=commission,
                atr_mult_sl=atr_mult_sl,
                rr_mult_tp=rr_mult_tp,
            )
            
            # Extract key metrics
            row = {
                'Pair': f"{base}/{quote}",
                'Return [%]': stats._stats['Return [%]'],
                'Max DD [%]': stats._stats['Max. Drawdown [%]'],
                'Avg DD [%]': stats._stats['Avg. Drawdown [%]'],
                'Win Rate [%]': stats._stats['Win Rate [%]'],
                '# Trades': stats._stats['# Trades'],
                'Exposure [%]': stats._stats['Exposure Time [%]'],
            }
            results.append(row)
        
        except Exception as e:
            print(f"   ✗ Error for {table_name}: {e}")
    
    # Create summary DataFrame
    df_summary = pd.DataFrame(results)
    
    # Add average row if we have results
    if len(df_summary) > 0:
        avg_row = df_summary[['Return [%]', 'Max DD [%]', 'Avg DD [%]', 'Win Rate [%]', '# Trades', 'Exposure [%]']].mean()
        avg_row['Pair'] = 'AVERAGE'
        df_summary = pd.concat([df_summary, pd.DataFrame([avg_row])], ignore_index=True)
    
    return df_summary


def run_multiple_strategies(
    table_name: str,
    strategies: Dict[str, BaseStrategy],
    db_path: str = DATABASE_PATH,
    cash: float = 1_000_000,
    commission: float = 0.0002,
) -> Dict[str, Tuple[Any, pd.DataFrame, Any]]:
    """
    Run backtests for multiple strategies on the same pair.
    Useful for comparing strategies.
    
    Args:
        table_name: Database table name
        strategies: Dictionary of {strategy_id: BaseStrategy}
        db_path: Database path
        cash: Initial cash
        commission: Commission per trade
    
    Returns:
        Dictionary of {strategy_id: (stats, df, bt)}
    """
    print(f"\n{'='*70}")
    print(f"Running Multiple Strategies on {table_name}")
    print(f"{'='*70}\n")
    
    results = {}
    for strategy_id, strategy in strategies.items():
        try:
            print(f"\n--- {strategy_id.upper()} ---")
            stats, df, bt = run_backtest_with_custom_strategy(
                table_name,
                strategy,
                db_path=db_path,
                cash=cash,
                commission=commission,
            )
            results[strategy_id] = (stats, df, bt)
        except Exception as e:
            print(f"✗ Error with {strategy_id}: {e}")
    
    # Print comparison
    print(f"\n{'='*70}")
    print(f"Strategy Comparison for {table_name}")
    print(f"{'='*70}\n")
    
    comparison = []
    for strategy_id, (stats, df, bt) in results.items():
        row = {
            'Strategy': strategy_id,
            'Return [%]': f"{stats._stats['Return [%]']:.2f}",
            'Max DD [%]': f"{stats._stats['Max. Drawdown [%]']:.2f}",
            'Win Rate [%]': f"{stats._stats['Win Rate [%]']:.2f}",
            '# Trades': int(stats._stats['# Trades']),
        }
        comparison.append(row)
        print(f"{row}")
    
    return results


def register_and_run_all_strategies(pair_list: List[str] = None) -> None:
    """
    Register all default strategies and run on all pairs.
    
    Args:
        pair_list: List of pair table names (default: all CURRENCY_PAIRS)
    """
    from ichimoku_strategy import create_ichimoku_strategy
    
    registry = get_registry()
    
    # Register Ichimoku with default parameters
    registry.register('ichimoku_default', create_ichimoku_strategy())
    
    # Optionally register variants
    registry.register('ichimoku_aggressive', create_ichimoku_strategy(ema_length=50))
    registry.register('ichimoku_conservative', create_ichimoku_strategy(ema_length=200))

    print(f"\n{'='*70}")
    print(f"Registered Strategies:")
    print(f"{'='*70}\n")
    for sid, desc in registry.list_strategies().items():
        print(f"  ✓ {sid}: {desc}")
    
    # Run all strategies on all pairs
    if pair_list is None:
        pair_list = [f"{base}_{quote}_daily" for base, quote in CURRENCY_PAIRS]
    
    for table_name in pair_list:
        print(f"\n{'='*70}")
        print(f"Running all strategies on {table_name}")
        print(f"{'='*70}\n")
        
        strategies = {sid: registry.get(sid) for sid in registry.list_strategies().keys()}
        results = run_multiple_strategies(table_name, strategies)


if __name__ == "__main__":
    # Example: Run all strategies on all pairs
    register_and_run_all_strategies()
