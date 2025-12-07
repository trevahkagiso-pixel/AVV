"""
Ichimoku Cloud indicator module.
Provides Ichimoku calculations, signal generation, and visualization functions.
Data can be pulled from the local database or fetched from yfinance.
"""

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import plotly.express as px
from database import load_from_database


# Ichimoku parameters (defaults)
TENKAN = 9
KIJUN = 26
SENKOU_B = 52

# Risk settings (ATR-based)
ATR_LEN = 14
ATR_MULT_SL = 2.0  # SL = ATR * this
ATR_MULT_TP = 4.0  # TP = ATR * this (≈ 2R by default)


def fetch_data_from_database(table_name: str, db_path: str = "sqlite:///forex.db") -> pd.DataFrame:
    """
    Fetch OHLC data from local SQLite database.
    
    Args:
        table_name: Table name in database (e.g., 'EUR_USD_daily')
        db_path: Database path
    
    Returns:
        DataFrame with columns: open, high, low, close, (volume)
    """
    df = load_from_database(table_name, db_path)

    # Ensure the index is a proper DatetimeIndex
    try:
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors='coerce')
    except Exception:
        pass

    # Standardize column names to title case
    df.columns = [c.title() for c in df.columns]

    # Drop rows with missing essential OHLC values
    for col in ("Open", "High", "Low", "Close"):
        if col not in df.columns:
            # Some tables use lowercase column names; try common variants
            lower = col.lower()
            if lower in df.columns:
                df = df.rename(columns={lower: col})

    return df.dropna()


