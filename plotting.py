"""
Plotting module for financial data visualization.
Uses Plotly for interactive candlestick charts and other visualizations.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def get_theme_detection_script() -> str:
    """
    Return a JavaScript snippet that detects parent dark-mode class and 
    updates the Plotly chart layout dynamically.
    
    This allows embedded charts (in iframes or divs) to respond to the parent 
    page's dark-mode toggle without page reload.
    
    Returns:
        HTML <script> tag with theme detection and layout update logic
    """
    return """
    <script>
    // Theme detection and dynamic chart update
    (function() {
        function detectDarkMode() {
            // Check if parent window or document has 'dark-mode' class
            try {
                if (window.parent && window.parent.document) {
                    return window.parent.document.body.classList.contains('dark-mode');
                }
            } catch(e) { /* cross-origin, ignore */ }
            return document.body.classList.contains('dark-mode') || 
                   (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
        }
        
        function applyTheme(isDark) {
            var template = isDark ? 'plotly_dark' : 'plotly_white';
            var plots = document.querySelectorAll('[data-plotly]');
            if (plots.length === 0) {
                // Fallback: look for any div with plotly graph
                plots = document.querySelectorAll('.plotly-graph-div');
            }
            plots.forEach(function(plot) {
                if (plot && plot.layout && Plotly) {
                    var newLayout = Object.assign({}, plot.layout, { template: template });
                    Plotly.relayout(plot, newLayout);
                }
            });
        }
        
        // Detect theme on page load
        window.addEventListener('load', function() {
            applyTheme(detectDarkMode());
        });
        
        // Watch for theme changes in parent window (triggered by dark-mode toggle)
        try {
            var observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.attributeName === 'class') {
                        applyTheme(detectDarkMode());
                    }
                });
            });
            
            // Observe parent body for class changes (cross-origin safe)
            if (window.parent && window.parent.document) {
                try {
                    observer.observe(window.parent.document.body, {
                        attributes: true,
                        attributeFilter: ['class']
                    });
                } catch(e) { /* cross-origin */ }
            }
            
            // Also observe local document (for local non-iframe use)
            observer.observe(document.body, {
                attributes: true,
                attributeFilter: ['class']
            });
        } catch(e) { /* noop */ }
    })();
    </script>
    """


def plot_candlestick(df: pd.DataFrame, title: str = "Candlestick Chart") -> None:
    """
    Create and display an interactive candlestick chart.
    
    Args:
        df: DataFrame with columns: open, high, low, close, and datetime index
        title: Title of the chart
    """
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close']
    )])
    
    fig.update_layout(
        title=title,
        yaxis_title="Price",
        xaxis_title="Date",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        hovermode="x unified"
    )
    
    fig.show()


def plot_price_line(df: pd.DataFrame, title: str = "Price Chart") -> None:
    """
    Create and display a line chart of closing prices.
    
    Args:
        df: DataFrame with columns: close, and datetime index
        title: Title of the chart
    """
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df['close'],
        mode='lines',
        name='Close Price',
        line=dict(color='blue', width=2)
    ))
    
    fig.update_layout(
        title=title,
        yaxis_title="Price",
        xaxis_title="Date",
        template="plotly_white",
        hovermode="x unified"
    )
    
    fig.show()


def plot_ohlc(df: pd.DataFrame, title: str = "OHLC Chart") -> None:
    """
    Create and display an OHLC (Open-High-Low-Close) bar chart.
    
    Args:
        df: DataFrame with columns: open, high, low, close, and datetime index
        title: Title of the chart
    """
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    fig = go.Figure(data=[go.Ohlc(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close']
    )])
    
    fig.update_layout(
        title=title,
        yaxis_title="Price",
        xaxis_title="Date",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        hovermode="x unified"
    )
    
    fig.show()


def plot_multiple_candlesticks(data_dict: dict, title: str = "Multiple Instruments") -> None:
    """
    Create candlestick charts for multiple instruments in subplots.
    
    Args:
        data_dict: Dictionary with format {instrument_name: dataframe}
        title: Title of the chart
    """
    num_pairs = len(data_dict)
    fig = make_subplots(
        rows=num_pairs, 
        cols=1,
        subplot_titles=list(data_dict.keys()),
        shared_xaxes=False
    )
    
    for idx, (name, df) in enumerate(data_dict.items(), 1):
        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name=name
            ),
            row=idx, col=1
        )
    
    fig.update_layout(
        title=title,
        height=300 * num_pairs,
        template="plotly_dark",
        hovermode="x unified"
    )
    
    fig.show()


def save_candlestick_html(df: pd.DataFrame, filename: str, title: str = "Candlestick Chart") -> None:
    """
    Create a candlestick chart and save it as an HTML file.
    The saved HTML will detect parent dark-mode and adjust theme dynamically.
    
    Args:
        df: DataFrame with columns: open, high, low, close, and datetime index
        filename: Output HTML filename
        title: Title of the chart
    """
    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close']
    )])
    
    fig.update_layout(
        title=title,
        yaxis_title="Price",
        xaxis_title="Date",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        hovermode="x unified"
    )
    
    fig.write_html(filename)
    
    # Inject theme-detection script into the saved HTML
    with open(filename, 'a') as f:
        f.write(get_theme_detection_script())
    
    print(f"✅ Chart saved to {filename}")


def plot_equity_curve(equity_series, title: str = "Equity Curve", filename: str = None, show: bool = True):
    """
    Plot an equity curve (P/L over time) and optionally save to an HTML file.

    Args:
        equity_series: Pandas Series or array-like of equity values (index should be datetime)
        title: Chart title
        filename: If provided, write the interactive chart to this HTML file
        show: If True, render the figure immediately
    Returns:
        plotly Figure
    """
    import pandas as pd
    import plotly.graph_objects as go

    if not isinstance(equity_series, pd.Series):
        try:
            equity_series = pd.Series(equity_series)
        except Exception:
            raise ValueError("equity_series must be a pandas Series or array-like")

    # Ensure datetime index if possible
    if not isinstance(equity_series.index, pd.DatetimeIndex):
        try:
            equity_series.index = pd.to_datetime(equity_series.index)
        except Exception:
            pass

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_series.index,
        y=equity_series.values,
        mode='lines',
        name='Equity',
        line=dict(color='green', width=2)
    ))

    # Draw zero (starting) line if useful
    fig.add_hline(y=equity_series.iloc[0] if len(equity_series) else 0, line=dict(color='gray', dash='dash'), annotation_text='Start')

    fig.update_layout(
        title=title,
        xaxis_title='Time',
        yaxis_title='Equity ($)',
        template='plotly_dark',
        hovermode='x unified',
    )

    if filename:
        fig.write_html(filename)
        
        # Inject theme-detection script into the saved HTML
        with open(filename, 'a') as f:
            f.write(get_theme_detection_script())
        
        print(f"✅ Equity chart saved to {filename}")

    if show:
        fig.show()

    return fig
