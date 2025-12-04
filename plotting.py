"""
Plotting module for financial data visualization.
Uses Plotly for interactive candlestick charts and other visualizations.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


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
        template="plotly_white",
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
        template="plotly_white",
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
        template="plotly_white",
        hovermode="x unified"
    )
    
    fig.show()


def save_candlestick_html(df: pd.DataFrame, filename: str, title: str = "Candlestick Chart") -> None:
    """
    Create a candlestick chart and save it as an HTML file.
    
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
        template="plotly_white",
        hovermode="x unified"
    )
    
    fig.write_html(filename)
    print(f"✅ Chart saved to {filename}")
