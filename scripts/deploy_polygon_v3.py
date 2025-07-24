
from brownie import FlashloanV3Polygon, accounts, config, network
from brownie.network import gas_price
from brownie.network.gas.strategies import LinearScalingStrategy

# Polygon Aave V3 Pool Addresses Provider
POLYGON_AAVE_V3_POOL_ADDRESSES_PROVIDER = "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"

def main():
    """
    Deploy FlashloanV3Polygon contract on Polygon network
    """
    
    # Set gas strategy for Polygon
    gas_strategy = LinearScalingStrategy("20 gwei", "50 gwei", 1.1)
    gas_price(gas_strategy)
    
    # Load account from private key
    account = accounts.add(config["wallets"]["from_key"])
    
    print(f"Deploying from account: {account.address}")
    print(f"Account balance: {account.balance() / 1e18:.4f} MATIC")
    
    # Deploy the contract
    flashloan = FlashloanV3Polygon.deploy(
        POLYGON_AAVE_V3_POOL_ADDRESSES_PROVIDER,
        {"from": account, "gas_limit": 3000000}
    )
    
    print(f"FlashloanV3Polygon deployed at: {flashloan.address}")
    print(f"Transaction hash: {flashloan.tx.txid}")
    
    # Verify deployment
    print(f"Contract owner: {flashloan.owner()}")
    print(f"Min profit basis: {flashloan.minProfitBasis()}")
    
    return flashloan

if __name__ == "__main__":
    main()
