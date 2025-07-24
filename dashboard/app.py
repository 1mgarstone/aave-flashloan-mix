import os
import json
from flask import Flask, render_template, jsonify
from datetime import datetime
import threading
import time

app = Flask(__name__)

# Global state for the dashboard
dashboard_state = {
    'wallet_balance': 0.0,
    'total_scans': 0,
    'opportunities_found': 0,
    'trades_executed': 0,
    'total_profit': 0.0,
    'status': 'Stopped',
    'last_scan': None,
    'is_running': False
}

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    """API endpoint to get current dashboard status"""
    return jsonify(dashboard_state)

@app.route('/api/start', methods=['POST'])
def start_scanner():
    """Start the arbitrage scanner"""
    dashboard_state['status'] = 'Running'
    dashboard_state['is_running'] = True
    return jsonify({'success': True, 'message': 'Scanner started'})

@app.route('/api/stop', methods=['POST'])
def stop_scanner():
    """Stop the arbitrage scanner"""
    dashboard_state['status'] = 'Stopped'
    dashboard_state['is_running'] = False
    return jsonify({'success': True, 'message': 'Scanner stopped'})

@app.route('/api/wallet-balance')
def get_wallet_balance():
    """Get current wallet balance"""
    try:
        from web3 import Web3
        from dotenv import load_dotenv

        load_dotenv()

        rpc_url = os.getenv('ALCHEMY_API_URL_MAINNET')
        if rpc_url:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if w3.is_connected():
                # Get wallet address from private key
                private_key = os.getenv('PRIVATE_KEY')
                if private_key:
                    from eth_account import Account
                    account = Account.from_key(private_key)
                    balance_wei = w3.eth.get_balance(account.address)
                    balance_matic = w3.from_wei(balance_wei, 'ether')
                    dashboard_state['wallet_balance'] = float(balance_matic)
                    return jsonify({'balance': float(balance_matic), 'currency': 'MATIC'})

        return jsonify({'balance': 0.0, 'currency': 'MATIC'})
    except Exception as e:
        print(f"Error getting wallet balance: {e}")
        return jsonify({'balance': 0.0, 'currency': 'MATIC', 'error': str(e)})

def background_scanner():
    """Background scanner simulation"""
    while True:
        if dashboard_state['is_running']:
            dashboard_state['total_scans'] += 1
            dashboard_state['last_scan'] = datetime.now().isoformat()

            # Simulate finding opportunities (random chance)
            import random
            if random.random() < 0.1:  # 10% chance
                dashboard_state['opportunities_found'] += 1

                # Simulate executing profitable trades (50% of opportunities)
                if random.random() < 0.5:
                    dashboard_state['trades_executed'] += 1
                    profit = random.uniform(0.5, 5.0)  # Random profit between $0.5-$5
                    dashboard_state['total_profit'] += profit

        time.sleep(2)  # Scan every 2 seconds

# Start background scanner
scanner_thread = threading.Thread(target=background_scanner, daemon=True)
scanner_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3146, debug=False)