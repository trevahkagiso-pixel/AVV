"""
Unified Dashboard UI – Toggle between Ichimoku and Order Block (OB) strategies.

This service provides a master dashboard that allows seamless switching between
the two analysis UIs (Ichimoku on port 5000, OB on port 5001).

Features:
- Toggle button to switch active strategy view
- Unified navigation across both UIs
- Shared health monitoring for both services
- Consolidated pair management (admin access)
- Session-based preference persistence

Usage:
  python unified_ui.py --port 5002  # Default port is 5002

Proxies to:
  - Ichimoku UI: http://127.0.0.1:5000
  - OB UI: http://127.0.0.1:5001
"""

import os
import argparse
import requests
import json
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from datetime import datetime
import threading

APP = Flask(__name__)
APP.secret_key = os.environ.get('SECRET_KEY', 'unified-ui-dev-key-change-in-prod')

# Default services
# Use forwarded URLs if available (for Codespaces)
# Internal URLs (for health checks from container)
ICHIMOKU_INTERNAL = "http://127.0.0.1:5000"
OB_INTERNAL = "http://127.0.0.1:5001"

# External URLs (for user-facing redirects, e.g., Codespaces)
ICHIMOKU_SERVICE = os.environ.get("ICHIMOKU_URL", "https://probable-trout-5vxr5wrx4jv3pg57-5000.app.github.dev/")
OB_SERVICE = os.environ.get("OB_URL", "https://probable-trout-5vxr5wrx4jv3pg57-5001.app.github.dev/")

# Session timeout
SESSION_TIMEOUT = 3600  # 1 hour


def get_service_health(use_internal=True):
    """Query /health endpoints from both services.
    
    Args:
        use_internal: If True, use localhost URLs (for internal checks).
    
    Returns:
        Tuple of (ichimoku_health, ob_health) dicts or None if offline.
    """
    ichimoku_url = ICHIMOKU_INTERNAL if use_internal else ICHIMOKU_SERVICE
    ob_url = OB_INTERNAL if use_internal else OB_SERVICE
    
    ichimoku_health = None
    ob_health = None
    
    try:
        resp = requests.get(f"{ichimoku_url}/health", timeout=2)
        if resp.status_code == 200:
            ichimoku_health = resp.json()
    except Exception:
        pass
    
    try:
        resp = requests.get(f"{ob_url}/health", timeout=2)
        if resp.status_code == 200:
            ob_health = resp.json()
    except Exception:
        pass
    
    return ichimoku_health, ob_health


def get_active_strategy():
    """Get the current active strategy from session (default: 'ichimoku')."""
    if 'active_strategy' not in session:
        session['active_strategy'] = 'ichimoku'
    return session['active_strategy']


def get_service_url(strategy):
    """Return the service URL for a given strategy."""
    return ICHIMOKU_SERVICE if strategy == 'ichimoku' else OB_SERVICE


@APP.route('/')
def index():
    """Main unified dashboard."""
    active = get_active_strategy()
    ichimoku_health, ob_health = get_service_health(use_internal=True)
    
    # Determine which service is "live"
    ichimoku_status = "✅ Online" if ichimoku_health else "❌ Offline"
    ob_status = "✅ Online" if ob_health else "❌ Offline"
    
    return render_template_string(
        UNIFIED_DASHBOARD_HTML,
        active_strategy=active,
        ichimoku_status=ichimoku_status,
        ob_status=ob_status,
        ichimoku_cache=ichimoku_health.get('cache', {}) if ichimoku_health else {},
        ob_cache=ob_health.get('cache', {}) if ob_health else {},
        ichimoku_service_url=ICHIMOKU_SERVICE,
        ob_service_url=OB_SERVICE,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )


@APP.route('/api/switch-strategy/<strategy>')
def switch_strategy(strategy):
    """Switch active strategy and persist in session."""
    if strategy in ['ichimoku', 'ob']:
        session['active_strategy'] = strategy
        session.modified = True
        return jsonify({'success': True, 'active_strategy': strategy})
    return jsonify({'success': False, 'error': 'Invalid strategy'}), 400


@APP.route('/api/active-strategy')
def active_strategy():
    """Get current active strategy."""
    return jsonify({'active_strategy': get_active_strategy()})


