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


def _list_sqlite_tables(sqlite_uri):
    """Return a list of table names for a sqlite:/// URI or file path."""
    try:
        import sqlite3
        path = sqlite_uri.replace('sqlite:///', '') if sqlite_uri.startswith('sqlite:///') else sqlite_uri
        if not os.path.exists(path):
            return []
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        return tables
    except Exception:
        return []


@APP.route('/health')
def health():
    """Health endpoint: returns cache file metadata and DB table lists."""
    try:
        cache_info = None
        if os.path.exists(OB_CACHE_FILE):
            st = os.stat(OB_CACHE_FILE)
            cache_info = {
                'path': OB_CACHE_FILE,
                'exists': True,
                'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
                'size_bytes': st.st_size,
            }
        else:
            cache_info = {'path': OB_CACHE_FILE, 'exists': False}

        from config import DATABASE_PATH, STOCKS_DB_PATH, COMMODITIES_DB_PATH
        dbs = {
            'forex': _list_sqlite_tables(DATABASE_PATH),
            'stocks': _list_sqlite_tables(STOCKS_DB_PATH),
            'commodities': _list_sqlite_tables(COMMODITIES_DB_PATH),
        }

        return {
            'cache': cache_info,
            'pairs': {
                'FOREX_PAIRS': FOREX_PAIRS,
                'STOCK_PAIRS': STOCK_PAIRS,
                'COMMODITY_PAIRS': COMMODITY_PAIRS,
                'ALL_PAIRS': ALL_PAIRS,
            },
            'databases': dbs,
        }
    except Exception as e:
        return {'error': str(e)}, 500


@APP.route('/admin/pairs', methods=['GET', 'POST'])
def admin_pairs():
    """Admin UI to view/edit `pairs.json` and trigger a rebuild.

    - GET: show an editable textarea with the current pairs.json content.
    - POST: validate & save JSON, start an async build for OB cache, and
      call the Ichimoku UI `/rebuild_async` endpoint to keep both caches in sync.
    """
    try:
        import json
        from urllib import request as urlrequest
        pairs_path = os.path.join(os.getcwd(), 'pairs.json')

        if request.method == 'POST':
            body = request.form.get('pairs_json', '')
            try:
                parsed = json.loads(body)
            except Exception as e:
                return f"Invalid JSON: {e}", 400

            # Basic validation: must contain keys
            for k in ('FOREX_PAIRS', 'STOCK_PAIRS', 'COMMODITY_PAIRS'):
                if k not in parsed:
                    return f"Missing key: {k}", 400

            # Write file
            with open(pairs_path, 'w') as fh:
                json.dump(parsed, fh, indent=2)

            # Start OB build in background thread
            def _start_build():
                try:
                    build_summary(OB_CACHE_FILE)
                except Exception:
                    pass

            t = threading.Thread(target=_start_build, daemon=True)
            t.start()

            # Trigger ichimoku UI rebuild (best-effort)
            try:
                url = 'http://127.0.0.1:5000/rebuild_async'
                req = urlrequest.Request(url, method='GET')
                urlrequest.urlopen(req, timeout=2)
            except Exception:
                # It's okay if the other UI isn't running or the call fails
                pass

            return redirect('/admin/pairs')

        # GET: load and display
        if os.path.exists(pairs_path):
            with open(pairs_path, 'r') as fh:
                content = fh.read()
        else:
            # build a default preview
            default = {
                'FOREX_PAIRS': DEFAULT_FOREX_PAIRS,
                'STOCK_PAIRS': DEFAULT_STOCK_PAIRS,
                'COMMODITY_PAIRS': DEFAULT_COMMODITY_PAIRS,
            }
            content = json.dumps(default, indent=2)

        html = get_base_css()
        html += """
        <div class="container">
            <header>
                <h1>🔧 Admin — Edit pairs.json</h1>
            </header>
            <form method="post">
                <p>Edit the JSON below to add/remove pairs. Keys required: <code>FOREX_PAIRS</code>, <code>STOCK_PAIRS</code>, <code>COMMODITY_PAIRS</code>.</p>
                <textarea name="pairs_json" style="width:100%;height:360px;font-family:monospace;">""" + content + """</textarea>
                <div style="margin-top:12px"><button class="btn" type="submit">💾 Save & Rebuild</button> <a class="btn secondary" href="/">Back</a></div>
            </form>
            <p style="margin-top:16px;font-size:0.9em;color:#666">Note: this UI is unauthenticated and intended for local usage only.</p>
        </div>
        """
        return html

    except Exception as e:
        return f"Admin error: {e}", 500

