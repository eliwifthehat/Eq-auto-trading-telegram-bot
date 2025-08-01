import os
from typing import Dict, List, Optional
from web3 import Web3
from eth_account import Account
from solana.rpc.api import Client as SolanaClient
from solana.transaction import Transaction
from solana.system_program import TransferParams, transfer
import requests

class TransactionManager:
    def __init__(self):
        """Initialize transaction manager with RPC endpoints"""
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
    
    def get_deposit_address(self, wallet_address: str, chain: str) -> Dict:
        """Get deposit address for a wallet (same as wallet address for now)"""
        try:
            if chain == "solana":
                return {
                    "success": True,
                    "deposit_address": wallet_address,
                    "chain": chain,
                    "note": "Send SOL to this address"
                }
            elif chain in self.web3_connections:
                return {
                    "success": True,
                    "deposit_address": wallet_address,
                    "chain": chain,
                    "note": f"Send {chain.upper()} to this address"
                }
            else:
                return {"success": False, "error": f"Unsupported chain: {chain}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_native_token(self, from_private_key: str, to_address: str, amount: float, chain: str) -> Dict:
        """Send native tokens (ETH, BNB, MATIC)"""
        try:
            if chain not in self.web3_connections:
                return {"success": False, "error": f"Unsupported chain: {chain}"}
            
            web3 = self.web3_connections[chain]
            
            # Create account from private key
            account = Account.from_key(from_private_key)
            from_address = account.address
            
            # Validate addresses
            if not web3.is_address(to_address):
                return {"success": False, "error": "Invalid recipient address"}
            
            # Convert amount to wei
            amount_wei = web3.to_wei(amount, 'ether')
            
            # Get gas price
            gas_price = web3.eth.gas_price
            
            # Estimate gas
            gas_estimate = web3.eth.estimate_gas({
                'from': from_address,
                'to': to_address,
                'value': amount_wei
            })
            
            # Build transaction
            transaction = {
                'from': from_address,
                'to': to_address,
                'value': amount_wei,
                'gas': gas_estimate,
                'gasPrice': gas_price,
                'nonce': web3.eth.get_transaction_count(from_address)
            }
            
            # Sign transaction
            signed_txn = web3.eth.account.sign_transaction(transaction, from_private_key)
            
            # Send transaction
            tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                "success": True,
                "tx_hash": tx_hash.hex(),
                "from_address": from_address,
                "to_address": to_address,
                "amount": amount,
                "gas_used": tx_receipt.gasUsed,
                "gas_price": gas_price,
                "total_cost": tx_receipt.gasUsed * gas_price,
                "status": "confirmed" if tx_receipt.status == 1 else "failed",
                "block_number": tx_receipt.blockNumber
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_sol(self, from_private_key: str, to_address: str, amount: float) -> Dict:
        """Send SOL tokens"""
        try:
            # Convert SOL to lamports
            amount_lamports = int(amount * 10**9)
            
            # Create transaction
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_private_key,  # This should be a public key
                    to_pubkey=to_address,
                    lamports=amount_lamports
                )
            )
            
            transaction = Transaction().add(transfer_ix)
            
            # Send transaction
            result = self.solana_client.send_transaction(transaction)
            
            if result.get('result'):
                return {
                    "success": True,
                    "tx_hash": result['result'],
                    "from_address": from_private_key,
                    "to_address": to_address,
                    "amount": amount,
                    "amount_lamports": amount_lamports,
                    "status": "sent"
                }
            else:
                return {"success": False, "error": "Failed to send SOL transaction"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_token(self, from_private_key: str, to_address: str, token_address: str, amount: float, chain: str) -> Dict:
        """Send ERC-20 tokens"""
        try:
            if chain not in self.web3_connections:
                return {"success": False, "error": f"Unsupported chain: {chain}"}
            
            web3 = self.web3_connections[chain]
            
            # ERC-20 ABI for transfer function
            abi = [
                {
                    "constant": False,
                    "inputs": [
                        {"name": "_to", "type": "address"},
                        {"name": "_value", "type": "uint256"}
                    ],
                    "name": "transfer",
                    "outputs": [{"name": "", "type": "bool"}],
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
            
            # Get token decimals
            decimals = contract.functions.decimals().call()
            symbol = contract.functions.symbol().call()
            
            # Convert amount to token units
            amount_raw = int(amount * (10 ** decimals))
            
            # Create account from private key
            account = Account.from_key(from_private_key)
            from_address = account.address
            
            # Build transaction
            transaction = contract.functions.transfer(to_address, amount_raw).build_transaction({
                'from': from_address,
                'gas': 100000,  # Standard gas limit for token transfer
                'gasPrice': web3.eth.gas_price,
                'nonce': web3.eth.get_transaction_count(from_address)
            })
            
            # Sign transaction
            signed_txn = web3.eth.account.sign_transaction(transaction, from_private_key)
            
            # Send transaction
            tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            return {
                "success": True,
                "tx_hash": tx_hash.hex(),
                "from_address": from_address,
                "to_address": to_address,
                "token_address": token_address,
                "token_symbol": symbol,
                "amount": amount,
                "amount_raw": amount_raw,
                "gas_used": tx_receipt.gasUsed,
                "status": "confirmed" if tx_receipt.status == 1 else "failed",
                "block_number": tx_receipt.blockNumber
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def estimate_gas(self, from_address: str, to_address: str, amount: float, chain: str, token_address: str = None) -> Dict:
        """Estimate gas for a transaction"""
        try:
            if chain not in self.web3_connections:
                return {"success": False, "error": f"Unsupported chain: {chain}"}
            
            web3 = self.web3_connections[chain]
            
            if token_address:
                # ERC-20 token transfer
                abi = [
                    {
                        "constant": False,
                        "inputs": [
                            {"name": "_to", "type": "address"},
                            {"name": "_value", "type": "uint256"}
                        ],
                        "name": "transfer",
                        "outputs": [{"name": "", "type": "bool"}],
                        "type": "function"
                    }
                ]
                
                contract = web3.eth.contract(address=token_address, abi=abi)
                decimals = contract.functions.decimals().call()
                amount_raw = int(amount * (10 ** decimals))
                
                transaction = contract.functions.transfer(to_address, amount_raw).build_transaction({
                    'from': from_address,
                    'gas': 100000,
                    'gasPrice': web3.eth.gas_price,
                    'nonce': web3.eth.get_transaction_count(from_address)
                })
            else:
                # Native token transfer
                amount_wei = web3.to_wei(amount, 'ether')
                transaction = {
                    'from': from_address,
                    'to': to_address,
                    'value': amount_wei,
                    'gas': 21000,
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
                "total_cost_eth": web3.from_wei(total_cost, 'ether'),
                "transaction_type": "token" if token_address else "native"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_transaction_status(self, tx_hash: str, chain: str) -> Dict:
        """Get transaction status and details"""
        try:
            if chain == "solana":
                result = self.solana_client.get_transaction(tx_hash)
                if result.get('result'):
                    tx_data = result['result']
                    return {
                        "success": True,
                        "tx_hash": tx_hash,
                        "status": "confirmed" if tx_data.get('meta', {}).get('err') is None else "failed",
                        "block_number": tx_data.get('slot'),
                        "confirmations": 1,  # Solana doesn't have confirmations like ETH
                        "fee": tx_data.get('meta', {}).get('fee', 0)
                    }
                else:
                    return {"success": False, "error": "Transaction not found"}
                    
            elif chain in self.web3_connections:
                web3 = self.web3_connections[chain]
                
                # Get transaction receipt
                receipt = web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    # Get current block number
                    current_block = web3.eth.block_number
                    confirmations = current_block - receipt.blockNumber
                    
                    return {
                        "success": True,
                        "tx_hash": tx_hash,
                        "status": "confirmed" if receipt.status == 1 else "failed",
                        "block_number": receipt.blockNumber,
                        "confirmations": confirmations,
                        "gas_used": receipt.gasUsed,
                        "effective_gas_price": receipt.effectiveGasPrice
                    }
                else:
                    return {"success": False, "error": "Transaction not found"}
            else:
                return {"success": False, "error": f"Unsupported chain: {chain}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)} 
