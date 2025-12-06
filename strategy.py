"""
Backtesting strategy module.
Provides SignalStrategy and SimpleSignalStrategy for backtesting with Ichimoku signals and ATR-based risk management.
"""

from backtesting import Strategy


class SignalStrategy(Strategy):
    """
    Generic signal-based trading strategy with ATR-based stop-loss and risk-reward management.
    
    Entry conditions:
      - Long: signal == 1, current ATR > 0
      - Short: signal == -1, current ATR > 0
    
    Exit conditions:
      - Stop-loss: SL = entry_price ± (ATR * atr_mult_sl)
      - Take-profit: TP = entry_price ± (SL_distance * rr_mult_tp)
    
    Parameters
    ----------
    atr_mult_sl : float
        Multiplier for ATR to calculate stop-loss distance (default 1.5)
    rr_mult_tp : float
        Risk-reward ratio multiplier; TP distance = SL distance * rr_mult_tp (default 2.0)
    """
    
    # Strategy parameters (can be optimized)
    atr_mult_sl: float = 1.5   # stop-loss distance = ATR * atr_mult_sl
    rr_mult_tp: float = 2.0    # take-profit distance = SL distance * rr_mult_tp

    def init(self):
        """
        Initialize strategy. Called once at backtest start.
        """
        pass

    def next(self):
        """
        Logic executed on each bar.
        Manages open trades and evaluates new entry signals.
        """
        i = -1  # Current bar index
        signal = int(self.data.signal[i])  # +1 long, -1 short, 0 none
        close = float(self.data.Close[i])
        atr = float(self.data.ATR[i])

        # Skip if ATR is invalid
        if not (atr > 0):
            return

        # --- Manage open trades ---
        if self.position:
            # Do nothing; backtesting.py handles SL/TP exits automatically
            return

        # --- New entry logic ---
        sl_dist = atr * self.atr_mult_sl
        tp_dist = sl_dist * self.rr_mult_tp

        if signal == 1:  # Long entry
            sl = close - sl_dist
            tp = close + tp_dist
            self.buy(size=0.99, sl=sl, tp=tp)

        elif signal == -1:  # Short entry
            sl = close + sl_dist
            tp = close - tp_dist
            self.sell(size=0.99, sl=sl, tp=tp)


class SimpleSignalStrategy(Strategy):
    """
    Simplified signal-based strategy with looser entry conditions.
    
    Entry conditions:
      - Long: EMA_signal == 1 (uptrend confirmed by EMA)
      - Short: EMA_signal == -1 (downtrend confirmed by EMA)
    
    This strategy trades EMA crossovers without requiring Ichimoku cloud pierces,
    making it more responsive and likely to generate more trades.
    
    Exit conditions:
      - Stop-loss: SL = entry_price ± (ATR * atr_mult_sl)
      - Take-profit: TP = entry_price ± (SL_distance * rr_mult_tp)
    
    Parameters
    ----------
    atr_mult_sl : float
        Multiplier for ATR to calculate stop-loss distance (default 1.5)
    rr_mult_tp : float
        Risk-reward ratio multiplier; TP distance = SL distance * rr_mult_tp (default 2.0)
    """
    
    # Strategy parameters
    atr_mult_sl: float = 1.5
    rr_mult_tp: float = 2.0

    def init(self):
        """Initialize strategy."""
        pass

    def next(self):
        """Execute strategy logic on each bar."""
        i = -1  # Current bar index
        close = float(self.data.Close[i])
        atr = float(self.data.ATR[i])
        
        # Try to use EMA_signal if available; otherwise use Ichimoku signal
        try:
            ema_signal = int(self.data.EMA_signal[i])
            signal = ema_signal
        except Exception:
            # Fall back to ichimoku signal if EMA_signal not available
            try:
                signal = int(self.data.signal[i])
            except Exception:
                signal = 0
        
        # Skip if ATR is invalid
        if not (atr > 0):
            return

        # --- Manage open trades ---
        if self.position:
            # Do nothing; backtesting.py handles SL/TP exits automatically
            return

        # --- New entry logic ---
        sl_dist = atr * self.atr_mult_sl
        tp_dist = sl_dist * self.rr_mult_tp

        if signal == 1:  # Long entry
            sl = close - sl_dist
            tp = close + tp_dist
            self.buy(size=0.99, sl=sl, tp=tp)

        elif signal == -1:  # Short entry
            sl = close + sl_dist
            tp = close - tp_dist
            self.sell(size=0.99, sl=sl, tp=tp)