# Background build state
_build_lock = threading.Lock()
_build_thread = None
_build_state = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_error": None,
}

# Database pairs (can be overridden by `pairs.json` in the repo root)
DEFAULT_FOREX_PAIRS = [
    "EUR_USD_daily", "GBP_USD_daily", "AUD_USD_daily",
    "USD_CAD_daily", "USD_JPY_daily",
]
DEFAULT_STOCK_PAIRS = ["AAPL_daily", "MSFT_daily", "GOOGL_daily", "AMZN_daily", "NVDA_daily"]
DEFAULT_COMMODITY_PAIRS = [
    "GC_F_daily", "CL_F_daily", "NG_F_daily",
    "HG_F_daily", "SI_F_daily"
]

def _load_pairs_from_json(path='pairs.json'):
    try:
        import json
        with open(path, 'r') as f:
            data = json.load(f)
        forex = data.get('FOREX_PAIRS', DEFAULT_FOREX_PAIRS)
        stocks = data.get('STOCK_PAIRS', DEFAULT_STOCK_PAIRS)
        commodities = data.get('COMMODITY_PAIRS', DEFAULT_COMMODITY_PAIRS)
        return forex, stocks, commodities
    except Exception:
        return DEFAULT_FOREX_PAIRS, DEFAULT_STOCK_PAIRS, DEFAULT_COMMODITY_PAIRS


