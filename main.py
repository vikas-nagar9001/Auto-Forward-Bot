from flask import Flask
from threading import Thread
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, AuthKeyDuplicatedError
import asyncio
import os
import time
import pymongo
from pymongo import MongoClient
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
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

# Constants
DELAY_BETWEEN_FORWARDS = 3  # seconds
DEFAULT_INTERVAL = 60  # 1 minute default interval

# Bot client
bot = TelegramClient('bot', int(API_ID), API_HASH)

# Dictionary to store user clients
user_clients = {}

# Dictionary to store forwarding tasks per user
forwarding_tasks = {}

# Dictionary to store messages to forward per user
messages_to_forward = {}

# Dictionary to track when each group was last forwarded to per user
last_forward_time = {}

# Helper functions
async def create_user_client(user_id, session_string):
    """Create a Telethon client for a user"""
    try:
        client = TelegramClient(StringSession(session_string), int(API_ID), API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None, "Session is not authorized. Please provide a valid session string."
        return client, None
    except Exception as e:
        logger.error(f"Error creating client for user {user_id}: {e}")
        return None, f"Error: {str(e)}"

async def get_user_client(user_id):
    """Get or create a client for a user"""
    if user_id in user_clients and user_clients[user_id].is_connected():
        return user_clients[user_id], None
    
    # Get user from database
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        return None, "You are not registered. Please register using /register <session_string>"
    
    # Create client
    client, error = await create_user_client(user_id, user["session_string"])
    if error:
        return None, error
    
    user_clients[user_id] = client
    return client, None

async def get_user_groups(user_id):
    """Get groups for a user"""
    groups = groups_collection.find({"user_id": user_id})
    return {group["group_id"]: {"interval": group["interval"]} for group in groups}

async def forward_to_group(user_id, group_id):
    """Forward message to a group"""
    try:
        if user_id not in messages_to_forward or not messages_to_forward[user_id]:
            return
        
        client, error = await get_user_client(user_id)
        if error:
            logger.error(f"Error getting client for user {user_id}: {error}")
            return
        
        groups = await get_user_groups(user_id)
        if group_id not in groups:
            logger.error(f"Group {group_id} not found for user {user_id}")
            return
        
        interval = groups[group_id]["interval"]
        
        while user_id in messages_to_forward and messages_to_forward[user_id]:
            try:
                await client.send_message(group_id, messages_to_forward[user_id])
                if user_id not in last_forward_time:
                    last_forward_time[user_id] = {}
                last_forward_time[user_id][group_id] = time.time()
            except Exception as e:
                logger.error(f"Failed to send message to group {group_id} for user {user_id}: {e}")
            
            # Wait for this group's specific interval
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        # Handle task cancellation gracefully
        pass

async def schedule_forward_message(user_id):
    """Schedule forwarding messages for a user"""
    try:
        groups = await get_user_groups(user_id)
        
        # Initialize the last forward time for each group
        if user_id not in last_forward_time:
            last_forward_time[user_id] = {}
        
        for group_id in groups:
            last_forward_time[user_id][group_id] = 0
        
        # Start a separate task for each group
        if user_id not in forwarding_tasks:
            forwarding_tasks[user_id] = {}
        
        for group_id in groups:
            if group_id not in forwarding_tasks[user_id] or forwarding_tasks[user_id][group_id].done():
                forwarding_tasks[user_id][group_id] = asyncio.create_task(forward_to_group(user_id, group_id))
                # Add a small delay between starting tasks to avoid rate limits
                await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Error scheduling forward for user {user_id}: {e}")

# Bot commands
@bot.on(events.NewMessage(pattern=r'^/start$'))
async def start_command(event):
    """Start command handler"""
    welcome_message = (
        "👋 Welcome to Auto Message Forwarder Bot!\n\n"
        "This bot allows you to automatically forward messages to multiple groups at specified intervals.\n\n"
        "To get started:\n"
        "1. Register your Telegram account using /register <session_string>\n"
        "2. Add groups using /addgroup <group_id> <interval_minutes>\n"
        "3. Reply to a message with /fwd to start forwarding\n\n"
        "Use /help to see all available commands."
    )
    await event.reply(welcome_message)

@bot.on(events.NewMessage(pattern=r'^/help$'))
async def help_command(event):
    """Help command handler"""
    help_message = (
        "📋 Available Commands:\n\n"
        "/start - Welcome message and bot information\n"
        "/help - Show this help message\n"
        "/register <session_string> - Register your Telegram account\n"
        "/addgroup <group_id> <interval_minutes> - Add a group to forward messages to\n"
        "/removegroup <group_id> - Remove a group\n"
        "/setinterval <minutes> <group_id> - Set forwarding interval for a group\n"
        "/fwd <optional_interval_minutes> - Forward a message (reply to a message)\n"
        "/stopfwd - Stop forwarding messages\n"
        "/status - Check forwarding status\n"
        "/mygroups - List your configured groups\n"
        "/myaccount - View your account information\n"
        "/unregister - Unregister your account"
    )
    await event.reply(help_message)

@bot.on(events.NewMessage(pattern=r'^/register (.+)$'))
async def register_command(event):
    """Register command handler"""
    user_id = event.sender_id
    session_string = event.pattern_match.group(1)
    
    # Check if user is already registered
    existing_user = users_collection.find_one({"user_id": user_id})
    if existing_user:
        await event.reply("❌ You are already registered. Use /unregister first if you want to register again.")
        return
    
    # Create client to validate session string
    client, error = await create_user_client(user_id, session_string)
    if error:
        await event.reply(f"❌ {error}")
        return
    
    # Get user info
    me = await client.get_me()
    username = me.username or "No username"
    
    # Store user in database
    users_collection.insert_one({
        "user_id": user_id,
        "session_string": session_string,
        "username": username,
        "registered_at": time.time()
    })
    
    # Store client
    user_clients[user_id] = client
    
    await event.reply(f"✅ Successfully registered as {username}. You can now add groups using /addgroup.")

@bot.on(events.NewMessage(pattern=r'^/unregister$'))
async def unregister_command(event):
    """Unregister command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    existing_user = users_collection.find_one({"user_id": user_id})
    if not existing_user:
        await event.reply("❌ You are not registered.")
        return
    
    # Stop any active forwarding tasks
    if user_id in forwarding_tasks:
        for group_id, task in forwarding_tasks[user_id].items():
            if task and not task.done():
                task.cancel()
        del forwarding_tasks[user_id]
    
    if user_id in messages_to_forward:
        del messages_to_forward[user_id]
    
    # Disconnect client
    if user_id in user_clients:
        await user_clients[user_id].disconnect()
        del user_clients[user_id]
    
    # Remove user from database
    users_collection.delete_one({"user_id": user_id})
    groups_collection.delete_many({"user_id": user_id})
    
    await event.reply("✅ Successfully unregistered. All your data has been removed.")

@bot.on(events.NewMessage(pattern=r'^/addgroup (-?\d+) (\d+)$'))
async def add_group_command(event):
    """Add group command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    client, error = await get_user_client(user_id)
    if error:
        await event.reply(f"❌ {error}")
        return
    
    try:
        group_id, minutes = event.pattern_match.groups()
        group_id = int(group_id)
        minutes = int(minutes)
        
        # Check if group already exists
        existing_group = groups_collection.find_one({"user_id": user_id, "group_id": group_id})
        if existing_group:
            await event.reply(f"❌ Group {group_id} is already in your list. Use /setinterval to change the interval.")
            return
        
        # Add group to database
        groups_collection.insert_one({
            "user_id": user_id,
            "group_id": group_id,
            "interval": minutes * 60,  # Convert to seconds
            "added_at": time.time()
        })
        
        await event.reply(f"✅ Added group {group_id} with forwarding interval of {minutes} minute(s).")
    except ValueError:
        await event.reply("❌ Invalid format. Use /addgroup <group_id> <minutes>")

@bot.on(events.NewMessage(pattern=r'^/removegroup (-?\d+)$'))
async def remove_group_command(event):
    """Remove group command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    client, error = await get_user_client(user_id)
    if error:
        await event.reply(f"❌ {error}")
        return
    
    try:
        group_id = int(event.pattern_match.group(1))
        
        # Check if group exists
        existing_group = groups_collection.find_one({"user_id": user_id, "group_id": group_id})
        if not existing_group:
            await event.reply(f"❌ Group {group_id} not found in your list.")
            return
        
        # Remove group from database
        groups_collection.delete_one({"user_id": user_id, "group_id": group_id})
        
        # Cancel any active task for this group
        if user_id in forwarding_tasks and group_id in forwarding_tasks[user_id]:
            if not forwarding_tasks[user_id][group_id].done():
                forwarding_tasks[user_id][group_id].cancel()
            del forwarding_tasks[user_id][group_id]
        
        await event.reply(f"✅ Removed group {group_id} from your forwarding list.")
    except ValueError:
        await event.reply("❌ Invalid format. Use /removegroup <group_id>")

@bot.on(events.NewMessage(pattern=r'^/setinterval (\d+) (-?\d+)$'))
async def set_interval_command(event):
    """Set interval command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    client, error = await get_user_client(user_id)
    if error:
        await event.reply(f"❌ {error}")
        return
    
    try:
        minutes, group_id = event.pattern_match.groups()
        minutes = int(minutes)
        group_id = int(group_id)
        
        # Check if group exists
        existing_group = groups_collection.find_one({"user_id": user_id, "group_id": group_id})
        if not existing_group:
            await event.reply(f"❌ Group {group_id} not found in your list. Add it first using /addgroup.")
            return
        
        # Update interval in database
        groups_collection.update_one(
            {"user_id": user_id, "group_id": group_id},
            {"$set": {"interval": minutes * 60}}  # Convert to seconds
        )
        
        await event.reply(f"✅ Interval for group {group_id} set to {minutes} minute(s).")
    except ValueError:
        await event.reply("❌ Invalid format. Use /setinterval <minutes> <group_id>")

@bot.on(events.NewMessage(pattern=r'^/fwd(?: (\d+))?$'))
async def fwd_command(event):
    """Forward command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    client, error = await get_user_client(user_id)
    if error:
        await event.reply(f"❌ {error}")
        return
    
    interval = event.pattern_match.group(1)
    
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg.text:
            messages_to_forward[user_id] = reply_msg.text
            
            try:
                # Set the same interval for all groups if specified
                if interval:
                    interval_seconds = int(interval) * 60
                    groups = await get_user_groups(user_id)
                    if not groups:
                        await event.reply("❌ You don't have any groups configured. Add groups using /addgroup.")
                        return
                    
                    for group_id in groups:
                        groups_collection.update_one(
                            {"user_id": user_id, "group_id": group_id},
                            {"$set": {"interval": interval_seconds}}
                        )
                    
                    await event.reply(f"✅ Message scheduled to be forwarded every {interval} minute(s) to all your groups.")
                else:
                    await event.reply(f"✅ Message scheduled to be forwarded using each group's configured interval.")
            except ValueError:
                await event.reply("❌ Invalid interval. Please use a number (e.g., /fwd 2).")
                return
            
            # Cancel any existing forwarding tasks
            if user_id in forwarding_tasks:
                for group_id, task in forwarding_tasks[user_id].items():
                    if task and not task.done():
                        task.cancel()
            
            # Create a new forwarding task
            asyncio.create_task(schedule_forward_message(user_id))
        else:
            await event.reply("❌ Replied message has no text.")
    else:
        await event.reply("❌ Please reply to the message you want to forward using /fwd <interval>.")

@bot.on(events.NewMessage(pattern=r'^/stopfwd$'))
async def stop_fwd_command(event):
    """Stop forwarding command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    client, error = await get_user_client(user_id)
    if error:
        await event.reply(f"❌ {error}")
        return
    
    if user_id in messages_to_forward:
        del messages_to_forward[user_id]
    
    # Cancel all forwarding tasks
    if user_id in forwarding_tasks:
        for group_id, task in forwarding_tasks[user_id].items():
            if task and not task.done():
                task.cancel()
        
        forwarding_tasks[user_id] = {}
        await event.reply("🛑 Forwarding stopped for all your groups.")
    else:
        await event.reply("❌ You don't have any active forwarding tasks.")

@bot.on(events.NewMessage(pattern=r'^/status$'))
async def status_command(event):
    """Status command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    client, error = await get_user_client(user_id)
    if error:
        await event.reply(f"❌ {error}")
        return
    
    if user_id in messages_to_forward and messages_to_forward[user_id]:
        groups = await get_user_groups(user_id)
        if not groups:
            await event.reply("❌ You don't have any groups configured. Add groups using /addgroup.")
            return
        
        status_message = "✅ Currently forwarding to groups with these intervals:\n"
        for group_id, settings in groups.items():
            minutes = settings['interval'] // 60
            status_message += f"- Group {group_id}: every {minutes} minute(s)\n"
        
        await event.reply(status_message)
    else:
        await event.reply("❌ No message is currently being forwarded.")

@bot.on(events.NewMessage(pattern=r'^/mygroups$'))
async def my_groups_command(event):
    """My groups command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    client, error = await get_user_client(user_id)
    if error:
        await event.reply(f"❌ {error}")
        return
    
    groups = list(groups_collection.find({"user_id": user_id}))
    
    if not groups:
        await event.reply("❌ You don't have any groups configured. Add groups using /addgroup.")
        return
    
    groups_message = "📋 Your configured groups:\n\n"
    for group in groups:
        minutes = group['interval'] // 60
        groups_message += f"- Group ID: {group['group_id']}\n  Interval: {minutes} minute(s)\n\n"
    
    await event.reply(groups_message)

@bot.on(events.NewMessage(pattern=r'^/myaccount$'))
async def my_account_command(event):
    """My account command handler"""
    user_id = event.sender_id
    
    # Check if user is registered
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        await event.reply("❌ You are not registered. Please register using /register <session_string>")
        return
    
    # Get group count
    group_count = groups_collection.count_documents({"user_id": user_id})
    
    account_message = (
        "📋 Your Account Information:\n\n"
        f"User ID: {user['user_id']}\n"
        f"Username: {user['username']}\n"
        f"Registered: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(user['registered_at']))}\n"
        f"Configured Groups: {group_count}"
    )
    
    await event.reply(account_message)

async def bot_main():
    """Main function for the bot"""
    # Start the bot here instead of at module level
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot started.")
    
    # Create indexes for better performance
    users_collection.create_index("user_id", unique=True)
    groups_collection.create_index(["user_id", "group_id"], unique=True)
    
    await bot.run_until_disconnected()

def run_flask():
    """Run the Flask app in a separate thread"""
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True  # This ensures the thread will exit when the main program exits
    flask_thread.start()
    
    # Run the bot in the main thread with its own event loop
    asyncio.run(bot_main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
