"""
AI-powered backtest results analysis and improvement recommendations.

This module provides functions to analyze backtest statistics and generate
detailed insights with optional improvements.
"""

import pandas as pd
from typing import Dict, Any, List, Tuple


def analyze_backtest_results(stats: Any, pair: str = "Unknown") -> Dict[str, Any]:
    """
    Analyze backtest statistics and generate insights.
    
    Args:
        stats: Backtest statistics object from backtesting library
        pair: Currency pair name (e.g., "EUR/USD")
    
    Returns:
        Dictionary with analysis results including metrics and insights
    """
    try:
        # Extract key metrics
        metrics = {
            'pair': pair,
            'total_return': float(stats.get('Return [%]', 0)),
            'buy_hold_return': float(stats.get('Buy & Hold Return [%]', 0)),
            'return_annual': float(stats.get('Return (ann.) [%]', 0)),
            'volatility': float(stats.get('Volatility (ann.) [%]', 0)),
            'sharpe': float(stats.get('Sharpe Ratio', 0)),
            'sortino': float(stats.get('Sortino Ratio', 0)),
            'max_drawdown': float(stats.get('Max. Drawdown [%]', 0)),
            'win_rate': float(stats.get('Win Rate [%]', 0)),
            'profit_factor': float(stats.get('Profit Factor', 0)),
            'trades': int(stats.get('# Trades', 0)),
            'duration': str(stats.get('Duration', 'N/A')),
        }
    except (ValueError, TypeError) as e:
        return {'error': f'Failed to extract metrics: {str(e)}'}
    
    # Generate analysis
    analysis = {
        'metrics': metrics,
        'overall_assessment': _assess_overall_performance(metrics),
        'risk_analysis': _analyze_risk(metrics),
        'trade_quality': _analyze_trade_quality(metrics),
        'improvements': _suggest_improvements(metrics),
        'summary': _generate_summary(metrics),
    }
    
    return analysis


