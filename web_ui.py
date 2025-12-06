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
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            padding: 40px;
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
            margin: 15px 0;
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
    # If cached summary exists, load it; otherwise run backtests and cache
    if os.path.exists(CACHE_FILE):
        df = pd.read_csv(CACHE_FILE)
    else:
        # kick off an async build and show a placeholder
        build_summary_async(CACHE_FILE)
        df = pd.DataFrame([{"Pair": "(building)", "Return [%]": None}])

    # Add chart links where available
    def chart_link(pair_text: str):
        try:
            sym = pair_text.replace("/", "_") + "_daily"
            return f'<a href="/pair/{sym}">View Details →</a>'
        except Exception:
            return "(no data)"

    df_display = df.copy()
    df_display["Details"] = df_display["Pair"].apply(chart_link)
    if "Chart" in df_display.columns:
        df_display = df_display.drop("Chart", axis=1)

    # Format numeric columns
    for col in df_display.columns:
        if col not in ["Pair", "Details"]:
            try:
                df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}" if x is not None else "N/A")
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
            <p style="color: #999; margin-top: 10px;">Real-time FX trading strategy analysis and equity curve visualization</p>
        </header>
    """
    
    html += status_html
    
    html += "<h3>📈 Backtest Results</h3>"
    html += df_display.to_html(escape=False, index=False, classes="results-table")
    
    html += "<h3>💹 Equity Curves</h3>"
    equity_files = []
    for pair in ["EUR_USD_daily", "GBP_USD_daily", "USD_JPY_daily", "AUD_USD_daily", "USD_CAD_daily"]:
        eq_file = f"{pair}_equity{CHART_EXT}"
        if os.path.exists(eq_file):
            pair_display = pair.replace("_daily", "").replace("_", "/")
            equity_files.append((pair_display, eq_file, pair))
    
    if equity_files:
        html += "<div class='equity-grid'>"
        for pair_display, eq_file, pair_full in equity_files:
            html += f"""
            <div class='equity-card'>
                <h4>💰 {pair_display}</h4>
                <iframe src="/chart/{eq_file}"></iframe>
                <div class='card-footer'>
                    <a href="/pair/{pair_full}">View Full Analysis →</a>
                </div>
            </div>
            """
        html += "</div>"
    else:
        html += "<p>⏳ No equity curves available yet.</p>"
    
    html += """
    <hr>
    <div class="button-group">
        <a href="/rebuild_async" class="btn">🔄 Rebuild Summary (Async)</a>
        <a href="/build_status" class="btn secondary">📊 Build Status</a>
    </div>
    <footer>Ichimoku Backtest Dashboard • Powered by Python, Flask & Plotly</footer>
    </div>
    """
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
        stats, df, bt = run_backtest_from_database(pair, show_plot=False)
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
        html += f"""
        <div class='equity-card'>
            <h4>{chart_label}</h4>
            <iframe src="/chart/{chart_file}"></iframe>
        </div>
        """

    html += "</div>"
    
    html += """
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
