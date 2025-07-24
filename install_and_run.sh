#!/bin/bash

echo "🚀 Setting up your Polygon Flashloan Arbitrage Project..."

# Check if .env exists
if [[ ! -f .env ]]; then
    echo "❌ .env file not found. Please run setup_polygon_env.py first"
    exit 1
fi

# Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

# Compile contracts
echo "🔨 Compiling contracts..."
brownie compile

# Start the dashboard
echo "🚀 Starting Polygon Arbitrage Engine Dashboard..."
python3 run_dashboard.py --host 0.0.0.0 --port 5000