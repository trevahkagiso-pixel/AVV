"""
Lightweight Flask web UI to view backtest summaries and charts.

Usage:
  # Build cached summary and exit
  python web_ui.py --build

  # Run web server (default host=127.0.0.1, port=5000)
  python web_ui.py

Endpoints:
  /           - Backtest summary (runs backtests if no cache)
  /pair/<pair> - Details and run single backtest for a table (e.g., EUR_USD_daily)
  /chart/<filename> - Serve saved HTML chart files

Notes:
- By default the app will look for `backtest_summary.csv` and chart HTML files in the repo root.
- If cache missing, running the summary will trigger backtests (may take time).
"""

import os
import argparse
import threading
import time
from flask import Flask, request, send_from_directory, redirect
import pandas as pd

from ichimoku_backtest import run_all_pairs_backtest, run_backtest_from_database
from config import DATABASE_PATH
import plotting
import ichimoku
from backtest_analysis import analyze_backtest_results, format_analysis_for_html, get_analysis_css

APP = Flask(__name__)
CACHE_FILE = "backtest_summary.csv"
CHART_EXT = ".html"

# Background build state (threaded fallback)
_build_lock = threading.Lock()
_build_thread = None
_build_state = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_error": None,
}

# Try to use RQ job queue if available
try:
    import job_queue
    from build_tasks import build_summary as build_tasks_build_summary
    _rq_available = True
except Exception:
    job_queue = None
    build_tasks_build_summary = None
    _rq_available = False


# Load pair lists from `pairs.json` if present (keeps parity with OB UI)
def _load_pairs_from_json(path='pairs.json'):
    try:
        import json
        with open(path, 'r') as f:
            data = json.load(f)
        forex = data.get('FOREX_PAIRS', [])
        stocks = data.get('STOCK_PAIRS', [])
        commodities = data.get('COMMODITY_PAIRS', [])
        return forex, stocks, commodities
    except Exception:
        return [], [], []

FOREX_PAIRS, STOCK_PAIRS, COMMODITY_PAIRS = _load_pairs_from_json()
ALL_PAIRS = FOREX_PAIRS + STOCK_PAIRS + COMMODITY_PAIRS


def _list_sqlite_tables(sqlite_uri):
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
    try:
        cache_info = None
        if os.path.exists(CACHE_FILE):
            st = os.stat(CACHE_FILE)
            cache_info = {
                'path': CACHE_FILE,
                'exists': True,
                'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
                'size_bytes': st.st_size,
            }
        else:
            cache_info = {'path': CACHE_FILE, 'exists': False}

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


