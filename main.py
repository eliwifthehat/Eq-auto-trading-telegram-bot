import os
import asyncio
import threading
from telegram.ext import Application, CommandHandler
from flask import Flask

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Simple Flask app for Render's port requirement
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is running!"

async def start(update, context):
    await update.message.reply_text("Hello! Your bot is running on Render.")

async def run_bot():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN environment variable not set")
        return
    
    print(f"Starting bot with token: {TELEGRAM_TOKEN[:10]}...")
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    
    print("Bot is starting...")
    await application.initialize()
    await application.start()
    await application.run_polling(allowed_updates=[])

def main():
    # Start bot in background thread
    bot_thread = threading.Thread(target=lambda: asyncio.run(run_bot()))
    bot_thread.daemon = True
    bot_thread.start()
    
    # Start Flask web server (required for Render)
    port = int(os.environ.get('PORT', 10000))
    print(f"Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    main()
