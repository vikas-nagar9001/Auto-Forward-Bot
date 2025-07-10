from telethon import events
from telethon.tl.custom import Button
import asyncio
import time
import logging
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

class ForwardHandler(BaseHandler):
    """Handler for message forwarding functionality"""
    
    def __init__(self, bot, users_collection, groups_collection, user_clients):
        super().__init__(bot, users_collection, groups_collection)
        self.user_clients = user_clients
        self.messages_to_forward = {}
        self.forwarding_tasks = {}
        self.last_forward_time = {}
        self.pending_forwards = {}  # {user_id: {"message": str, "step": str, "selected_groups": []}}

    async def register_handlers(self):
        """Register all forwarding-related handlers"""
        self.bot.add_event_handler(
            self.forward_command,
            events.NewMessage(pattern=r'^/fwd$')
        )
        self.bot.add_event_handler(
            self.stop_forward_command,
            events.NewMessage(pattern=r'^/stopfwd$')
        )
        self.bot.add_event_handler(
            self.handle_interval_input,
            events.NewMessage()
        )
        self.bot.add_event_handler(
            self.forward_callback,
            events.CallbackQuery(pattern=r'^forward_')
        )

    async def initialize_active_forwards(self):
        """Initialize active forwards from database when bot starts"""
        try:
            # Find all users in the database
            users = self.users_collection.find({})
            
            for user in users:
                user_id = user['user_id']
                
                # Skip if user client not available
                if user_id not in self.user_clients:
                    continue
                
                # Get user's active forwards from database
                # You may want to add a new collection for storing active forwards
                active_forwards = self.users_collection.find_one(
                    {"user_id": user_id},
                    {"active_forwards": 1}
                ).get('active_forwards', [])

                if not active_forwards:
                    continue

                # Initialize message forwarding for each active forward
                self.messages_to_forward[user_id] = []
                
                for forward in active_forwards:
                    self.messages_to_forward[user_id].append({
                        "message": forward['message'],
                        "target_groups": forward['target_groups'],
                        "message_id": forward['message_id']
                    })

                # Start forwarding tasks
                asyncio.create_task(self.schedule_forwards(user_id))
                logger.info(f"Initialized {len(active_forwards)} forwards for user {user_id}")

            logger.info("Successfully initialized all active forwards")
            
        except Exception as e:
            logger.error(f"Error initializing active forwards: {e}")
            # Don't raise the exception as this is not critical
            # The bot can still function without restoring previous forwards

    async def forward_command(self, event):
        """Enhanced forward command handler with step-by-step process"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        if not event.is_reply:
            keyboard = [
                [Button.inline("📋 How to Forward", data="help_category_forward")],
                [Button.inline("👥 View My Groups", data="group_action_view")]
            ]
            await event.reply(
                "❌ Please reply to a message you want to forward.\n\n"
                "**Steps to forward:**\n"
                "1️⃣ Find the message to forward\n"
                "2️⃣ Reply to it with /fwd\n"
                "3️⃣ Select target groups\n"
                "4️⃣ Choose forwarding interval",
                buttons=keyboard
            )
            return

        reply_msg = await event.get_reply_message()
        if not reply_msg.text:
            await self.show_error(event, "Only text messages can be forwarded.")
            return

        # Get user's groups
        groups = await self.get_user_groups(user_id)
        if not groups:
            keyboard = [[Button.inline("➕ Add First Group", data="group_action_add")]]
            await event.reply(
                "❌ You don't have any groups configured.\n"
                "Add groups first using /addgroup",
                buttons=keyboard
            )
            return

        # Start forwarding process
        self.pending_forwards[user_id] = {
            "message": reply_msg.text,
            "step": "group_selection",
            "selected_groups": [],
            "message_id": f"{int(time.time())}_{hash(reply_msg.text) % 10000}"
        }

        await self.show_group_selection(event, user_id, groups, is_initial=True)

    async def show_group_selection(self, event, user_id, groups, is_initial=False):
        """Show enhanced group selection UI"""
        message = (
            "📤 **Forward Message**\n\n"
            "Message preview:\n"
            f"`{self.get_message_preview(self.pending_forwards[user_id]['message'])}`\n\n"
            "Select groups to forward to:"
        )

        keyboard = []
        selected_groups = self.pending_forwards[user_id]['selected_groups']
        
        for group in groups:
            group_title = group.get('title', f"Group {group['group_id']}")
            selected = "☑" if str(group['group_id']) in selected_groups else "☐"
            keyboard.append([
                Button.inline(
                    f"{selected} {group_title}",
                    data=f"forward_toggle_{group['group_id']}"
                )
            ])

        # Check if all groups are selected
        all_selected = len(selected_groups) == len(groups) and len(groups) > 0
        select_button_text = "❌ Unselect All" if all_selected else "✅ Select All"
        select_button_data = "forward_unselect_all" if all_selected else "forward_select_all"

        keyboard.extend([
            [Button.inline(select_button_text, data=select_button_data)],
            [
                Button.inline("✅ Next", data="forward_set_interval"),
                Button.inline("❌ Cancel", data="forward_cancel")
            ]
        ])

        # Use reply for initial call, edit for subsequent calls
        if is_initial:
            await event.reply(message, buttons=keyboard)
        else:
            try:
                await event.edit(message, buttons=keyboard)
            except Exception as e:
                # If edit fails (e.g., message too old), send a new message
                await event.reply(message, buttons=keyboard)

    async def handle_interval_input(self, event):
        """Handle custom interval input"""
        user_id = event.sender_id
        if user_id not in self.pending_forwards or self.pending_forwards[user_id]["step"] != "custom_interval":
            return

        try:
            minutes = int(event.text.strip())
            if minutes < 1:
                raise ValueError("Interval must be at least 1 minute")
            elif minutes > 1440:
                raise ValueError("Interval cannot be more than 24 hours (1440 minutes)")
            
            forward_data = self.pending_forwards[user_id]
            # Update intervals for selected groups
            for group_id in forward_data["selected_groups"]:
                self.groups_collection.update_one(
                    {"user_id": user_id, "group_id": int(group_id)},
                    {"$set": {"interval": minutes * 60}}
                )

            # Start forwarding
            keyboard = [
                [Button.inline("📊 View Status", data="forward_status")],
                [Button.inline("📤 Forward Another", data="forward_new")]
            ]
            success_msg = (
                f"✅ Message scheduled for forwarding every {minutes} minutes!\n"
                "Use /status to monitor forwarding progress."
            )

            try:
                await event.delete()  # Delete the user's message with interval
                await event.respond(success_msg, buttons=keyboard)
            except Exception as e:
                if "MessageIdInvalidError" in str(e):
                    await event.reply(success_msg, buttons=keyboard)

            # Initialize forwarding
            await self.start_forwarding(user_id, forward_data, minutes)

        except ValueError as e:
            error_msg = str(e) or "Please send a valid number of minutes (minimum 1)"
            await self.show_error(event, error_msg)

    def get_message_preview(self, message: str, length: int = 30) -> str:
        """Get a preview of a message"""
        return message[:length] + "..." if len(message) > length else message

    async def forward_callback(self, event):
        """Handle forward-related callbacks"""
        user_id = event.sender_id
        data = event.data.decode('utf-8').replace('forward_', '')

        # Validate user registration first
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        # Handle stop commands separately since they don't need pending_forwards
        if data.startswith("stop_"):
            if user_id not in self.messages_to_forward or not self.messages_to_forward[user_id]:
                await self.show_error(event, "No active forwarding tasks.")
                return
                
            index = data.replace("stop_", "")
            if index == "all":
                # Stop all forwards
                self.messages_to_forward[user_id] = []
                keyboard = [[Button.inline("📤 New Forward", data="forward_new")]]
                await event.edit("✅ Stopped all forwards.", buttons=keyboard)
            else:
                # Stop specific forward
                try:
                    idx = int(index)
                    if 0 <= idx < len(self.messages_to_forward[user_id]):
                        del self.messages_to_forward[user_id][idx]
                        keyboard = [[Button.inline("📤 New Forward", data="forward_new")]]
                        await event.edit("✅ Forward stopped successfully.", buttons=keyboard)
                except (ValueError, IndexError):
                    await self.show_error(event, "Invalid forward index.")
            return

        # Handle callbacks when no pending forward
        if data == "new":
            keyboard = [
                [Button.inline("📋 How to Forward", data="help_category_forward")],
                [Button.inline("👥 View My Groups", data="group_action_view")]
            ]
            await event.edit(
                "**Steps to forward:**\n"
                "1️⃣ Find the message to forward\n"
                "2️⃣ Reply to it with /fwd\n"
                "3️⃣ Select target groups\n"
                "4️⃣ Choose forwarding interval",
                buttons=keyboard
            )
            return

        if data == "status":
            # Show status menu
            keyboard = [
                [Button.inline("📋 View Messages", data="status_view_messages")],
                [Button.inline("⏱️ View Schedules", data="status_view_schedules")],
                [Button.inline("📊 View Stats", data="status_view_stats")],
                [Button.inline("« Back", data="forward_new")]
            ]
            await event.edit(
                "📊 **Forwarding Status**\n\n"
                "Choose what to view:",
                buttons=keyboard
            )
            return

        # All other actions require pending forwards
        if user_id not in self.pending_forwards:
            await self.show_error(event, "No active forwarding setup.")
            return

        forward_data = self.pending_forwards[user_id]

        if data.startswith("toggle_"):
            group_id = data.replace("toggle_", "")
            if group_id in forward_data["selected_groups"]:
                forward_data["selected_groups"].remove(group_id)
            else:
                forward_data["selected_groups"].append(group_id)
            groups = await self.get_user_groups(user_id)
            await self.show_group_selection(event, user_id, groups)

        elif data == "select_all":
            groups = await self.get_user_groups(user_id)
            forward_data["selected_groups"] = [str(g["group_id"]) for g in groups]
            await self.show_group_selection(event, user_id, groups)

        elif data == "unselect_all":
            groups = await self.get_user_groups(user_id)
            forward_data["selected_groups"] = []
            await self.show_group_selection(event, user_id, groups)

        elif data == "set_interval":
            if not forward_data["selected_groups"]:
                await self.show_error(event, "Please select at least one group first.")
                return

            forward_data["step"] = "interval"
            keyboard = [
                [
                    Button.inline("30 min", data="forward_interval_30"),
                    Button.inline("1 hour", data="forward_interval_60")
                ],
                [
                    Button.inline("2 hours", data="forward_interval_120"),
                    Button.inline("Custom", data="forward_interval_custom")
                ],
                [Button.inline("« Back", data="forward_back_to_groups")]
            ]
            await event.edit(
                "⏱️ **Set Forwarding Interval**\n\n"
                "Choose how often to forward the message:",
                buttons=keyboard
            )

        elif data.startswith("interval_"):
            interval = data.replace("interval_", "")
            if interval == "custom":
                forward_data["step"] = "custom_interval"
                await event.edit(
                    "📝 Enter the interval in minutes (e.g., 45):\n\n"
                    "• Minimum: 1 minute\n"
                    "• Recommended: 30-120 minutes",
                    buttons=[[Button.inline("❌ Cancel", data="forward_cancel")]]
                )
            else:
                minutes = int(interval)
                await self.start_forwarding(user_id, forward_data, minutes)
                
                # Show success message
                keyboard = [
                    [Button.inline("📊 View Status", data="forward_status")],
                    [Button.inline("📤 Forward Another", data="forward_new")]
                ]
                success_msg = (
                    f"✅ Message scheduled for forwarding every {minutes} minutes!\n"
                    "Use /status to monitor forwarding progress."
                )
                await event.edit(success_msg, buttons=keyboard)

        elif data == "cancel":
            del self.pending_forwards[user_id]
            keyboard = [
                [Button.inline("📤 Try Again", data="forward_new")],
                [Button.inline("👥 Manage Groups", data="group_action_view")]
            ]
            await event.edit("❌ Forwarding setup cancelled.", buttons=keyboard)

        elif data == "back_to_groups":
            forward_data["step"] = "group_selection"
            groups = await self.get_user_groups(user_id)
            await self.show_group_selection(event, user_id, groups)

    async def start_forwarding(self, user_id: int, forward_data: dict, minutes: int):
        """Start forwarding messages"""
        # Initialize user's messages list
        if user_id not in self.messages_to_forward:
            self.messages_to_forward[user_id] = []

        # Add message to forwarding queue
        self.messages_to_forward[user_id].append({
            "message": forward_data["message"],
            "target_groups": forward_data["selected_groups"],
            "message_id": forward_data["message_id"]
        })

        # Update intervals
        for group_id in forward_data["selected_groups"]:
            self.groups_collection.update_one(
                {"user_id": user_id, "group_id": int(group_id)},
                {"$set": {"interval": minutes * 60}}
            )

        # Clear pending forward
        del self.pending_forwards[user_id]

        # Start forwarding tasks
        asyncio.create_task(self.schedule_forwards(user_id))

    async def schedule_forwards(self, user_id: int):
        """Schedule and manage message forwarding"""
        while True:
            try:
                if user_id not in self.messages_to_forward:
                    break

                for message_data in self.messages_to_forward[user_id]:
                    for group_id_str in message_data["target_groups"]:
                        group_id = int(group_id_str)
                        group = self.groups_collection.find_one({
                            "user_id": user_id,
                            "group_id": group_id
                        })

                        if not group or "interval" not in group:
                            continue

                        last_time = self.last_forward_time.get(user_id, {}).get(
                            group_id, {}).get(message_data["message_id"], 0)

                        if time.time() - last_time >= group["interval"]:
                            # Forward the message
                            client = self.user_clients.get(user_id)
                            if client:
                                try:
                                    await client.send_message(group_id, message_data["message"])
                                    # Update last forward time
                                    if user_id not in self.last_forward_time:
                                        self.last_forward_time[user_id] = {}
                                    if group_id not in self.last_forward_time[user_id]:
                                        self.last_forward_time[user_id][group_id] = {}
                                    self.last_forward_time[user_id][group_id][message_data["message_id"]] = time.time()
                                except Exception as e:
                                    logger.error(f"Error forwarding message: {e}")

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in schedule_forwards: {e}")
                await asyncio.sleep(60)

    async def stop_forward_command(self, event):
        """Enhanced stop forward command handler"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered.")
            return

        if user_id not in self.messages_to_forward or not self.messages_to_forward[user_id]:
            await self.show_error(event, "No active forwarding tasks.")
            return

        # Show message selection UI
        keyboard = []
        for i, message_data in enumerate(self.messages_to_forward[user_id], 1):
            preview = self.get_message_preview(message_data["message"])
            keyboard.append([
                Button.inline(f"🛑 Stop Message {i}", data=f"forward_stop_{i-1}")
            ])

        if len(self.messages_to_forward[user_id]) > 1:
            keyboard.append([Button.inline("🛑 Stop All", data="forward_stop_all")])

        keyboard.append([Button.inline("❌ Cancel", data="forward_cancel")])

        await event.reply(
            "Select which message to stop forwarding:",
            buttons=keyboard
        )