#!/usr/bin/env python
"""
Quick-Start Script: Run Backtests with Strategy Framework

Examples of how to use the new modular strategy framework.
Demonstrates:
1. Single strategy on single pair
2. Single strategy on all pairs
3. Multiple strategies comparison
4. Using the registry
"""

from ichimoku_strategy import create_ichimoku_strategy
from rsi_strategy import create_rsi_strategy
from backtest_runner import (
    run_backtest_with_custom_strategy,
    run_all_pairs_with_strategy,
    run_multiple_strategies,
)
from strategy_framework import get_registry
import pandas as pd


def demo_single_pair_single_strategy():
    """Demo 1: Run Ichimoku on EUR_USD_daily."""
    print("\n" + "="*70)
    print("DEMO 1: Single Pair, Single Strategy")
    print("="*70)
    
    strategy = create_ichimoku_strategy()
    stats, df, bt = run_backtest_with_custom_strategy(
        table_name='EUR_USD_daily',
        strategy=strategy,
    )
    
    print(f"\n📊 Results:")
    print(f"   Return: {stats._stats['Return [%]']:.2f}%")
    print(f"   Max DD: {stats._stats['Max. Drawdown [%]']:.2f}%")
    print(f"   Win Rate: {stats._stats['Win Rate [%]']:.2f}%")
    print(f"   Trades: {int(stats._stats['# Trades'])}")


def demo_all_pairs_single_strategy():
    """Demo 2: Run RSI on all currency pairs."""
    print("\n" + "="*70)
    print("DEMO 2: All Pairs, Single Strategy")
    print("="*70)
    
    strategy = create_rsi_strategy(rsi_length=21, oversold=25, overbought=75)
    df_summary = run_all_pairs_with_strategy(strategy)
    
    print("\n📊 Summary across all pairs:")
    print(df_summary.to_string(index=False))


def demo_multiple_strategies():
    """Demo 3: Compare Ichimoku vs RSI on one pair."""
    print("\n" + "="*70)
    print("DEMO 3: Multiple Strategies Comparison")
    print("="*70)
    
    strategies = {
        'Ichimoku (Default)': create_ichimoku_strategy(),
        'Ichimoku (Aggressive)': create_ichimoku_strategy(ema_length=50),
        'RSI (Standard)': create_rsi_strategy(),
        'RSI (Aggressive)': create_rsi_strategy(oversold=20, overbought=80),
    }
    
    results = run_multiple_strategies('EUR_USD_daily', strategies)
    
    print("\n📊 Strategy Comparison Results:")
    print("\nStrategy | Return % | Max DD % | Win Rate % | Trades")
    print("-" * 60)
    
    for sid, (stats, df, bt) in results.items():
        ret = stats._stats['Return [%]']
        dd = stats._stats['Max. Drawdown [%]']
        wr = stats._stats['Win Rate [%]']
        trades = int(stats._stats['# Trades'])
        print(f"{sid:30} | {ret:7.2f} | {dd:7.2f} | {wr:8.2f} | {trades:6}")


def demo_registry():
    """Demo 4: Using the strategy registry."""
    print("\n" + "="*70)
    print("DEMO 4: Strategy Registry")
    print("="*70)
    
    registry = get_registry()
    
    # Register strategies
    print("\n📌 Registering strategies...")
    registry.register('ichimoku_v1', create_ichimoku_strategy())
    registry.register('ichimoku_v2', create_ichimoku_strategy(ema_length=50))
    registry.register('rsi_v1', create_rsi_strategy())
    
    # List all
    print("\n📚 Available strategies:")
    for sid, desc in registry.list_strategies().items():
        print(f"   ✓ {sid}: {desc}")
    
    # Get and use a specific one
    print(f"\n🎯 Testing registry.get('rsi_v1')...")
    strategy = registry.get('rsi_v1')
    if strategy:
        print(f"   ✓ Retrieved: {strategy}")
        print(f"   ✓ Parameters: {strategy.get_parameters()}")


def main():
    """Run all demos."""
    print("\n" + "█"*70)
    print("█  Strategy Framework Quick-Start Demos")
    print("█"*70)
    
    try:
        # Uncomment any demos you want to run
        
        # demo_single_pair_single_strategy()
        # demo_all_pairs_single_strategy()
        # demo_multiple_strategies()
        demo_registry()
        
        print("\n" + "█"*70)
        print("█  Demos Complete!")
        print("█"*70)
        print("\n📖 For more info, read: STRATEGY_FRAMEWORK.md\n")
    
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
