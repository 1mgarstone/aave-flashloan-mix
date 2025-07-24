
from brownie import PolygonArbitrageEngine, accounts, config, network
import os
from dotenv import load_dotenv

load_dotenv()

def main():
    """
    Deploy the PolygonArbitrageEngine contract
    """
    print(f"Deploying to network: {network.show_active()}")
    
    # Get account from private key
    private_key = os.getenv('PRIVATE_KEY')
    if not private_key:
        private_key = config["wallets"]["from_key"]
    
    acct = accounts.add(private_key)
    print(f"Deploying from account: {acct.address}")
    print(f"Account balance: {acct.balance() / 1e18:.4f} MATIC")
    
    # Deploy the contract
    print("Deploying PolygonArbitrageEngine...")
    arbitrage_engine = PolygonArbitrageEngine.deploy(
        {"from": acct}
    )
    
    print(f"✅ Contract deployed at: {arbitrage_engine.address}")
    print(f"📝 Transaction hash: {arbitrage_engine.tx.txid}")
    
    # Verify deployment
    print("\n🔍 Verifying deployment...")
    print(f"Contract owner: {arbitrage_engine.owner()}")
    print(f"Min wallet balance: {arbitrage_engine.MIN_WALLET_BALANCE() / 1e18} MATIC")
    print(f"Safe mode threshold: {arbitrage_engine.SAFE_MODE_THRESHOLD() / 1e18} MATIC")
    
    # Fund the contract with some MATIC for gas
    funding_amount = 1  # 1 MATIC
    if acct.balance() > funding_amount * 1e18:
        print(f"\n💰 Funding contract with {funding_amount} MATIC...")
        acct.transfer(arbitrage_engine.address, funding_amount * 1e18)
        print(f"Contract balance: {arbitrage_engine.balance() / 1e18:.4f} MATIC")
    
    print(f"\n🎉 Deployment complete!")
    print(f"📋 Add this to your .env file:")
    print(f"ARBITRAGE_CONTRACT_ADDRESS={arbitrage_engine.address}")
    
    return arbitrage_engine

if __name__ == "__main__":
    main()
