# Unified Dashboard Quick Start

## Overview

The Unified Dashboard (port 5002) provides a central hub to toggle between two analysis strategies:

- **Ichimoku Strategy** (port 5000) - Technical indicator-based analysis
- **Order Block Strategy** (port 5001) - Support/resistance level analysis

## Accessing the Dashboard

```bash
# Open in browser
http://127.0.0.1:5002
```

## Main Features

### 1. Strategy Toggle
In the header, use the toggle buttons to switch between strategies:
- 📈 **Ichimoku** - Switch to Ichimoku analysis
- 🔲 **Order Block** - Switch to Order Block analysis

The active strategy preference is saved in your browser session.

### 2. Service Status Monitor
Real-time status indicators show:
- ✅ Online / ❌ Offline status for each service
- Cache update timestamps
- Available database tables

### 3. Unified Admin Panel
Access via the ⚙️ **Admin** button in the header:

```
http://127.0.0.1:5002/admin
```

**Admin Panel Features:**
- ✏️ Edit `pairs.json` directly from the browser
- 📡 View real-time service status
- 💾 Save changes with one-click rebuild triggers
- 🔗 Quick links to all three services

### 4. Dark Mode
Click the 🌙 moon icon to toggle dark/light mode:
- Preference saved to localStorage
- Applies across all pages

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/admin` | GET | Admin panel for pair management |
| `/api/service-status` | GET | JSON status of both services |
| `/api/active-strategy` | GET | Get current active strategy |
| `/api/switch-strategy/<strategy>` | GET | Switch strategy (ichimoku or ob) |
| `/api/pairs` | GET | Get pairs.json content |
| `/api/pairs` | POST | Update pairs.json and trigger rebuilds |
| `/switch` | GET | Redirect to active strategy UI |
| `/pair/<pair>` | GET | Redirect to pair detail in active UI |

## Workflow Examples

### Viewing a Specific Pair

1. Go to dashboard: `http://127.0.0.1:5002`
2. Select your preferred strategy (Ichimoku or OB)
3. Navigate to the UI by clicking "Open [Strategy] UI"
4. View pair details from there

Alternatively, direct URLs:
```
# Ichimoku view
http://127.0.0.1:5000/pair/EUR_USD_daily

# Order Block view with Bokeh chart
http://127.0.0.1:5001/pair/EUR_USD_daily
```

### Adding a New Trading Pair

1. Go to admin panel: `http://127.0.0.1:5002/admin`
2. Edit the `pairs.json` textarea
3. Add your pair to the appropriate category (FOREX_PAIRS, STOCK_PAIRS, or COMMODITY_PAIRS)
4. Click "💾 Save & Rebuild"
5. Both services will automatically rebuild their caches

Example:
```json
{
  "FOREX_PAIRS": [
    "EUR_USD_daily",
    "GBP_USD_daily",
    "AUD_USD_daily",
    "USD_CAD_daily",
    "USD_JPY_daily",
    "NEW_PAIR_daily"  // Add here
  ],
  "STOCK_PAIRS": [...],
  "COMMODITY_PAIRS": [...]
}
```

### Switching Between Strategies Mid-Session

Click the toggle buttons in the header:
- 📈 Click to switch to Ichimoku
- 🔲 Click to switch to Order Block

Your preference is saved and persists during your session.

## Running the Services

Start all three services:

```bash
# Terminal 1: Ichimoku UI (port 5000)
cd /workspaces/AVV
python3 web_ui.py --port 5000

# Terminal 2: Order Block UI (port 5001)
cd /workspaces/AVV
python3 ob_ui.py --port 5001

# Terminal 3: Unified Dashboard (port 5002)
cd /workspaces/AVV
python3 unified_ui.py --port 5002
```

Or in background:
```bash
python3 web_ui.py --port 5000 > web_ui.log 2>&1 &
python3 ob_ui.py --port 5001 > ob_ui.log 2>&1 &
python3 unified_ui.py --port 5002 > unified_ui.log 2>&1 &
```

## Troubleshooting

### Dashboard shows services as offline
- Verify services are running: `ps aux | grep -E "web_ui|ob_ui"`
- Check logs: `tail -f unified_ui.log`
- Restart services if needed

### Admin panel won't save pairs
- Check JSON syntax (use browser console for errors)
- Verify both services are online
- Check disk space and file permissions on pairs.json
- Review `unified_ui.log` for POST errors

### Strategy toggle not working
- Browser cookies/session might be disabled
- Try refreshing the page
- Check browser console for JavaScript errors

### Cannot connect to dashboard
- Ensure port 5002 is free: `lsof -i :5002`
- Kill existing process: `pkill -f unified_ui.py`
- Restart: `python3 unified_ui.py --port 5002 &`

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│         Unified Dashboard (Port 5002)                   │
│  • Master UI with toggle & admin features               │
│  • Proxies to Ichimoku and OB services                  │
│  • Session management & preferences                     │
└────────────┬──────────────────────────┬─────────────────┘
             │                          │
      ┌──────▼────────┐        ┌────────▼──────────┐
      │ Ichimoku UI   │        │  Order Block UI   │
      │ (Port 5000)   │        │  (Port 5001)      │
      │               │        │                   │
      │ • Technical   │        │ • OB indicators   │
      │   indicators  │        │ • Bokeh charts   │
      │ • Ichimoku    │        │ • Trade markers  │
      │   clouds      │        │                   │
      └───────┬───────┘        └────────┬──────────┘
              │                         │
              └──────────┬──────────────┘
                         │
                    ┌────▼────┐
                    │ Database │
                    │  Cache   │
                    │ pairs.json
                    └──────────┘
```

## Key Files

- `unified_ui.py` - Master dashboard service (port 5002)
- `web_ui.py` - Ichimoku strategy UI (port 5000)
- `ob_ui.py` - Order Block strategy UI (port 5001)
- `pairs.json` - Centralized pair configuration

All configuration changes in the admin panel update `pairs.json` and trigger automatic rebuilds in both services.
