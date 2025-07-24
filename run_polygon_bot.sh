#!/bin/bash

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
    print(f'{op["token_a_name"]}/{op["token_b_name"]}: ${op["profit_usd"]:.2f}')
"
        ;;
    *)
        echo "❌ Invalid choice"
        ;;
esac
