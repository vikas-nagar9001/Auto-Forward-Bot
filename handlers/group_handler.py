from telethon import events, TelegramClient
from telethon.tl.custom import Button
from telethon.errors import (
    ChatAdminRequiredError, 
    ChatWriteForbiddenError,
    ChannelPrivateError
)
import time
import logging
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

class GroupHandler(BaseHandler):
    """Handler for group management commands"""
    
    def __init__(self, bot, users_collection, groups_collection, user_clients):
        super().__init__(bot, users_collection, groups_collection)
        self.user_clients = user_clients
        self.pending_group_actions = {}
        self.group_validation_cache = {}  # {user_id: {group_id: {"valid": bool, "error": str}}}

    async def register_handlers(self):
        """Register all group-related handlers"""
        self.bot.add_event_handler(
            self.add_group_command,
            events.NewMessage(pattern=r'^/addgroup$')
        )
        self.bot.add_event_handler(
            self.remove_group_command,
            events.NewMessage(pattern=r'^/removegroup$')
        )
        self.bot.add_event_handler(
            self.set_interval_command,
            events.NewMessage(pattern=r'^/setinterval$')
        )
        self.bot.add_event_handler(
            self.my_groups_command,
            events.NewMessage(pattern=r'^/mygroups$')
        )
        self.bot.add_event_handler(
            self.handle_group_input,
            events.NewMessage()
        )
        # Callback handlers
        self.bot.add_event_handler(
            self.group_action_callback,
            events.CallbackQuery(pattern=r'^group_action_')
        )

    async def validate_group_id(self, user_id: int, group_id: int) -> tuple[bool, str]:
        """Validate if a group ID is valid and bot has proper permissions"""
        try:
            client = self.user_clients.get(user_id)
            if not client:
                logger.error(f"No client found for user {user_id}")
                return False, "You are not properly registered. Please /register first."

            # Ensure client is connected
            if not client.is_connected():
                await client.connect()
                
            if not await client.is_user_authorized():
                await client.disconnect()
                logger.error(f"Client authorization failed for user {user_id}")
                # Remove invalid client
                if user_id in self.user_clients:
                    del self.user_clients[user_id]
                return False, "Session expired or invalid. Please use /register to update your session."

            # Try to get group info
            chat = await client.get_entity(group_id)
            
            # Try to send a test message
            test_msg = await client.send_message(
                group_id, 
                "🤖 Checking bot permissions... This message will be deleted."
            )
            await test_msg.delete()

            # Cache the successful validation
            if user_id not in self.group_validation_cache:
                self.group_validation_cache[user_id] = {}
            self.group_validation_cache[user_id][group_id] = {
                "valid": True,
                "error": None,
                "title": getattr(chat, "title", str(group_id))
            }
            
            return True, None

        except ValueError:
            return False, "Invalid group ID format. Please provide a valid group ID."
        except ChatAdminRequiredError:
            return False, "Bot needs admin privileges in this group."
        except ChatWriteForbiddenError:
            return False, "Bot cannot send messages in this group."
        except ChannelPrivateError:
            return False, "This group/channel is private or bot is not a member."
        except Exception as e:
            error_msg = str(e).lower()
            if "auth_key" in error_msg:
                # Remove invalid client
                if user_id in self.user_clients:
                    del self.user_clients[user_id]
                return False, "Session expired. Please use /register to update your session."
            return False, f"Error validating group: {str(e)}"

    async def show_group_validation_progress(self, event, group_id: int):
        """Show interactive validation progress"""
        validation_msg = (
            "🔄 **Validating Group Access**\n\n"
            f"Group ID: `{group_id}`\n\n"
            "Checking:\n"
            "☑️ Group exists\n"
            "☑️ Bot is member\n"
            "☑️ Bot has permissions\n\n"
            "Please wait..."
        )
        await event.edit(validation_msg)

    async def add_group_command(self, event):
        """Enhanced add group command handler with validation"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        # Start group addition process
        self.pending_group_actions[user_id] = {
            "action": "add",
            "step": "group_id"
        }

        instructions = (
            "➕ **Add a New Group**\n\n"
            "Let's add a group step by step:\n\n"
            "1️⃣ First, add this bot to your group as admin\n"
            "2️⃣ Get the group ID:\n"
            "   • Forward a message from the group to @username_to_id_bot, or\n"
            "   • Use the ID from group invite link after 't.me/+' or 'joinchat/'\n\n"
            "3️⃣ Send the group ID here\n\n"
            "*Send the group ID now, or use the buttons below:*"
        )

        keyboard = [
            [Button.inline("❓ How to Get Group ID", data="group_action_help_id")],
            [Button.inline("❌ Cancel", data="group_action_cancel")]
        ]
        await event.reply(instructions, buttons=keyboard)

    async def handle_group_input(self, event):
        """Handle group input with validation"""
        user_id = event.sender_id
        
        # Skip if no pending action or if message starts with a command
        if user_id not in self.pending_group_actions or event.text.startswith('/'):
            return

        action_data = self.pending_group_actions[user_id]
        text = event.text.strip()

        if action_data["action"] == "add":
            if action_data["step"] == "group_id":
                try:
                    group_id = int(text)
                    # Show validation progress
                    progress_msg = await event.reply(
                        "🔄 Validating group access...\n"
                        "Please wait while I check permissions."
                    )

                    # Validate group
                    is_valid, error = await self.validate_group_id(user_id, group_id)
                    
                    if not is_valid:
                        keyboard = [
                            [Button.inline("🔄 Try Again", data="group_action_retry")],
                            [Button.inline("❓ Help", data="group_action_help_id")],
                            [Button.inline("❌ Cancel", data="group_action_cancel")]
                        ]
                        await progress_msg.edit(
                            f"❌ **Validation Failed**\n\n"
                            f"Error: {error}\n\n"
                            "Please try again with a different group ID.",
                            buttons=keyboard
                        )
                        return

                    # Check if group already exists
                    if self.groups_collection.find_one({"user_id": user_id, "group_id": group_id}):
                        keyboard = [
                            [Button.inline("⏱️ Update Interval", data=f"group_action_update_interval_{group_id}")],
                            [Button.inline("🔄 Add Different Group", data="group_action_retry")],
                            [Button.inline("❌ Cancel", data="group_action_cancel")]
                        ]
                        await progress_msg.edit(
                            f"❌ Group {group_id} is already in your list.\n"
                            "What would you like to do?",
                            buttons=keyboard
                        )
                        return

                    # Group is valid, move to interval selection
                    action_data["group_id"] = group_id
                    action_data["step"] = "interval"

                    group_title = self.group_validation_cache[user_id][group_id]["title"]
                    await progress_msg.edit(
                        f"✅ **Group Validated Successfully!**\n\n"
                        f"Group: {group_title}\n"
                        f"ID: `{group_id}`\n\n"
                        "Now, choose the forwarding interval:",
                        buttons=[
                            [
                                Button.inline("30 min", data=f"group_action_set_interval_{group_id}_30"),
                                Button.inline("1 hour", data=f"group_action_set_interval_{group_id}_60")
                            ],
                            [
                                Button.inline("2 hours", data=f"group_action_set_interval_{group_id}_120"),
                                Button.inline("Custom", data=f"group_action_set_interval_{group_id}_custom")
                            ],
                            [Button.inline("« Back", data="group_action_retry")],
                            [Button.inline("❌ Cancel", data="group_action_cancel")]
                        ]
                    )

                except ValueError:
                    keyboard = [
                        [Button.inline("❓ How to Get Group ID", data="group_action_help_id")],
                        [Button.inline("❌ Cancel", data="group_action_cancel")]
                    ]
                    await event.reply(
                        "❌ Invalid group ID format.\n\n"
                        "Example: `-1001234567890`",
                        buttons=keyboard
                    )
                    return

            elif action_data["step"] == "custom_interval":
                try:
                    minutes = int(text)
                    if minutes < 1:
                        raise ValueError("Interval must be at least 1 minute")
                    elif minutes > 1440:
                        raise ValueError("Interval cannot be more than 24 hours (1440 minutes)")
                    
                    group_id = action_data["group_id"]
                    group_title = self.group_validation_cache[user_id][group_id]["title"]

                    # Add group to database
                    self.groups_collection.insert_one({
                        "user_id": user_id,
                        "group_id": group_id,
                        "title": group_title,
                        "interval": minutes * 60,
                        "added_at": time.time()
                    })

                    # Clear all pending data
                    del self.pending_group_actions[user_id]
                    if user_id in self.group_validation_cache:
                        del self.group_validation_cache[user_id]

                    keyboard = [
                        [Button.inline("👥 View All Groups", data="group_action_view")],
                        [Button.inline("➕ Add Another Group", data="group_action_add")],
                        [Button.inline("📤 Start Forwarding", data="forward_new")]
                    ]
                    await event.reply(
                        f"✅ Successfully added group!\n\n"
                        f"Group: {group_title}\n"
                        f"ID: `{group_id}`\n"
                        f"Interval: {minutes} minute(s)\n\n"
                        "What would you like to do next?",
                        buttons=keyboard
                    )
                except ValueError as e:
                    await event.reply(
                        f"❌ {str(e)}\n"
                        "Please enter a valid number between 1 and 1440.",
                        buttons=[[Button.inline("❌ Cancel", data="group_action_cancel")]]
                    )

        elif action_data["action"] == "set_interval":
            try:
                minutes = int(text)
                if minutes < 1:
                    raise ValueError("Interval must be at least 1 minute")
                elif minutes > 1440:
                    raise ValueError("Interval cannot be more than 24 hours (1440 minutes)")

                group_id = action_data["group_id"]
                # Update interval in database
                self.groups_collection.update_one(
                    {"user_id": user_id, "group_id": group_id},
                    {"$set": {"interval": minutes * 60}}
                )

                # Clear pending action
                del self.pending_group_actions[user_id]

                keyboard = [
                    [Button.inline("👥 View All Groups", data="group_action_view")],
                    [Button.inline("⏱️ Update Another", data="group_action_set_interval")]
                ]
                await event.reply(
                    f"✅ Updated interval for group {group_id} to {minutes} minutes!",
                    buttons=keyboard
                )
            except ValueError as e:
                await self.show_error(event, str(e) or "Please enter a valid number between 1 and 1440 minutes")
            except Exception as e:
                await self.show_error(event, f"An error occurred: {str(e)}")

    async def group_action_callback(self, event):
        """Handle group action callbacks"""
        try:
            user_id = event.sender_id
            data = event.data.decode('utf-8').replace('group_action_', '')

            if not await self.check_registered(user_id):
                await self.show_error(event, "You are not registered. Use /register first.")
                return

            if data == "retry":
                # Reset group addition process
                self.pending_group_actions[user_id] = {
                    "action": "add",
                    "step": "group_id"
                }
                
                instructions = (
                     "➕ **Add a New Group**\n\n"
            "Let's add a group step by step:\n\n"
            "1️⃣ First, add this bot to your group as admin\n"
            "2️⃣ Get the group ID:\n"
            "   • Forward a message from the group to @username_to_id_bot, or\n"
            "   • Use the ID from group invite link after 't.me/+' or 'joinchat/'\n\n"
            "3️⃣ Send the group ID here\n\n"
            "*Send the group ID now, or use the buttons below:*"
                )

                keyboard = [
                    [Button.inline("❓ How to Get Group ID", data="group_action_help_id")],
                    [Button.inline("❌ Cancel", data="group_action_cancel")]
                ]
                await event.edit(instructions, buttons=keyboard)
                return

            if data == "view":
                groups = await self.get_user_groups(user_id)
                if not groups:
                    keyboard = [
                        [Button.inline("➕ Add Group", data="group_action_add")],
                        [Button.inline("« Back to Menu", data="account_action_view")]
                    ]
                    await event.edit(
                        "❌ You don't have any groups configured.\n\n"
                        "Add your first group to start forwarding!",
                        buttons=keyboard
                    )
                    return

                # Show group list with actions
                message = "👥 **Your Groups**\n\n"
                keyboard = []
                
                for group in groups:
                    group_id = group['group_id']
                    interval = group['interval'] // 60  # Convert to minutes
                    message += f"• Group {group_id} (every {interval}min)\n"
                    keyboard.append([
                        Button.inline(f"⚙️ Group {group_id}", data=f"group_action_manage_{group_id}")
                    ])

                message += "\nSelect a group to manage, or add a new one:"
                keyboard.extend([
                    [Button.inline("➕ Add Group", data="group_action_add")],
                    [Button.inline("« Back to Menu", data="account_action_view")]
                ])
                
                await event.edit(message, buttons=keyboard)

            elif data == "add":
                # Start group addition process
                self.pending_group_actions[user_id] = {
                    "action": "add",
                    "step": "group_id"
                }

                keyboard = [[Button.inline("❌ Cancel", data="group_action_cancel")]]
                await event.edit(
                   "➕ **Add a New Group**\n\n"
            "Let's add a group step by step:\n\n"
            "1️⃣ First, add this bot to your group as admin\n"
            "2️⃣ Get the group ID:\n"
            "   • Forward a message from the group to @username_to_id_bot, or\n"
            "   • Use the ID from group invite link after 't.me/+' or 'joinchat/'\n\n"
            "3️⃣ Send the group ID here\n\n"
            "*Send the group ID now, or use the buttons below:*",
                    buttons=keyboard
                )

            elif data.startswith("manage_"):
                group_id = int(data.replace("manage_", ""))
                group = await self.get_group(user_id, group_id)
                if not group:
                    await self.show_error(event, "Group not found.")
                    return

                interval = group['interval'] // 60  # Convert to minutes
                keyboard = [
                    [Button.inline("⏱️ Change Interval", data=f"group_action_interval_{group_id}")],
                    [Button.inline("🗑️ Remove Group", data=f"group_action_remove_{group_id}")],
                    [Button.inline("« Back to Groups", data="group_action_view")]
                ]
                
                await event.edit(
                    f"⚙️ **Group {group_id} Settings**\n\n"
                    f"Current interval: {interval} minutes\n\n"
                    "What would you like to do?",
                    buttons=keyboard
                )

            elif data.startswith("interval_"):
                group_id = int(data.replace("interval_", ""))
                keyboard = [
                    [
                        Button.inline("30 min", data=f"group_action_set_interval_{group_id}_30"),
                        Button.inline("1 hour", data=f"group_action_set_interval_{group_id}_60")
                    ],
                    [
                        Button.inline("2 hours", data=f"group_action_set_interval_{group_id}_120"),
                        Button.inline("Custom", data=f"group_action_set_interval_{group_id}_custom")
                    ],
                    [Button.inline("« Back", data=f"group_action_manage_{group_id}")]
                ]
                await event.edit(
                    "⏱️ **Set Message Interval**\n\n"
                    "How often should messages be forwarded to this group?",
                    buttons=keyboard
                )

            elif data.startswith("set_interval_"):
                parts = data.replace("set_interval_", "").split("_")
                if len(parts) == 2:
                    group_id, interval = parts
                elif len(parts) == 3:
                    _, group_id, interval = parts
                else:
                    await self.show_error(event, "Invalid interval data format.")
                    return
                group_id = int(group_id)
                if interval == "custom":
                    # Check if this is an add or update operation
                    is_add = any(pd.get("action") == "add" for pd in [self.pending_group_actions.get(user_id, {})])
                    
                    self.pending_group_actions[user_id] = {
                        "action": "add" if is_add else "set_interval",
                        "step": "custom_interval",
                        "group_id": group_id
                    }
                    keyboard = [[Button.inline("❌ Cancel", data=f"group_action_cancel")]]
                    await event.edit(
                        "📝 Enter the interval in minutes (e.g., 45):\n\n"
                        "• Minimum: 1 minute\n"
                        "• Maximum: 1440 minutes (24 hours)",
                        buttons=keyboard
                    )
                    return
                
                interval = int(interval)
                await self.update_group_interval(event, user_id, group_id, interval)

            elif data.startswith("remove_"):
                group_id = int(data.replace("remove_", ""))
                keyboard = [
                    [Button.inline("⚠️ Yes, Remove", data=f"group_action_confirm_remove_{group_id}")],
                    [Button.inline("❌ No, Keep", data=f"group_action_manage_{group_id}")]
                ]
                await event.edit(
                    f"⚠️ **Remove Group {group_id}**\n\n"
                    "Are you sure you want to remove this group?\n"
                    "All active forwards to this group will be stopped.",
                    buttons=keyboard
                )

            elif data.startswith("confirm_remove_"):
                group_id = int(data.replace("confirm_remove_", ""))
                if await self.remove_group(user_id, group_id):
                    keyboard = [
                        [Button.inline("👥 View Groups", data="group_action_view")],
                        [Button.inline("➕ Add New Group", data="group_action_add")]
                    ]
                    await event.edit(
                        "✅ Group removed successfully!",
                        buttons=keyboard
                    )
                else:
                    await self.show_error(event, "Failed to remove group. Please try again.")

            elif data == "cancel":
                if user_id in self.pending_group_actions:
                    del self.pending_group_actions[user_id]
                keyboard = [
                    [Button.inline("👥 View Groups", data="group_action_view")],
                    [Button.inline("📤 Forward Message", data="forward_new")]
                ]
                await event.edit("❌ Operation cancelled.", buttons=keyboard)

        except Exception as e:
            await self.handle_error(event, e, "An error occurred while processing your request.")

    async def update_group_interval(self, event, user_id: int, group_id: int, minutes: int):
        """Update a group's forwarding interval or add new group"""
        try:
            # Check if group exists
            existing_group = self.groups_collection.find_one({
                "user_id": user_id, 
                "group_id": group_id
            })
            
            if existing_group:
                # Update existing group
                self.groups_collection.update_one(
                    {"user_id": user_id, "group_id": group_id},
                    {"$set": {"interval": minutes * 60}}
                )
            else:
                # Add new group
                group_title = self.group_validation_cache[user_id][group_id]["title"]
                self.groups_collection.insert_one({
                    "user_id": user_id,
                    "group_id": group_id,
                    "title": group_title,
                    "interval": minutes * 60,
                    "added_at": time.time()
                })

            # Clear any pending actions
            if user_id in self.pending_group_actions:
                del self.pending_group_actions[user_id]

            keyboard = [
                [Button.inline("« Back to Settings", data=f"group_action_manage_{group_id}")],
                [Button.inline("👥 View All Groups", data="group_action_view")]
            ]
            
            action = "updated" if existing_group else "added"
            await event.edit(
                f"✅ Successfully {action} group with interval of {minutes} minutes!",
                buttons=keyboard
            )
        except Exception as e:
            await self.handle_error(event, e, "Failed to update interval. Please try again.")

    async def my_groups_command(self, event):
        """Enhanced my groups command handler"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        groups = await self.get_user_groups(user_id)
        if not groups:
            keyboard = [[Button.inline("➕ Add First Group", data="group_action_add")]]
            await event.reply(
                "❌ You don't have any groups configured.",
                buttons=keyboard
            )
            return

        groups_message = "📋 **Your Groups**\n\n"
        keyboard = []

        for group in groups:
            minutes = group['interval'] // 60
            groups_message += f"🔹 **Group {group['group_id']}**\n"
            groups_message += f"   ⏱️ Interval: {minutes} minute(s)\n\n"
            
            keyboard.append([
                Button.inline(f"⚙️ Group {group['group_id']}", data=f"group_action_manage_{group['group_id']}")
            ])

        keyboard.append([Button.inline("➕ Add New Group", data="group_action_add")])
        await event.reply(groups_message, buttons=keyboard)

    async def remove_group_command(self, event):
        """Enhanced remove group command handler"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        groups = await self.get_user_groups(user_id)
        if not groups:
            await self.show_error(event, "You don't have any groups to remove.")
            return

        keyboard = []
        for group in groups:
            keyboard.append([
                Button.inline(f"🗑️ Remove Group {group['group_id']}", 
                            data=f"group_action_remove_{group['group_id']}")
            ])
        keyboard.append([Button.inline("❌ Cancel", data="group_action_cancel")])

        await event.reply(
            "Select a group to remove:",
            buttons=keyboard
        )

    async def set_interval_command(self, event):
        """Enhanced set interval command handler"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        groups = await self.get_user_groups(user_id)
        if not groups:
            await self.show_error(event, "You don't have any groups to update.")
            return

        keyboard = []
        for group in groups:
            minutes = group['interval'] // 60
            keyboard.append([
                Button.inline(
                    f"⏱️ Group {group['group_id']} ({minutes}min)", 
                    data=f"group_action_update_interval_{group['group_id']}"
                )
            ])
        keyboard.append([Button.inline("❌ Cancel", data="group_action_cancel")])

        await event.reply(
            "Select a group to update its interval:",
            buttons=keyboard
        )

    async def get_group(self, user_id: int, group_id: int) -> dict:
        """Get a specific group for a user"""
        return self.groups_collection.find_one({
            "user_id": user_id,
            "group_id": group_id
        })

    async def remove_group(self, user_id: int, group_id: int) -> bool:
        """Remove a group and stop any active forwards to it"""
        try:
            # Check if group exists
            existing_group = self.groups_collection.find_one({
                "user_id": user_id,
                "group_id": group_id
            })
            
            if not existing_group:
                return False

            # Remove group from database
            self.groups_collection.delete_one({
                "user_id": user_id,
                "group_id": group_id
            })

            # Clean up any forwarding tasks for this group
            from .forward_handler import ForwardHandler
            for handler in self.bot.list_event_handlers():
                if isinstance(handler[0].__self__, ForwardHandler):
                    forward_handler = handler[0].__self__
                    # Remove the group from any active forwards
                    if user_id in forward_handler.messages_to_forward:
                        for message in forward_handler.messages_to_forward[user_id]:
                            if str(group_id) in message["target_groups"]:
                                message["target_groups"].remove(str(group_id))

                    # Clean up last forward time tracking
                    if user_id in forward_handler.last_forward_time:
                        if group_id in forward_handler.last_forward_time[user_id]:
                            del forward_handler.last_forward_time[user_id][group_id]
                    break

            return True
        except Exception as e:
            logger.error(f"Error removing group: {e}")
            return False