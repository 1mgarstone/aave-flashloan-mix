
import time
import json
import requests
from brownie import FlashloanV3Polygon, accounts, config, network, Contract
from web3 import Web3
import threading
from datetime import datetime

class PolygonArbitrageBot:
    def __init__(self, contract_address, private_key):
        self.contract = Contract.from_abi(
            "FlashloanV3Polygon", 
            contract_address, 
            FlashloanV3Polygon.abi
        )
        self.account = accounts.add(private_key)
        self.running = False
        
        # Polygon token addresses
        self.tokens = {
            'WMATIC': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',
            'USDC': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
            'WETH': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',
            'DAI': '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063',
            'USDT': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F'
        }
        
        # DEX addresses
        self.dexes = {
            'QUICKSWAP': '0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff',
            'SUSHISWAP': '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506'
        }
        
        # Trade amounts (in wei)
        self.trade_amounts = [
            Web3.toWei(1000, 'ether'),    # 1000 MATIC
            Web3.toWei(3146, 'ether'),    # 3146 MATIC
            Web3.toWei(10000, 'ether'),   # 10000 MATIC
        ]
        
        self.min_profit_usd = 10  # Minimum $10 profit
        self.max_gas_price = Web3.toWei(100, 'gwei')  # Max 100 gwei
        
    def get_token_price_usd(self, token_address):
        """Get token price in USD from CoinGecko API"""
        try:
            # Map addresses to CoinGecko IDs
            token_map = {
                self.tokens['WMATIC']: 'matic-network',
                self.tokens['USDC']: 'usd-coin',
                self.tokens['WETH']: 'ethereum',
                self.tokens['DAI']: 'dai',
                self.tokens['USDT']: 'tether'
            }
            
            if token_address in token_map:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={token_map[token_address]}&vs_currencies=usd"
                response = requests.get(url, timeout=5)
                data = response.json()
                return float(list(data.values())[0]['usd'])
        except Exception as e:
            print(f"Error fetching price for {token_address}: {e}")
        return 0

    def scan_arbitrage_opportunities(self):
        """Scan for profitable arbitrage opportunities"""
        opportunities = []
        
        token_pairs = [
            ('WMATIC', 'USDC'),
            ('WMATIC', 'WETH'), 
            ('USDC', 'WETH'),
            ('WMATIC', 'DAI'),
            ('USDC', 'DAI')
        ]
        
        for token_a_name, token_b_name in token_pairs:
            token_a = self.tokens[token_a_name]
            token_b = self.tokens[token_b_name]
            
            for amount in self.trade_amounts:
                try:
                    # Check arbitrage opportunity
                    profit, profitable = self.contract.checkArbitrageOpportunity(
                        token_a, token_b, amount
                    )
                    
                    if profitable:
                        # Calculate USD value of profit
                        token_price = self.get_token_price_usd(token_a)
                        profit_usd = (profit / 1e18) * token_price
                        
                        if profit_usd >= self.min_profit_usd:
                            opportunities.append({
                                'token_a': token_a,
                                'token_b': token_b,
                                'token_a_name': token_a_name,
                                'token_b_name': token_b_name,
                                'amount': amount,
                                'profit': profit,
                                'profit_usd': profit_usd,
                                'timestamp': datetime.now()
                            })
                            
                except Exception as e:
                    print(f"Error checking {token_a_name}/{token_b_name}: {e}")
                    
        return opportunities

    def execute_arbitrage(self, opportunity):
        """Execute profitable arbitrage trade"""
        try:
            print(f"\n🔥 EXECUTING ARBITRAGE:")
            print(f"Pair: {opportunity['token_a_name']}/{opportunity['token_b_name']}")
            print(f"Amount: {opportunity['amount'] / 1e18:.2f}")
            print(f"Expected Profit: ${opportunity['profit_usd']:.2f}")
            
            # Check gas price
            current_gas_price = network.gas_price()
            if current_gas_price > self.max_gas_price:
                print(f"❌ Gas price too high: {current_gas_price / 1e9:.1f} gwei")
                return False
            
            # Execute flashloan arbitrage
            tx = self.contract.startFlashLoanArbitrage(
                opportunity['token_a'],           # asset to borrow
                opportunity['amount'],            # amount to borrow
                opportunity['token_a'],           # tokenA
                opportunity['token_b'],           # tokenB  
                self.dexes['QUICKSWAP'],         # dexA
                self.dexes['SUSHISWAP'],         # dexB
                opportunity['profit'],            # expected profit
                {"from": self.account, "gas_limit": 314600}
            )
            
            print(f"✅ Transaction sent: {tx.txid}")
            print(f"Gas used: {tx.gas_used:,}")
            print(f"Gas price: {tx.gas_price / 1e9:.1f} gwei")
            
            return True
            
        except Exception as e:
            print(f"❌ Execution failed: {e}")
            return False

    def run_continuous_scan(self):
        """Run continuous arbitrage scanning"""
        print("🚀 POLYGON ARBITRAGE BOT STARTED")
        print(f"Account: {self.account.address}")
        print(f"Balance: {self.account.balance() / 1e18:.4f} MATIC")
        print("=" * 50)
        
        self.running = True
        scan_count = 0
        
        while self.running:
            try:
                scan_count += 1
                print(f"\n📊 Scan #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                opportunities = self.scan_arbitrage_opportunities()
                
                if opportunities:
                    print(f"🎯 Found {len(opportunities)} opportunities!")
                    
                    # Sort by profit and execute best one
                    best_opportunity = max(opportunities, key=lambda x: x['profit_usd'])
                    
                    if self.execute_arbitrage(best_opportunity):
                        # Wait longer after successful execution
                        time.sleep(30)
                    else:
                        time.sleep(5)
                else:
                    print("⏳ No profitable opportunities found")
                    time.sleep(10)
                    
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Scan error: {e}")
                time.sleep(15)
        
        self.running = False

    def stop(self):
        """Stop the bot"""
        self.running = False

def main():
    """Main bot execution"""
    
    # Load configuration
    contract_address = input("Enter FlashloanV3Polygon contract address: ")
    private_key = config["wallets"]["from_key"]
    
    # Initialize and start bot
    bot = PolygonArbitrageBot(contract_address, private_key)
    
    try:
        bot.run_continuous_scan()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down bot...")
        bot.stop()

if __name__ == "__main__":
    main()
