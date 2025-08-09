import os
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from cryptography.fernet import Fernet

class SyncDatabaseManager:
    """Synchronous database manager using direct HTTP requests to Supabase REST API"""
    
    def __init__(self):
        """Initialize synchronous Supabase connection"""
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_ANON_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")
        
        # Initialize encryption key
        self.encryption_key = os.environ.get("ENCRYPTION_KEY")
        if not self.encryption_key:
            # Generate new key if not exists
            self.encryption_key = Fernet.generate_key().decode()
            print(f"Generated new encryption key: {self.encryption_key}")
        
        self.cipher = Fernet(self.encryption_key.encode())
        
        # Setup HTTP headers
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
    
    def encrypt_private_key(self, private_key: str) -> str:
        """Encrypt private key for storage"""
        return self.cipher.encrypt(private_key.encode()).decode()
    
    def decrypt_private_key(self, encrypted_key: str) -> str:
        """Decrypt private key for use"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()
    
    def _make_request(self, method: str, table: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make HTTP request to Supabase REST API"""
        try:
            url = f"{self.supabase_url}/rest/v1/{table}"
            
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=10)
            elif method.upper() == "PATCH":
                response = requests.patch(url, headers=self.headers, json=data, params=params, timeout=10)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self.headers, params=params, timeout=10)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}
            
            if response.status_code in [200, 201, 204]:
                return {
                    "success": True,
                    "data": response.json() if response.content else [],
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout - database may be slow"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Connection error - database may be unavailable"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # User Management
    def create_user(self, telegram_id: str, username: str = None, first_name: str = None, last_name: str = None) -> Dict:
        """Create a new user"""
        try:
            user_data = {
                "telegram_id": str(telegram_id),
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "settings": {
                    "default_chain": "ethereum",
                    "max_slippage": 5.0,
                    "notifications": True
                }
            }
            
            result = self._make_request("POST", "users", data=user_data)
            
            if result["success"]:
                return {"success": True, "user": result["data"][0] if result["data"] else user_data}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user(self, telegram_id: str) -> Dict:
        """Get user by Telegram ID"""
        try:
            params = {"telegram_id": f"eq.{telegram_id}", "select": "*"}
            result = self._make_request("GET", "users", params=params)
            
            if result["success"]:
                if result["data"]:
                    return {"success": True, "user": result["data"][0]}
                else:
                    return {"success": False, "error": "User not found"}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def update_user_settings(self, telegram_id: str, settings: Dict) -> Dict:
        """Update user settings"""
        try:
            params = {"telegram_id": f"eq.{telegram_id}"}
            data = {"settings": settings}
            result = self._make_request("PATCH", "users", data=data, params=params)
            
            if result["success"]:
                return {"success": True}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Wallet Management
    def add_wallet(self, telegram_id: str, name: str, address: str, private_key: str, chain: str) -> Dict:
        """Add a new wallet"""
        try:
            encrypted_key = self.encrypt_private_key(private_key)
            
            wallet_data = {
                "telegram_id": str(telegram_id),
                "name": name,
                "address": address,
                "encrypted_private_key": encrypted_key,
                "chain": chain.lower(),
                "balance": 0.0
            }
            
            result = self._make_request("POST", "wallets", data=wallet_data)
            
            if result["success"]:
                return {
                    "success": True, 
                    "wallet": result["data"][0] if result["data"] else wallet_data,
                    "wallet_address": address
                }
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_wallet(self, telegram_id: str, name: str, chain: str) -> Dict:
        """Get specific wallet"""
        try:
            params = {
                "telegram_id": f"eq.{telegram_id}",
                "name": f"eq.{name}",
                "chain": f"eq.{chain.lower()}",
                "select": "*"
            }
            result = self._make_request("GET", "wallets", params=params)
            
            if result["success"]:
                if result["data"]:
                    return {"success": True, "wallet": result["data"][0]}
                else:
                    return {"success": False, "error": "Wallet not found"}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_wallets(self, telegram_id: str) -> Dict:
        """Get all wallets for a user"""
        try:
            params = {
                "telegram_id": f"eq.{telegram_id}",
                "select": "*",
                "order": "created_at.desc"
            }
            result = self._make_request("GET", "wallets", params=params)
            
            if result["success"]:
                return {"success": True, "wallets": result["data"]}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def remove_wallet(self, telegram_id: str, name: str, chain: str) -> Dict:
        """Remove a wallet"""
        try:
            params = {
                "telegram_id": f"eq.{telegram_id}",
                "name": f"eq.{name}",
                "chain": f"eq.{chain.lower()}"
            }
            result = self._make_request("DELETE", "wallets", params=params)
            
            if result["success"]:
                return {"success": True}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def update_wallet_balance(self, telegram_id: str, name: str, chain: str, balance: float) -> Dict:
        """Update wallet balance"""
        try:
            params = {
                "telegram_id": f"eq.{telegram_id}",
                "name": f"eq.{name}",
                "chain": f"eq.{chain.lower()}"
            }
            data = {"balance": balance}
            result = self._make_request("PATCH", "wallets", data=data, params=params)
            
            if result["success"]:
                return {"success": True}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Transaction Management
    def add_transaction(self, telegram_id: str, wallet_name: str, chain: str, tx_hash: str, 
                       from_address: str, to_address: str, amount: float, token_address: str = None) -> Dict:
        """Add a new transaction"""
        try:
            transaction_data = {
                "telegram_id": str(telegram_id),
                "wallet_name": wallet_name,
                "chain": chain.lower(),
                "tx_hash": tx_hash,
                "from_address": from_address,
                "to_address": to_address,
                "amount": amount,
                "token_address": token_address,
                "status": "pending"
            }
            
            result = self._make_request("POST", "transactions", data=transaction_data)
            
            if result["success"]:
                return {"success": True, "transaction": result["data"][0] if result["data"] else transaction_data}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_transactions(self, telegram_id: str, limit: int = 10) -> Dict:
        """Get user's recent transactions"""
        try:
            params = {
                "telegram_id": f"eq.{telegram_id}",
                "select": "*",
                "order": "created_at.desc",
                "limit": limit
            }
            result = self._make_request("GET", "transactions", params=params)
            
            if result["success"]:
                return {"success": True, "transactions": result["data"]}
            else:
                return {"success": False, "error": result["error"]}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
