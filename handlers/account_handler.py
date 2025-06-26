from telethon import events, TelegramClient
from telethon.sessions import StringSession
from telethon.tl.custom import Button
import time
import logging
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

class AccountHandler(BaseHandler):
    """Handler for account management commands"""
    
    def __init__(self, bot, users_collection, groups_collection, user_clients, api_id, api_hash):
        super().__init__(bot, users_collection, groups_collection)
        self.user_clients = user_clients
        self.api_id = api_id
        self.api_hash = api_hash
        # Store users who are in the registration process
        self.pending_registrations = set()

    async def initialize_user_clients(self):
        """Initialize user clients from database on bot startup"""
        try:
            all_users = list(self.users_collection.find({}))
            for user in all_users:
                user_id = user['user_id']
                session_string = user['session_string']
                
                # Create and connect client
                client, error = await self.create_user_client(user_id, session_string)
                if client and not error:
                    if not client.is_connected():
                        await client.connect()
                    
                    if await client.is_user_authorized():
                        self.user_clients[user_id] = client
                        logger.info(f"Successfully initialized client for user {user_id}")
                    else:
                        logger.error(f"Client authorization failed for user {user_id}")
                else:
                    logger.error(f"Failed to initialize client for user {user_id}: {error}")
            
            logger.info(f"Initialized {len(self.user_clients)} user clients")
        except Exception as e:
            logger.error(f"Error initializing user clients: {e}")

    async def register_handlers(self):
        """Register all account-related command handlers"""
        # Initialize user clients first
        await self.initialize_user_clients()
        
        # Register handlers
        self.bot.add_event_handler(
            self.register_command,
            events.NewMessage(pattern=r'^/register$')
        )
        self.bot.add_event_handler(
            self.handle_session_string,
            events.NewMessage()
        )
        self.bot.add_event_handler(
            self.unregister_command,
            events.NewMessage(pattern=r'^/unregister$')
        )
        self.bot.add_event_handler(
            self.my_account_command,
            events.NewMessage(pattern=r'^/myaccount$')
        )
        self.bot.add_event_handler(
            self.account_action_callback,
            events.CallbackQuery(pattern=r'^account_action_')
        )

    async def create_user_client(self, user_id: int, session_string: str):
        """Create a Telethon client for a user"""
        try:
            # Basic format validation
            if not session_string or len(session_string.strip()) < 100:
                return None, "Invalid session string format. The string appears too short - please make sure you copied the entire string."
            
            # Check for common invalid characters
            invalid_chars = ['<', '>', '"', "'", ' ']
            if any(char in session_string for char in invalid_chars):
                return None, "The session string contains invalid characters. Please make sure you copied it correctly without any extra spaces or quotes."
            
            # Verify base64-like format (most session strings are base64)
            if not all(c in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_=' for c in session_string):
                return None, "The session string contains invalid characters. Please generate a new one using @SessionStringZBot."
                
            client = TelegramClient(StringSession(session_string), self.api_id, self.api_hash)
            await client.connect()
            
            if not await client.is_user_authorized():
                await client.disconnect()
                return None, "Session is not authorized. Please generate a new session string using @SessionStringZBot."
                
            return client, None
        except ValueError:
            return None, "Invalid session string format. Please make sure you copied the complete string without any extra spaces."
        except Exception as e:
            error_msg = str(e).lower()
            if "encoding" in error_msg or "decode" in error_msg:
                return None, "The session string contains invalid characters. Please generate a new one."
            return None, f"Error validating session string: {str(e)}\nPlease generate a new session string."

    async def register_command(self, event):
        """Enhanced register command handler with step-by-step process"""
        user_id = event.sender_id
        
        # Check if already registered
        if await self.check_registered(user_id):
            keyboard = [
                [Button.inline("🔄 Update Session", data="account_action_update_session")],
                [Button.inline("🗑️ Unregister", data="account_action_unregister")]
            ]
            await event.reply(
                "❌ You are already registered.\n\n"
                "What would you like to do?",
                buttons=keyboard
            )
            return

        # Start registration process
        self.pending_registrations.add(user_id)
        
        instructions = (
            "📝 **Registration Process**\n\n"
            "To register, you'll need a Telegram session string. Here's how to get one:\n\n"
            "1️⃣ Visit [@SessionStringZBot](https://t.me/SessionStringZBot)\n"
            "2️⃣ Start the bot and follow its instructions\n"
            "3️⃣ Copy the generated session string\n"
            "4️⃣ Send the session string here\n\n"
            "⚠️ Keep your session string private! Anyone with your session string can access your account.\n\n"
            "*Send your session string now, or click Cancel to abort.*"
        )
        
        keyboard = [[Button.inline("❌ Cancel Registration", data="account_action_cancel_register")]]
        await event.reply(instructions, buttons=keyboard)

    async def handle_session_string(self, event):
        """Handle session string input during registration"""
        user_id = event.sender_id
        
        # Ignore command messages
        if event.text.startswith('/'):
            return
        
        # Only process messages from users in registration
        if user_id not in self.pending_registrations:
            return
        
        # Remove user from pending registrations
        self.pending_registrations.remove(user_id)
        
        session_string = event.text.strip()
        
        # Basic format validation
        if not session_string or len(session_string) < 100:  # Session strings are typically long
            keyboard = [[Button.inline("🔄 Try Again", data="account_action_retry_register")]]
            await event.reply(
                "❌ Error: The session string appears to be invalid or too short.\n\n"
                "Please make sure you copied the entire session string from @SessionStringZBot.",
                buttons=keyboard
            )
            return

        # Create client to validate session string
        client, error = await self.create_user_client(user_id, session_string)
        if error:
            keyboard = [[Button.inline("🔄 Try Again", data="account_action_retry_register")]]
            error_msg = "❌ Invalid session string. "
            if "base64" in str(error).lower():
                error_msg += "The string appears to be malformed. Please copy the entire session string exactly as provided."
            elif "auth_key" in str(error).lower():
                error_msg += "Authentication failed. Please generate a new session string."
            else:
                error_msg += f"Error: {str(error)}"
            
            await event.reply(
                f"{error_msg}\n\nPlease try again with a valid session string.",
                buttons=keyboard
            )
            return

        # Get user info
        me = await client.get_me()
        username = me.username or "No username"

        # Check if user exists
        existing_user = await self.check_registered(user_id)
        
        if existing_user:
            # Update existing user's session string
            try:
                # Disconnect old client if it exists
                if user_id in self.user_clients:
                    old_client = self.user_clients[user_id]
                    await old_client.disconnect()
                
                # Update user in database
                self.users_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "session_string": session_string,
                            "username": username,
                            "last_updated": time.time()
                        }
                    }
                )
                
                # Update client
                self.user_clients[user_id] = client
                
                keyboard = [
                    [Button.inline("👤 View Account", data="account_action_view")],
                    [Button.inline("📤 Forward Message", data="forward_new")]
                ]
                await event.reply(
                    "✅ Successfully updated your session!\n\n"
                    "Your account has been updated and is ready to use.",
                    buttons=keyboard
                )
                
            except Exception as e:
                await self.handle_error(
                    event,
                    e,
                    "Failed to update your session. Please try again."
                )
                
        else:
            # Register new user
            try:
                # Store user in database
                self.users_collection.insert_one({
                    "user_id": user_id,
                    "session_string": session_string,
                    "username": username,
                    "registered_at": time.time()
                })

                # Store client
                self.user_clients[user_id] = client

                # Ensure client is connected
                if not client.is_connected():
                    await client.connect()
                
                if not await client.is_user_authorized():
                    await client.disconnect()
                    del self.user_clients[user_id]
                    self.users_collection.delete_one({"user_id": user_id})
                    await event.reply(
                        "❌ Error: Session authorization failed. Please generate a new session string and try again.",
                        buttons=[[Button.inline("🔄 Try Again", data="account_action_retry_register")]]
                    )
                    return

                keyboard = [
                    [Button.inline("➕ Add First Group", data="group_action_add")],
                    [Button.inline("👤 View Account", data="account_action_view")]
                ]
                await event.reply(
                    f"✅ Successfully registered as {username}!\n\n"
                    "What would you like to do next?",
                    buttons=keyboard
                )
                
            except Exception as e:
                await self.handle_error(
                    event,
                    e, 
                    "Failed to register. Please try again."
                )

    async def unregister_command(self, event):
        """Enhanced unregister command handler"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered.")
            return

        keyboard = self.create_confirm_buttons(
            "account_action_unregister_confirm",
            "account_action_view"
        )
        await event.reply(
            "⚠️ **Unregister Account**\n\n"
            "Are you sure you want to unregister? This will:\n\n"
            "• Delete all your data\n"
            "• Stop all forwarding tasks\n"
            "• Remove all your configured groups\n\n"
            "This action cannot be undone!",
            buttons=keyboard
        )

    async def my_account_command(self, event):
        """Enhanced my account command handler"""
        user_id = event.sender_id
        user = await self.check_registered(user_id)
        if not user:
            keyboard = [[Button.inline("📝 Register Now", data="register_info")]]
            await event.reply(
                "❌ You are not registered.\n\n"
                "Register first to use the bot!",
                buttons=keyboard
            )
            return

        await self.show_account_details(event, user)

    async def show_account_details(self, event, user):
        """Show account details with active forwards count"""
        groups = await self.get_user_groups(user["user_id"])
        registered_date = await self.format_time_ago(user.get('registered_at', time.time()))
        
        # Get active forwards count from user's messages_to_forward
        active_forwards = 0
        from .forward_handler import ForwardHandler
        for handler in self.bot.list_event_handlers():
            if isinstance(handler[0].__self__, ForwardHandler):
                forward_handler = handler[0].__self__
                user_forwards = forward_handler.messages_to_forward.get(user["user_id"], [])
                active_forwards = len(user_forwards)
                break

        account_info = (
            "👤 **Account Information**\n\n"
            f"Username: `{user.get('username', 'Not set')}`\n"
            f"User ID: `{user['user_id']}`\n"
            f"Registered: {registered_date}\n"
            f"Groups: {len(groups)}\n"
            f"Active Forwards: {active_forwards}\n\n"
            "What would you like to do?"
        )

        keyboard = [
            [
                Button.inline("🔄 Update Session", data="account_action_update_session"),
                Button.inline("👥 Manage Groups", data="group_action_view")
            ],
            [
                Button.inline("📤 Forward Message", data="forward_new"),
                Button.inline("📊 View Status", data="status_main_menu")
            ],
            [Button.inline("🗑️ Unregister", data="account_action_unregister")]
        ]

        await event.edit(account_info, buttons=keyboard)

    async def account_action_callback(self, event):
        """Handle account action callbacks"""
        user_id = event.sender_id
        data = event.data.decode('utf-8').replace('account_action_', '')

        if data == "retry_register":
            # Restart registration process
            await self.register_command(event)
        
        elif data == "cancel_register":
            # Cancel registration process
            if user_id in self.pending_registrations:
                self.pending_registrations.remove(user_id)
            keyboard = [[Button.inline("📝 Register Now", data="account_action_retry_register")]]
            await event.edit(
                "❌ Registration cancelled.\n\n"
                "Use /register when you're ready to try again.",
                buttons=keyboard
            )

        elif data == "view":
            user = await self.check_registered(user_id)
            if user:
                await self.show_account_details(event, user)
            else:
                keyboard = [[Button.inline("📝 Register Now", data="account_action_retry_register")]]
                await event.edit(
                    "❌ Account not found.\n\n"
                    "Would you like to register?",
                    buttons=keyboard
                )

        elif data == "update_session":
            # Start session update process
            self.pending_registrations.add(user_id)
            msg = (
                "🔄 **Update Session**\n\n"
                "Please send your new session string.\n\n"
                "To get a new session string:\n"
                "1️⃣ Visit [@SessionStringZBot](https://t.me/SessionStringZBot)\n"
                "2️⃣ Generate a new session string\n"
                "3️⃣ Send it here\n\n"
                "*Send your new session string now, or click Cancel*"
            )
            keyboard = [[Button.inline("❌ Cancel Update", data="account_action_cancel_update")]]
            await event.edit(msg, buttons=keyboard)

        elif data == "cancel_update":
            if user_id in self.pending_registrations:
                self.pending_registrations.remove(user_id)
            user = await self.check_registered(user_id)
            if user:
                await self.show_account_details(event, user)
            else:
                await event.edit("❌ Update cancelled.")

        elif data == "unregister":
            keyboard = [
                [Button.inline("⚠️ Yes, Unregister", data="account_action_unregister_confirm")],
                [Button.inline("❌ No, Keep Account", data="account_action_view")]
            ]
            await event.edit(
                "⚠️ **Unregister Account**\n\n"
                "Are you sure you want to unregister? This will:\n\n"
                "• Delete all your data\n"
                "• Stop all forwarding tasks\n"
                "• Remove all your configured groups\n\n"
                "This action cannot be undone!",
                buttons=keyboard
            )

        elif data == "unregister_confirm":
            try:
                # Stop and disconnect client
                if user_id in self.user_clients:
                    client = self.user_clients[user_id]
                    await client.disconnect()
                    del self.user_clients[user_id]

                # Remove user data
                self.users_collection.delete_one({"user_id": user_id})
                self.groups_collection.delete_many({"user_id": user_id})

                # Clear registration status if present
                if user_id in self.pending_registrations:
                    self.pending_registrations.remove(user_id)

                keyboard = [[Button.inline("📝 Register Again", data="account_action_retry_register")]]
                await event.edit(
                    "✅ Successfully unregistered.\n\n"
                    "All your data has been removed.",
                    buttons=keyboard
                )
            except Exception as e:
                await self.handle_error(event, e, "Failed to unregister. Please try again.")