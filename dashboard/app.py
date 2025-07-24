
from flask import Flask, render_template, jsonify, request
import json
import sqlite3
import asyncio
import threading
from datetime import datetime, timedelta
import os
from automation.arbitrage_scanner import PolygonArbitrageScanner
import logging

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Global scanner instance
scanner = None
scanner_thread = None
scanner_running = False

# Database setup
def init_db():
    conn = sqlite3.connect('arbitrage.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            token_a TEXT,
            token_b TEXT,
            amount_in REAL,
            profit REAL,
            profit_percentage REAL,
            tx_hash TEXT,
            status TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            opportunities_found INTEGER,
            scan_duration REAL
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def run_scanner():
    global scanner, scanner_running
    if scanner and scanner_running:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(scanner.continuous_scan())

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    global scanner, scanner_running
    
    if not scanner:
        scanner = PolygonArbitrageScanner()
    
    balance = float(scanner.get_wallet_balance())
    loan_budget, is_high_risk = scanner.calculate_loan_budget()
    
    return jsonify({
        'running': scanner_running,
        'balance': balance,
        'loan_budget': float(loan_budget),
        'mode': 'High-Risk' if is_high_risk else 'Safe',
        'scan_count': scanner.scan_count,
        'opportunities_found': scanner.opportunities_found,
        'trades_executed': scanner.trades_executed,
        'total_profit': scanner.total_profit,
        'min_balance': 10.0,
        'mode_threshold': 320.0
    })

@app.route('/api/start', methods=['POST'])
def start_scanner():
    global scanner, scanner_thread, scanner_running
    
    if not scanner_running:
        scanner_running = True
        if not scanner:
            scanner = PolygonArbitrageScanner()
        
        scanner_thread = threading.Thread(target=run_scanner)
        scanner_thread.daemon = True
        scanner_thread.start()
        
        return jsonify({'status': 'started'})
    
    return jsonify({'status': 'already_running'})

@app.route('/api/stop', methods=['POST'])
def stop_scanner():
    global scanner_running
    scanner_running = False
    return jsonify({'status': 'stopped'})

@app.route('/api/trades')
def get_trades():
    conn = sqlite3.connect('arbitrage.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT timestamp, token_a, token_b, amount_in, profit, 
               profit_percentage, tx_hash, status
        FROM trades 
        ORDER BY timestamp DESC 
        LIMIT 20
    ''')
    
    trades = []
    for row in cursor.fetchall():
        trades.append({
            'timestamp': row[0],
            'token_a': row[1],
            'token_b': row[2],
            'amount_in': row[3],
            'profit': row[4],
            'profit_percentage': row[5],
            'tx_hash': row[6],
            'status': row[7]
        })
    
    conn.close()
    return jsonify(trades)

@app.route('/api/opportunities')
def get_opportunities():
    global scanner
    
    if scanner:
        # This would be populated in real-time by the scanner
        # For now, return empty list
        return jsonify([])
    
    return jsonify([])

@app.route('/api/performance')
def get_performance():
    conn = sqlite3.connect('arbitrage.db')
    cursor = conn.cursor()
    
    # Get performance data for the last 24 hours
    cursor.execute('''
        SELECT 
            strftime('%H', timestamp) as hour,
            COUNT(*) as trades,
            SUM(profit) as total_profit,
            AVG(profit_percentage) as avg_profit_pct
        FROM trades 
        WHERE timestamp > datetime('now', '-24 hours')
        GROUP BY strftime('%H', timestamp)
        ORDER BY hour
    ''')
    
    performance = []
    for row in cursor.fetchall():
        performance.append({
            'hour': int(row[0]),
            'trades': row[1],
            'profit': row[2] or 0,
            'avg_profit_pct': row[3] or 0
        })
    
    conn.close()
    return jsonify(performance)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