def get_base_css():
    """Return base CSS styling for all pages."""
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
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            padding: 40px;
            transition: background 0.25s ease, color 0.25s ease;
        }
        
        header {
            margin-bottom: 40px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 20px;
        }
        
        h1, h2 {
            color: #667eea;
            margin: 20px 0;
            font-size: 2.2em;
        }
        
        h3 {
            color: #764ba2;
            margin: 25px 0 15px 0;
            font-size: 1.6em;
            border-left: 4px solid #667eea;
            padding-left: 12px;
        }
        
        h4 {
            color: #555;
            margin-bottom: 10px;
        }
        
        p {
            margin: 15px 0;
            color: #666;
        }
        
        .status-banner {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .status-banner.running {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .status-banner.success {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }
        
        table thead {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        table th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
            font-size: 0.95em;
        }
        
        table td {
            padding: 12px 15px;
            border-bottom: 1px solid #f0f0f0;
        }
        
        table tbody tr {
            transition: all 0.3s ease;
        }
        
        table tbody tr:hover {
            background-color: #f8f9ff;
            transform: scale(1.01);
        }
        
        table tbody tr:last-child {
            background: #f5f5f5;
            font-weight: 600;
        }
        
        .button-group {
            display: flex;
            gap: 12px;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        
        a {
            color: #667eea;
            text-decoration: none;
            transition: all 0.3s ease;
            font-weight: 500;
        }
        
        a:hover {
            color: #764ba2;
            text-decoration: underline;
        }
        
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 600;
            transition: all 0.3s ease;
            text-decoration: none;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            color: white;
        }
        
        .btn.secondary {
            background: #f0f0f0;
            color: #667eea;
            box-shadow: none;
        }
        
        .btn.secondary:hover {
            background: #e0e0e0;
        }
        
        .equity-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 24px;
            margin: 30px 0;
        }
        
        .equity-card {
            border: 2px solid #f0f0f0;
            border-radius: 12px;
            padding: 20px;
            background: #fafafa;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }
        
        .equity-card:hover {
            border-color: #667eea;
            box-shadow: 0 4px 16px rgba(102, 126, 234, 0.15);
            transform: translateY(-3px);
        }
        
        .equity-card h4 {
            color: #667eea;
            font-size: 1.3em;
            margin-bottom: 12px;
        }
        
        .equity-card iframe {
            width: 100%;
            height: 380px;
            border: none;
            border-radius: 8px;

        .chart-meta {
            font-size: 12px;
            color: #666;
            padding: 8px 12px 16px 12px;
        }

        .dark-mode .chart-meta { color: #bbb; }
            margin: 15px 0;
            background: transparent;
        }
        
        .card-footer {
            text-align: center;
            margin-top: 12px;
        }
        
        .card-footer a {
            display: inline-block;
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border-radius: 6px;
            transition: all 0.3s ease;
        }
        
        .card-footer a:hover {
            background: #764ba2;
            color: white;
            text-decoration: none;
            transform: scale(1.05);
        }
        
        .stats-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }
        
        .stat-box {
            background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
            border-left: 4px solid #667eea;
            padding: 18px;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        
        .stat-box:hover {
            border-left-color: #764ba2;
            transform: translateX(5px);
        }
        
        .stat-box strong {
            color: #667eea;
            display: block;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        
        .stat-box span {
            font-size: 1.8em;
            color: #333;
            font-weight: 600;
        }
        
        .back-link {
            display: inline-block;
            margin: 20px 0;
            padding: 10px 20px;
            background: #f0f0f0;
            border-radius: 6px;
            transition: all 0.3s ease;
        }
        
        .back-link:hover {
            background: #e0e0e0;
        }
        
        hr {
            margin: 40px 0;
            border: none;
            height: 2px;
            background: linear-gradient(90deg, transparent, #667eea, transparent);
        }
        
        .error-box {
            background: #ff6b6b;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #ff4444;
        }
        
        .success-box {
            background: #4caf50;
            color: white;
        }
        
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.8);
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .modal-content {
            background-color: white;
            margin: 2% auto;
            padding: 0;
            width: 95%;
            height: 90%;
            border-radius: 12px;
            box-shadow: 0 10px 50px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            animation: slideIn 0.3s ease;
        }
        
        @keyframes slideIn {
            from {
                transform: translateY(-50px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }
        
        .modal-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 12px 12px 0 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 1.3em;
            font-weight: 600;
        }
        
        .close-btn {
            color: white;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
            padding: 0 10px;
        }
        
        .close-btn:hover {
            transform: scale(1.2);
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
            border-radius: 8px;
        }
        
        /* Clickable chart styling */
        .equity-card.clickable {
            cursor: pointer;
            position: relative;
        }
        
        .equity-card.clickable:hover {
            box-shadow: 0 6px 25px rgba(102, 126, 234, 0.25);
        }
        
        .equity-card.clickable::after {
            content: "🔍 Click to expand";
            position: absolute;
            top: 10px;
            right: 10px;
            background: #667eea;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8em;
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .equity-card.clickable:hover::after {
            opacity: 1;
        }
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            border-left: 4px solid #45a049;
        }
        
        .building-indicator {
            display: inline-block;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        footer {
            text-align: center;
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #f0f0f0;
            color: #999;
            font-size: 0.9em;
        }
    </style>
    <script>
    // Dark mode toggle: injects a button into the header and persists preference
    (function() {
        function setDarkMode(enabled) {
            try {
                if (enabled) document.body.classList.add('dark-mode');
                else document.body.classList.remove('dark-mode');
                localStorage.setItem('avv_theme', enabled ? 'dark' : 'light');
                updateToggleUI(enabled);
            } catch(e) { /* noop */ }
        }

        function updateToggleUI(enabled) {
            var btn = document.getElementById('themeToggle');
            if (!btn) return;
            btn.textContent = enabled ? '🌙 Dark Mode' : '☀️ Light Mode';
            btn.setAttribute('aria-pressed', enabled ? 'true' : 'false');
        }

        function createToggle() {
            var hdr = document.querySelector('.container header');
            if (!hdr) hdr = document.querySelector('header');
            if (!hdr) return;

            var btn = document.createElement('button');
            btn.id = 'themeToggle';
            btn.className = 'btn secondary';
            btn.style.marginLeft = '20px';
            btn.style.padding = '8px 14px';
            btn.style.fontSize = '0.9em';
            btn.onclick = function(e) {
                var isDark = document.body.classList.contains('dark-mode');
                setDarkMode(!isDark);
            };

            // Insert toggle into header (right side)
            var wrapper = document.createElement('div');
            wrapper.style.display = 'inline-block';
            wrapper.style.float = 'right';
            wrapper.appendChild(btn);
            hdr.appendChild(wrapper);

            // initialize UI state
            var stored = localStorage.getItem('avv_theme');
            var preferDark = stored === 'dark' || (stored === null && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
            setDarkMode(preferDark);
        }

        document.addEventListener('DOMContentLoaded', function() {
            createToggle();
        });
    })();
    </script>

    <style>
    /* Dark mode overrides - enhanced contrast and visibility */
    .dark-mode body, .dark-mode html { background: linear-gradient(135deg, #0f1724 0%, #0b1220 100%); color: #e8eef8; }
    .dark-mode .container { background: #0f1724; color: #e8eef8; box-shadow: 0 10px 40px rgba(0,0,0,0.6); border: 1px solid rgba(155,176,255,0.1); }
    .dark-mode header { border-bottom: 2px solid rgba(155,176,255,0.3); }
    .dark-mode h1, .dark-mode h2 { color: #c8d5ff; font-weight: 700; }
    .dark-mode h3 { color: #d4c5ff; font-weight: 700; border-left-color: rgba(155,176,255,0.5); }
    .dark-mode h4 { color: #b8cfe8; font-weight: 600; }
    .dark-mode p { color: #d4dce8; }
    .dark-mode li { color: #d4dce8; }
    .dark-mode table { border: 1px solid rgba(155,176,255,0.15); background: #1a2f5a; }
    .dark-mode table thead { background: linear-gradient(135deg, #1a2f5a 0%, #2b1f3d 100%); color: #f0f4ff; font-weight: 700; border-bottom: 2px solid rgba(155,176,255,0.2); }
    .dark-mode table td { color: #d4dce8; border-bottom: 1px solid rgba(155,176,255,0.08); }
    .dark-mode table tbody tr:last-child { background: rgba(155,176,255,0.05); font-weight: 600; }
    .dark-mode .btn { background: linear-gradient(135deg, #334155, #1f2937); color: #f5f7ff; font-weight: 600; }
    .dark-mode .btn.secondary { background: #1a3a52; color: #b8d4ff; border: 1px solid rgba(155,176,255,0.2); font-weight: 600; }
    .dark-mode a { color: #a8c5ff; font-weight: 500; }
    .dark-mode a:hover { color: #d4e3ff; }
    .dark-mode .status-banner { color: #f5f7ff; font-weight: 600; border: 1px solid rgba(255,255,255,0.1); }
    .dark-mode .status-banner.success { background: linear-gradient(135deg, #0f766e, #065f46); border: 1px solid rgba(0,255,200,0.2); }
    .dark-mode .status-banner.running { background: linear-gradient(135deg, #7c3aed, #db2777); border: 1px solid rgba(255,100,150,0.2); }
    .dark-mode .error-box { background: #8b1f1f; color: #fff; border: 1px solid rgba(255,100,100,0.3); font-weight: 500; }
    .dark-mode .equity-card { background: #1a3a52; border: 1px solid rgba(155,176,255,0.3); color: #d4dce8; }
    .dark-mode .equity-card h4 { color: #b8d4ff; }
    .dark-mode .equity-card p { color: #d4dce8; }
    .dark-mode .equity-card strong { color: #e8eef8; }
    .dark-mode .stat-box { background: rgba(155,176,255,0.08); border-left: 3px solid rgba(155,176,255,0.4); color: #d4dce8; }
    .dark-mode .stat-box strong { color: #a8c5ff; }
    .dark-mode .stat-box span { color: #e8eef8; font-weight: 700; }
    .dark-mode ul li { color: #d4dce8; }
    .dark-mode ol li { color: #d4dce8; }
    .dark-mode .analysis-section { background: #1a3a52; border: 1px solid rgba(155,176,255,0.2); color: #d4dce8; }
    </style>
    """


def build_summary(cache_path: str = CACHE_FILE):
    """Synchronous build that delegates to worker-safe `build_tasks.build_summary`.

    This keeps the same behavior while allowing the RQ worker to import
    `build_tasks` and run the job without importing the Flask app.
    """
    if build_tasks_build_summary is not None:
        return build_tasks_build_summary(cache_path)

    # Fallback: run inline
    print("Running multi-pair backtests (this may take a while)...")
    df_summary = run_all_pairs_backtest(show_plot=False)
    df_summary.to_csv(cache_path, index=False)

    # Also build commodity backtests and save a separate cache
    try:
        from ichimoku_backtest import run_commodity_backtests
        commodity_df = run_commodity_backtests(show_plot=False)
        commodity_df.to_csv('commodity_backtest_summary.csv', index=False)
    except Exception:
        pass
    print(f"Summary saved to {cache_path}")
    return df_summary


def _build_worker(cache_path: str = CACHE_FILE):
    """Worker that runs the summary build in a separate thread and updates state."""
    global _build_state
    try:
        _build_state["running"] = True
        _build_state["last_started"] = time.time()
        _build_state["last_error"] = None
        build_summary(cache_path)
        _build_state["last_finished"] = time.time()
    except Exception as e:
        _build_state["last_error"] = str(e)
    finally:
        _build_state["running"] = False


def build_summary_async(cache_path: str = CACHE_FILE) -> dict:
    """Start an asynchronous build.

    If RQ is available, enqueue a background job and return the job id dict.
    Otherwise, fall back to starting the internal thread-based worker.
    Returns a dict with keys: `started` (bool) and `job_id` (optional).
    """
    # Prefer RQ if available
    if _rq_available and job_queue is not None:
        try:
            job_id = job_queue.enqueue_build(cache_path)
            # persist last job id for status checks
            if job_id:
                with open(".last_build_job_id", "w") as fh:
                    fh.write(job_id)
            return {"started": True, "job_id": job_id}
        except Exception:
            # Fall through to threaded fallback
            pass

    # Threaded fallback (previous behavior)
    global _build_thread
    with _build_lock:
        if _build_thread is not None and _build_thread.is_alive():
            return {"started": False}
        _build_thread = threading.Thread(target=_build_worker, args=(cache_path,), daemon=True)
        _build_thread.start()
        return {"started": True}


@APP.route("/")
def index():

    # Load Forex and Stock summaries
    forex_df = None
    stock_df = None
    if os.path.exists(CACHE_FILE):
        forex_df = pd.read_csv(CACHE_FILE)
    else:
        build_summary_async(CACHE_FILE)
        forex_df = pd.DataFrame([{"Pair": "(building)", "Return [%]": None}])

    if os.path.exists("stock_backtest_summary.csv"):
        stock_df = pd.read_csv("stock_backtest_summary.csv")
    else:
        stock_df = pd.DataFrame([{"Symbol": "(building)", "Return [%]": None}])

    # Helper for details link
    def chart_link_fx(pair_text: str):
        try:
            sym = pair_text.replace("/", "_") + "_daily"
            return f'<a href="/pair/{sym}">View Details →</a>'
        except Exception:
            return "(no data)"

    def chart_link_stock(symbol: str):
        try:
            sym = symbol + "_daily"
            return f'<a href="/pair/{sym}">View Details →</a>'
        except Exception:
            return "(no data)"

    fx_display = forex_df.copy()
    fx_display["Details"] = fx_display["Pair"].apply(chart_link_fx)
    if "Chart" in fx_display.columns:
        fx_display = fx_display.drop("Chart", axis=1)
    for col in fx_display.columns:
        if col not in ["Pair", "Details"]:
            try:
                fx_display[col] = fx_display[col].apply(lambda x: f"{x:.2f}" if x is not None else "N/A")
            except:
                pass

    stock_display = stock_df.copy()
    stock_display["Details"] = stock_display["Symbol"].apply(chart_link_stock)
    for col in stock_display.columns:
        if col not in ["Symbol", "Details"]:
            try:
                stock_display[col] = stock_display[col].apply(lambda x: f"{x:.2f}" if x is not None else "N/A")
            except:
                pass

    status_html = ""
    if _build_state.get("running"):
        status_html = f"<div class='status-banner running'><div><span class='building-indicator'>⚙️</span> Build running...</div></div>"
    elif _build_state.get("last_error"):
        status_html = f"<div class='error-box'><strong>Last Build Error:</strong> {_build_state.get('last_error')}</div>"
    else:
        status_html = f"<div class='status-banner success'>✅ All systems operational</div>"

    html = get_base_css()
    html += """
    <div class="container">
        <header>
            <h1>📊 Ichimoku Backtest Dashboard</h1>
            <p style="color: #999; margin-top: 10px;">Real-time FX & Stock trading strategy analysis and equity curve visualization</p>
        </header>
        <div class="tab-nav">
            <button class="tab-btn active" onclick="showTab('forex')">Forex Results</button>
            <button class="tab-btn" onclick="showTab('stock')">Stock Results</button>
            <button class="tab-btn" onclick="showTab('commodity')">Commodity Results</button>
        </div>
        <div id="tab-forex" class="tab-content active">
            <h3>📈 Forex Backtest Results</h3>
            {forex_table}
            <h3>💹 Forex Equity Curves</h3>
            {forex_equity}
        </div>
        <div id="tab-stock" class="tab-content">
            <h3>📈 Stock Backtest Results</h3>
            {stock_table}
            <h3>💹 Stock Equity Curves</h3>
            {stock_equity}
        </div>
        <div id="tab-commodity" class="tab-content">
            <h3>⛏️ Commodity Backtest Results</h3>
            {commodity_table}
            <h3>💹 Commodity Equity Curves</h3>
            {commodity_equity}
        </div>
        <hr>
        <div class="button-group">
            <a href="/rebuild_async" class="btn">🔄 Rebuild Summary (Async)</a>
            <a href="/build_status" class="btn secondary">📊 Build Status</a>
        </div>
        <footer>Ichimoku Backtest Dashboard • Powered by Python, Flask & Plotly</footer>
    </div>
    <script>
    function showTab(tab) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(tabEl => tabEl.classList.remove('active'));
        document.querySelector('.tab-btn[onclick*="' + tab + '"]').classList.add('active');
        document.getElementById('tab-' + tab).classList.add('active');
    }
    </script>
    <style>
    .tab-nav { display: flex; gap: 20px; margin-bottom: 30px; }
    .tab-btn { padding: 12px 32px; font-size: 1.1em; border: none; border-radius: 8px 8px 0 0; background: #f0f0f0; color: #667eea; cursor: pointer; font-weight: 600; transition: all 0.3s; }
    .tab-btn.active { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    </style>
    """

    # Render tables and equity curves
    forex_table = fx_display.to_html(escape=False, index=False, classes="results-table")
    stock_table = stock_display.to_html(escape=False, index=False, classes="results-table")

    # Forex equity curves
    forex_equity_files = []
    for pair in ["EUR_USD_daily", "GBP_USD_daily", "USD_JPY_daily", "AUD_USD_daily", "USD_CAD_daily"]:
        eq_file = f"{pair}_equity{CHART_EXT}"
        if os.path.exists(eq_file):
            pair_display = pair.replace("_daily", "").replace("_", "/")
            forex_equity_files.append((pair_display, eq_file, pair))
    forex_equity = ""
    if forex_equity_files:
        forex_equity += "<div class='equity-grid'>"
        for pair_display, eq_file, pair_full in forex_equity_files:
            forex_equity += f"""
            <div class='equity-card'>
                <h4>💰 {pair_display}</h4>
                <iframe src="/chart/{eq_file}"></iframe>
                <div class='card-footer'>
                    <a href="/pair/{pair_full}">View Full Analysis →</a>
                </div>
            </div>
            """
        forex_equity += "</div>"
    else:
        forex_equity += "<p>⏳ No equity curves available yet.</p>"

    # Stock equity curves (if any)
    stock_equity_files = []
    for symbol in stock_df["Symbol"].dropna().unique():
        eq_file = f"{symbol}_daily_equity{CHART_EXT}"
        if os.path.exists(eq_file):
            stock_equity_files.append((symbol, eq_file, f"{symbol}_daily"))
    stock_equity = ""
    if stock_equity_files:
        stock_equity += "<div class='equity-grid'>"
        for symbol, eq_file, pair_full in stock_equity_files:
            stock_equity += f"""
            <div class='equity-card'>
                <h4>💰 {symbol}</h4>
                <iframe src="/chart/{eq_file}"></iframe>
                <div class='card-footer'>
                    <a href="/pair/{pair_full}">View Full Analysis →</a>
                </div>
            </div>
            """
        stock_equity += "</div>"
    else:
        stock_equity += "<p>⏳ No equity curves available yet.</p>"

    # Fill template
    # Insert tables and equity sections using f-string to avoid KeyError from CSS curly braces
    # Commodity table (if available)
    commodity_table = ""
    commodity_equity = ""
    if os.path.exists('commodity_backtest_summary.csv'):
        commodity_df = pd.read_csv('commodity_backtest_summary.csv')
        def chart_link_comm(row):
            try:
                sym = row.replace('=','_') + '_daily'
                return f'<a href="/pair/{sym}">View Details →</a>'
            except Exception:
                return '(no data)'
        comm_display = commodity_df.copy()
        if 'Ticker' in comm_display.columns:
            comm_display['Details'] = comm_display['Ticker'].apply(chart_link_comm)
        commodity_table = comm_display.to_html(escape=False, index=False, classes='results-table')

    html = html.replace("{forex_table}", forex_table)
    html = html.replace("{forex_equity}", forex_equity)
    html = html.replace("{stock_table}", stock_table)
    html = html.replace("{stock_equity}", stock_equity)
    html = html.replace("{commodity_table}", commodity_table)
    html = html.replace("{commodity_equity}", commodity_equity)
    return html


@APP.route("/rebuild")
def rebuild():
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    build_summary(CACHE_FILE)
    return redirect("/")


@APP.route("/rebuild_async")
def rebuild_async():
    started = build_summary_async(CACHE_FILE)
    if started:
        return redirect("/")
    else:
        return "A build is already running.", 409


@APP.route("/build_status")
def build_status():
    s = _build_state.copy()
    html = get_base_css()
    html += """
    <div class="container">
        <header>
            <h1>📊 Build Status</h1>
        </header>
    """
    
    if s.get("running"):
        html += "<div class='status-banner running'><span class='building-indicator'>⚙️</span> Build is currently running...</div>"
    else:
        html += "<div class='status-banner success'>✅ Build completed</div>"
    
    html += "<div class='stat-box'>"
    html += f"<strong>Last Started:</strong> <span>{s.get('last_started', 'Never')}</span><br>"
    html += f"<strong>Last Finished:</strong> <span>{s.get('last_finished', 'Never')}</span><br>"
    if s.get('last_error'):
        html += f"<strong style='color: red;'>Last Error:</strong> <span>{s.get('last_error')}</span>"
    html += "</div>"
    
    html += '<p><a href="/" class="back-link">← Back to Dashboard</a></p>'
    html += '</div>'
    return html


@APP.route("/pair/<pair>")
def pair_details(pair: str):
    try:
        # Determine which database to use based on pair name
        from config import STOCK_SYMBOLS, COMMODITY_SYMBOLS, STOCKS_DB_PATH, COMMODITIES_DB_PATH
        
        # Check if it's a stock
        base_symbol = pair.split('_')[0].upper()
        if base_symbol in [s.upper() for s in STOCK_SYMBOLS]:
            db_path = STOCKS_DB_PATH
        # Check if it's a commodity (e.g., GC_F_daily -> GC=F)
        elif any(pair.startswith(sym.replace('=', '_')) for sym in COMMODITY_SYMBOLS):
            db_path = COMMODITIES_DB_PATH
        # Default to forex
        else:
            db_path = DATABASE_PATH

        stats, df, bt = run_backtest_from_database(pair, db_path=db_path, show_plot=False)
    except Exception as e:
        html = get_base_css()
        html += f"""
        <div class="container">
            <div class="error-box">
                <h2>Error</h2>
                <p>Could not run backtest for {pair}</p>
                <pre>{str(e)}</pre>
            </div>
            <a href="/" class="back-link">← Back to Dashboard</a>
        </div>
        """
        return html, 400

    pair_display = pair.replace("_daily", "").replace("_", "/")
    
    # Collect stats for display
    stats_dict = {}
    for key in ["Return [%]", "Max. Drawdown [%]", "Win Rate [%]", "# Trades", "Exposure Time [%]"]:
        val = stats.get(key, "N/A")
        if isinstance(val, float):
            stats_dict[key] = f"{val:.2f}"
        else:
            stats_dict[key] = str(val)

    # Generate analysis
    analysis = analyze_backtest_results(stats, pair=pair_display)
    analysis_html = format_analysis_for_html(analysis)

    html = get_base_css()
    html += get_analysis_css()
    html += f"""
    <div class="container">
        <header>
            <h1>📊 {pair_display} Analysis</h1>
            <p style="color: #999;">Detailed backtest results and charts</p>
        </header>
    """
    
    
    html += "<h3>📈 Performance Metrics</h3>"
    html += "<div class='stats-list'>"
    
    metrics = [
        ("Return [%]", "📊", stats_dict.get("Return [%]", "N/A")),
        ("Max Drawdown [%]", "📉", stats_dict.get("Max. Drawdown [%]", "N/A")),
        ("Win Rate [%]", "🎯", stats_dict.get("Win Rate [%]", "N/A")),
        ("# Trades", "💹", stats_dict.get("# Trades", "N/A")),
        ("Exposure [%]", "⏱️", stats_dict.get("Exposure Time [%]", "N/A")),
    ]
    
    for label, icon, value in metrics:
        html += f"""
        <div class='stat-box'>
            <strong>{icon} {label}</strong>
            <span>{value}</span>
        </div>
        """
    
    html += "</div>"
    
    # Add analysis section
    html += "<h3>💡 AI-Generated Analysis & Insights</h3>"
    html += analysis_html

    # Charts section
    html += "<h3>📊 Charts</h3>"
    html += "<div class='equity-grid'>"
    
    charts = []
    
    # Equity curve
    try:
        eq_html = f"{pair}_equity{CHART_EXT}"
        equity_series = getattr(stats, '_equity_series', None)
        if equity_series is None:
            equity_df = getattr(stats, '_equity_df', None)
            if equity_df is not None and 'Equity' in equity_df.columns:
                equity_series = equity_df['Equity']

        if equity_series is not None:
            plotting.plot_equity_curve(equity_series, title=f"Equity Curve: {pair_display}", filename=eq_html, show=False)
            charts.append((f"💰 Equity Curve", eq_html))
    except Exception as e:
        print(f"Equity chart error: {e}")

    # Clean candlestick chart
    try:
        clean_html = f"{pair}_clean{CHART_EXT}"
        df_clean = df.copy()
        rename_map = {}
        for orig in ['Open','High','Low','Close']:
            if orig in df_clean.columns:
                rename_map[orig] = orig.lower()
        df_clean = df_clean.rename(columns=rename_map)
        plotting.save_candlestick_html(df_clean, clean_html, title=f"{pair_display} - Clean Chart")
        charts.append((f"📈 Candlestick Chart", clean_html))
    except Exception as e:
        print(f"Clean chart error: {e}")

    # Ichimoku chart
    try:
        ann_html = f"{pair}_ichimoku{CHART_EXT}"
        fig = ichimoku.plot_signals_ichimoku(df, 0, len(df) - 1, show_cloud=True, show=False)
        fig.write_html(ann_html)
        charts.append((f"☁️ Ichimoku Analysis", ann_html))
    except Exception as e:
        print(f"Ichimoku chart error: {e}")

    for chart_label, chart_file in charts:
        # compute file meta
        try:
            if os.path.exists(chart_file):
                _size = os.path.getsize(chart_file)
                _meta_size = f"{_size/1024:.1f} KB"
                _meta_time = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(chart_file)))
                _meta = f"{_meta_size} · {_meta_time}"
            else:
                _meta = '—'
        except Exception:
            _meta = '—'

        html += f"""
        <div class='equity-card clickable' onclick="openModal('{chart_file}', '{chart_label}')">
            <h4>{chart_label}</h4>
            <iframe data-src="/chart/{chart_file}" src="about:blank" onclick="event.stopPropagation()"></iframe>
            <div class="chart-meta">{_meta}</div>
        </div>
        """

    html += "</div>"
    
    # Add modal for chart expansion
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
            // lazy-load thumbnail iframe if present
            try {
                const thumb = document.querySelector('iframe[data-src="/chart/' + chartFile + '"]');
                if (thumb && (!thumb.src || thumb.src === 'about:blank')) {
                    thumb.src = thumb.getAttribute('data-src');
                    thumb.setAttribute('data-loaded', '1');
                }
            } catch(e) { console.warn('thumb load', e); }

            iframe.src = '/chart/' + chartFile;
            title.textContent = chartLabel + ' - Full View';
            modal.style.display = 'block';
        }
        
        function closeModal() {
            const modal = document.getElementById('chartModal');
            modal.style.display = 'none';
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('chartModal');
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
        
        // Close modal on Escape key
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeModal();
            }
        });
    </script>
    
    <hr>
    <a href="/" class="back-link">← Back to Dashboard</a>
    <footer>Ichimoku Backtest Dashboard • Powered by Python, Flask & Plotly</footer>
    </div>
    """
    return html


@APP.route("/chart/<filename>")
def serve_chart(filename):
    return send_from_directory(".", filename)


def main():
    parser = argparse.ArgumentParser(description="Ichimoku Backtest Web UI")
    parser.add_argument("--build", action="store_true", help="Build cache and exit")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    args = parser.parse_args()

    if args.build:
        print("Building cache...")
        build_summary(CACHE_FILE)
        print(f"Cache saved to {CACHE_FILE}")
        return

    print(f"Starting web server on http://{args.host}:{args.port}")
    APP.run(host=args.host, port=args.port, debug=True)


if __name__ == "__main__":
    main()
