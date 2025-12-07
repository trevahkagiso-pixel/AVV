"""
Order Block (OB) Strategy Web UI – Dedicated dashboard for OB backtest analysis.

Features:
- Displays OB-detected signals on OHLC charts
- Summary statistics and P&L analysis
- Pair-by-pair drilldown with interactive charts
- Dark mode toggle (localStorage persisted)
- Responsive grid layout
- Modal chart expansion
- Commodity & stock pair support

Usage:
  # Build cached summary
  python ob_ui.py --build

  # Run web server (default: http://127.0.0.1:5001)
  python ob_ui.py --port 5001
"""

import os
import argparse
import threading
import time
from flask import Flask, request, send_from_directory, redirect
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from ichimoku_backtest import run_backtest_from_database
from config import DATABASE_PATH
import plotting
from ob_refined_strategy import (
    load_price_csv,
    compute_indicators,
    detect_order_blocks,
    refined_backtest,
    summarize_trades,
    year_by_year,
)

APP = Flask(__name__, static_folder=".", static_url_path="/static")
OB_CACHE_FILE = "ob_backtest_summary.csv"
CHART_EXT = ".html"

# Background build state
_build_lock = threading.Lock()
_build_thread = None
_build_state = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_error": None,
}

# Database pairs (mirrored from ichimoku_backtest)
FOREX_PAIRS = [
    "EUR_USD_daily", "GBP_USD_daily", "AUD_USD_daily",
    "EURUSD_1h", "GBPUSD_1h", "AUDUSD_1h"
]
STOCK_PAIRS = ["AAPL_daily", "MSFT_daily", "GOOGL_daily", "AMZN_daily", "NVDA_daily"]
COMMODITY_PAIRS = [
    "GC_F_daily", "CL_F_daily", "NG_F_daily",
    "HG_F_daily", "SI_F_daily"
]
ALL_PAIRS = FOREX_PAIRS + STOCK_PAIRS + COMMODITY_PAIRS


def get_base_css():
    """Return base CSS styling for OB UI."""
    return """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
            min-height: 100vh;
            padding: 20px;
            transition: background 0.25s ease, color 0.25s ease;
        }
        
        body.dark-mode {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            padding: 40px;
            transition: background 0.25s ease, color 0.25s ease;
        }
        
        .dark-mode .container {
            background: #1a1a2e;
            color: #e0e0e0;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }
        
        header {
            margin-bottom: 40px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .dark-mode header {
            border-bottom-color: #764ba2;
        }
        
        h1, h2 {
            color: #667eea;
            margin: 20px 0;
            font-size: 2.2em;
        }
        
        .dark-mode h1, .dark-mode h2 {
            color: #bb86fc;
        }
        
        h3 {
            color: #555;
            margin: 15px 0;
            font-size: 1.4em;
        }
        
        .dark-mode h3 {
            color: #bb86fc;
        }
        
        .theme-toggle {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.25s ease;
        }
        
        .dark-mode .theme-toggle {
            background: #764ba2;
        }
        
        .theme-toggle:hover {
            background: #764ba2;
        }
        
        .dark-mode .theme-toggle:hover {
            background: #bb86fc;
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        
        .stat-card {
            background: #f5f5f5;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        .dark-mode .stat-card {
            background: #2d2d44;
            border-color: #444;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.2);
        }
        
        .stat-card h3 {
            color: #667eea;
            font-size: 1em;
            margin-bottom: 10px;
        }
        
        .dark-mode .stat-card h3 {
            color: #bb86fc;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
            margin: 10px 0;
        }
        
        .dark-mode .stat-value {
            color: #e0e0e0;
        }
        
        .stat-label {
            font-size: 0.85em;
            color: #666;
        }
        
        .dark-mode .stat-label {
            color: #999;
        }
        
        .equity-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        
        .equity-card {
            background: white;
            border: 2px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        .dark-mode .equity-card {
            background: #2d2d44;
            border-color: #444;
        }
        
        .equity-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 24px rgba(102, 126, 234, 0.2);
        }
        
        .equity-card h4 {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            margin: 0;
            font-size: 1.1em;
        }
        
        .equity-card iframe {
            width: 100%;
            height: 300px;
            border: none;
        }
        
        .clickable {
            cursor: pointer;
        }
        
        .clickable:active {
            opacity: 0.9;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
        }
        
        .dark-mode table {
            background: #2d2d44;
        }
        
        thead {
            background: #667eea;
            color: white;
        }
        
        .dark-mode thead {
            background: #764ba2;
        }
        
        td, th {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        
        .dark-mode td, .dark-mode th {
            border-bottom-color: #444;
        }
        
        tbody tr:hover {
            background: #f0f0f0;
        }
        
        .dark-mode tbody tr:hover {
            background: #363654;
        }
        
        a {
            color: #667eea;
            text-decoration: none;
            transition: color 0.2s ease;
        }
        
        .dark-mode a {
            color: #bb86fc;
        }
        
        a:hover {
            color: #764ba2;
            text-decoration: underline;
        }
        
        .back-link {
            display: inline-block;
            margin: 20px 0;
            font-weight: bold;
        }
        
        footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ddd;
            color: #666;
            font-size: 0.9em;
        }
        
        .dark-mode footer {
            border-top-color: #444;
            color: #999;
        }
        
        /* Modal styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
        }
        
        .modal-content {
            background: white;
            margin: auto;
            padding: 0;
            border-radius: 8px;
            width: 90%;
            max-width: 1200px;
            height: 90vh;
            display: flex;
            flex-direction: column;
            position: relative;
            top: 50%;
            transform: translateY(-50%);
        }
        
        .dark-mode .modal-content {
            background: #1a1a2e;
        }
        
        .modal-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-radius: 8px 8px 0 0;
        }
        
        .close-btn {
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            transition: color 0.2s ease;
        }
        
        .close-btn:hover {
            color: #ddd;
        }
        
        .modal-body {
            flex: 1;
            overflow: auto;
            padding: 20px;
        }
        
        .modal-body iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        
        .pairs-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .pair-link {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            font-weight: bold;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            display: block;
            text-decoration: none;
        }
        
        .pair-link:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 16px rgba(102, 126, 234, 0.3);
            color: white;
        }
        
        .analysis-section {
            background: #f9f9f9;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        
        .dark-mode .analysis-section {
            background: #2d2d44;
            border-color: #444;
        }
        
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
        }
        
        .dark-mode .error {
            background: #3d1f1f;
            color: #ff6b6b;
        }
        
        .success {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
        }
        
        .dark-mode .success {
            background: #1f3d1f;
            color: #66bb6a;
        }
        
        hr {
            margin: 30px 0;
            border: none;
            border-top: 2px solid #ddd;
        }
        
        .dark-mode hr {
            border-top-color: #444;
        }
    </style>
    """


