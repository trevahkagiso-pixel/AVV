# Quick Start: Dual Strategy UI

## 🚀 Start Both UIs Right Now

```bash
# Make sure you're in /workspaces/AVV
cd /workspaces/AVV

# Start OB UI (Port 5001)
nohup python3 ob_ui.py --port 5001 > ob_ui.log 2>&1 & 
echo $! > ob_ui.pid

# Start Ichimoku UI (Port 5000) - if not already running
nohup python3 web_ui.py --port 5000 > ichimoku_ui.log 2>&1 &
echo $! > web_ui.pid

# Wait for servers to start
sleep 3

echo "✅ Both servers started!"
```

## 🌐 Access the Dashboards

- **Order Block Strategy**: http://127.0.0.1:5001
- **Ichimoku Cloud Strategy**: http://127.0.0.1:5000

## 📊 What You Can Do

### On OB Dashboard (5001)
1. **View Summary**: See total trades, wins, P&L across all pairs
2. **Analyze by Pair**: Click "View Details" on any pair row
3. **Trade Log**: See every trade with entry, stop, and R-multiple
4. **Charts**: Interactive candlestick + OB detection markers
5. **Dark Mode**: Click 🌙 Dark Mode toggle in top right

### On Ichimoku Dashboard (5000)
1. **View Summary**: See Ichimoku strategy performance
2. **Analyze by Pair**: Click "View Details" on any pair row
3. **Cloud Analysis**: Interactive candlestick + Ichimoku cloud + EMA
4. **Equity Curve**: Visual representation of P&L over time
5. **Dark Mode**: Click 🌙 Dark Mode toggle in top right

## 🎯 Key Differences

| Feature | OB UI | Ichimoku UI |
|---------|-------|-------------|
| **Port** | 5001 | 5000 |
| **Strategy** | Order Block (3-bar fractals) | Ichimoku Cloud |
| **Entry Signal** | BOS + Mitigation | Cloud Pierce + EMA Bias |
| **Risk Rule** | 1R Partial + BE + 2R | ATR-based |
| **Chart Type** | OB Markers | Cloud + EMA + Signals |

## 📝 Build Cache (Optional)

If you want to refresh the backtest results:

```bash
# Rebuild OB backtest cache
python3 ob_ui.py --build

# Rebuild Ichimoku backtest cache
python3 web_ui.py --build
```

## 🛑 Stop the Servers

```bash
# Kill both servers
pkill -f "python3 ob_ui.py"
pkill -f "python3 web_ui.py"

# Or kill by PID
kill $(cat ob_ui.pid)
kill $(cat web_ui.pid)
```

## 🔍 Check Logs

```bash
# Monitor OB UI logs
tail -f ob_ui.log

# Monitor Ichimoku UI logs
tail -f ichimoku_ui.log

# Or check specific error
grep -i error *.log
```

## 💡 Tips

1. **Dark Mode Persistence**: Your theme preference is saved locally
2. **Modal Charts**: Click any chart card to expand it
3. **Responsive Design**: Works on mobile, tablet, desktop
4. **Real-Time Updates**: Rebuild cache to get latest backtest results
5. **Custom Ports**: Change port with `--port 5002` (or any available port)

---

**Enjoy your dual-strategy dashboard! 📈**
