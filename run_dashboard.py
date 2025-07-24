
#!/usr/bin/env python3
"""
Polygon Arbitrage Engine - Main Application Runner
"""
import os
import sys
import subprocess
import threading
import time
from dotenv import load_dotenv

load_dotenv()

def check_requirements():
    """Check if all required environment variables are set"""
    required_vars = [
        'PRIVATE_KEY',
        'ALCHEMY_API_URL_MAINNET'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n📝 Please copy .env.example to .env and fill in the values")
        return False
    
    return True

def run_dashboard():
    """Run the Flask dashboard"""
    print("🚀 Starting Polygon Arbitrage Engine Dashboard...")
    print("📊 Dashboard will be available at: http://0.0.0.0:5000")
    print("🔗 Access from browser: http://localhost:5000")
    print("\n" + "="*50)
    
    # Import and run the dashboard
    from dashboard.app import app
    app.run(host='0.0.0.0', port=5000, debug=False)

def main():
    """Main application entry point"""
    print("🤖 Polygon Arbitrage Engine")
    print("=" * 40)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check if contract is deployed
    contract_address = os.getenv('ARBITRAGE_CONTRACT_ADDRESS')
    if not contract_address:
        print("⚠️  No contract address found in environment variables")
        print("📝 Please deploy the contract first using:")
        print("   brownie run scripts/deploy_arbitrage.py --network polygon-main")
        print("\n🔄 Starting dashboard in monitoring mode only...")
    else:
        print(f"✅ Contract address: {contract_address}")
    
    # Start the dashboard
    try:
        run_dashboard()
    except KeyboardInterrupt:
        print("\n👋 Shutting down Polygon Arbitrage Engine...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