@APP.route('/api/service-status')
def service_status():
    """Return health status of both services."""
    ichimoku_health, ob_health = get_service_health(use_internal=True)
    
    return jsonify({
        'ichimoku': {
            'online': ichimoku_health is not None,
            'url': ICHIMOKU_SERVICE,
            'cache': ichimoku_health.get('cache') if ichimoku_health else None,
            'databases': ichimoku_health.get('databases') if ichimoku_health else None
        },
        'ob': {
            'online': ob_health is not None,
            'url': OB_SERVICE,
            'cache': ob_health.get('cache') if ob_health else None,
            'databases': ob_health.get('databases') if ob_health else None
        }
    })


@APP.route('/switch')
def switch_ui():
    """Redirect to the active strategy UI (using external URL)."""
    active = get_active_strategy()
    service_url = get_service_url(active)
    # Always use external URL for Codespaces
    return redirect(service_url)


@APP.route('/pair/<pair>')
def view_pair(pair):
    """Redirect to pair detail in active UI."""
    active = get_active_strategy()
    service_url = get_service_url(active)
    return redirect(f"{service_url}/pair/{pair}")


@APP.route('/admin')
def admin_panel():
    """Unified admin panel for both services."""
    ichimoku_health, ob_health = get_service_health(use_internal=True)
    
    # Try to fetch pairs.json
    pairs_data = {}
    try:
        with open('pairs.json', 'r') as f:
            pairs_data = json.load(f)
    except Exception:
        pairs_data = {'FOREX_PAIRS': [], 'STOCK_PAIRS': [], 'COMMODITY_PAIRS': []}
    
    return render_template_string(ADMIN_PANEL_HTML,
                                  pairs_json=json.dumps(pairs_data, indent=2),
                                  ichimoku_online=ichimoku_health is not None,
                                  ob_online=ob_health is not None,
                                  timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


@APP.route('/api/pairs')
def get_pairs():
    """Fetch pairs.json."""
    try:
        with open('pairs.json', 'r') as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@APP.route('/api/pairs', methods=['POST'])
def save_pairs():
    """Save pairs.json and trigger rebuilds in both services."""
    try:
        data = request.json
        
        # Validate JSON structure
        if not all(k in data for k in ['FOREX_PAIRS', 'STOCK_PAIRS', 'COMMODITY_PAIRS']):
            return jsonify({'error': 'Missing required keys'}), 400
        
        # Save to disk
        with open('pairs.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        # Trigger rebuild in both services asynchronously
        def trigger_rebuilds():
            try:
                requests.post(f"{ICHIMOKU_SERVICE}/admin/pairs", 
                            json=data, timeout=5)
            except Exception:
                pass
            try:
                requests.post(f"{OB_SERVICE}/admin/pairs", 
                            json=data, timeout=5)
            except Exception:
                pass
        
        thread = threading.Thread(target=trigger_rebuilds, daemon=True)
        thread.start()
        
        return jsonify({'success': True, 'message': 'Pairs saved and rebuild triggered'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# HTML Templates

UNIFIED_DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unified Strategy Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #2196F3;
            --primary-dark: #1976D2;
            --success: #4CAF50;
            --danger: #f44336;
            --warning: #ff9800;
            --dark-bg: #1a1a1a;
            --dark-surface: #2a2a2a;
            --dark-text: #e0e0e0;
            --light-text: #333;
            --border: #ddd;
            --dark-border: #444;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: var(--light-text);
            transition: background-color 0.3s, color 0.3s;
        }

        body.dark-mode {
            background: var(--dark-bg);
            color: var(--dark-text);
        }

        header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .logo {
            font-size: 24px;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .strategy-toggle {
            display: flex;
            gap: 10px;
            background: rgba(255,255,255,0.2);
            padding: 8px;
            border-radius: 6px;
        }

        .strategy-btn {
            padding: 8px 16px;
            border: none;
            background: transparent;
            color: white;
            cursor: pointer;
            border-radius: 4px;
            font-weight: 500;
            transition: background 0.3s;
            font-size: 14px;
        }

        .strategy-btn.active {
            background: rgba(255,255,255,0.3);
        }

        .strategy-btn:hover {
            background: rgba(255,255,255,0.25);
        }

        .header-right {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            font-size: 12px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }

        .status-dot.online {
            background: #4CAF50;
        }

        .status-dot.offline {
            background: #f44336;
        }

        .dark-mode-toggle {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.3s;
        }

        .dark-mode-toggle:hover {
            background: rgba(255,255,255,0.3);
        }

        .admin-link {
            background: rgba(255,255,255,0.2);
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 14px;
            transition: background 0.3s;
        }

        .admin-link:hover {
            background: rgba(255,255,255,0.3);
        }

        main {
            max-width: 1400px;
            margin: 20px auto;
            padding: 0 20px;
        }

        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        body.dark-mode .card {
            background: var(--dark-surface);
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }

        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .card-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card-icon {
            font-size: 24px;
        }

        .service-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
        }

        body.dark-mode .service-info {
            border-bottom-color: var(--dark-border);
        }

        .service-info:last-child {
            border-bottom: none;
        }

        .info-label {
            font-weight: 500;
            color: var(--light-text);
        }

        body.dark-mode .info-label {
            color: var(--dark-text);
        }

        .info-value {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            color: #666;
        }

        body.dark-mode .info-value {
            color: #aaa;
        }

        .cache-status {
            padding: 10px;
            background: #f0f0f0;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 12px;
        }

        body.dark-mode .cache-status {
            background: #333;
        }

        .cache-age {
            color: #666;
        }

        body.dark-mode .cache-age {
            color: #aaa;
        }

        .action-buttons {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }

        .btn {
            padding: 10px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.3s;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
        }

        .btn-secondary {
            background: #f0f0f0;
            color: var(--light-text);
        }

        body.dark-mode .btn-secondary {
            background: #444;
            color: var(--dark-text);
        }

        .btn-secondary:hover {
            background: #e0e0e0;
        }

        body.dark-mode .btn-secondary:hover {
            background: #555;
        }

        .timestamp {
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 20px;
        }

        body.dark-mode .timestamp {
            color: #666;
        }

        .info-section {
            margin-bottom: 20px;
        }

        .info-section h3 {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 10px;
            color: var(--primary);
        }

        .cache-file {
            background: #f5f5f5;
            padding: 8px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 11px;
            word-break: break-all;
            margin-bottom: 5px;
        }

        body.dark-mode .cache-file {
            background: #333;
        }

        @media (max-width: 768px) {
            header {
                flex-direction: column;
                align-items: flex-start;
            }

            .cards-grid {
                grid-template-columns: 1fr;
            }

            .strategy-toggle {
                width: 100%;
            }

            .strategy-btn {
                flex: 1;
            }

            main {
                margin: 10px auto;
                padding: 0 10px;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="header-left">
            <div class="logo">
                📊 Unified Strategy Dashboard
            </div>
            <div class="strategy-toggle">
                <button class="strategy-btn active" id="ichimoku-btn" onclick="switchStrategy('ichimoku')">
                    📈 Ichimoku
                </button>
                <button class="strategy-btn" id="ob-btn" onclick="switchStrategy('ob')">
                    🔲 Order Block
                </button>
            </div>
        </div>
        <div class="header-right">
            <div class="status-indicator">
                <span class="status-dot ichimoku" id="ichimoku-status"></span>
                Ichimoku: <span id="ichimoku-status-text">{{ ichimoku_status }}</span>
            </div>
            <div class="status-indicator">
                <span class="status-dot ob" id="ob-status"></span>
                OB: <span id="ob-status-text">{{ ob_status }}</span>
            </div>
            <button class="dark-mode-toggle" onclick="toggleDarkMode()">🌙</button>
            <a href="/admin" class="admin-link">⚙️ Admin</a>
        </div>
    </header>

    <main>
        <div class="cards-grid">
            <!-- Ichimoku Service Card -->
            <div class="card">
                <div class="card-title">
                    <span class="card-icon">📈</span>
                    Ichimoku Strategy
                </div>
                <div class="service-info">
                    <span class="info-label">Status</span>
                    <span>{{ ichimoku_status }}</span>
                </div>
                <div class="service-info">
                    <span class="info-label">Port</span>
                    <span class="info-value">5000</span>
                </div>
                <div class="service-info">
                    <span class="info-label">Service URL</span>
                    <span class="info-value">http://127.0.0.1:5000</span>
                </div>
                {% if ichimoku_cache %}
                <div class="info-section">
                    <h3>Cache Status</h3>
                    <div class="cache-status">
                        <div class="cache-age">Last Updated: {{ ichimoku_cache.mtime }}</div>
                        <div class="cache-file">{{ ichimoku_cache.path }} ({{ ichimoku_cache.size_bytes }} bytes)</div>
                    </div>
                </div>
                {% endif %}
                <div class="action-buttons">
                    <button class="btn btn-primary" onclick="window.location.href='{{ ichimoku_service_url }}'">
                        Open Ichimoku UI
                    </button>
                </div>
            </div>

            <!-- Order Block Service Card -->
            <div class="card">
                <div class="card-title">
                    <span class="card-icon">🔲</span>
                    Order Block Strategy
                </div>
                <div class="service-info">
                    <span class="info-label">Status</span>
                    <span>{{ ob_status }}</span>
                </div>
                <div class="service-info">
                    <span class="info-label">Port</span>
                    <span class="info-value">5001</span>
                </div>
                <div class="service-info">
                    <span class="info-label">Service URL</span>
                    <span class="info-value">{{ ob_service_url }}</span>
                </div>
                {% if ob_cache %}
                <div class="info-section">
                    <h3>Cache Status</h3>
                    <div class="cache-status">
                        <div class="cache-age">Last Updated: {{ ob_cache.mtime }}</div>
                        <div class="cache-file">{{ ob_cache.path }} ({{ ob_cache.size_bytes }} bytes)</div>
                    </div>
                </div>
                {% endif %}
                <div class="action-buttons">
                    <button class="btn btn-primary" onclick="window.location.href='{{ ob_service_url }}'">
                        Open OB UI
                    </button>
                </div>
            </div>
        </div>
    </main>

    <div class="timestamp">
        Last refreshed: {{ timestamp }}
    </div>

    <script>
        // Initialize dark mode from localStorage
        function initDarkMode() {
            const isDark = localStorage.getItem('darkMode') === 'true';
            if (isDark) {
                document.body.classList.add('dark-mode');
            }
        }

        function toggleDarkMode() {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('darkMode', isDark);
        }

        function switchStrategy(strategy) {
            fetch(`/api/switch-strategy/${strategy}`)
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        // Update UI
                        document.getElementById('ichimoku-btn').classList.toggle('active', strategy === 'ichimoku');
                        document.getElementById('ob-btn').classList.toggle('active', strategy === 'ob');
                    }
                })
                .catch(err => console.error('Switch failed:', err));
        }

        function updateServiceStatus() {
            fetch('/api/service-status')
                .then(r => r.json())
                .then(data => {
                    // Update Ichimoku status
                    const ichOnline = data.ichimoku.online;
                    document.getElementById('ichimoku-status').className = 'status-dot ' + (ichOnline ? 'online' : 'offline');
                    document.getElementById('ichimoku-status-text').textContent = ichOnline ? '✅ Online' : '❌ Offline';

                    // Update OB status
                    const obOnline = data.ob.online;
                    document.getElementById('ob-status').className = 'status-dot ' + (obOnline ? 'online' : 'offline');
                    document.getElementById('ob-status-text').textContent = obOnline ? '✅ Online' : '❌ Offline';
                })
                .catch(err => console.error('Status update failed:', err));
        }

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            initDarkMode();
            updateServiceStatus();
            setInterval(updateServiceStatus, 10000); // Update every 10 seconds
        });
    </script>