FOREX_PAIRS, STOCK_PAIRS, COMMODITY_PAIRS = _load_pairs_from_json()
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
        
        /* Back to dashboard button */
        .back-btn {
            background: transparent;
            color: #667eea;
            border: 2px solid transparent;
            padding: 8px 12px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            margin-right: 12px;
        }

        .back-btn:hover {
            background: rgba(102,126,234,0.06);
            border-color: rgba(102,126,234,0.12);
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

        .chart-meta {
            font-size: 12px;
            color: #666;
            padding: 8px 12px 16px 12px;
        }

        .dark-mode .chart-meta { color: #bbb; }
        
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
            color: #111;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.5;
            font-size: 15px;
        }

        .dark-mode .analysis-section {
            background: #1a1a2e;
            border-color: #2b2b3a;
            color: #ffffff;
        }

        .analysis-section ul { margin-left: 18px; }
        .analysis-section li { margin: 8px 0; }
        .analysis-section strong { color: #ffffff; }
        .analysis-block { background: #f0f0f0; padding: 15px; border-radius: 8px; margin: 15px 0; color: #111; }
        .dark-mode .analysis-block { background: #1a1a2e; color: #ffffff; }
        
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
        
        /* Collapsible Trade Log Styles */
        .collapsible-header {
            background: #667eea;
            color: white;
            padding: 15px 20px;
            cursor: pointer;
            border: none;
            width: 100%;
            text-align: left;
            font-size: 1.1em;
            font-weight: bold;
            border-radius: 6px 6px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s ease;
        }
        
        .dark-mode .collapsible-header {
            background: #764ba2;
        }
        
        .collapsible-header:hover {
            background: #764ba2;
        }
        
        .dark-mode .collapsible-header:hover {
            background: #bb86fc;
        }
        
        .collapsible-content {
            max-height: 500px;
            overflow-y: auto;
            transition: max-height 0.3s ease, opacity 0.3s ease;
            opacity: 1;
        }
        
        .collapsible-content.collapsed {
            max-height: 0;
            opacity: 0;
            overflow: hidden;
        }
        
        .toggle-icon {
            display: inline-block;
            transition: transform 0.3s ease;
        }
        
        .toggle-icon.collapsed {
            transform: rotate(-90deg);
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
        template="plotly_dark",
        width=1000,
        height=600,
    )
    
    return fig


def plot_equity_curve(trades: pd.DataFrame, pair_name: str = "") -> go.Figure:
    """
    Create cumulative P&L equity curve from trades.
    
    Args:
        trades: DataFrame with outcome_R column
        pair_name: Name of pair for title
    
    Returns:
        Plotly Figure
    """
    if trades.empty:
        fig = go.Figure()
        fig.add_annotation(text="No trades to plot", showarrow=False)
        return fig
    
    # Calculate cumulative P&L
    trades_copy = trades.copy()
    trades_copy["cumulative_R"] = trades_copy["outcome_R"].cumsum()
    trades_copy["trade_number"] = range(1, len(trades_copy) + 1)
    
    fig = go.Figure()
    
    # Equity curve
    fig.add_trace(go.Scatter(
        x=trades_copy["trade_number"],
        y=trades_copy["cumulative_R"],
        mode="lines+markers",
        name="Cumulative P&L",
        line=dict(color="#667eea", width=3),
        marker=dict(size=8),
        fill="tozeroy",
        fillcolor="rgba(102, 126, 234, 0.2)",
        hovertemplate="Trade %{x}<br>Cumulative P&L: %{y:.2f}R<extra></extra>"
    ))
    
    # Breakeven line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Breakeven")
    
    fig.update_layout(
        title=f"Equity Curve – {pair_name}",
        xaxis_title="Trade Number",
        yaxis_title="Cumulative P&L (R-Multiples)",
        hovermode="x unified",
        template="plotly_dark",
        width=1000,
        height=600,
        showlegend=True,
    )
    
    return fig


def plot_traded_positions(trades: pd.DataFrame, df: pd.DataFrame, pair_name: str = "") -> go.Figure:
    """
    Plot candlesticks with entry and exit markers for each trade.

    Args:
        trades: DataFrame containing trades (must include entry_date, exit_date, entry, exit, outcome_R)
        df: Price DataFrame with datetime index and open/high/low/close
        pair_name: Title for the chart

    Returns:
        Plotly Figure
    """
    fig = go.Figure()

    # Candlesticks
    try:
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ))
    except Exception:
        fig.add_annotation(text="No price data available", showarrow=False)
        return fig

    # Add entries/exits
    if trades is None or trades.empty:
        fig.add_annotation(text="No trades to plot", showarrow=False)
        fig.update_layout(title=f"Traded Positions – {pair_name}", template="plotly_dark")
        return fig

    for _, t in trades.iterrows():
        # robustly get fields
        entry_dt = t.get('entry_date') or t.get('entryTime') or t.get('entry_time')
        exit_dt = t.get('exit_date') or t.get('exitTime') or t.get('exit_time')
        entry_price = t.get('entry') if pd.notna(t.get('entry')) else None
        exit_price = t.get('exit') if pd.notna(t.get('exit')) else t.get('exit_price')
        outcome = t.get('outcome_R', 0)

        # If dates are strings, attempt parse
        try:
            if entry_dt is not None and not isinstance(entry_dt, (pd.Timestamp,)):
                entry_dt = pd.to_datetime(entry_dt)
            if exit_dt is not None and not isinstance(exit_dt, (pd.Timestamp,)):
                exit_dt = pd.to_datetime(exit_dt)
        except Exception:
            pass

        color = 'green' if outcome > 0 else 'red'

        # Entry marker
        if entry_dt is not None and entry_price is not None:
            fig.add_trace(go.Scatter(
                x=[entry_dt], y=[entry_price], mode='markers',
                marker=dict(symbol='triangle-up' if outcome >= 0 else 'triangle-down', size=12, color=color),
                name='Entry', hovertemplate=f"Entry<br>%{{x|%Y-%m-%d}}<br>{entry_price:.4f}<extra></extra>"
            ))

        # Exit marker
        if exit_dt is not None and exit_price is not None:
            fig.add_trace(go.Scatter(
                x=[exit_dt], y=[exit_price], mode='markers',
                marker=dict(symbol='circle', size=10, color=color),
                name='Exit', hovertemplate=f"Exit<br>%{{x|%Y-%m-%d}}<br>{exit_price:.4f}<extra></extra>"
            ))

        # Line between entry and exit
        if entry_dt is not None and exit_dt is not None and entry_price is not None and exit_price is not None:
            fig.add_trace(go.Scatter(
                x=[entry_dt, exit_dt], y=[entry_price, exit_price], mode='lines',
                line=dict(color=color, width=2), opacity=0.6, showlegend=False
            ))

    fig.update_layout(
        title=f"Traded Positions – {pair_name}",
        xaxis_title='Date', yaxis_title='Price',
        xaxis_rangeslider_visible=False, hovermode='x unified', template='plotly_dark', width=1000, height=600
    )

    return fig


def generate_analysis_text(stats: dict, trades: pd.DataFrame, pair_name: str = "") -> str:
    """
    Generate human-readable analysis of backtest results.
    
    Args:
        stats: Dictionary with trades, wins, losses, total_pnl, win_rate, avg_r
        trades: DataFrame with trade details
        pair_name: Name of pair
    
    Returns:
        HTML string with analysis
    """
    if stats.get("trades", 0) == 0:
        return """
        <div class="analysis-section">
            <h3>📊 Analysis</h3>
            <p><strong>Result:</strong> No trades generated from OB signals.</p>
            <p>The Order Block strategy did not detect any valid entry opportunities within the test period.</p>
        </div>
        """
    
    trades_count = stats.get("trades", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    win_rate = stats.get("win_rate", 0)
    total_pnl = stats.get("total_pnl", 0)
    avg_r = stats.get("avg_r", 0)
    
    # Determine strategy quality
    quality_verdict = "❌ POOR"
    quality_desc = "This strategy underperformed."
    
    if win_rate >= 60 and avg_r > 0.5:
        quality_verdict = "✅ EXCELLENT"
        quality_desc = "Outstanding performance with high win rate and positive expectancy."
    elif win_rate >= 55 and avg_r > 0.2:
        quality_verdict = "✅ GOOD"
        quality_desc = "Solid performance with above-breakeven expectancy."
    elif win_rate >= 50 and avg_r > 0:
        quality_verdict = "⚠️ ACCEPTABLE"
        quality_desc = "Marginally profitable with potential after optimization."
    elif win_rate >= 45 and avg_r > -0.2:
        quality_verdict = "⚠️ MARGINAL"
        quality_desc = "Near-breakeven results. Consider parameter adjustments."
    else:
        quality_verdict = "❌ POOR"
        quality_desc = "Losing strategy. Requires significant optimization or reconsideration."
    
    # Win/Loss analysis
    win_loss_insight = f"With {wins} wins and {losses} losses out of {trades_count} trades"
    if losses == 0:
        win_loss_insight += ", the strategy maintained a PERFECT record (100% wins)."
    elif wins == 0:
        win_loss_insight += ", the strategy experienced consistent losses (0% wins)."
    else:
        win_loss_insight += f", the win rate of {win_rate:.1f}% is "
        if win_rate >= 55:
            win_loss_insight += "above the 50% breakeven threshold, which is positive."
        elif win_rate >= 50:
            win_loss_insight += "at the breakeven threshold, indicating marginal edge."
        else:
            win_loss_insight += "below 50%, meaning losses outweigh wins in frequency."
    
    # R-multiple analysis
    if avg_r > 0:
        r_insight = f"The strategy averages {avg_r:.2f}R per trade, which is positive and indicates"
        if avg_r > 1.0:
            r_insight += " strong risk-adjusted returns. Excellent expectancy."
        elif avg_r > 0.5:
            r_insight += " good risk-adjusted returns. Solid expectancy."
        else:
            r_insight += " weak but positive risk-adjusted returns."
    else:
        r_insight = f"The strategy loses {abs(avg_r):.2f}R per trade on average, indicating negative expectancy."
    
    # Total P&L assessment
    pnl_verdict = "LOSS" if total_pnl < 0 else "PROFIT"
    pnl_color = "red" if total_pnl < 0 else "green"
    
    # Extended performance insights
    if trades_count > 0:
        loss_pnl = trades[trades['outcome_R'] <= 0]['outcome_R'].sum() if 'outcome_R' in trades.columns else 0
        win_pnl = trades[trades['outcome_R'] > 0]['outcome_R'].sum() if 'outcome_R' in trades.columns else 0
        avg_win = trades[trades['outcome_R'] > 0]['outcome_R'].mean() if wins > 0 else 0
        avg_loss = trades[trades['outcome_R'] <= 0]['outcome_R'].mean() if losses > 0 else 0
        profit_factor = abs(win_pnl / loss_pnl) if loss_pnl != 0 else float('inf')
        largest_win = trades['outcome_R'].max() if len(trades) > 0 else 0
        largest_loss = trades['outcome_R'].min() if len(trades) > 0 else 0
    else:
        loss_pnl = win_pnl = avg_win = avg_loss = profit_factor = largest_win = largest_loss = 0
    
    html = f"""
    <div class="analysis-section">
        <h3>📊 Backtest Analysis for {pair_name}</h3>
        
        <div class="analysis-block">
            <p><strong>Overall Verdict:</strong> <span style="color: #333; font-size: 1.2em;">{quality_verdict}</span></p>
            <p>{quality_desc}</p>
        </div>
        
        <h4>📈 Performance Breakdown</h4>
        <div class="analysis-block">
        <ul>
            <li><strong>Sample Size:</strong> {trades_count} trades executed during backtest period. This sample provides {'strong' if trades_count >= 20 else 'moderate' if trades_count >= 10 else 'limited'} statistical confidence.</li>
            
            <li><strong>Win/Loss Record:</strong> {wins} winning trades vs {losses} losing trades. 
                {'This shows a healthy win rate with more wins than losses.' if win_rate > 50 else 'This is below the 50% breakeven threshold and indicates the strategy is losing more trades than it wins.'}
            </li>
            
            <li><strong>Win Rate Analysis:</strong> {win_rate:.1f}% ({win_loss_insight})
                <ul style="margin-left: 20px; margin-top: 8px;">
                    <li>Expected breakeven: ~50% (1:1 risk-reward)</li>
                    <li>Actual performance: {'Well above' if win_rate >= 60 else 'Above' if win_rate > 50 else 'Below'} breakeven</li>
                    <li>Win rate sustainability: {'Very high - this strategy has strong edge' if win_rate >= 60 else 'Good - edge present' if win_rate > 55 else 'Moderate - limited edge' if win_rate > 50 else 'Low - strategy is losing'}</li>
                </ul>
            </li>
            
            <li><strong>Risk-Adjusted Returns (R-Multiples):</strong> {r_insight}
                <ul style="margin-left: 20px; margin-top: 8px;">
                    <li>Average per winning trade: {avg_win:+.3f}R</li>
                    <li>Average per losing trade: {avg_loss:+.3f}R</li>
                    <li>Profit Factor: {profit_factor:.2f}x (winners are {profit_factor:.2f}x larger than losers)</li>
                    <li>Largest winning trade: {largest_win:+.2f}R</li>
                    <li>Largest losing trade: {largest_loss:+.2f}R</li>
                </ul>
            </li>
            
            <li><strong>Total P&L Summary:</strong> <span style="color: {pnl_color}; font-weight: bold;">{total_pnl:+.2f}R total ({pnl_verdict})</span>
                <ul style="margin-left: 20px; margin-top: 8px;">
                    <li>Gross profit from winners: {win_pnl:+.2f}R</li>
                    <li>Total loss from losers: {loss_pnl:+.2f}R</li>
                    <li>Net outcome: {total_pnl:+.2f}R ({'Highly positive edge' if total_pnl > 5 else 'Positive edge' if total_pnl > 0 else 'Negative - strategy needs redesign'})</li>
                </ul>
            </li>
        </ul>
        </div>
        
        <h4>🎯 Key Insights</h4>
        <ul>
    """
    
    # Add insights based on metrics
    if win_rate >= 60:
        html += "<li>✅ <strong>High Win Rate:</strong> The strategy consistently picks profitable setups.</li>"
    elif win_rate < 45:
        html += "<li>⚠️ <strong>Low Win Rate:</strong> More than half of trades are losing. This needs investigation.</li>"
    
    if avg_r > 0.5:
        html += "<li>✅ <strong>Strong Risk/Reward:</strong> Winners significantly outweigh losers in magnitude.</li>"
    elif avg_r < 0:
        html += "<li>❌ <strong>Negative Expectancy:</strong> Losers are larger than winners on average.</li>"
    
    if total_pnl > 0 and avg_r > 0:
        html += "<li>✅ <strong>Profitable:</strong> The strategy generated positive returns with valid edge.</li>"
    elif total_pnl > 0 and avg_r <= 0:
        html += "<li>⚠️ <strong>Profitable by Luck:</strong> Positive total P&L but negative expectancy (unsustainable).</li>"
    elif total_pnl <= 0:
        html += "<li>❌ <strong>Unprofitable:</strong> The strategy resulted in losses. Optimization needed.</li>"
    
    # Recommendation
    html += """
        </ul>
        
        <h4>💡 Recommendation</h4>
    """
    
    if quality_verdict == "✅ EXCELLENT":
        html += "<p>✅ This is a <strong>production-ready strategy</strong> with strong historical performance. Consider forward testing and live deployment with proper position sizing.</p>"
    elif quality_verdict == "✅ GOOD":
        html += "<p>✅ This is a <strong>promising strategy</strong> with solid edge. Consider further optimization and validation on different market regimes.</p>"
    elif quality_verdict == "⚠️ ACCEPTABLE":
        html += "<p>⚠️ This strategy shows <strong>potential but needs refinement</strong>. Test parameter adjustments and validate on out-of-sample data.</p>"
    elif quality_verdict == "⚠️ MARGINAL":
        html += "<p>⚠️ This strategy is <strong>near-breakeven and risky</strong>. Significant optimization or redesign is recommended before live trading.</p>"
    else:
        html += "<p>❌ This strategy is <strong>not viable in its current form</strong>. Major revisions, parameter changes, or strategy redesign is needed.</p>"
    
    html += """
    </div>
    """
    
    return html


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
        <style>
            /* Category tabs on dashboard */
            .category-tabs {{ display:flex; gap:8px; margin:12px 0; }}
            .category-btn {{ padding:8px 12px; border-radius:6px; background:#222; color:#ddd; border:1px solid #333; cursor:pointer; }}
            .category-btn.active {{ background:#7b3be6; color:#fff; }}
            .category-pane {{ display:none; margin-top:12px; }}
            .category-pane.active {{ display:block; }}
            /* Analysis section dark-mode compatible font/color */
            .analysis-section {{ color: #222; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
            .dark-mode .analysis-section {{ color: #e0e0e0; }}
        </style>
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
            <div class="category-tabs">
                <button class="category-btn active" onclick="showCategory('cat-forex', this)">Forex</button>
                <button class="category-btn" onclick="showCategory('cat-stocks', this)">Stocks</button>
                <button class="category-btn" onclick="showCategory('cat-commodities', this)">Commodities</button>
            </div>

            <div id="cat-forex" class="category-pane active">
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

            # build category lists
            stocks = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
            commodities = ["GC_F", "CL_F", "NG_F", "HG_F", "SI_F"]

            # Forex pane rows (exclude stocks & commodities)
            for _, row in df.iterrows():
                pair = row["pair"]
                if any(s in pair for s in stocks) or any(c in pair for c in commodities):
                    continue
                html += f"""
                        <tr>
                            <td><strong>{pair}</strong></td>
                            <td>{int(row['trades'])}</td>
                            <td style=\"color: green;\">{int(row['wins'])}</td>
                            <td style=\"color: red;\">{int(row['losses'])}</td>
                            <td>{row['win_rate']:.1f}%</td>
                            <td style=\"color: {'green' if row['total_pnl'] > 0 else 'red'};\">{row['total_pnl']:.2f}R</td>
                            <td>{row['avg_r']:.2f}R</td>
                            <td><a href=\"/pair/{pair}\">View Details →</a></td>
                        </tr>
                """

            html += """
                    </tbody>
                </table>
            </div>

            <div id="cat-stocks" class="category-pane">
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
                if any(s in pair for s in stocks):
                    html += f"""
                        <tr>
                            <td><strong>{pair}</strong></td>
                            <td>{int(row['trades'])}</td>
                            <td style=\"color: green;\">{int(row['wins'])}</td>
                            <td style=\"color: red;\">{int(row['losses'])}</td>
                            <td>{row['win_rate']:.1f}%</td>
                            <td style=\"color: {'green' if row['total_pnl'] > 0 else 'red'};\">{row['total_pnl']:.2f}R</td>
                            <td>{row['avg_r']:.2f}R</td>
                            <td><a href=\"/pair/{pair}\">View Details →</a></td>
                        </tr>
                    """

            html += """
                    </tbody>
                </table>
            </div>

            <div id="cat-commodities" class="category-pane">
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
                if any(c in pair for c in commodities):
                    html += f"""
                        <tr>
                            <td><strong>{pair}</strong></td>
                            <td>{int(row['trades'])}</td>
                            <td style=\"color: green;\">{int(row['wins'])}</td>
                            <td style=\"color: red;\">{int(row['losses'])}</td>
                            <td>{row['win_rate']:.1f}%</td>
                            <td style=\"color: {'green' if row['total_pnl'] > 0 else 'red'};\">{row['total_pnl']:.2f}R</td>
                            <td>{row['avg_r']:.2f}R</td>
                            <td><a href=\"/pair/{pair}\">View Details →</a></td>
                        </tr>
                    """

            html += """
                    </tbody>
                </table>
            </div>

            <script>
                function showCategory(id, btn) {{
                    document.querySelectorAll('.category-pane').forEach(p => p.classList.remove('active'));
                    document.querySelectorAll('.category-btn').forEach(b => b.classList.remove('active'));
                    const el = document.getElementById(id);
                    if (el) el.classList.add('active');
                    if (btn) btn.classList.add('active');
                }}
            </script>
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
        <style>
            .tab-buttons {{ display:flex; gap:8px; margin:12px 0; }}
            .tab-btn {{ padding:8px 12px; border-radius:6px; background:#222; color:#ddd; border:1px solid #333; cursor:pointer; }}
            .tab-btn.active {{ background:#0b84ff; color:#fff; }}
            .tab-content {{ margin-top:12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>🔷 {pair}</h1>
                    <p>Order Block Analysis</p>
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                    <a href="/" class="back-btn">← Dashboard</a>
                    <button id="themeToggle" class="theme-toggle" onclick="toggleTheme()">🌙 Dark Mode</button>
                </div>
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
        
        # Summary section — now inside tabbed Details View
        html += f"""
            <div class="tabs">
                <div class="tab-buttons">
                    <button class="tab-btn active" onclick="showTab('tab-summary', this)">Summary</button>
                    <button class="tab-btn" onclick="showTab('tab-trades', this)">Trades</button>
                    <button class="tab-btn" onclick="showTab('tab-plots', this)">Plots</button>
                    <button class="tab-btn" onclick="showTab('tab-analysis', this)">Analysis</button>
                </div>

                <div class="tab-content" id="tab-summary">
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
        </div>
        """
        
        # Trades table (collapsible)
        # Wrap trade log in its own tab content
        if not trades.empty:
            html += f"""
            <div class="tab-content" id="tab-trades" style="display:none">
            <h2>Trade Log</h2>
            <button class="collapsible-header" onclick="toggleCollapsible(this)">
                <span><span class="toggle-icon">▶</span> Expand Trade Log ({len(trades)} trades)</span>
            </button>
            <div class="collapsible-content">
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
                
                # Format trade values safely
                entry_str = f"{trade.get('entry'):.4f}" if pd.notna(trade.get('entry')) else 'N/A'
                stop_str = f"{trade.get('stop'):.4f}" if pd.notna(trade.get('stop')) else 'N/A'
                r_str = f"{trade.get('R'):.4f}" if pd.notna(trade.get('R')) else 'N/A'
                
                html += f"""
                    <tr>
                        <td>{trade.get('type', 'N/A')}</td>
                        <td>{trade.get('ob_date', 'N/A')}</td>
                        <td>{trade.get('entry_date', 'N/A')}</td>
                        <td>{entry_str}</td>
                        <td>{stop_str}</td>
                        <td>{r_str}</td>
                        <td style="color: {outcome_color}; font-weight: bold;">
                            {trade.get('outcome_R', 0):.2f}R
                        </td>
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
            </div>
            </div>
            """
        
        # Charts (placed into the Plots tab)
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
            
            # Create trades overlay chart (entries/exits)
            try:
                fig_trades = plot_traded_positions(trades, df, pair)
                trades_file = f"{pair}_ob_trades.html"
                fig_trades.write_html(trades_file)
            except Exception:
                trades_file = chart_file

            # Create equity curve
            fig_equity = plot_equity_curve(trades, pair)
            equity_file = f"{pair}_ob_equity.html"
            fig_equity.write_html(equity_file)

            # Helper to get file metadata
            def _file_meta(path: str) -> str:
                try:
                    if not os.path.exists(path):
                        return "—"
                    size = os.path.getsize(path)
                    mtime = time.localtime(os.path.getmtime(path))
                    friendly_size = f"{size/1024:.1f} KB"
                    friendly_time = time.strftime('%Y-%m-%d %H:%M', mtime)
                    return f"{friendly_size} · {friendly_time}"
                except Exception:
                    return "—"

            chart_meta = _file_meta(chart_file)
            trades_meta = _file_meta(trades_file)
            equity_meta = _file_meta(equity_file)
            
            html += f"""
            <div class="tab-content" id="tab-plots" style="display:none">
            <h2>Charts</h2>
            <div class="equity-grid">
                <div class="equity-card clickable" onclick="openModal('{chart_file}', 'OB Detection Chart')">
                    <h4>📊 OB Detection Chart</h4>
                    <iframe data-src="/chart/{chart_file}" src="about:blank" onclick="event.stopPropagation()"></iframe>
                    <div class="chart-meta">{chart_meta}</div>
                </div>
                <div class="equity-card clickable" onclick="openModal('{trades_file}', 'Traded Positions')">
                    <h4>🎯 Traded Positions</h4>
                    <iframe data-src="/chart/{trades_file}" src="about:blank" onclick="event.stopPropagation()"></iframe>
                    <div class="chart-meta">{trades_meta}</div>
                </div>
                <div class="equity-card clickable" onclick="openModal('{equity_file}', 'Equity Curve')">
                    <h4>📈 Equity Curve</h4>
                    <iframe data-src="/chart/{equity_file}" src="about:blank" onclick="event.stopPropagation()"></iframe>
                    <div class="chart-meta">{equity_meta}</div>
                </div>
            </div>
            """
            
            # Add analysis text (place it in the Analysis tab)
            analysis_html = generate_analysis_text(stats, trades, pair)
            # close the plots tab content and open analysis tab
            html += """
            </div>
            <div class="tab-content" id="tab-analysis" style="display:none">
            """
            html += analysis_html
            html += """
            </div>
            """
        
        except Exception as e:
            print(f"Chart generation error for {pair}: {e}")
        
    except Exception as e:
        html += f'<div class="error">Error: {str(e)}</div>'
    
    # Modal
    html += r"""
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
        function showTab(tabId, btn) {
            // hide all tab contents
            document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
            // remove active class from buttons
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            // show requested tab
            const t = document.getElementById(tabId);
            if (t) {
                t.style.display = 'block';
                // Lazy-load any iframe thumbnails inside this tab
                t.querySelectorAll('iframe[data-src]').forEach(iframe => {
                    try {
                        if (!iframe.src || iframe.src === 'about:blank') {
                            iframe.src = iframe.getAttribute('data-src');
                            iframe.setAttribute('data-loaded', '1');
                        }
                    } catch (e) {
                        console.warn('Failed to lazy-load iframe', e);
                    }
                });
            }
            // mark button active
            if (btn) btn.classList.add('active');
        }

        // Ensure default tab is shown on load
        document.addEventListener('DOMContentLoaded', function() {
            // if a tab button is active, use it; otherwise default to summary
            const active = document.querySelector('.tab-btn.active');
            if (active) {
                const onclick = active.getAttribute('onclick');
                // try to parse the target id from the onclick call
                const m = onclick && onclick.match(/showTab\('([^']+)'/);
                if (m && m[1]) showTab(m[1], active);
                else showTab('tab-summary', active);
            } else {
                showTab('tab-summary', document.querySelector('.tab-btn'));
            }
        });

        function toggleCollapsible(button) {
            const content = button.nextElementSibling;
            const icon = button.querySelector('.toggle-icon');
            
            if (content.classList.contains('collapsed')) {
                content.classList.remove('collapsed');
                icon.classList.remove('collapsed');
            } else {
                content.classList.add('collapsed');
                icon.classList.add('collapsed');
            }
        }
        
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
    <div style="text-align:center; margin:20px 0;">
        <a href="/" class="back-btn">← Back to Dashboard</a>
    </div>
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
