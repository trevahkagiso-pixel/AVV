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


def create_combined_equity_chart(filename: str = "combined_equity.html"):
    """Create a combined equity curve chart for all pairs with equity files.
    
    Returns the filename if successful, None otherwise.
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        equity_files = []
        for pair in ["EUR_USD_daily", "GBP_USD_daily", "USD_JPY_daily", "AUD_USD_daily", "USD_CAD_daily"]:
            eq_file = f"{pair}_equity{CHART_EXT}"
            if os.path.exists(eq_file):
                equity_files.append((pair, eq_file))
        
        if not equity_files:
            return None
        
        # Create subplots with one row per pair
        fig = make_subplots(
            rows=len(equity_files),
            cols=1,
            subplot_titles=[pair.replace("_daily", "") for pair, _ in equity_files],
            shared_xaxes=False,
            vertical_spacing=0.08
        )
        
        # Read each equity HTML and extract data
        for idx, (pair, eq_file) in enumerate(equity_files, 1):
            try:
                # Read the equity CSV data if available, or reconstruct from database
                # For now, we'll add a simple placeholder and link
                pass
            except Exception as e:
                print(f"Could not load equity data for {pair}: {e}")
        
        return None  # Fallback: don't generate combined chart for now
    except Exception as e:
        print(f"Error creating combined equity chart: {e}")
        return None


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
        # Expect pair_text like "EUR/USD" -> table name EUR_USD_daily
        try:
            sym = pair_text.replace("/", "_") + "_daily"
            filename = f"{sym}{CHART_EXT}"
            if os.path.exists(filename):
                return f'<a href="/pair/{sym}">Details</a>'
            else:
                return "(no chart)"
        except Exception:
            return "(no chart)"

    df_display = df.copy()
    df_display["Details"] = df_display["Pair"].apply(chart_link)
    # Remove old "Chart" column if it exists
    if "Chart" in df_display.columns:
        df_display = df_display.drop("Chart", axis=1)

    html = "<h2>Ichimoku Backtest Summary</h2>"
    html += "<p>Refresh this page to rebuild the cached summary if you re-run backtests.</p>"
    # Show build state
    if _build_state.get("running"):
        html += f"<p><b>Build running</b> (started: {_build_state.get('last_started')})</p>"
    else:
        if _build_state.get("last_finished"):
            html += f"<p>Last build finished: {_build_state.get('last_finished')}</p>"
    
    html += "<h3>Backtest Results</h3>"
    html += df_display.to_html(escape=False, index=False)
    
    # Add equity curves section
    html += "<h3>Equity Curves</h3>"
    equity_files = []
    for pair in ["EUR_USD_daily", "GBP_USD_daily", "USD_JPY_daily", "AUD_USD_daily", "USD_CAD_daily"]:
        eq_file = f"{pair}_equity{CHART_EXT}"
        if os.path.exists(eq_file):
            pair_display = pair.replace("_daily", "").replace("_", "/")
            equity_files.append((pair_display, eq_file))
    
    if equity_files:
        html += "<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 20px;'>"
        for pair_display, eq_file in equity_files:
            html += f"""
            <div style='border: 1px solid #ddd; padding: 10px; border-radius: 5px;'>
                <h4>{pair_display}</h4>
                <iframe src="/chart/{eq_file}" style='width: 100%; height: 400px; border: none;'></iframe>
                <p style='text-align: center;'><a href="/pair/{eq_file.replace('_equity.html', '')}">View Details</a></p>
            </div>
            """
        html += "</div>"
    else:
        html += "<p>No equity curves available yet. <a href='/rebuild_async'>Run backtest</a></p>"
    
    html += "<hr><p><a href=\"/rebuild_async\">Rebuild Summary (start async)</a> | <a href=\"/build_status\">Build status</a></p>"
    return html


@APP.route("/rebuild")
def rebuild():
    # Force re-run backtests and update cache
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    build_summary(CACHE_FILE)
    return redirect("/")


@APP.route("/rebuild_async")
def rebuild_async():
    # Start an asynchronous rebuild and return immediately
    started = build_summary_async(CACHE_FILE)
    if started:
        return redirect("/")
    else:
        return "A build is already running.", 409


@APP.route("/build_status")
def build_status():
    s = _build_state.copy()
    html = "<h3>Build Status</h3>"
    html += f"<pre>{s}</pre>"
    html += '<p><a href="/">Back</a></p>'
    return html


@APP.route("/pair/<pair>")
def pair_details(pair: str):
    """Run a single pair backtest and return stats and link to chart if present.
    Pair should be provided as table name, e.g. EUR_USD_daily
    """
    try:
        stats, df, bt = run_backtest_from_database(pair, show_plot=False)
    except Exception as e:
        return f"<h3>Error running backtest for {pair}</h3><pre>{e}</pre>", 400

    html = f"<h2>Backtest Results: {pair}</h2>"
    html += "<h3>Stats</h3>"
    # Render key stats
    keys = ["Return [%]", "Max. Drawdown [%]", "Win Rate [%]", "# Trades", "Exposure Time [%]"]
    html += "<ul>"
    for k in keys:
        v = stats.get(k, "N/A")
        html += f"<li><b>{k}</b>: {v}</li>"
    html += "</ul>"

    # Attach and save equity curve if available
    try:
        eq_html = f"{pair}_equity{CHART_EXT}"
        equity_df = getattr(stats, '_equity_df', None)
        equity_series = getattr(stats, '_equity_series', None)
        if equity_series is None and equity_df is not None and 'Equity' in equity_df.columns:
            equity_series = equity_df['Equity']

        if equity_series is not None:
            plotting.plot_equity_curve(equity_series, title=f"Equity Curve: {pair}", filename=eq_html, show=False)
            html += f'<p><a href="/chart/{eq_html}">Equity curve</a></p>'
    except Exception as e:
        html += f"<p>Could not create equity chart: {e}</p>"

    # Save clean candlestick chart
    try:
        clean_html = f"{pair}_clean{CHART_EXT}"
        # prepare a clean DataFrame (open/high/low/close columns expected by plotting)
        df_clean = df.copy()
        # standardize column names to lower-case for plotting.save_candlestick_html
        # plotting expects columns named 'open','high','low','close'
        rename_map = {c: c.lower() for c in df_clean.columns if c.lower() in ['open','high','low','close']}
        if not rename_map:
            # common columns maybe Title cased
            rename_map = {}
            for orig in ['Open','High','Low','Close']:
                if orig in df_clean.columns:
                    rename_map[orig] = orig.lower()
        df_clean = df_clean.rename(columns=rename_map)
        plotting.save_candlestick_html(df_clean, clean_html, title=f"{pair} - Clean Chart")
        html += f'<p><a href="/chart/{clean_html}">Clean chart</a></p>'
    except Exception as e:
        html += f"<p>Could not create clean chart: {e}</p>"

    # Save annotated Ichimoku chart with entries/exits
    try:
        ann_html = f"{pair}_ichimoku{CHART_EXT}"
        # Use ichimoku.plot_signals_ichimoku to build the annotated chart
        # We'll attempt to save full-range annotated chart
        fig = ichimoku.plot_signals_ichimoku(df, 0, len(df) - 1, show_cloud=True, show=False)
        fig.write_html(ann_html)
        html += f'<p><a href="/chart/{ann_html}">Annotated Ichimoku chart</a></p>'
    except Exception as e:
        html += f"<p>Could not create annotated chart: {e}</p>"

    # Link to saved chart if exists
    filename = f"{pair}{CHART_EXT}"
    if os.path.exists(filename):
        html += f'<p><a href="/chart/{filename}">Open saved chart</a></p>'

    html += '<p><a href="/">Back to summary</a></p>'
    return html


@APP.route("/chart/<path:filename>")
def serve_chart(filename: str):
    # Serve HTML files from repo root
    root = os.getcwd()
    if not os.path.exists(os.path.join(root, filename)):
        return f"Chart {filename} not found", 404
    return send_from_directory(root, filename)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lightweight Ichimoku web UI")
    parser.add_argument("--build", action="store_true", help="Build cached summary and exit")
    parser.add_argument("--host", default="127.0.0.1", help="Host for Flask app")
    parser.add_argument("--port", default=5000, type=int, help="Port for Flask app")
    args = parser.parse_args(argv)

    if args.build:
        build_summary()
        return

    # Run Flask app
    APP.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
