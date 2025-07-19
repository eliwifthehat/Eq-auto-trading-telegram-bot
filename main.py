import os
import asyncio
import threading
import http.server
import socketserver
import json
from urllib.parse import parse_qs

try:
    from telegram.ext import Application, CommandHandler
    from telegram import Update
except ImportError as e:
    raise ImportError(
        "The 'python-telegram-bot' package is required. Install it with 'pip install python-telegram-bot'."
    ) from e

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Global application variable
application = None

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

async def start(update, context):
    await update.message.reply_text("Hello! Your bot is running on Render.")

async def setup_webhook():
    global application
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable not set")
        return
    
    print(f"Starting bot with token: {TELEGRAM_TOKEN[:10]}...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    
    print("Bot is starting...")
    await application.initialize()
    await application.start()
    
    # Set webhook
    webhook_url = "https://eliwifthehat-eq-auto-trading-telegram-bot.onrender.com/webhook"
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
