import os
import asyncio
import threading
import http.server
import socketserver
import json
from urllib.parse import parse_qs

try:
    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
except ImportError as e:
    raise ImportError(
        "The 'python-telegram-bot' package is required. Install it with 'pip install python-telegram-bot'."
    ) from e

from supabase_manager import SupabaseManager
from balance_checker import BalanceChecker

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Global application variable
application = None
db_manager = SupabaseManager()
balance_checker = BalanceChecker()

# Simple HTTP server for Render's port requirement with webhook support
class WebhookHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Telegram Bot is running!")
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/webhook':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                update_data = json.loads(post_data.decode('utf-8'))
                # Process the update asynchronously
                asyncio.run(self.process_update(update_data))
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok": true}')
            except Exception as e:
                print(f"Error processing webhook: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    async def process_update(self, update_data):
        global application
        if application:
            update = Update.de_json(update_data, application.bot)
            await application.process_update(update)

def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    with socketserver.TCPServer(("", port), WebhookHTTPRequestHandler) as httpd:
        print(f"Starting HTTP server on port {port}")
        httpd.serve_forever()

# Bot command handlers
async def start(update, context):
    """Welcome message with wallet management options"""
    user_id = str(update.effective_user.id)
    
    # Create or get user in database
    user = update.effective_user
    user_result = db_manager.get_user(user_id)
    
    if not user_result["success"]:
        # Create new user
        create_result = db_manager.create_user(
            telegram_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        if not create_result["success"]:
            await update.message.reply_text("❌ Error creating user account. Please try again.")
            return
    
    welcome_text = """
🤖 **Welcome to EQ Trading Bot!**

**Available Commands:**
🔐 **Wallet Management:**
• `/connect <name> <private_key> <chain>` - Add wallet
• `/wallets` - View your wallets
• `/balance <wallet_name> <chain>` - Check balance
• `/remove <wallet_name> <chain>` - Remove wallet

⚙️ **Settings:**
• `/settings` - View your settings
• `/setchain <chain>` - Set default chain
• `/setslippage <percentage>` - Set max slippage

📊 **Trading (Coming Soon):**
• `/buy <token> <amount>` - Manual buy
• `/sell <token> <amount>` - Manual sell
• `/autostart <strategy>` - Start auto trading

**Supported Chains:** Ethereum, Base, BSC, Polygon

**Example:** `/connect mywallet 1234567890abcdef ethereum`
    """
    
    keyboard = [
        [InlineKeyboardButton("🔐 Connect Wallet", callback_data="connect_wallet")],
        [InlineKeyboardButton("📊 View Wallets", callback_data="view_wallets")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def connect_wallet(update, context):
    """Connect a new wallet"""
    user_id = str(update.effective_user.id)
    
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ **Usage:** `/connect <wallet_name> <private_key> <chain>`\n\n"
            "**Example:** `/connect mywallet 1234567890abcdef ethereum`\n\n"
            "**Supported chains:** ethereum, base, bsc, polygon",
            parse_mode='Markdown'
        )
        return
    
    wallet_name = context.args[0]
    private_key = context.args[1]
    chain = context.args[2].lower()
    
    # Validate chain
    supported_chains = ['ethereum', 'base', 'bsc', 'polygon']
    if chain not in supported_chains:
        await update.message.reply_text(
            f"❌ **Unsupported chain:** {chain}\n\n"
            f"**Supported chains:** {', '.join(supported_chains)}",
            parse_mode='Markdown'
        )
        return
    
    # Add wallet to database
    result = db_manager.add_wallet(user_id, wallet_name, private_key, chain)
    
    if result["success"]:
        await update.message.reply_text(
            f"✅ **Wallet Connected Successfully!**\n\n"
            f"**Name:** {wallet_name}\n"
            f"**Address:** `{result['wallet_address']}`\n"
            f"**Chain:** {chain.capitalize()}\n\n"
            f"Use `/balance {wallet_name} {chain}` to check balance",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ **Failed to connect wallet:** {result['error']}",
            parse_mode='Markdown'
        )

async def list_wallets(update, context):
    """List user's wallets"""
    user_id = str(update.effective_user.id)
    result = db_manager.get_user_wallets(user_id)
    
    if not result["success"]:
        await update.message.reply_text(f"❌ **Error:** {result['error']}", parse_mode='Markdown')
        return
    
    wallets = result["wallets"]
    
    if not wallets:
        await update.message.reply_text(
            "📭 **No wallets connected**\n\n"
            "Use `/connect <name> <private_key> <chain>` to add your first wallet",
            parse_mode='Markdown'
        )
        return
    
    wallet_text = "🔐 **Your Wallets:**\n\n"
    for i, wallet in enumerate(wallets, 1):
        wallet_text += f"{i}. **{wallet['name']}** ({wallet['chain'].capitalize()})\n"
        wallet_text += f"   Address: `{wallet['address']}`\n"
        wallet_text += f"   Added: {wallet['created_at']}\n\n"
    
    wallet_text += "Use `/balance <wallet_name> <chain>` to check balance"
    
    await update.message.reply_text(wallet_text, parse_mode='Markdown')

async def check_balance(update, context):
    """Check wallet balance"""
    user_id = str(update.effective_user.id)
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Usage:** `/balance <wallet_name> <chain>`\n\n"
            "**Example:** `/balance mywallet ethereum`",
            parse_mode='Markdown'
        )
        return
    
    wallet_name = context.args[0]
    chain = context.args[1].lower()
    
    # Get wallet from database
    wallet_result = db_manager.get_wallet(user_id, wallet_name, chain)
    
    if not wallet_result["success"]:
        await update.message.reply_text(f"❌ **Error:** {wallet_result['error']}", parse_mode='Markdown')
        return
    
    wallet = wallet_result["wallet"]
    
    # Get real-time balance from blockchain
    if chain.lower() == "solana":
        balance_result = balance_checker.get_sol_balance(wallet["address"])
        if balance_result["success"]:
            result = {
                "success": True,
                "wallet_address": wallet["address"],
                "balance_eth": balance_result["balance_sol"],
                "balance_wei": str(balance_result["balance_lamports"]),
                "symbol": "SOL"
            }
        else:
            result = {"success": False, "error": balance_result["error"]}
    else:
        balance_result = balance_checker.get_eth_balance(wallet["address"], chain.lower())
        if balance_result["success"]:
            result = {
                "success": True,
                "wallet_address": wallet["address"],
                "balance_eth": balance_result["balance_eth"],
                "balance_wei": balance_result["balance_wei"],
                "symbol": balance_result["symbol"]
            }
        else:
            result = {"success": False, "error": balance_result["error"]}
    
    if result["success"]:
        await update.message.reply_text(
            f"💰 **Balance for {wallet_name}**\n\n"
            f"**Chain:** {chain.capitalize()}\n"
            f"**Address:** `{result['wallet_address']}`\n"
            f"**Balance:** {result['balance_eth']:.6f} {result['symbol']}\n"
            f"**Raw:** {result['balance_wei']} wei",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ **Failed to get balance:** {result['error']}",
            parse_mode='Markdown'
        )

async def remove_wallet(update, context):
    """Remove a wallet"""
    user_id = str(update.effective_user.id)
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Usage:** `/remove <wallet_name> <chain>`\n\n"
            "**Example:** `/remove mywallet ethereum`",
            parse_mode='Markdown'
        )
        return
    
    wallet_name = context.args[0]
    chain = context.args[1].lower()
    
    result = db_manager.remove_wallet(user_id, wallet_name, chain)
    
    if result["success"]:
        await update.message.reply_text(
            f"✅ **Wallet Removed Successfully!**\n\n"
            f"**Name:** {wallet_name}\n"
            f"**Chain:** {chain.capitalize()}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ **Failed to remove wallet:** {result['error']}",
            parse_mode='Markdown'
        )

async def user_settings(update, context):
    """Show user settings"""
    user_id = str(update.effective_user.id)
    user_result = db_manager.get_user(user_id)
    
    if not user_result["success"]:
        await update.message.reply_text(f"❌ **Error:** {user_result['error']}", parse_mode='Markdown')
        return
    
    user = user_result["user"]
    settings = user.get("settings", {})
    
    settings_text = "⚙️ **Your Settings:**\n\n"
    settings_text += f"**Default Chain:** {settings.get('default_chain', 'ethereum').capitalize()}\n"
    settings_text += f"**Max Slippage:** {settings.get('max_slippage', 5.0)}%\n"
    settings_text += f"**Notifications:** {'✅' if settings.get('notifications', True) else '❌'}\n\n"
    settings_text += "Use `/setchain <chain>` or `/setslippage <percentage>` to update"
    
    await update.message.reply_text(settings_text, parse_mode='Markdown')

async def set_default_chain(update, context):
    """Set default chain"""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Usage:** `/setchain <chain>`\n\n"
            "**Supported chains:** ethereum, base, bsc, polygon",
            parse_mode='Markdown'
        )
        return
    
    chain = context.args[0].lower()
    supported_chains = ['ethereum', 'base', 'bsc', 'polygon']
    
    if chain not in supported_chains:
        await update.message.reply_text(
            f"❌ **Unsupported chain:** {chain}\n\n"
            f"**Supported chains:** {', '.join(supported_chains)}",
            parse_mode='Markdown'
        )
        return
    
    # Get current user settings
    user_result = db_manager.get_user(user_id)
    if not user_result["success"]:
        await update.message.reply_text(f"❌ **Error:** {user_result['error']}", parse_mode='Markdown')
        return
    
    user = user_result["user"]
    current_settings = user.get("settings", {})
    current_settings["default_chain"] = chain
    
    result = db_manager.update_user_settings(user_id, current_settings)
    
    if result["success"]:
        await update.message.reply_text(
            f"✅ **Default chain updated to:** {chain.capitalize()}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ **Failed to update settings:** {result['error']}",
            parse_mode='Markdown'
        )