def get_theme_script():
    """Return JavaScript for dark mode toggle with localStorage persistence."""
    return """
    <script>
        // Load theme from localStorage
        const savedTheme = localStorage.getItem('ob-ui-theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-mode');
            const btn = document.getElementById('themeToggle');
            if (btn) btn.textContent = '☀️ Light Mode';
        }
        
        // Toggle function
        function toggleTheme() {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('ob-ui-theme', isDark ? 'dark' : 'light');
            const btn = document.getElementById('themeToggle');
            if (btn) btn.textContent = isDark ? '☀️ Light Mode' : '🌙 Dark Mode';
        }
    </script>
    """


def run_ob_backtest_for_pair(pair_name: str, db_path: str = None) -> dict:
    """
    Run OB backtest for a single pair.
    
    Returns:
        dict with keys: stats, trades_df, summary, errors
    """
    try:
        # Determine correct database path
        if db_path is None:
            if "_daily" in pair_name or "_1h" in pair_name:
                # Check if it's a stock or commodity
                if any(stock in pair_name for stock in ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]):
                    db_path = "sqlite:///stocks.db"
                elif any(comm in pair_name for comm in ["GC_F", "CL_F", "NG_F", "HG_F", "SI_F"]):
                    db_path = "sqlite:///commodities.db"
                else:
                    db_path = "sqlite:///forex.db"
        
        # Load data from database
        from database import load_from_database
        df = load_from_database(pair_name, db_path)
        
        if df.empty:
            return {"error": f"No data found for {pair_name}"}
        
        # Standardize columns
        df.columns = [c.lower().strip() for c in df.columns]
        df = df[["open", "high", "low", "close"]].copy()
        df.columns = ["open", "high", "low", "close"]
        df = df.dropna()
        
        # Add indicators
        df = compute_indicators(df, ema_span=50, atr_span=14)
        
        # Detect order blocks
        ob = detect_order_blocks(df, lookback=10)
        
        if ob.empty:
            return {
                "stats": {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0,
                    "win_rate": 0,
                    "avg_r": 0,
                },
                "trades": pd.DataFrame(),
                "summary": "No OB signals detected.",
            }
        
        # Run backtest
        trades = refined_backtest(df, ob, entry_wait_bars=60, atr_threshold=0.0060, stop_on_tie=True)
        
        if trades.empty:
            return {
                "stats": {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0,
                    "win_rate": 0,
                    "avg_r": 0,
                },
                "trades": pd.DataFrame(),
                "summary": "No trades generated from OB signals.",
            }
        
        # Calculate stats
        stats = {
            "trades": len(trades),
            "wins": len(trades[trades["outcome_R"] > 0]),
            "losses": len(trades[trades["outcome_R"] <= 0]),
            "total_pnl": trades["outcome_R"].sum(),
            "win_rate": (len(trades[trades["outcome_R"] > 0]) / len(trades) * 100) if len(trades) > 0 else 0,
            "avg_r": trades["outcome_R"].mean() if len(trades) > 0 else 0,
        }
        
        return {
            "stats": stats,
            "trades": trades,
            "summary": f"{stats['trades']} trades, {stats['wins']} wins, {stats['losses']} losses, "
                      f"{stats['win_rate']:.1f}% WR, {stats['avg_r']:.2f}R avg",
        }
    
    except Exception as e:
        return {"error": str(e)}


