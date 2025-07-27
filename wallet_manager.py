import sqlite3
import json
import os
from cryptography.fernet import Fernet
from web3 import Web3
import requests
from typing import Dict, List, Optional

class WalletManager:
    def __init__(self, db_path: str = "wallets.db"):
        self.db_path = db_path
        self.encryption_key = self._get_or_create_key()
        self.cipher = Fernet(self.encryption_key)
        self._init_database()
        
        # RPC endpoints for different chains
        self.rpc_endpoints = {
            'ethereum': 'https://cloudflare-eth.com',
            'base': 'https://base.llamarpc.com',
            'bsc': 'https://bsc-dataseed.binance.org',
            'polygon': 'https://polygon-rpc.com'
        }
        
        # Initialize Web3 connections
        self.web3_connections = {}
        for chain, endpoint in self.rpc_endpoints.items():
            try:
                self.web3_connections[chain] = Web3(Web3.HTTPProvider(endpoint))
            except Exception as e:
                print(f"Failed to connect to {chain}: {e}")
    
    def _get_or_create_key(self) -> bytes:
        """Get existing encryption key or create a new one"""
        key_file = "encryption.key"
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            return key
    
    def _init_database(self):
        """Initialize SQLite database for wallet storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                wallet_name TEXT NOT NULL,
                encrypted_private_key TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                chain TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                default_chain TEXT DEFAULT 'ethereum',
                max_slippage REAL DEFAULT 5.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def encrypt_private_key(self, private_key: str) -> str:
        """Encrypt private key"""
        return self.cipher.encrypt(private_key.encode()).decode()
    
    def decrypt_private_key(self, encrypted_key: str) -> str:
        """Decrypt private key"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()
    
    def add_wallet(self, user_id: str, wallet_name: str, private_key: str, chain: str = 'ethereum') -> Dict:
        """Add a new wallet for a user"""
        try:
            # Validate private key
            if not self._validate_private_key(private_key, chain):
                return {"success": False, "error": "Invalid private key"}
            
            # Get wallet address
            wallet_address = self._get_wallet_address(private_key, chain)
            if not wallet_address:
                return {"success": False, "error": "Could not derive wallet address"}
            
            # Encrypt private key
            encrypted_key = self.encrypt_private_key(private_key)
            
            # Store in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO wallets (user_id, wallet_name, encrypted_private_key, wallet_address, chain)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, wallet_name, encrypted_key, wallet_address, chain))
            
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "wallet_address": wallet_address,
                "chain": chain,
                "message": f"Wallet '{wallet_name}' added successfully"
            }
            
        except Exception as e:
            return {"success": False, "error": f"Failed to add wallet: {str(e)}"}
    
    def get_user_wallets(self, user_id: str) -> List[Dict]:
        """Get all wallets for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT wallet_name, wallet_address, chain, created_at
            FROM wallets
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        wallets = []
        for row in cursor.fetchall():
            wallets.append({
                "name": row[0],
                "address": row[1],
                "chain": row[2],
                "created_at": row[3]
            })
        
        conn.close()
        return wallets
    
    def get_wallet_balance(self, user_id: str, wallet_name: str, chain: str = 'ethereum') -> Dict:
        """Get wallet balance for a specific chain"""
        try:
            # Get wallet address
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT wallet_address
                FROM wallets
                WHERE user_id = ? AND wallet_name = ? AND chain = ?
            ''', (user_id, wallet_name, chain))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return {"success": False, "error": "Wallet not found"}
            
            wallet_address = result[0]
            
            # Get balance
            if chain in self.web3_connections:
                web3 = self.web3_connections[chain]
                balance_wei = web3.eth.get_balance(wallet_address)
                balance_eth = web3.from_wei(balance_wei, 'ether')
                
                return {
                    "success": True,
                    "wallet_address": wallet_address,
                    "chain": chain,
                    "balance_wei": balance_wei,
                    "balance_eth": float(balance_eth),
                    "symbol": "ETH" if chain == "ethereum" else "BNB" if chain == "bsc" else "MATIC"
                }
            else:
                return {"success": False, "error": f"Chain {chain} not supported"}
                
        except Exception as e:
            return {"success": False, "error": f"Failed to get balance: {str(e)}"}
    
    def remove_wallet(self, user_id: str, wallet_name: str, chain: str = 'ethereum') -> Dict:
        """Remove a wallet"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM wallets
                WHERE user_id = ? AND wallet_name = ? AND chain = ?
            ''', (user_id, wallet_name, chain))
            
            if cursor.rowcount == 0:
                conn.close()
                return {"success": False, "error": "Wallet not found"}
            
            conn.commit()
            conn.close()
            
            return {"success": True, "message": f"Wallet '{wallet_name}' removed successfully"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to remove wallet: {str(e)}"}
    
    def _validate_private_key(self, private_key: str, chain: str) -> bool:
        """Validate private key format"""
        try:
            if chain in ['ethereum', 'base', 'bsc', 'polygon']:
                # Remove '0x' prefix if present
                if private_key.startswith('0x'):
                    private_key = private_key[2:]
                
                # Check if it's a valid hex string of correct length
                if len(private_key) != 64:
                    return False
                
                int(private_key, 16)  # Check if it's valid hex
                return True
            else:
                return False
        except:
            return False
    
    def _get_wallet_address(self, private_key: str, chain: str) -> Optional[str]:
        """Get wallet address from private key"""
        try:
            if chain in ['ethereum', 'base', 'bsc', 'polygon']:
                if chain in self.web3_connections:
                    web3 = self.web3_connections[chain]
                    account = web3.eth.account.from_key(private_key)
                    return account.address
            return None
        except:
            return None
    
    def get_user_settings(self, user_id: str) -> Dict:
        """Get user settings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT default_chain, max_slippage
            FROM user_settings
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                "default_chain": result[0],
                "max_slippage": result[1]
            }
        else:
            return {
                "default_chain": "ethereum",
                "max_slippage": 5.0
            }
    
    def update_user_settings(self, user_id: str, default_chain: str = None, max_slippage: float = None) -> Dict:
        """Update user settings"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if default_chain and max_slippage:
                cursor.execute('''
                    INSERT OR REPLACE INTO user_settings (user_id, default_chain, max_slippage)
                    VALUES (?, ?, ?)
                ''', (user_id, default_chain, max_slippage))
            elif default_chain:
                cursor.execute('''
                    INSERT OR REPLACE INTO user_settings (user_id, default_chain)
                    VALUES (?, ?)
                ''', (user_id, default_chain))
            elif max_slippage:
                cursor.execute('''
                    INSERT OR REPLACE INTO user_settings (user_id, max_slippage)
                    VALUES (?, ?)
                ''', (user_id, max_slippage))
            
            conn.commit()
            conn.close()
            
            return {"success": True, "message": "Settings updated successfully"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to update settings: {str(e)}"} 