</body>
</html>
"""

ADMIN_PANEL_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unified Admin Panel</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary: #2196F3;
            --primary-dark: #1976D2;
            --success: #4CAF50;
            --danger: #f44336;
            --dark-bg: #1a1a1a;
            --dark-surface: #2a2a2a;
            --dark-text: #e0e0e0;
            --light-text: #333;
            --border: #ddd;
            --dark-border: #444;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: var(--light-text);
            transition: background-color 0.3s, color 0.3s;
        }

        body.dark-mode {
            background: var(--dark-bg);
            color: var(--dark-text);
        }

        header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header-title {
            font-size: 24px;
            font-weight: bold;
        }

        .header-actions {
            display: flex;
            gap: 10px;
        }

        .back-link {
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            background: rgba(255,255,255,0.2);
            border-radius: 4px;
            transition: background 0.3s;
        }

        .back-link:hover {
            background: rgba(255,255,255,0.3);
        }

        .dark-mode-toggle {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.3s;
        }

        .dark-mode-toggle:hover {
            background: rgba(255,255,255,0.3);
        }

        main {
            max-width: 1200px;
            margin: 30px auto;
            padding: 0 20px;
        }

        .admin-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }

        body.dark-mode .admin-section {
            background: var(--dark-surface);
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }

        .section-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .section-icon {
            font-size: 24px;
        }

        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .status-card {
            background: #f5f5f5;
            border-left: 4px solid var(--primary);
            padding: 15px;
            border-radius: 4px;
        }

        body.dark-mode .status-card {
            background: #333;
            border-left-color: var(--primary);
        }

        .status-card.online {
            border-left-color: var(--success);
        }

        .status-card.offline {
            border-left-color: var(--danger);
        }

        .status-label {
            font-weight: 600;
            margin-bottom: 5px;
        }

        .status-value {
            font-size: 12px;
            color: #666;
            font-family: monospace;
        }

        body.dark-mode .status-value {
            color: #aaa;
        }

        textarea {
            width: 100%;
            min-height: 400px;
            padding: 15px;
            border: 1px solid var(--border);
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            background: white;
            color: var(--light-text);
            resize: vertical;
        }

        body.dark-mode textarea {
            background: #333;
            color: var(--dark-text);
            border-color: var(--dark-border);
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            font-weight: 600;
            margin-bottom: 10px;
        }

        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.3s;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
        }

        .btn-success {
            background: var(--success);
            color: white;
        }

        .btn-success:hover {
            background: #45a049;
        }

        .btn-secondary {
            background: #f0f0f0;
            color: var(--light-text);
        }

        body.dark-mode .btn-secondary {
            background: #444;
            color: var(--dark-text);
        }

        .btn-secondary:hover {
            background: #e0e0e0;
        }

        .alert {
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }

        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }

        body.dark-mode .alert-success {
            background: #1e4620;
            color: #90ee90;
            border-color: #2d5a2d;
        }

        body.dark-mode .alert-error {
            background: #5a1e1e;
            color: #ff7777;
            border-color: #8b3d3d;
        }

        body.dark-mode .alert-info {
            background: #1e3a4a;
            color: #7fc7d7;
            border-color: #2d5a7a;
        }

        .info-box {
            background: #e3f2fd;
            border-left: 4px solid var(--primary);
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }

        body.dark-mode .info-box {
            background: #1a3a52;
            border-left-color: var(--primary);
        }

        .info-box-title {
            font-weight: 600;
            margin-bottom: 8px;
        }

        .info-box-text {
            font-size: 13px;
            line-height: 1.5;
        }

        @media (max-width: 768px) {
            header {
                flex-direction: column;
                gap: 15px;
                align-items: flex-start;
            }

            .header-actions {
                width: 100%;
            }

            .button-group {
                flex-direction: column;
            }

            .btn {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="header-title">⚙️ Unified Admin Panel</div>
        <div class="header-actions">
            <a href="/" class="back-link">← Back to Dashboard</a>
            <button class="dark-mode-toggle" onclick="toggleDarkMode()">🌙</button>
        </div>
    </header>

    <main>
        <!-- Service Status -->
        <div class="admin-section">
            <div class="section-title">
                <span class="section-icon">📡</span>
                Service Status
            </div>
            <div class="status-grid">
                <div class="status-card {% if ichimoku_online %}online{% else %}offline{% endif %}">
                    <div class="status-label">Ichimoku UI</div>
                    <div class="status-value">Port 5000: {% if ichimoku_online %}✅ Online{% else %}❌ Offline{% endif %}</div>
                </div>
                <div class="status-card {% if ob_online %}online{% else %}offline{% endif %}">
                    <div class="status-label">Order Block UI</div>
                    <div class="status-value">Port 5001: {% if ob_online %}✅ Online{% else %}❌ Offline{% endif %}</div>
                </div>
            </div>
        </div>

        <!-- Pair Management -->
        <div class="admin-section">
            <div class="section-title">
                <span class="section-icon">📋</span>
                Pair Configuration (pairs.json)
            </div>

            <div class="info-box">
                <div class="info-box-title">ℹ️ How to Edit Pairs</div>
                <div class="info-box-text">
                    Edit the JSON below to add/remove trading pairs. Changes will be saved to disk and trigger 
                    automatic rebuilds in both Ichimoku and Order Block services. Keep the three categories: 
                    FOREX_PAIRS, STOCK_PAIRS, and COMMODITY_PAIRS.
                </div>
            </div>

            <form id="pairs-form">
                <div class="form-group">
                    <label class="form-label">pairs.json Content</label>
                    <textarea id="pairs-textarea" required></textarea>
                </div>
                <div class="button-group">
                    <button type="button" class="btn btn-success" onclick="savePairs()">
                        💾 Save & Rebuild
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="resetPairs()">
                        ↺ Reset
                    </button>
                </div>
            </form>

            <div id="alert-container"></div>
        </div>

        <!-- Service Links -->
        <div class="admin-section">
            <div class="section-title">
                <span class="section-icon">🔗</span>
                Service Links
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                <a href="http://127.0.0.1:5000" target="_blank" style="display: inline-block; padding: 15px; background: #e3f2fd; border-radius: 4px; text-decoration: none; color: var(--primary); font-weight: 500;">
                    📈 Ichimoku UI (Port 5000) →
                </a>
                <a href="http://127.0.0.1:5001" target="_blank" style="display: inline-block; padding: 15px; background: #e3f2fd; border-radius: 4px; text-decoration: none; color: var(--primary); font-weight: 500;">
                    🔲 Order Block UI (Port 5001) →
                </a>
                <a href="http://127.0.0.1:5002" target="_blank" style="display: inline-block; padding: 15px; background: #e3f2fd; border-radius: 4px; text-decoration: none; color: var(--primary); font-weight: 500;">
                    📊 Unified Dashboard (Port 5002) →
                </a>
            </div>
        </div>
    </main>

    <script>
        // Initialize dark mode
        function initDarkMode() {
            const isDark = localStorage.getItem('darkMode') === 'true';
            if (isDark) {
                document.body.classList.add('dark-mode');
            }
        }

        function toggleDarkMode() {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('darkMode', isDark);
        }

        // Load pairs on page load
        function loadPairs() {
            fetch('/api/pairs')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('pairs-textarea').value = JSON.stringify(data, null, 2);
                })
                .catch(err => {
                    showAlert('Failed to load pairs: ' + err, 'error');
                });
        }

        // Save pairs
        function savePairs() {
            const textarea = document.getElementById('pairs-textarea');
            try {
                const data = JSON.parse(textarea.value);
                
                // Validate structure
                if (!data.FOREX_PAIRS || !data.STOCK_PAIRS || !data.COMMODITY_PAIRS) {
                    showAlert('Missing required keys: FOREX_PAIRS, STOCK_PAIRS, COMMODITY_PAIRS', 'error');
                    return;
                }

                fetch('/api/pairs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                })
                .then(r => r.json())
                .then(result => {
                    if (result.success) {
                        showAlert('✅ Pairs saved! Rebuilds triggered in both services.', 'success');
                    } else {
                        showAlert('Error: ' + result.error, 'error');
                    }
                })
                .catch(err => showAlert('Save failed: ' + err, 'error'));
            } catch (err) {
                showAlert('Invalid JSON: ' + err.message, 'error');
            }
        }

        // Reset textarea
        function resetPairs() {
            loadPairs();
        }

        // Show alert
        function showAlert(message, type) {
            const container = document.getElementById('alert-container');
            const alert = document.createElement('div');
            alert.className = 'alert alert-' + type;
            alert.textContent = message;
            container.innerHTML = '';
            container.appendChild(alert);
            
            if (type === 'success') {
                setTimeout(() => alert.remove(), 4000);
            }
        }

        // Load pairs on page load
        document.addEventListener('DOMContentLoaded', function() {
            initDarkMode();
            loadPairs();
        });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Unified Strategy Dashboard')
    parser.add_argument('--port', type=int, default=5002, help='Port to run on (default: 5002)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    args = parser.parse_args()

    print(f"Unified Dashboard running at http://{args.host}:{args.port}")
    print(f"Proxying to Ichimoku ({ICHIMOKU_SERVICE}) and OB ({OB_SERVICE})")
    print("Press Ctrl+C to stop")
    
    APP.run(host=args.host, port=args.port, debug=False, use_reloader=False)
