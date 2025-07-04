import os
import asyncio
from telegram.ext import Application, CommandHandler

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update, context):
    await update.message.reply_text("Hello! Your bot is running on Render.")

async def main():
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

if __name__ == "__main__":
    asyncio.run(main()) 