def plot_ob_signals(df: pd.DataFrame, ob: pd.DataFrame, pair_name: str = "") -> go.Figure:
    """
    Create Plotly chart showing price action with OB detection markers.
    
    Args:
        df: DataFrame with OHLC + indicators
        ob: DataFrame with OB detections (from detect_order_blocks)
        pair_name: Name of pair for title
    
    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Price"
    ))
    
    # EMA(50)
    if "ema" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["ema"],
            mode="lines",
            name="EMA(50)",
            line=dict(color="blue", width=2, dash="dot")
        ))
    
    # Mark OBs on chart
    if not ob.empty:
        bullish_ob = ob[ob["type"] == "Bullish"]
        bearish_ob = ob[ob["type"] == "Bearish"]
        
        if not bullish_ob.empty:
            fig.add_trace(go.Scatter(
                x=bullish_ob["bos_date"],
                y=bullish_ob["ob_low"],
                mode="markers",
                name="Bullish OB",
                marker=dict(symbol="triangle-up", size=10, color="green"),
                hovertemplate="Bullish OB<br>%{x|%Y-%m-%d}<extra></extra>"
            ))
        
        if not bearish_ob.empty:
            fig.add_trace(go.Scatter(
                x=bearish_ob["bos_date"],
                y=bearish_ob["ob_high"],
                mode="markers",
                name="Bearish OB",
                marker=dict(symbol="triangle-down", size=10, color="red"),
                hovertemplate="Bearish OB<br>%{x|%Y-%m-%d}<extra></extra>"
            ))
    
    fig.update_layout(
        title=f"Order Block Detection – {pair_name}",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        template="plotly_white",
        width=1000,
        height=600,
    )
    
    return fig


def build_summary(cache_file: str):
    """Build OB backtest summary for all pairs and save to CSV."""
    with _build_lock:
        _build_state["running"] = True
        _build_state["last_started"] = time.time()
        _build_state["last_error"] = None
    
    try:
        results = []
        
        for pair in ALL_PAIRS:
            print(f"Running OB backtest for {pair}...")
            try:
                result = run_ob_backtest_for_pair(pair)
                if "error" in result:
                    print(f"  Error: {result['error']}")
                    continue
                
                stats = result.get("stats", {})
                results.append({
                    "pair": pair,
                    "trades": stats.get("trades", 0),
                    "wins": stats.get("wins", 0),
                    "losses": stats.get("losses", 0),
                    "total_pnl": stats.get("total_pnl", 0),
                    "win_rate": stats.get("win_rate", 0),
                    "avg_r": stats.get("avg_r", 0),
                })
            except Exception as e:
                print(f"  Exception for {pair}: {e}")
                continue
        
        if results:
            df = pd.DataFrame(results)
            df.to_csv(cache_file, index=False)
            print(f"Summary saved to {cache_file}")
        
        _build_state["last_finished"] = time.time()
    
    except Exception as e:
        _build_state["last_error"] = str(e)
        print(f"Build error: {e}")
    
    finally:
        with _build_lock:
            _build_state["running"] = False


@APP.route("/")
def index():
    """OB backtest summary dashboard."""
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Order Block Strategy – Dashboard</title>
        {get_base_css()}
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>🔷 Order Block Strategy</h1>
                    <p>Advanced price-action backtest dashboard</p>
                </div>
                <button id="themeToggle" class="theme-toggle" onclick="toggleTheme()">🌙 Dark Mode</button>
            </header>
            
            <h2>Dashboard Summary</h2>
    """
    
    # Load cache if available
    if os.path.exists(OB_CACHE_FILE):
        try:
            df = pd.read_csv(OB_CACHE_FILE)
            
            html += """
            <div class="summary-grid">
            """
            
            # Summary stats
            total_trades = df["trades"].sum()
            total_wins = df["wins"].sum()
            total_losses = df["losses"].sum()
            total_pnl = df["total_pnl"].sum()
            avg_wr = df["win_rate"].mean()
            avg_r = df["avg_r"].mean()
            
            html += f"""
                <div class="stat-card">
                    <h3>Total Trades</h3>
                    <div class="stat-value">{total_trades}</div>
                    <div class="stat-label">Across all pairs</div>
                </div>
                <div class="stat-card">
                    <h3>Total Wins</h3>
                    <div class="stat-value" style="color: green;">{total_wins}</div>
                    <div class="stat-label">{total_losses} losses</div>
                </div>
                <div class="stat-card">
                    <h3>Average Win Rate</h3>
                    <div class="stat-value">{avg_wr:.1f}%</div>
                    <div class="stat-label">Across all pairs</div>
                </div>
                <div class="stat-card">
                    <h3>Average R-Multiple</h3>
                    <div class="stat-value">{avg_r:.2f}R</div>
                    <div class="stat-label">Mean outcome per trade</div>
                </div>
                <div class="stat-card">
                    <h3>Total P&L (R)</h3>
                    <div class="stat-value" style="color: {'green' if total_pnl > 0 else 'red'};">{total_pnl:.2f}R</div>
                    <div class="stat-label">Cumulative outcome</div>
                </div>
            </div>
            
            <h2>Pair Performance</h2>
            <table>
                <thead>
                    <tr>
                        <th>Pair</th>
                        <th>Trades</th>
                        <th>Wins</th>
                        <th>Losses</th>
                        <th>Win Rate</th>
                        <th>Total P&L</th>
                        <th>Avg R</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for _, row in df.iterrows():
                pair = row["pair"]
                html += f"""
                    <tr>
                        <td><strong>{pair}</strong></td>
                        <td>{int(row['trades'])}</td>
                        <td style="color: green;">{int(row['wins'])}</td>
                        <td style="color: red;">{int(row['losses'])}</td>
                        <td>{row['win_rate']:.1f}%</td>
                        <td style="color: {'green' if row['total_pnl'] > 0 else 'red'};">{row['total_pnl']:.2f}R</td>
                        <td>{row['avg_r']:.2f}R</td>
                        <td><a href="/pair/{pair}">View Details →</a></td>
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
            """
        
        except Exception as e:
            html += f'<div class="error">Error loading cache: {e}</div>'
    else:
        html += """
        <div class="error">
            📊 No summary cache found. Run <code>python ob_ui.py --build</code> to generate backtest results.
        </div>
        """
    
    html += f"""
        {get_theme_script()}
        <hr>
        <footer>Order Block Strategy UI • Powered by Python, Flask & Plotly</footer>
        </div>
    </body>
    </html>
    """
    return html


@APP.route("/pair/<pair>")
def pair_detail(pair):
    """Detailed analysis for a single pair."""
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{pair} – Order Block Analysis</title>
        {get_base_css()}
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>🔷 {pair}</h1>
                    <p>Order Block Analysis</p>
                </div>
                <button id="themeToggle" class="theme-toggle" onclick="toggleTheme()">🌙 Dark Mode</button>
            </header>
    """
    
    try:
        # Run backtest
        result = run_ob_backtest_for_pair(pair)
        
        if "error" in result:
            html += f'<div class="error">Error: {result["error"]}</div>'
            html += '<a href="/" class="back-link">← Back to Dashboard</a>'
            html += f'{get_theme_script()}</div></body></html>'
            return html
        
        stats = result.get("stats", {})
        trades = result.get("trades", pd.DataFrame())
        
        # Summary section
        html += f"""
            <h2>Summary</h2>
            <div class="summary-grid">
                <div class="stat-card">
                    <h3>Total Trades</h3>
                    <div class="stat-value">{stats.get('trades', 0)}</div>
                </div>
                <div class="stat-card">
                    <h3>Wins / Losses</h3>
                    <div class="stat-value">{stats.get('wins', 0)} / {stats.get('losses', 0)}</div>
                </div>
                <div class="stat-card">
                    <h3>Win Rate</h3>
                    <div class="stat-value">{stats.get('win_rate', 0):.1f}%</div>
                </div>
                <div class="stat-card">
                    <h3>Total P&L</h3>
                    <div class="stat-value" style="color: {'green' if stats.get('total_pnl', 0) > 0 else 'red'};">
                        {stats.get('total_pnl', 0):.2f}R
                    </div>
                </div>
                <div class="stat-card">
                    <h3>Avg R-Multiple</h3>
                    <div class="stat-value">{stats.get('avg_r', 0):.2f}R</div>
                </div>
            </div>
        """
        
        # Trades table
        if not trades.empty:
            html += """
            <h2>Trade Log</h2>
            <table>
                <thead>
                    <tr>
                        <th>OB Type</th>
                        <th>OB Date</th>
                        <th>Entry Date</th>
                        <th>Entry Price</th>
                        <th>Stop Price</th>
                        <th>Risk (R)</th>
                        <th>Outcome</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for _, trade in trades.iterrows():
                outcome_color = "green" if trade.get("outcome_R", 0) > 0 else "red"
                html += f"""
                    <tr>
                        <td>{trade.get('type', 'N/A')}</td>
                        <td>{trade.get('ob_date', 'N/A')}</td>
                        <td>{trade.get('entry_date', 'N/A')}</td>
                        <td>{trade.get('entry', 'N/A'):.4f if pd.notna(trade.get('entry')) else 'N/A'}</td>
                        <td>{trade.get('stop', 'N/A'):.4f if pd.notna(trade.get('stop')) else 'N/A'}</td>
                        <td>{trade.get('R', 'N/A'):.4f if pd.notna(trade.get('R')) else 'N/A'}</td>
                        <td style="color: {outcome_color}; font-weight: bold;">
                            {trade.get('outcome_R', 0):.2f}R
                        </td>
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
            """
        
        # Charts
        try:
            from database import load_from_database
            
            # Determine correct DB path
            if any(stock in pair for stock in ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]):
                db_path = "sqlite:///stocks.db"
            elif any(comm in pair for comm in ["GC_F", "CL_F", "NG_F", "HG_F", "SI_F"]):
                db_path = "sqlite:///commodities.db"
            else:
                db_path = "sqlite:///forex.db"
            
            df = load_from_database(pair, db_path)
            df.columns = [c.lower().strip() for c in df.columns]
            df = df[["open", "high", "low", "close"]].copy()
            df.columns = ["open", "high", "low", "close"]
            df = compute_indicators(df)
            ob = detect_order_blocks(df)
            
            # Create and save charts
            fig = plot_ob_signals(df, ob, pair)
            chart_file = f"{pair}_ob_clean.html"
            fig.write_html(chart_file)
            
            html += f"""
            <h2>Charts</h2>
            <div class="equity-grid">
                <div class="equity-card clickable" onclick="openModal('{chart_file}', 'OB Detection Chart')">
                    <h4>📊 OB Detection Chart</h4>
                    <iframe src="/chart/{chart_file}" onclick="event.stopPropagation()"></iframe>
                </div>
            </div>
            """
        
        except Exception as e:
            print(f"Chart generation error for {pair}: {e}")
        
    except Exception as e:
        html += f'<div class="error">Error: {str(e)}</div>'
    
    # Modal
    html += """
    <div id="chartModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span id="modalTitle">Chart</span>
                <span class="close-btn" onclick="closeModal()">&times;</span>
            </div>
            <div class="modal-body">
                <iframe id="modalIframe"></iframe>
            </div>
        </div>
    </div>
    
    <script>
        function openModal(chartFile, chartLabel) {
            const modal = document.getElementById('chartModal');
            const iframe = document.getElementById('modalIframe');
            const title = document.getElementById('modalTitle');
            
            iframe.src = '/chart/' + chartFile;
            title.textContent = chartLabel + ' - Full View';
            modal.style.display = 'block';
        }
        
        function closeModal() {
            const modal = document.getElementById('chartModal');
            modal.style.display = 'none';
        }
        
        window.onclick = function(event) {
            const modal = document.getElementById('chartModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
        
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
    </script>
    
    <hr>
    <a href="/" class="back-link">← Back to Dashboard</a>
    <footer>Order Block Strategy UI • Powered by Python, Flask & Plotly</footer>
    </div>
    """
    
    html += f"{get_theme_script()}"
    html += """
    </body>
    </html>
    """
    return html


@APP.route("/chart/<filename>")
def serve_chart(filename):
    """Serve chart HTML files."""
    return send_from_directory(".", filename)


def main():
    parser = argparse.ArgumentParser(description="Order Block Strategy Web UI")
    parser.add_argument("--build", action="store_true", help="Build cache and exit")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5001, help="Port to bind to (default 5001)")
    args = parser.parse_args()

    if args.build:
        print("Building OB backtest cache...")
        build_summary(OB_CACHE_FILE)
        print(f"Cache saved to {OB_CACHE_FILE}")
        return

    print(f"🔷 Starting OB UI server on http://{args.host}:{args.port}")
    APP.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
