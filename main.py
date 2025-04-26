from flask import Flask
from threading import Thread
import asyncio
import os
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
from pymongo import MongoClient

# Import handlers
from handlers.account_handler import AccountHandler
from handlers.group_handler import GroupHandler
from handlers.forward_handler import ForwardHandler
from handlers.status_handler import StatusHandler
from handlers.help_handler import HelpHandler
from handlers.keyboard_handler import KeyboardHandler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for keeping the bot alive
app = Flask(__name__)

@app.route('/')
def home():
    return 'Auto Message Forwarder Bot is running!'

# Environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

# Check if environment variables are set
if not all([API_ID, API_HASH, BOT_TOKEN, MONGO_URI]):
    logger.error("Environment variables not set. Please set API_ID, API_HASH, BOT_TOKEN, and MONGO_URI.")
    exit(1)

# MongoDB setup
try:
    client = MongoClient(MONGO_URI)
    db = client['auto_forward_bot']
    users_collection = db['users']
    groups_collection = db['groups']
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    exit(1)

# Bot client
bot = TelegramClient('bot', int(API_ID), API_HASH)

# Dictionary to store user clients
user_clients = {}

async def init_handlers():
    """Initialize all handlers"""
    try:
        # Create handler instances
        forward_handler = ForwardHandler(bot, users_collection, groups_collection, user_clients)
        account_handler = AccountHandler(bot, users_collection, groups_collection, user_clients, int(API_ID), API_HASH)
        group_handler = GroupHandler(bot, users_collection, groups_collection, user_clients)
        status_handler = StatusHandler(bot, users_collection, groups_collection, forward_handler)
        help_handler = HelpHandler(bot, users_collection, groups_collection)
        keyboard_handler = KeyboardHandler(bot, users_collection, groups_collection)
        
        # Register all handlers
        handlers = [
            account_handler,
            group_handler,
            forward_handler,
            status_handler,
            help_handler,
            keyboard_handler
        ]
        
        for handler in handlers:
            await handler.register_handlers()
            logger.info(f"Registered handler: {handler.__class__.__name__}")
        
        # Initialize any active forwards from database
        await forward_handler.initialize_active_forwards()
        
        logger.info("All handlers registered successfully")
    except Exception as e:
        logger.error(f"Error initializing handlers: {e}")
        raise

async def bot_main():
    """Main function for the bot"""
    try:
        # Start the bot
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("Bot started successfully")

        # Create indexes for better performance
        users_collection.create_index("user_id", unique=True)
        groups_collection.create_index(["user_id", "group_id"], unique=True)
        
        # Initialize handlers
        await init_handlers()
        
        # Send startup notification to admin if configured
        admin_id = os.getenv('ADMIN_ID')
        if admin_id:
            try:
                await bot.send_message(
                    int(admin_id),
                    "✅ Bot has started successfully!\n\n"
                    "System Info:\n"
                    f"• MongoDB Connected: ✅\n"
                    f"• Handlers Initialized: ✅\n"
                    f"• Web Server: Running\n\n"
                    "Ready to process commands."
                )
            except Exception as e:
                logger.error(f"Failed to send admin notification: {e}")
        
        # Keep the bot running
        await bot.run_until_disconnected()
    except Exception as e:
        logger.error(f"Error in bot_main: {e}")
        raise

def run_flask():
    """Run the Flask app in a separate thread"""
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def main():
    """Main entry point"""
    try:
        # Start Flask in a separate thread
        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        logger.info("Flask server started")

        # Run the bot in the main thread
        asyncio.run(bot_main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()
