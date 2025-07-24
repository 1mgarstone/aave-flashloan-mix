
#!/usr/bin/env python3
"""
Polygon Flashloan Arbitrage - Environment Setup
"""

import os
import json
from pathlib import Path

def create_env_file():
    """Create .env file with Polygon configuration"""
    
    env_content = """# Polygon Network Configuration
NETWORK_NAME=polygon
CHAIN_ID=137
NATIVE_TOKEN=POLYGON
NATIVE_SYMBOL=MATIC
RPC_URL=https://polygon-rpc.com

# Wallet Configuration (FILL THESE IN)
PRIVATE_KEY=your_private_key_here
MNEMONIC=your_twelve_word_mnemonic_here

# Aave V3 Polygon Addresses
AAVE_POOL_ADDRESSES_PROVIDER=0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
AAVE_POOL=0x794a61358D6845594F94dc1DB02A252b5b4814aD

# Token Addresses on Polygon
WMATIC_ADDRESS=0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270
USDC_ADDRESS=0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
WETH_ADDRESS=0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619
DAI_ADDRESS=0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063
USDT_ADDRESS=0xc2132D05D31c914a87C6611C10748AEb04B58e8F

# DEX Router Addresses
QUICKSWAP_ROUTER=0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff
SUSHISWAP_ROUTER=0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506

# Bot Configuration  
MIN_PROFIT_USD=10
MAX_GAS_GWEI=100
SCAN_INTERVAL_SECONDS=10

# API Keys (Optional but recommended)
POLYGONSCAN_API_KEY=your_polygonscan_api_key
COINGECKO_API_KEY=your_coingecko_api_key
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env file")

def create_requirements():
    """Create requirements.txt for dependencies"""
    
    requirements = """eth-brownie>=1.19.0
web3>=6.0.0
requests>=2.28.0
python-dotenv>=0.19.0
pandas>=1.5.0
numpy>=1.21.0
"""
    
    with open('requirements.txt', 'w') as f:
        f.write(requirements)
    
    print("✅ Created requirements.txt")

def create_run_script():
    """Create run script for easy execution"""
    
    run_script = """#!/bin/bash

echo "🚀 POLYGON FLASHLOAN ARBITRAGE BOT"
echo "================================="

# Check if .env exists
if [[ ! -f .env ]]; then
    echo "❌ .env file not found. Please run setup_polygon_env.py first"
    exit 1
fi

# Check if virtual environment exists
if [[ ! -d venv ]]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# Compile contracts
echo "🔨 Compiling contracts..."
brownie compile

# Ask user what to do
echo ""
echo "Choose an option:"
echo "1) Deploy new contract"
echo "2) Run arbitrage bot"
echo "3) Check opportunities only"

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "🚀 Deploying contract to Polygon..."
        brownie run scripts/deploy_polygon_v3.py --network polygon-main
        ;;
    2)
        echo "🤖 Starting arbitrage bot..."
        brownie run scripts/polygon_arbitrage_bot.py --network polygon-main
        ;;
    3)
        echo "👀 Checking opportunities..."
        python3 -c "
from scripts.polygon_arbitrage_bot import PolygonArbitrageBot
bot = PolygonArbitrageBot('CONTRACT_ADDRESS_HERE', 'PRIVATE_KEY_HERE')
opportunities = bot.scan_arbitrage_opportunities()
print(f'Found {len(opportunities)} opportunities')
for op in opportunities:
    print(f'{op[\"token_a_name\"]}/{op[\"token_b_name\"]}: ${op[\"profit_usd\"]:.2f}')
"
        ;;
    *)
        echo "❌ Invalid choice"
        ;;
esac
"""
    
    with open('run_polygon_bot.sh', 'w') as f:
        f.write(run_script)
    
    os.chmod('run_polygon_bot.sh', 0o755)
    print("✅ Created run_polygon_bot.sh")

def main():
    """Main setup function"""
    
    print("🔧 POLYGON FLASHLOAN ARBITRAGE - SETUP")
    print("=" * 40)
    
    create_env_file()
    create_requirements()
    create_run_script()
    
    print("\n✅ SETUP COMPLETE!")
    print("\n📝 NEXT STEPS:")
    print("1. Edit .env file with your private key and API keys")
    print("2. Run: chmod +x run_polygon_bot.sh")
    print("3. Run: ./run_polygon_bot.sh")
    print("\n💰 Ready for live Polygon arbitrage trading!")

if __name__ == "__main__":
    main()
