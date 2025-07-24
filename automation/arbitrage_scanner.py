import asyncio
import json
import logging
import time
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from web3 import Web3
from web3.middleware import geth_poa_middleware
import requests
from dataclasses import dataclass
import os
from dotenv import load_dotenv
import aiohttp

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arbitrage.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TokenPair:
    token_a: str
    token_b: str
    symbol_a: str
    symbol_b: str
    decimals_a: int
    decimals_b: int

@dataclass
class ArbitrageOpportunity:
    token_pair: TokenPair
    dex_a: str
    dex_b: str
    amount_in: int
    expected_profit: int
    profit_percentage: float
    gas_estimate: int

class PolygonArbitrageScanner:
    def __init__(self):
        # Load environment variables
        self.private_key = os.getenv('PRIVATE_KEY')
        self.rpc_url = os.getenv('POLYGON_RPC_URL')
        self.contract_address = os.getenv('ARBITRAGE_CONTRACT_ADDRESS')

        # API Keys for aggregators
        self.oneinch_api_key = os.getenv('ONEINCH_API_KEY')
        self.zerox_api_key = os.getenv('ZEROX_API_KEY')
        self.oneinch_api_url = os.getenv('ONEINCH_API_URL', 'https://api.1inch.io/v5.0')
        self.zerox_api_url = os.getenv('ZEROX_API_URL', 'https://api.0x.org')

        if not self.private_key or not self.rpc_url:
            raise ValueError("Missing required environment variables")

        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.account = self.w3.eth.account.from_key(self.private_key)

        # Trading parameters
        self.min_profit_usd = float(os.getenv('MIN_PROFIT_USD', '1.0'))
        self.min_profit_percentage = float(os.getenv('MIN_PROFIT_PERCENTAGE', '0.30'))
        self.max_gas_price = int(os.getenv('MAX_GAS_PRICE_GWEI', '50')) * 10**9
        self.scan_interval = int(os.getenv('SCAN_INTERVAL_SECONDS', '1'))
        self.monitoring_interval = int(os.getenv('MONITORING_INTERVAL', '15000'))

        # Strategy parameters
        self.loan_fee_percentage = float(os.getenv('LOAN_FEE_PERCENTAGE', '60'))
        self.gas_buffer_percentage = float(os.getenv('GAS_BUFFER_PERCENTAGE', '40'))
        self.arbitrage_threshold = float(os.getenv('ARBITRAGE_THRESHOLD_PERCENT', '0.30'))

        # Performance tracking
        self.scan_count = 0
        self.opportunities_found = 0
        self.trades_executed = 0
        self.total_profit = 0

        # Configuration
        self.min_profit_usd = 1.0  # Minimum $1 profit
        self.max_gas_price_gwei = 50
        self.scan_interval = 1  # 1 second between scans

        # Load contract ABI
        self.contract_abi = self._load_contract_abi()

    def _load_token_list(self) -> List[TokenPair]:
        """Load popular Polygon token pairs for arbitrage scanning"""
        # Popular Polygon tokens
        tokens = [
            {
                'address': '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',  # WMATIC
                'symbol': 'WMATIC',
                'decimals': 18
            },
            {
                'address': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',  # USDC
                'symbol': 'USDC',
                'decimals': 6
            },
            {
                'address': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',  # USDT
                'symbol': 'USDT',
                'decimals': 6
            },
            {
                'address': '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063',  # DAI
                'symbol': 'DAI',
                'decimals': 18
            },
            {
                'address': '0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6',  # WBTC
                'symbol': 'WBTC',
                'decimals': 8
            },
            {
                'address': '0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619',  # WETH
                'symbol': 'WETH',
                'decimals': 18
            }
        ]

        pairs = []
        for i, token_a in enumerate(tokens):
            for token_b in tokens[i+1:]:
                pairs.append(TokenPair(
                    token_a=token_a['address'],
                    token_b=token_b['address'],
                    symbol_a=token_a['symbol'],
                    symbol_b=token_b['symbol'],
                    decimals_a=token_a['decimals'],
                    decimals_b=token_b['decimals']
                ))

        return pairs

    def _load_contract_abi(self) -> List:
        """Load the arbitrage contract ABI"""
        # Simplified ABI for the arbitrage functions we need
        return [
            {
                "inputs": [
                    {"name": "tokenA", "type": "address"},
                    {"name": "tokenB", "type": "address"},
                    {"name": "amountIn", "type": "uint256"}
                ],
                "name": "getArbitrageOpportunity",
                "outputs": [
                    {"name": "expectedProfit", "type": "uint256"},
                    {"name": "isProfitable", "type": "bool"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "tokens", "type": "address[]"},
                    {"name": "amounts", "type": "uint256[]"},
                    {"name": "userData", "type": "bytes"}
                ],
                "name": "executeBalancerFlashLoan",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

    def get_wallet_balance(self) -> Decimal:
        """Get current wallet balance in MATIC"""
        try:
            balance_wei = self.w3.eth.get_balance(self.account.address)
            balance_matic = Decimal(self.w3.from_wei(balance_wei, 'ether'))
            return balance_matic
        except Exception as e:
            logger.error(f"Error getting wallet balance: {str(e)}")
            return Decimal('0')

    async def get_1inch_quote(self, from_token: str, to_token: str, amount: int) -> Optional[Dict]:
        """Get quote from 1inch API"""
        try:
            url = f"{self.oneinch_api_url}/137/quote"
            params = {
                'fromTokenAddress': from_token,
                'toTokenAddress': to_token,
                'amount': amount
            }
            headers = {
                'Authorization': f'Bearer {self.oneinch_api_key}',
                'accept': 'application/json'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except Exception as e:
            logger.debug(f"1inch API error: {str(e)}")
            return None

    async def get_0x_quote(self, sell_token: str, buy_token: str, sell_amount: int) -> Optional[Dict]:
        """Get quote from 0x API"""
        try:
            url = f"{self.zerox_api_url}/swap/v1/quote"
            params = {
                'sellToken': sell_token,
                'buyToken': buy_token,
                'sellAmount': sell_amount
            }
            headers = {
                '0x-api-key': self.zerox_api_key,
                'accept': 'application/json'
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except Exception as e:
            logger.debug(f"0x API error: {str(e)}")
            return None

    def calculate_loan_budget(self) -> Tuple[Decimal, bool]:
        """Calculate available loan budget and determine mode"""
        balance = self.get_wallet_balance()

        # Check minimum balance requirement
        if balance < Decimal('10'):  # $10 minimum
            return Decimal('0'), False

        # Determine mode and allocation
        is_high_risk = balance >= Decimal('320')  # $320 threshold

        if is_high_risk:
            loan_percentage = Decimal('0.80')  # 80% for high-risk mode
        else:
            loan_percentage = Decimal('0.70')  # 70% for safe mode

        loan_budget = balance * loan_percentage
        return loan_budget, is_high_risk

    async def scan_arbitrage_opportunities(self) -> List[ArbitrageOpportunity]:
        """Scan all token pairs across all DEXs for arbitrage opportunities"""
        opportunities = []
        loan_budget, is_high_risk = self.calculate_loan_budget()

        if loan_budget == 0:
            logger.warning("Insufficient balance for arbitrage operations")
            return opportunities

        logger.info(f"Scanning with {loan_budget} MATIC budget ({'High-Risk' if is_high_risk else 'Safe'} mode)")

        # Create contract instance
        if self.contract_address:
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )

        for pair in self.tokens:
            self.scan_count += 1

            # Calculate test amount (use 10% of available budget)
            test_amount_matic = loan_budget * Decimal('0.1')
            test_amount_wei = self.w3.to_wei(test_amount_matic, 'ether')

            try:
                # Check opportunity using smart contract
                if self.contract_address:
                    result = contract.functions.getArbitrageOpportunity(
                        pair.token_a,
                        pair.token_b,
                        test_amount_wei
                    ).call()

                    expected_profit_wei, is_profitable = result

                    if is_profitable and expected_profit_wei > 0:
                        expected_profit_matic = Decimal(self.w3.from_wei(expected_profit_wei, 'ether'))
                        profit_percentage = float((expected_profit_matic / test_amount_matic) * 100)

                        # Check if profit meets minimum threshold
                        if expected_profit_matic >= Decimal(str(self.min_profit_usd)):
                            opportunity = ArbitrageOpportunity(
                                token_pair=pair,
                                dex_a='quickswap',
                                dex_b='sushiswap',
                                amount_in=int(test_amount_wei),
                                expected_profit=int(expected_profit_wei),
                                profit_percentage=profit_percentage,
                                gas_estimate=200000  # Estimated gas
                            )

                            opportunities.append(opportunity)
                            self.opportunities_found += 1

                            logger.info(f"Found opportunity: {pair.symbol_a}/{pair.symbol_b} - "
                                      f"Profit: {expected_profit_matic:.4f} MATIC ({profit_percentage:.2f}%)")

            except Exception as e:
                logger.debug(f"Error scanning {pair.symbol_a}/{pair.symbol_b}: {str(e)}")
                continue

        return opportunities

    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> bool:
        """Execute arbitrage opportunity using flash loan"""
        try:
            if not self.contract_address:
                logger.error("Contract address not configured")
                return False

            # Create contract instance
            contract = self.w3.eth.contract(
                address=self.contract_address,
                abi=self.contract_abi
            )

            # Prepare parameters
            tokens = [opportunity.token_pair.token_a]
            amounts = [opportunity.amount_in]

            # Encode arbitrage parameters
            arbitrage_params = {
                'tokenA': opportunity.token_pair.token_a,
                'tokenB': opportunity.token_pair.token_b,
                'dexA': self.dex_configs['quickswap']['router'],
                'dexB': self.dex_configs['sushiswap']['router'],
                'amountIn': opportunity.amount_in,
                'minProfitBps': int(opportunity.profit_percentage * 100)  # Convert to basis points
            }

            # This would need proper ABI encoding in production
            user_data = json.dumps(arbitrage_params).encode()

            # Estimate gas
            gas_estimate = contract.functions.executeBalancerFlashLoan(
                tokens, amounts, user_data
            ).estimate_gas({'from': self.account.address})

            # Check gas price
            gas_price = self.w3.eth.gas_price
            if self.w3.from_wei(gas_price, 'gwei') > self.max_gas_price_gwei:
                logger.warning(f"Gas price too high: {self.w3.from_wei(gas_price, 'gwei')} gwei")
                return False

            # Execute transaction
            transaction = contract.functions.executeBalancerFlashLoan(
                tokens, amounts, user_data
            ).build_transaction({
                'from': self.account.address,
                'gas': gas_estimate,
                'gasPrice': gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                self.trades_executed += 1
                profit_matic = Decimal(self.w3.from_wei(opportunity.expected_profit, 'ether'))
                self.total_profit += float(profit_matic)

                logger.info(f"✅ Arbitrage executed successfully! "
                          f"Profit: {profit_matic:.4f} MATIC | TX: {tx_hash.hex()}")
                return True
            else:
                logger.error(f"❌ Transaction failed: {tx_hash.hex()}")
                return False

        except Exception as e:
            logger.error(f"Error executing arbitrage: {str(e)}")
            return False

    async def continuous_scan(self):
        """Main scanning loop"""
        logger.info("🚀 Starting continuous arbitrage scanning...")

        while True:
            try:
                start_time = time.time()

                # Scan for opportunities
                opportunities = await self.scan_arbitrage_opportunities()

                # Execute most profitable opportunity
                if opportunities:
                    # Sort by profit percentage
                    opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
                    best_opportunity = opportunities[0]

                    logger.info(f"🎯 Best opportunity: {best_opportunity.token_pair.symbol_a}/"
                              f"{best_opportunity.token_pair.symbol_b} - "
                              f"{best_opportunity.profit_percentage:.2f}% profit")

                    # Execute the trade
                    success = await self.execute_arbitrage(best_opportunity)

                    if success:
                        # Brief pause after successful trade
                        await asyncio.sleep(2)
                else:
                    logger.info("🔍 No profitable opportunities found")

                # Performance logging
                scan_time = time.time() - start_time
                logger.info(f"📊 Scan completed in {scan_time:.2f}s | "
                          f"Scans: {self.scan_count} | Opportunities: {self.opportunities_found} | "
                          f"Trades: {self.trades_executed} | Profit: {self.total_profit:.4f} MATIC")

                # Wait before next scan
                await asyncio.sleep(self.scan_interval)

            except KeyboardInterrupt:
                logger.info("👋 Shutting down scanner...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying
import aiohttp

if __name__ == "__main__":
    scanner = PolygonArbitrageScanner()
    asyncio.run(scanner.continuous_scan())