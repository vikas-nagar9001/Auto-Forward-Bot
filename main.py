from flask import Flask
from threading import Thread
import asyncio
import logging
from telethon import TelegramClient
from pymongo import MongoClient

# Import config and handlers
import config
from handlers.account_handler import AccountHandler
from handlers.group_handler import GroupHandler
from handlers.forward_handler import ForwardHandler
from handlers.status_handler import StatusHandler
from handlers.help_handler import HelpHandler
from handlers.keyboard_handler import KeyboardHandler

logger = logging.getLogger(__name__)

# Flask app for keeping the bot alive
app = Flask(__name__)

@app.route('/')
def home():
    return 'Auto Message Forwarder Bot is running!'

# Check configuration
if not config.validate_config():
    exit(1)

# MongoDB setup
try:
    client = MongoClient(config.MONGO_URI)
    db = client[config.DB_NAME]
    users_collection = db[config.USERS_COLLECTION]
    groups_collection = db[config.GROUPS_COLLECTION]
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    exit(1)

# Bot client
bot = TelegramClient('bot', int(config.API_ID), config.API_HASH)

# Dictionary to store user clients
user_clients = {}

async def init_handlers():
    """Initialize all handlers"""
    try:
        # Create handler instances
        forward_handler = ForwardHandler(bot, users_collection, groups_collection, user_clients)
        account_handler = AccountHandler(bot, users_collection, groups_collection, user_clients, int(config.API_ID), config.API_HASH)
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
        
        # Initialize user clients first (required for forwarding)
        await account_handler.initialize_user_clients()
        
        # Set account handler reference in forward handler for debugging
        forward_handler.set_account_handler(account_handler)
        
        # Initialize any active forwards from database after user clients are ready
        await forward_handler.initialize_active_forwards()
        
        logger.info("All handlers registered successfully")
        
        # Return account_handler for cleanup later
        return account_handler
    except Exception as e:
        logger.error(f"Error initializing handlers: {e}")
        raise

async def bot_main():
    """Main function for the bot"""
    try:
        # Start the bot
        await bot.start(bot_token=config.BOT_TOKEN)
        logger.info("Bot started successfully")

        # Create indexes for better performance
        users_collection.create_index("user_id", unique=True)
        groups_collection.create_index(["user_id", "group_id"], unique=True)
        
        # Initialize handlers
        account_handler = await init_handlers()
        
        # Send startup notification to admin if configured
        if config.ADMIN_ID:
            try:
                await bot.send_message(
                    int(config.ADMIN_ID),
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
    finally:
        # Cleanup user clients on shutdown
        await cleanup_clients(account_handler)

async def cleanup_clients(account_handler):
    """Clean up all user clients to prevent asyncio warnings"""
    try:
        if account_handler:
            await account_handler.cleanup_user_clients()
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def run_flask():
    """Run the Flask app in a separate thread"""
    app.run(host=config.HOST, port=config.PORT)

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