def fetch_data_yfinance(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
    """
    Fetch OHLC data from yfinance.
    
    Args:
        symbol: Ticker symbol (e.g., 'EURUSD=X', 'AAPL')
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        interval: Candlestick interval (e.g., '4h', '1d', '1h')
    
    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance not installed. Install with: pip install yfinance")
    
    df = yf.download(symbol, start=start, end=end, interval=interval,
                     auto_adjust=True, progress=False, threads=False)

    if df.empty:
        raise ValueError(f"No data returned for {symbol} @ {interval}. "
                         "Try a different symbol/interval or earlier START.")

    # Handle yfinance MultiIndex format
    if isinstance(df.columns, pd.MultiIndex):
        try:
            df = df.xs(symbol, axis=1, level=1)
        except KeyError:
            possible = [lev for lev in df.columns.levels[1]]
            raise KeyError(f"Symbol '{symbol}' not found. Available: {possible}")

    # Standardize column names
    df.columns = [c.title() for c in df.columns]
    return df.dropna()


def add_ichimoku(df: pd.DataFrame,
                 tenkan: int = TENKAN,
                 kijun: int = KIJUN,
                 senkou_b: int = SENKOU_B) -> pd.DataFrame:
    """
    Add Ichimoku Cloud indicators to DataFrame.
    
    - Computes Tenkan, Kijun, Span A, Span B (raw, no forward shift).
    - Adds ATR for risk management.
    - Provides bias-free chikou confirmations for signal logic.
    
    Args:
        df: DataFrame with columns: Open, High, Low, Close
        tenkan: Tenkan line period (default 9)
        kijun: Kijun line period (default 26)
        senkou_b: Senkou B line period (default 52)
    
    Returns:
        DataFrame with Ichimoku and ATR columns added
    """
    out = df.copy()

    # Try pandas_ta, fall back to manual
    tenkan_series, kijun_series = None, None
    try:
        res = ta.ichimoku(
            high=out["High"], low=out["Low"], close=out["Close"],
            tenkan=tenkan, kijun=kijun, senkou=senkou_b
        )
        ichi_core = res[0] if isinstance(res, tuple) else (res if isinstance(res, pd.DataFrame) else None)

        if isinstance(ichi_core, pd.DataFrame) and not ichi_core.empty:
            its_col = f"ITS_{tenkan}"
            iks_col = f"IKS_{kijun}"
            if its_col in ichi_core.columns and iks_col in ichi_core.columns:
                tenkan_series = ichi_core[its_col]
                kijun_series = ichi_core[iks_col]
    except Exception:
        pass

    # Manual fallback if pandas_ta unavailable or columns missing
    if tenkan_series is None or kijun_series is None:
        h, l = out["High"], out["Low"]
        tenkan_series = (h.rolling(tenkan).max() + l.rolling(tenkan).min()) / 2.0
        kijun_series = (h.rolling(kijun).max() + l.rolling(kijun).min()) / 2.0

    # Compute raw spans (no forward shift)
    h, l, c = out["High"], out["Low"], out["Close"]
    span_a_raw = (tenkan_series + kijun_series) / 2.0
    span_b_raw = (h.rolling(senkou_b).max() + l.rolling(senkou_b).min()) / 2.0

    out["ich_tenkan"] = tenkan_series
    out["ich_kijun"] = kijun_series
    out["ich_spanA"] = span_a_raw
    out["ich_spanB"] = span_b_raw

    # Plotting-only lagging line
    out["ich_chikou_plot"] = c.shift(-kijun)

    # Bias-free chikou confirmations for logic
    cloud_top = out[["ich_spanA", "ich_spanB"]].max(axis=1)
    cloud_bot = out[["ich_spanA", "ich_spanB"]].min(axis=1)
    out["chik_ok_long"] = c.shift(kijun) > cloud_top.shift(kijun)
    out["chik_ok_short"] = c.shift(kijun) < cloud_bot.shift(kijun)

    # ATR for risk management
    out["ATR"] = ta.atr(out["High"], out["Low"], out["Close"], length=ATR_LEN)

    # Drop warmup rows
    cols_needed = ["ich_tenkan", "ich_kijun", "ich_spanA", "ich_spanB", "ATR", "chik_ok_long", "chik_ok_short"]
    out = out.dropna(subset=cols_needed)
    
    return out


def add_ema_signal(df: pd.DataFrame, ema_length: int = 100, back_candles: int = 5) -> pd.DataFrame:
    """
    Add EMA trend signal to DataFrame.
    
    Rules:
      +1 (uptrend): For the last (back_candles + 1) bars, EVERY bar has Open > EMA and Close > EMA.
      -1 (downtrend): For the same window, EVERY bar has Open < EMA and Close < EMA.
       0 otherwise.
    
    Args:
        df: DataFrame with columns: Open, Close
        ema_length: EMA period (default 100)
        back_candles: Number of lookback candles (default 5)
    
    Returns:
        DataFrame with EMA and EMA_signal columns added
    """
    out = df.copy()
    
    # Add EMA
    out["EMA"] = ta.ema(close=out["Close"], length=ema_length)

    # Ensure numeric EMA and handle NaNs safely: comparisons should be False when EMA is not available
    ema_series = pd.to_numeric(out["EMA"], errors="coerce")
    ema_for_above = ema_series.fillna(float('inf'))   # missing EMA -> comparisons to inf -> False for '>'
    ema_for_below = ema_series.fillna(float('-inf'))  # missing EMA -> comparisons to -inf -> False for '<'

    # Window size: current bar + back_candles previous bars
    w = int(back_candles) + 1

    # Booleans per-bar relative to EMA (use filled series to avoid TypeError on NaN)
    above = (out["Open"] > ema_for_above) & (out["Close"] > ema_for_above)
    below = (out["Open"] < ema_for_below) & (out["Close"] < ema_for_below)
    
    # "All true in the last w bars" via rolling sum
    above_all = (above.rolling(w, min_periods=w).sum() == w)
    below_all = (below.rolling(w, min_periods=w).sum() == w)
    
    # Single signal column
    signal = np.where(above_all, 1, np.where(below_all, -1, 0)).astype(int)
    out["EMA_signal"] = signal
    
    return out


def create_ichimoku_signal(df: pd.DataFrame,
                           lookback_window: int = 10,
                           min_confirm: int = 5,
                           cloud_top_cols: tuple = ("ich_spanA", "ich_spanB"),
                           ema_signal_col: str = "EMA_signal") -> pd.DataFrame:
    """
    Generate trading signals combining Ichimoku cloud pierces with EMA trend confirmation.
    
    Signal logic:
      +1 (long): Cloud pierce-up + enough bars entirely above cloud + EMA_signal == +1
      -1 (short): Cloud pierce-down + enough bars entirely below cloud + EMA_signal == -1
       0 (none): otherwise
    
    Args:
        df: DataFrame with Ichimoku and EMA columns
        lookback_window: Number of bars to check for above/below cloud
        min_confirm: Minimum bars required entirely above/below cloud
        cloud_top_cols: Tuple of (spanA_col, spanB_col) names
        ema_signal_col: Name of EMA signal column
    
    Returns:
        DataFrame with signal column added
    """
    out = df.copy()
    
    # Verify required columns
    req_cols = ["Open", "Close", cloud_top_cols[0], cloud_top_cols[1], ema_signal_col]
    missing = [c for c in req_cols if c not in out.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")
    
    # Cloud boundaries
    spanA_col, spanB_col = cloud_top_cols
    cloud_top = out[[spanA_col, spanB_col]].max(axis=1)
    cloud_bot = out[[spanA_col, spanB_col]].min(axis=1)
    
    # Candles entirely above/below cloud
    above_cloud = (out["Open"] > cloud_top) & (out["Close"] > cloud_top)
    below_cloud = (out["Open"] < cloud_bot) & (out["Close"] < cloud_bot)
    
    above_count = above_cloud.rolling(lookback_window, min_periods=lookback_window).sum()
    below_count = below_cloud.rolling(lookback_window, min_periods=lookback_window).sum()
    
    # Current-bar pierce conditions
    pierce_up = (out["Open"] < cloud_top) & (out["Close"] > cloud_top)
    pierce_down = (out["Open"] > cloud_bot) & (out["Close"] < cloud_bot)
    
    # Trend confirmations
    up_trend_ok = above_count >= min_confirm
    down_trend_ok = below_count >= min_confirm
    
    # EMA alignment
    ema_up = (out[ema_signal_col] == 1)
    ema_down = (out[ema_signal_col] == -1)
    
    # Final conditions
    long_cond = up_trend_ok & pierce_up & ema_up
    short_cond = down_trend_ok & pierce_down & ema_down
    
    # Single signal column
    signal = np.where(long_cond & ~short_cond, 1,
             np.where(short_cond & ~long_cond, -1, 0)).astype(int)
    
    out["signal"] = signal
    return out


def plot_signals_ichimoku(
    df: pd.DataFrame,
    start_idx: int,
    end_idx: int,
    show_cloud: bool = True,
    title: str = None,
    offset_frac: float = 0.006,
    marker_size: int = 12,
    fig_width: int = 1000,
    fig_height: int = 700,
    show: bool = True,
):
    """
    Plot candlestick slice with Ichimoku cloud, EMA, and signal markers.
    
    Args:
        df: Full dataframe with Ichimoku/signal columns
        start_idx, end_idx: Row slice bounds (iloc-based)
        show_cloud: If True, overlay ich_spanA/B cloud
        title: Optional plot title
        offset_frac: Fraction of price for marker offset
        marker_size: Size of signal triangles
        fig_width, fig_height: Figure dimensions
        show: If True, render immediately
    
    Returns:
        Plotly Figure
    """
    data = df.iloc[start_idx:end_idx + 1].copy()
    if data.empty:
        raise ValueError("Selected slice is empty. Check start_idx/end_idx.")

    for col in ["Open", "High", "Low", "Close", "signal"]:
        if col not in data.columns:
            raise KeyError(f"Missing required column: {col}")

    x = data.index
    fig = go.Figure()

    # Candles
    fig.add_trace(go.Candlestick(
        x=x,
        open=data["Open"],
        high=data["High"],
        low=data["Low"],
        close=data["Close"],
        name="Price"
    ))

    # Ichimoku cloud
    if show_cloud:
        for col in ["ich_spanA", "ich_spanB"]:
            if col not in data.columns:
                raise KeyError(f"show_cloud=True but missing column: {col}")
        spanA, spanB = data["ich_spanA"], data["ich_spanB"]
        fig.add_trace(go.Scatter(x=x, y=spanA, mode="lines", name="Span A", line=dict(width=1)))
        fig.add_trace(go.Scatter(x=x, y=spanB, mode="lines", name="Span B",
                                 fill="tonexty", opacity=0.2, line=dict(width=1)))

    # EMA
    if "EMA" in data.columns:
        fig.add_trace(go.Scatter(
            x=x, y=data["EMA"], mode="lines", name="EMA",
            line=dict(color="blue", width=2, dash="dot")
        ))

    # Offset for markers
    pad = offset_frac * data["Close"].abs().replace(0, np.nan).fillna(method="ffill").fillna(method="bfill")

    # Long markers
    bull = data["signal"] == 1
    if bull.any():
        fig.add_trace(go.Scatter(
            x=x[bull],
            y=(data.loc[bull, "Low"] - pad.loc[bull]),
            mode="markers",
            name="Long signal",
            marker=dict(symbol="triangle-up", size=marker_size, color="green"),
            hovertemplate="Long signal<br>%{x|%Y-%m-%d %H:%M}<extra></extra>"
        ))

    # Short markers
    bear = data["signal"] == -1
    if bear.any():
        fig.add_trace(go.Scatter(
            x=x[bear],
            y=(data.loc[bear, "High"] + pad.loc[bear]),
            mode="markers",
            name="Short signal",
            marker=dict(symbol="triangle-down", size=marker_size, color="red"),
            hovertemplate="Short signal<br>%{x|%Y-%m-%d %H:%M}<extra></extra>"
        ))

    # Layout
    fig.update_layout(
        title=title or "Signals, Ichimoku & EMA",
        width=fig_width,
        height=fig_height,
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0)
    )

    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=True)

    if show:
        fig.show()

    return fig


def plot_ichimoku_cloud(
    df: pd.DataFrame,
    title: str = "Ichimoku Cloud",
    kijun_periods: int = 26,
    shift_cloud_forward: bool = False,
    show_chikou: bool = True,
    show_atr: bool = False,
    cloud_eps: float = None,
    fig_width: int = 1000,
    fig_height: int = 800,
):
    """
    Plot full Ichimoku cloud with candles and indicators.
    
    Args:
        df: DataFrame with Ichimoku columns
        title: Plot title
        kijun_periods: Kijun period for cloud shift
        shift_cloud_forward: If True, shift cloud forward by kijun_periods
        show_chikou: If True, overlay Chikou span
        show_atr: If True, overlay ATR on secondary y-axis
        cloud_eps: Tolerance for cloud bull/bear detection
        fig_width, fig_height: Figure dimensions
    
    Returns:
        Plotly Figure
    """
    df = df.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    if cloud_eps is None:
        cloud_eps = max(1e-8, float(df["Close"].abs().median()) * 1e-6)

    # Bar spacing
    if len(df.index) >= 2:
        bar_delta = pd.Series(df.index).diff().median()
        if pd.isna(bar_delta):
            bar_delta = pd.Timedelta(hours=4)
    else:
        bar_delta = pd.Timedelta(hours=4)

    x_main = df.index
    x_cloud = x_main + kijun_periods * bar_delta if shift_cloud_forward else x_main
    x_chikou = x_main - kijun_periods * bar_delta

    spanA = df["ich_spanA"]
    spanB = df["ich_spanB"]

    # Regime detection
    diff = spanA - spanB
    bull_mask = diff > cloud_eps
    bear_mask = diff < -cloud_eps
    flat_mask = ~(bull_mask | bear_mask)
    regime = pd.Series(np.where(bull_mask, 1, np.where(bear_mask, -1, 0)), index=df.index)
    regime = regime.replace(0, np.nan).ffill().bfill().fillna(0).astype(int)
    bull_mask = regime == 1
    bear_mask = regime == -1

    fig = go.Figure()

    # Candles
    fig.add_trace(go.Candlestick(
        x=x_main, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Price", increasing_line_color="#26a69a", decreasing_line_color="#ef5350"
    ))

    # Tenkan & Kijun
    fig.add_trace(go.Scatter(
        x=x_main, y=df["ich_tenkan"], name="Tenkan", mode="lines",
        line=dict(width=1.5, color="#2962ff")
    ))
    fig.add_trace(go.Scatter(
        x=x_main, y=df["ich_kijun"], name="Kijun", mode="lines",
        line=dict(width=1.5, color="#ff6d00")
    ))

    # Helper: add filled cloud segments
    def add_cloud_segments(mask: pd.Series, fillcolor: str, showlabel: str):
        grp_id = (mask != mask.shift()).cumsum()
        first_legend = True
        for g, sub in mask.groupby(grp_id):
            if not sub.iloc[0]:
                continue
            idx = sub.index
            xa = x_cloud[df.index.get_indexer_for(idx)]
            ya_top = spanA.loc[idx]
            yb_bot = spanB.loc[idx]

            fig.add_trace(go.Scatter(
                x=xa, y=ya_top, mode="lines",
                line=dict(width=1, color="rgba(33,150,243,0.7)"),
                showlegend=first_legend, name=showlabel
            ))
            fig.add_trace(go.Scatter(
                x=xa, y=yb_bot, mode="lines",
                line=dict(width=1, color="rgba(244,67,54,0.7)"),
                fill="tonexty", fillcolor=fillcolor,
                showlegend=False, hoverinfo="x+y"
            ))
            first_legend = False

    add_cloud_segments(bull_mask, fillcolor="rgba(0,200,0,0.18)", showlabel="Cloud (Bull)")
    add_cloud_segments(bear_mask, fillcolor="rgba(200,0,0,0.18)", showlabel="Cloud (Bear)")

    # Chikou span
    if show_chikou and "ich_chikou_plot" in df.columns:
        fig.add_trace(go.Scatter(
            x=x_chikou, y=df["ich_chikou_plot"], name="Chikou",
            mode="lines", line=dict(width=1.2, color="#7b1fa2", dash="dot")
        ))

    # ATR (optional, secondary y)
    if show_atr and "ATR" in df.columns:
        fig.add_trace(go.Scatter(
            x=x_main, y=df["ATR"], name="ATR",
            mode="lines", line=dict(width=1.2, color="#455a64"), yaxis="y2"
        ))
        fig.update_layout(yaxis2=dict(title="ATR", overlaying="y", side="right", showgrid=False))

    fig.update_layout(
        title=title,
        xaxis=dict(title="Time", rangeslider=dict(visible=False)),
        yaxis=dict(title="Price"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        template="plotly_white",
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode="x unified",
        width=fig_width,
        height=fig_height,
    )

    return fig