def _assess_overall_performance(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Assess overall strategy performance."""
    total_return = metrics['total_return']
    sharpe = metrics['sharpe']
    max_dd = abs(metrics['max_drawdown'])
    
    # Determine performance level
    if total_return > 50 and sharpe > 1.5:
        rating = "Excellent"
        emoji = "🌟"
    elif total_return > 20 and sharpe > 1.0:
        rating = "Good"
        emoji = "✅"
    elif total_return > 5 and sharpe > 0.5:
        rating = "Fair"
        emoji = "⚠️"
    else:
        rating = "Poor"
        emoji = "❌"
    
    return {
        'rating': rating,
        'emoji': emoji,
        'description': f"{emoji} Overall Performance: {rating}",
        'total_return_verdict': _verdict_return(total_return),
        'risk_reward_balance': _verdict_risk_reward(total_return, max_dd, sharpe),
    }


def _verdict_return(return_pct: float) -> str:
    """Generate verdict on returns."""
    if return_pct < 0:
        return "Strategy is unprofitable ❌"
    elif return_pct < 5:
        return "Returns are modest - consider optimizations 📊"
    elif return_pct < 20:
        return "Solid returns with reasonable risk 👍"
    elif return_pct < 50:
        return "Strong returns, excellent performance 🚀"
    else:
        return "Outstanding returns! 🎉"


def _verdict_risk_reward(return_pct: float, max_dd: float, sharpe: float) -> str:
    """Generate verdict on risk-reward balance."""
    if max_dd == 0:
        return "No drawdown recorded - very limited trading ⚠️"
    
    rr_ratio = abs(return_pct) / max(max_dd, 0.01)
    
    if rr_ratio > 2.0:
        return "Excellent risk-reward ratio - strong strategy 💪"
    elif rr_ratio > 1.0:
        return "Good risk-reward balance 👌"
    elif rr_ratio > 0.5:
        return "Moderate risk-reward - consider improvements 🔧"
    else:
        return "Poor risk-reward - high risk for low returns ⚠️"


def _analyze_risk(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze risk metrics."""
    max_dd = abs(metrics['max_drawdown'])
    volatility = metrics['volatility']
    sharpe = metrics['sharpe']
    sortino = metrics['sortino']
    
    analysis = {
        'max_drawdown_verdict': _verdict_drawdown(max_dd),
        'volatility_verdict': _verdict_volatility(volatility),
        'risk_adjusted_returns': {
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'sharpe_assessment': _assess_sharpe(sharpe),
        }
    }
    
    # Risk level classification
    if max_dd < 10 and volatility < 15:
        risk_level = "Low 🟢"
    elif max_dd < 20 and volatility < 25:
        risk_level = "Medium 🟡"
    elif max_dd < 40 and volatility < 40:
        risk_level = "High 🟠"
    else:
        risk_level = "Very High 🔴"
    
    analysis['risk_level'] = risk_level
    return analysis


def _verdict_drawdown(max_dd: float) -> str:
    """Generate verdict on maximum drawdown."""
    if max_dd < 5:
        return "Minimal drawdown - excellent preservation of capital ✨"
    elif max_dd < 15:
        return "Moderate drawdown - acceptable for most traders 👍"
    elif max_dd < 30:
        return "Significant drawdown - increased portfolio volatility ⚠️"
    else:
        return "Severe drawdown - consider risk management improvements 🚨"


def _verdict_volatility(volatility: float) -> str:
    """Generate verdict on volatility."""
    if volatility < 10:
        return "Low volatility - stable returns 📈"
    elif volatility < 20:
        return "Moderate volatility - typical for trading strategies 🎯"
    elif volatility < 35:
        return "High volatility - significant price swings ⚡"
    else:
        return "Very high volatility - unstable and risky 🌪️"


def _assess_sharpe(sharpe: float) -> str:
    """Assess Sharpe ratio."""
    if sharpe > 2.0:
        return "Excellent risk-adjusted returns 🌟"
    elif sharpe > 1.0:
        return "Good risk-adjusted returns ✅"
    elif sharpe > 0.5:
        return "Acceptable risk-adjusted returns 👌"
    elif sharpe > 0:
        return "Poor risk-adjusted returns ⚠️"
    else:
        return "Negative risk-adjusted returns ❌"


def _analyze_trade_quality(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze trading activity and quality."""
    trades = metrics['trades']
    win_rate = metrics['win_rate']
    profit_factor = metrics['profit_factor']
    
    analysis = {
        'total_trades': trades,
        'trade_frequency': _assess_trade_frequency(trades),
        'win_rate_verdict': _verdict_win_rate(win_rate),
        'profit_factor_verdict': _verdict_profit_factor(profit_factor),
    }
    
    # Trade quality assessment
    if trades == 0:
        quality = "No trades executed ⚠️"
    elif win_rate > 60 and profit_factor > 2.0:
        quality = "Excellent trade quality - high win rate with strong profitability 🏆"
    elif win_rate > 55 and profit_factor > 1.5:
        quality = "Good trade quality - consistent wins with positive profit factor ✅"
    elif win_rate > 50 and profit_factor > 1.0:
        quality = "Acceptable trade quality - barely profitable 👌"
    else:
        quality = "Poor trade quality - need improvements 🔧"
    
    analysis['overall_quality'] = quality
    return analysis


def _assess_trade_frequency(trades: int) -> str:
    """Assess trading frequency."""
    if trades == 0:
        return "No trades - signal generation issue ⚠️"
    elif trades < 10:
        return "Very few trades - limited signal generation 🔍"
    elif trades < 50:
        return "Low frequency - selective entry points 📊"
    elif trades < 200:
        return "Moderate frequency - good signal generation ✅"
    else:
        return "High frequency - many trading opportunities 🎯"


def _verdict_win_rate(win_rate: float) -> str:
    """Generate verdict on win rate."""
    if win_rate > 70:
        return "Exceptional win rate - excellent strategy 🌟"
    elif win_rate > 60:
        return "High win rate - strong entry/exit signals 👍"
    elif win_rate > 55:
        return "Good win rate - above 50% threshold ✅"
    elif win_rate > 50:
        return "Slight edge - barely above random 🤔"
    else:
        return "Losing strategy - more losses than wins ❌"


def _verdict_profit_factor(pf: float) -> str:
    """Generate verdict on profit factor."""
    if pf > 3.0:
        return "Exceptional profit factor - very strong strategy 🚀"
    elif pf > 2.0:
        return "Excellent profit factor - great win/loss balance 💪"
    elif pf > 1.5:
        return "Good profit factor - solid performance 👌"
    elif pf > 1.0:
        return "Acceptable profit factor - marginally profitable ⚠️"
    else:
        return "Profit factor < 1.0 - unprofitable ❌"


def _suggest_improvements(metrics: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate improvement suggestions based on metrics."""
    suggestions = []
    
    # Check returns
    if metrics['total_return'] < 10:
        suggestions.append({
            'category': 'Strategy Profitability',
            'issue': 'Low returns detected',
            'suggestion': 'Consider optimizing entry/exit timing or adjusting indicator parameters',
            'priority': '🔴 High'
        })
    
    # Check drawdown
    if metrics['max_drawdown'] < -30:
        suggestions.append({
            'category': 'Risk Management',
            'issue': 'Excessive maximum drawdown',
            'suggestion': 'Implement tighter stop-losses or increase position size limits',
            'priority': '🔴 Critical'
        })
    
    # Check volatility
    if metrics['volatility'] > 30:
        suggestions.append({
            'category': 'Volatility Control',
            'issue': 'High portfolio volatility',
            'suggestion': 'Add volatility filters or diversify across more pairs',
            'priority': '🟡 Medium'
        })
    
    # Check trade volume
    if metrics['trades'] < 10:
        suggestions.append({
            'category': 'Signal Generation',
            'issue': 'Very few trades executed',
            'suggestion': 'Relax entry conditions or add additional technical indicators',
            'priority': '🟡 Medium'
        })
    elif metrics['trades'] > 500:
        suggestions.append({
            'category': 'Over-Trading',
            'issue': 'Excessive number of trades',
            'suggestion': 'Tighten entry filters to reduce whipsaw and transaction costs',
            'priority': '🟡 Medium'
        })
    
    # Check win rate
    if metrics['win_rate'] < 50:
        suggestions.append({
            'category': 'Entry/Exit Quality',
            'issue': 'Below-average win rate',
            'suggestion': 'Review entry signals or improve exit strategy with better stop-loss/take-profit',
            'priority': '🔴 High'
        })
    
    # Check Sharpe ratio
    if metrics['sharpe'] < 0.5:
        suggestions.append({
            'category': 'Risk-Adjusted Returns',
            'issue': 'Poor Sharpe ratio',
            'suggestion': 'Improve consistency by adding trend confirmation or reducing position sizing',
            'priority': '🟡 Medium'
        })
    
    # Check profit factor
    if metrics['profit_factor'] < 1.5:
        suggestions.append({
            'category': 'Profitability Structure',
            'issue': 'Profit factor below 1.5',
            'suggestion': 'Adjust risk-reward ratio or improve win rate through better signal filtering',
            'priority': '🟡 Medium'
        })
    
    # Positive feedback
    if len(suggestions) == 0:
        suggestions.append({
            'category': 'Overall',
            'issue': 'Strategy is performing well',
            'suggestion': 'Continue monitoring and consider paper trading on live data',
            'priority': '🟢 Monitor'
        })
    
    return suggestions


def _generate_summary(metrics: Dict[str, Any]) -> str:
    """Generate executive summary of backtest results."""
    pair = metrics['pair']
    ret = metrics['total_return']
    trades = metrics['trades']
    wr = metrics['win_rate']
    dd = metrics['max_drawdown']
    sharpe = metrics['sharpe']
    
    summary = f"""
📊 BACKTEST SUMMARY: {pair}
{'='*60}

🎯 Performance Metrics:
   • Total Return: {ret:+.2f}%
   • Annual Return: {metrics['return_annual']:+.2f}%
   • Max Drawdown: {dd:.2f}%
   • Number of Trades: {trades}
   
📈 Trade Quality:
   • Win Rate: {wr:.1f}%
   • Profit Factor: {metrics['profit_factor']:.2f}
   
⚖️ Risk Metrics:
   • Sharpe Ratio: {sharpe:.2f}
   • Sortino Ratio: {metrics['sortino']:.2f}
   • Annual Volatility: {metrics['volatility']:.2f}%

📅 Duration: {metrics['duration']}
"""
    return summary


def format_analysis_for_html(analysis: Dict[str, Any]) -> str:
    """Format analysis results as HTML for web display."""
    if 'error' in analysis:
        return f"<div class='error-box'><strong>Analysis Error:</strong> {analysis['error']}</div>"
    
    metrics = analysis['metrics']
    assessment = analysis['overall_assessment']
    risk = analysis['risk_analysis']
    trade = analysis['trade_quality']
    improvements = analysis['improvements']
    summary = analysis['summary']
    
    html = f"""
    <div class="analysis-container">
        <h3>{assessment['emoji']} {assessment['description']}</h3>
        
        <div class="analysis-summary">
            <pre>{summary}</pre>
        </div>
        
        <div class="analysis-section">
            <h4>💡 Key Verdicts</h4>
            <ul>
                <li><strong>Returns:</strong> {assessment['total_return_verdict']}</li>
                <li><strong>Risk-Reward:</strong> {assessment['risk_reward_balance']}</li>
                <li><strong>Risk Level:</strong> {risk['risk_level']}</li>
                <li><strong>Trade Quality:</strong> {trade['overall_quality']}</li>
            </ul>
        </div>
        
        <div class="analysis-section">
            <h4>🎯 Detailed Risk Analysis</h4>
            <ul>
                <li><strong>Drawdown:</strong> {risk['max_drawdown_verdict']}</li>
                <li><strong>Volatility:</strong> {risk['volatility_verdict']}</li>
                <li><strong>Sharpe Assessment:</strong> {risk['risk_adjusted_returns']['sharpe_assessment']}</li>
            </ul>
        </div>
        
        <div class="analysis-section">
            <h4>📊 Trade Quality Details</h4>
            <ul>
                <li><strong>Frequency:</strong> {trade['trade_frequency']}</li>
                <li><strong>Win Rate:</strong> {trade['win_rate_verdict']}</li>
                <li><strong>Profit Factor:</strong> {trade['profit_factor_verdict']}</li>
            </ul>
        </div>
    """
    
    # Add improvements section if there are suggestions
    if improvements:
        html += """
        <div class="analysis-section improvements-section">
            <h4>🔧 Suggested Improvements</h4>
            <div class="improvements-list">
        """
        
        for imp in improvements:
            html += f"""
            <div class="improvement-card">
                <div class="improvement-priority">{imp['priority']}</div>
                <div class="improvement-content">
                    <strong>{imp['category']}</strong><br/>
                    <em>Issue:</em> {imp['issue']}<br/>
                    <em>Suggestion:</em> {imp['suggestion']}
                </div>
            </div>
            """
        
        html += """
            </div>
        </div>
        """
    
    html += "</div>"
    return html


def get_analysis_css() -> str:
    """Return CSS styling for analysis display."""
    return """
    <style>
        .analysis-container {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 12px;
            padding: 25px;
            margin: 25px 0;
            border-left: 5px solid #667eea;
        }
        
        .analysis-summary {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border: 1px solid #e0e0e0;
            overflow-x: auto;
        }
        
        .analysis-summary pre {
            margin: 0;
            font-size: 0.95em;
            line-height: 1.4;
            color: #333;
            font-family: 'Monaco', 'Courier New', monospace;
        }
        
        .analysis-section {
            background: white;
            border-radius: 8px;
            padding: 18px;
            margin: 15px 0;
            border: 1px solid #e8e8e8;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }
        
        .analysis-section h4 {
            color: #667eea;
            margin-top: 0;
            margin-bottom: 12px;
            font-size: 1.1em;
        }
        
        .analysis-section ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        
        .analysis-section li {
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
            color: #555;
        }
        
        .analysis-section li:last-child {
            border-bottom: none;
        }
        
        .analysis-section strong {
            color: #764ba2;
        }
        
        .improvements-section {
            border-left-color: #ff6b6b;
        }
        
        .improvements-list {
            display: grid;
            gap: 12px;
        }
        
        .improvement-card {
            background: linear-gradient(135deg, #fff5f7 0%, #f0f4ff 100%);
            border-left: 4px solid #ff6b6b;
            padding: 12px;
            border-radius: 6px;
            display: flex;
            gap: 12px;
        }
        
        .improvement-priority {
            font-weight: bold;
            min-width: 100px;
            padding-top: 2px;
        }
        
        .improvement-content {
            flex: 1;
            font-size: 0.95em;
            line-height: 1.5;
        }
        
        .improvement-content em {
            color: #764ba2;
            font-style: italic;
        }
    </style>
    """
