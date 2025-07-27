import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from cryptography.fernet import Fernet
from supabase import create_client, Client

class SupabaseManager:
    def __init__(self):
        """Initialize Supabase connection"""
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_ANON_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")
        
        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Initialize encryption key
        self.encryption_key = os.environ.get("ENCRYPTION_KEY")
        if not self.encryption_key:
            # Generate new key if not exists
            self.encryption_key = Fernet.generate_key().decode()
            print(f"Generated new encryption key: {self.encryption_key}")
        
        self.cipher = Fernet(self.encryption_key.encode())
    
    def encrypt_private_key(self, private_key: str) -> str:
        """Encrypt private key for storage"""
        return self.cipher.encrypt(private_key.encode()).decode()
    
    def decrypt_private_key(self, encrypted_key: str) -> str:
        """Decrypt private key for use"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()
    
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
            
            result = self.client.table("users").insert(user_data).execute()
            
            if result.data:
                return {"success": True, "user": result.data[0]}
            else:
                return {"success": False, "error": "Failed to create user"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user(self, telegram_id: str) -> Dict:
        """Get user by Telegram ID"""
        try:
            result = self.client.table("users").select("*").eq("telegram_id", str(telegram_id)).execute()
            
            if result.data:
                return {"success": True, "user": result.data[0]}
            else:
                return {"success": False, "error": "User not found"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def update_user_settings(self, telegram_id: str, settings: Dict) -> Dict:
        """Update user settings"""
        try:
            result = self.client.table("users").update({"settings": settings}).eq("telegram_id", str(telegram_id)).execute()
            
            if result.data:
                return {"success": True, "user": result.data[0]}
            else:
                return {"success": False, "error": "Failed to update settings"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Wallet Management
    def add_wallet(self, telegram_id: str, name: str, private_key: str, chain: str) -> Dict:
        """Add a new wallet for user"""
        try:
            # Get user first
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            # Encrypt private key
            encrypted_key = self.encrypt_private_key(private_key)
            
            wallet_data = {
                "user_id": user["id"],
                "name": name,
                "address": "",  # Will be set after validation
                "encrypted_private_key": encrypted_key,
                "chain": chain.lower()
            }
            
            result = self.client.table("wallets").insert(wallet_data).execute()
            
            if result.data:
                return {"success": True, "wallet": result.data[0]}
            else:
                return {"success": False, "error": "Failed to add wallet"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_wallets(self, telegram_id: str) -> Dict:
        """Get all wallets for a user"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            result = self.client.table("wallets").select("*").eq("user_id", user["id"]).execute()
            
            return {"success": True, "wallets": result.data}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_wallet(self, telegram_id: str, wallet_name: str, chain: str) -> Dict:
        """Get specific wallet"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            result = self.client.table("wallets").select("*").eq("user_id", user["id"]).eq("name", wallet_name).eq("chain", chain.lower()).execute()
            
            if result.data:
                return {"success": True, "wallet": result.data[0]}
            else:
                return {"success": False, "error": "Wallet not found"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def remove_wallet(self, telegram_id: str, wallet_name: str, chain: str) -> Dict:
        """Remove a wallet"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            result = self.client.table("wallets").delete().eq("user_id", user["id"]).eq("name", wallet_name).eq("chain", chain.lower()).execute()
            
            if result.data:
                return {"success": True, "message": "Wallet removed successfully"}
            else:
                return {"success": False, "error": "Wallet not found"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def update_wallet_balance(self, wallet_id: str, balance_eth: float, balance_wei: str) -> Dict:
        """Update wallet balance"""
        try:
            result = self.client.table("wallets").update({
                "balance_eth": balance_eth,
                "balance_wei": balance_wei,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", wallet_id).execute()
            
            if result.data:
                return {"success": True, "wallet": result.data[0]}
            else:
                return {"success": False, "error": "Failed to update balance"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Transaction Management
    def add_transaction(self, telegram_id: str, wallet_id: str, tx_data: Dict) -> Dict:
        """Add a new transaction"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            transaction_data = {
                "user_id": user["id"],
                "wallet_id": wallet_id,
                **tx_data
            }
            
            result = self.client.table("transactions").insert(transaction_data).execute()
            
            if result.data:
                return {"success": True, "transaction": result.data[0]}
            else:
                return {"success": False, "error": "Failed to add transaction"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_transactions(self, telegram_id: str, limit: int = 50) -> Dict:
        """Get user's transaction history"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            result = self.client.table("transactions").select("*").eq("user_id", user["id"]).order("created_at", desc=True).limit(limit).execute()
            
            return {"success": True, "transactions": result.data}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Strategy Management
    def add_strategy(self, telegram_id: str, name: str, strategy_type: str, parameters: Dict) -> Dict:
        """Add a new trading strategy"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            strategy_data = {
                "user_id": user["id"],
                "name": name,
                "strategy_type": strategy_type,
                "parameters": parameters
            }
            
            result = self.client.table("strategies").insert(strategy_data).execute()
            
            if result.data:
                return {"success": True, "strategy": result.data[0]}
            else:
                return {"success": False, "error": "Failed to add strategy"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_strategies(self, telegram_id: str) -> Dict:
        """Get user's strategies"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            result = self.client.table("strategies").select("*").eq("user_id", user["id"]).execute()
            
            return {"success": True, "strategies": result.data}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # Portfolio Management
    def update_portfolio(self, telegram_id: str, wallet_id: str, token_data: Dict) -> Dict:
        """Update portfolio with token data"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            portfolio_data = {
                "user_id": user["id"],
                "wallet_id": wallet_id,
                **token_data
            }
            
            # Upsert portfolio data
            result = self.client.table("portfolios").upsert(portfolio_data).execute()
            
            if result.data:
                return {"success": True, "portfolio": result.data[0]}
            else:
                return {"success": False, "error": "Failed to update portfolio"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_user_portfolio(self, telegram_id: str) -> Dict:
        """Get user's portfolio"""
        try:
            user_result = self.get_user(telegram_id)
            if not user_result["success"]:
                return user_result
            
            user = user_result["user"]
            
            result = self.client.table("portfolios").select("*").eq("user_id", user["id"]).execute()
            
            return {"success": True, "portfolio": result.data}
                
        except Exception as e:
            return {"success": False, "error": str(e)} 
