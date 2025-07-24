
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";

interface IUniswapV2Router {
    function swapExactTokensForTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external returns (uint[] memory amounts);
    
    function getAmountsOut(uint amountIn, address[] calldata path)
        external view returns (uint[] memory amounts);
}

interface IBalancerVault {
    function flashLoan(
        address recipient,
        address[] memory tokens,
        uint256[] memory amounts,
        bytes memory userData
    ) external;
}

interface IAavePool {
    function flashLoan(
        address receiverAddress,
        address[] calldata assets,
        uint256[] calldata amounts,
        uint256[] calldata modes,
        address onBehalfOf,
        bytes calldata params,
        uint16 referralCode
    ) external;
}

contract PolygonArbitrageEngine is Ownable, ReentrancyGuard {
    using SafeMath for uint256;
    
    // DEX Router addresses on Polygon
    IUniswapV2Router public constant QUICKSWAP = IUniswapV2Router(0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff);
    IUniswapV2Router public constant SUSHISWAP = IUniswapV2Router(0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506);
    IBalancerVault public constant BALANCER = IBalancerVault(0xBA12222222228d8Ba445958a75a0704d566BF2C8);
    IAavePool public constant AAVE_POOL = IAavePool(0x794a61358D6845594F94dc1DB02A252b5b4814aD);
    
    // Configuration
    uint256 public constant SAFE_MODE_THRESHOLD = 320 * 10**18; // $320 in MATIC
    uint256 public constant MIN_WALLET_BALANCE = 10 * 10**18; // $10 in MATIC
    uint256 public constant CHARITY_PERCENTAGE = 208; // 2.08%
    uint256 public constant PERCENTAGE_BASE = 10000;
    
    // State variables
    bool public isHighRiskMode = false;
    bool public charityEnabled = false;
    address public charityAddress;
    uint256 public totalProfits = 0;
    uint256 public totalTrades = 0;
    
    // Wallet allocation percentages
    uint256 public loanBudgetPercentage = 7000; // 70% in safe mode
    uint256 public gasReservePercentage = 3000; // 30% in safe mode
    
    struct ArbitrageParams {
        address tokenA;
        address tokenB;
        address dexA;
        address dexB;
        uint256 amountIn;
        uint256 minProfitBps;
    }
    
    event ArbitrageExecuted(
        address indexed tokenA,
        address indexed tokenB,
        uint256 amountIn,
        uint256 profit,
        uint256 timestamp
    );
    
    event ModeChanged(bool isHighRisk, uint256 timestamp);
    
    constructor() {
        charityAddress = 0x000000000000000000000000000000000000dEaD; // Burn address as default
    }
    
    modifier onlyWhenBalanceSufficient() {
        require(address(this).balance >= MIN_WALLET_BALANCE, "Insufficient wallet balance");
        _;
    }
    
    function updateMode() internal {
        bool shouldBeHighRisk = address(this).balance >= SAFE_MODE_THRESHOLD;
        if (shouldBeHighRisk != isHighRiskMode) {
            isHighRiskMode = shouldBeHighRisk;
            if (isHighRiskMode) {
                loanBudgetPercentage = 8000; // 80%
                gasReservePercentage = 2000; // 20%
            } else {
                loanBudgetPercentage = 7000; // 70%
                gasReservePercentage = 3000; // 30%
            }
            emit ModeChanged(isHighRiskMode, block.timestamp);
        }
    }
    
    function calculateLoanAmount() public view returns (uint256) {
        uint256 availableBalance = address(this).balance;
        return availableBalance.mul(loanBudgetPercentage).div(PERCENTAGE_BASE);
    }
    
    function calculateRequiredSpread(uint256 loanFeeRate, uint256 gasMargin) 
        public pure returns (uint256) {
        return loanFeeRate.add(gasMargin);
    }
    
    function executeBalancerFlashLoan(
        address[] memory tokens,
        uint256[] memory amounts,
        bytes memory userData
    ) external onlyOwner onlyWhenBalanceSufficient nonReentrant {
        updateMode();
        BALANCER.flashLoan(address(this), tokens, amounts, userData);
    }
    
    function executeAaveFlashLoan(
        address[] memory assets,
        uint256[] memory amounts,
        bytes memory params
    ) external onlyOwner onlyWhenBalanceSufficient nonReentrant {
        updateMode();
        uint256[] memory modes = new uint256[](assets.length);
        // 0 = no debt (flash loan)
        for (uint256 i = 0; i < assets.length; i++) {
            modes[i] = 0;
        }
        
        AAVE_POOL.flashLoan(
            address(this),
            assets,
            amounts,
            modes,
            address(this),
            params,
            0
        );
    }
    
    function receiveFlashLoan(
        address[] memory tokens,
        uint256[] memory amounts,
        uint256[] memory feeAmounts,
        bytes memory userData
    ) external {
        require(msg.sender == address(BALANCER), "Invalid flashloan caller");
        
        ArbitrageParams memory params = abi.decode(userData, (ArbitrageParams));
        
        // Execute arbitrage logic
        uint256 profit = _executeArbitrage(params);
        
        // Handle charity donation
        if (charityEnabled && profit > 0) {
            uint256 charityAmount = profit.mul(CHARITY_PERCENTAGE).div(PERCENTAGE_BASE);
            if (charityAmount > 0) {
                payable(charityAddress).transfer(charityAmount);
                profit = profit.sub(charityAmount);
            }
        }
        
        // Repay flash loan
        for (uint256 i = 0; i < tokens.length; i++) {
            uint256 amountToRepay = amounts[i].add(feeAmounts[i]);
            IERC20(tokens[i]).transfer(address(BALANCER), amountToRepay);
        }
        
        if (profit > 0) {
            totalProfits = totalProfits.add(profit);
            totalTrades = totalTrades.add(1);
            
            emit ArbitrageExecuted(
                params.tokenA,
                params.tokenB,
                params.amountIn,
                profit,
                block.timestamp
            );
        }
    }
    
    function _executeArbitrage(ArbitrageParams memory params) 
        internal returns (uint256 profit) {
        
        // Step 1: Swap tokenA for tokenB on first DEX
        address[] memory path1 = new address[](2);
        path1[0] = params.tokenA;
        path1[1] = params.tokenB;
        
        IERC20(params.tokenA).approve(params.dexA, params.amountIn);
        
        uint256[] memory amounts1;
        if (params.dexA == address(QUICKSWAP)) {
            amounts1 = QUICKSWAP.swapExactTokensForTokens(
                params.amountIn,
                0,
                path1,
                address(this),
                block.timestamp + 300
            );
        } else if (params.dexA == address(SUSHISWAP)) {
            amounts1 = SUSHISWAP.swapExactTokensForTokens(
                params.amountIn,
                0,
                path1,
                address(this),
                block.timestamp + 300
            );
        }
        
        uint256 tokenBReceived = amounts1[1];
        
        // Step 2: Swap tokenB back to tokenA on second DEX
        address[] memory path2 = new address[](2);
        path2[0] = params.tokenB;
        path2[1] = params.tokenA;
        
        IERC20(params.tokenB).approve(params.dexB, tokenBReceived);
        
        uint256[] memory amounts2;
        if (params.dexB == address(QUICKSWAP)) {
            amounts2 = QUICKSWAP.swapExactTokensForTokens(
                tokenBReceived,
                0,
                path2,
                address(this),
                block.timestamp + 300
            );
        } else if (params.dexB == address(SUSHISWAP)) {
            amounts2 = SUSHISWAP.swapExactTokensForTokens(
                tokenBReceived,
                0,
                path2,
                address(this),
                block.timestamp + 300
            );
        }
        
        uint256 tokenAReceived = amounts2[1];
        
        // Calculate profit
        if (tokenAReceived > params.amountIn) {
            profit = tokenAReceived.sub(params.amountIn);
        }
        
        return profit;
    }
    
    function getArbitrageOpportunity(
        address tokenA,
        address tokenB,
        uint256 amountIn
    ) external view returns (uint256 expectedProfit, bool isProfitable) {
        
        // Get price on QuickSwap
        address[] memory path1 = new address[](2);
        path1[0] = tokenA;
        path1[1] = tokenB;
        uint256[] memory amounts1 = QUICKSWAP.getAmountsOut(amountIn, path1);
        
        // Get reverse price on SushiSwap
        address[] memory path2 = new address[](2);
        path2[0] = tokenB;
        path2[1] = tokenA;
        uint256[] memory amounts2 = SUSHISWAP.getAmountsOut(amounts1[1], path2);
        
        if (amounts2[1] > amountIn) {
            expectedProfit = amounts2[1].sub(amountIn);
            isProfitable = true;
        }
        
        return (expectedProfit, isProfitable);
    }
    
    function setCharityEnabled(bool _enabled) external onlyOwner {
        charityEnabled = _enabled;
    }
    
    function setCharityAddress(address _charityAddress) external onlyOwner {
        charityAddress = _charityAddress;
    }
    
    function withdrawProfits() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > MIN_WALLET_BALANCE, "Must maintain minimum balance");
        
        uint256 withdrawable = balance.sub(MIN_WALLET_BALANCE);
        payable(owner()).transfer(withdrawable);
    }
    
    function emergencyWithdraw(address token) external onlyOwner {
        if (token == address(0)) {
            payable(owner()).transfer(address(this).balance);
        } else {
            IERC20(token).transfer(owner(), IERC20(token).balanceOf(address(this)));
        }
    }
    
    receive() external payable {}
}
