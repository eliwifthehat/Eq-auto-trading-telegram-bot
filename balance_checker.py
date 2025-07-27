import os
from typing import Dict, List, Optional
from web3 import Web3
from solana.rpc.api import Client as SolanaClient
import requests

class BalanceChecker:
    def __init__(self):
        """Initialize balance checker with RPC endpoints"""
        self.rpc_endpoints = {
            'ethereum': os.environ.get('ETHEREUM_RPC', 'https://eth.llamarpc.com'),
            'base': os.environ.get('BASE_RPC', 'https://mainnet.base.org'),
            'bsc': os.environ.get('BSC_RPC', 'https://bsc-dataseed1.binance.org'),
            'polygon': os.environ.get('POLYGON_RPC', 'https://polygon-rpc.com'),
        }
        
        # Initialize Web3 connections
        self.web3_connections = {}
        for chain, endpoint in self.rpc_endpoints.items():
            try:
                self.web3_connections[chain] = Web3(Web3.HTTPProvider(endpoint))
            except Exception as e:
                print(f"Failed to connect to {chain}: {e}")
        
        # Initialize Solana client
        self.solana_client = SolanaClient(os.environ.get('SOLANA_RPC', 'https://api.mainnet-beta.solana.com'))
    
    def get_eth_balance(self, address: str, chain: str) -> Dict:
        """Get ETH/BNB/MATIC balance for EVM chains"""
        try:
            if chain not in self.web3_connections:
                return {"success": False, "error": f"Unsupported chain: {chain}"}
            
            web3 = self.web3_connections[chain]
            
            # Validate address
            if not web3.is_address(address):
                return {"success": False, "error": "Invalid address"}
            
            # Get balance in wei
            balance_wei = web3.eth.get_balance(address)
            balance_eth = web3.from_wei(balance_wei, 'ether')
            
            # Get symbol based on chain
            symbols = {
                'ethereum': 'ETH',
                'base': 'ETH',
                'bsc': 'BNB',
                'polygon': 'MATIC'
            }
            
            return {
                "success": True,
                "balance_eth": float(balance_eth),
                "balance_wei": str(balance_wei),
                "symbol": symbols.get(chain, 'ETH'),
                "chain": chain,
                "address": address
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_sol_balance(self, address: str) -> Dict:
        """Get SOL balance for Solana"""
        try:
            # Get SOL balance
            response = self.solana_client.get_balance(address)
            
            if response.get('result'):
                balance_lamports = response['result']['value']
                balance_sol = balance_lamports / 10**9  # Convert lamports to SOL
                
                return {
                    "success": True,
                    "balance_sol": float(balance_sol),
                    "balance_lamports": balance_lamports,
                    "symbol": "SOL",
                    "chain": "solana",
                    "address": address
                }
            else:
                return {"success": False, "error": "Failed to get Solana balance"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_token_balance(self, wallet_address: str, token_address: str, chain: str) -> Dict:
        """Get ERC-20 token balance"""
        try:
            if chain not in self.web3_connections:
                return {"success": False, "error": f"Unsupported chain: {chain}"}
            
            web3 = self.web3_connections[chain]
            
            # ERC-20 ABI for balanceOf function
            abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "symbol",
                    "outputs": [{"name": "", "type": "string"}],
                    "type": "function"
                }
            ]
            
            # Create contract instance
            contract = web3.eth.contract(address=token_address, abi=abi)
            
            # Get balance
            balance_raw = contract.functions.balanceOf(wallet_address).call()
            decimals = contract.functions.decimals().call()
            symbol = contract.functions.symbol().call()
            
            # Convert to human readable
            balance = balance_raw / (10 ** decimals)
            
            return {
                "success": True,
                "balance": float(balance),
                "balance_raw": str(balance_raw),
                "symbol": symbol,
                "decimals": decimals,
                "token_address": token_address,
                "chain": chain
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_all_balances(self, wallet_address: str, chain: str) -> Dict:
        """Get all balances for a wallet (native + tokens)"""
        try:
            balances = {
                "native": None,
                "tokens": [],
                "chain": chain,
                "address": wallet_address
            }
            
            # Get native balance
            if chain == "solana":
                balances["native"] = self.get_sol_balance(wallet_address)
            else:
                balances["native"] = self.get_eth_balance(wallet_address, chain)
            
            # TODO: Add token balance fetching for popular tokens
            # This would require maintaining a list of popular token addresses
            
            return {
                "success": True,
                "balances": balances
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def estimate_gas(self, from_address: str, to_address: str, value: int, chain: str) -> Dict:
        """Estimate gas for a transaction"""
        try:
            if chain not in self.web3_connections:
                return {"success": False, "error": f"Unsupported chain: {chain}"}
            
            web3 = self.web3_connections[chain]
            
            # Build transaction
            transaction = {
                'from': from_address,
                'to': to_address,
                'value': value,
                'gas': 21000,  # Standard gas limit for ETH transfer
                'gasPrice': web3.eth.gas_price
            }
            
            # Estimate gas
            estimated_gas = web3.eth.estimate_gas(transaction)
            gas_price = web3.eth.gas_price
            total_cost = estimated_gas * gas_price
            
            return {
                "success": True,
                "estimated_gas": estimated_gas,
                "gas_price": gas_price,
                "total_cost_wei": total_cost,
                "total_cost_eth": web3.from_wei(total_cost, 'ether')
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)} 