async def help_command(update, context):
    """Show help information"""
    help_text = """
❓ **EQ Trading Bot Help**

**🔐 Wallet Management:**
• `/connect <name> <private_key> <chain>` - Add wallet
• `/wallets` - View your wallets  
• `/balance <wallet_name> <chain>` - Check native balance
• `/token <wallet_name> <chain> <token_address>` - Check token balance
• `/remove <wallet_name> <chain>` - Remove wallet

**⚙️ Settings:**
• `/settings` - View your settings
• `/setchain <chain>` - Set default chain
• `/setslippage <percentage>` - Set max slippage

**📊 Trading (Coming Soon):**
• `/buy <token> <amount>` - Manual buy
• `/sell <token> <amount>` - Manual sell
• `/send <wallet_name> <chain> <to_address> <amount>` - Send transaction
• `/autostart <strategy>` - Start auto trading

**🔗 Supported Chains:**
• Ethereum (ETH)
• Base (ETH)
• BSC (BNB)
• Polygon (MATIC)
• Solana (SOL)

**💡 Tips:**
• Keep your private keys secure
• Start with small amounts for testing
• Use testnet first if available
• Real-time balance checking from blockchain
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def check_token_balance(update, context):
    """Check token balance for a specific wallet"""
    user_id = str(update.effective_user.id)
    
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ **Usage:** `/token <wallet_name> <chain> <token_address>`\n\n"
            "**Example:** `/token mywallet ethereum 0xA0b86a33E6441b8c4C8C1C1C1C1C1C1C1C1C1C1C1`\n\n"
            "**Supported chains:** ethereum, base, bsc, polygon",
            parse_mode='Markdown'
        )
        return
    
    wallet_name = context.args[0]
    chain = context.args[1].lower()
    token_address = context.args[2]
    
    # Get wallet from database
    wallet_result = db_manager.get_wallet(user_id, wallet_name, chain)
    
    if not wallet_result["success"]:
        await update.message.reply_text(f"❌ **Error:** {wallet_result['error']}", parse_mode='Markdown')
        return
    
    wallet = wallet_result["wallet"]
    
    # Get token balance
    token_result = balance_checker.get_token_balance(wallet["address"], token_address, chain)
    
    if token_result["success"]:
        await update.message.reply_text(
            f"🪙 **Token Balance for {wallet_name}**\n\n"
            f"**Token:** {token_result['symbol']}\n"
            f"**Chain:** {chain.capitalize()}\n"
            f"**Address:** `{wallet['address']}`\n"
            f"**Token Address:** `{token_address}`\n"
            f"**Balance:** {token_result['balance']:,.6f} {token_result['symbol']}\n"
            f"**Raw Balance:** {token_result['balance_raw']}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ **Failed to get token balance:** {token_result['error']}",
            parse_mode='Markdown'
        )

async def setup_webhook():
    global application
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable not set")
        return
    
    print(f"Starting bot with token: {TELEGRAM_TOKEN[:10]}...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("connect", connect_wallet))
    application.add_handler(CommandHandler("wallets", list_wallets))
    application.add_handler(CommandHandler("balance", check_balance))
    application.add_handler(CommandHandler("token", check_token_balance))
    application.add_handler(CommandHandler("remove", remove_wallet))
    application.add_handler(CommandHandler("settings", user_settings))
    application.add_handler(CommandHandler("setchain", set_default_chain))
    application.add_handler(CommandHandler("help", help_command))
    
    print("Bot is starting...")
    await application.initialize()
    await application.start()
    
    # Set webhook to the new service URL
    webhook_url = "https://eq-auto-trading-telegram-bot-1.onrender.com/webhook"
    await application.bot.set_webhook(url=webhook_url)
    print(f"Webhook set to: {webhook_url}")

def main():
    # Start bot setup in background thread
    bot_thread = threading.Thread(target=lambda: asyncio.run(setup_webhook()))
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start HTTP server in main thread
    run_http_server()

if __name__ == "__main__":
    main() 
