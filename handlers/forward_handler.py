from telethon import events
from telethon.tl.custom import Button
import asyncio
import time
import logging
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)

class ForwardHandler(BaseHandler):
    """Handler for message forwarding functionality"""
    
    # Batch sending configuration to avoid rate limiting
    BATCH_SIZE = 4  # Send to 5 groups at a time
    BATCH_DELAY = 4  # Wait 4 seconds between batches
    MAX_CONCURRENT_SENDS = 1  # Maximum concurrent send operations per batch
    
    def __init__(self, bot, users_collection, groups_collection, user_clients):
        super().__init__(bot, users_collection, groups_collection)
        self.user_clients = user_clients
        self.account_handler = None  # Will be set later
        self.messages_to_forward = {}  # {user_id: [{"message": str, "target_groups": [], "message_id": str, "interval": int}]}
        self.forwarding_tasks = {}  # {user_id: {message_id: task}}
        self.last_forward_time = {}  # {user_id: {message_id: {group_id: timestamp}}}
        self.pending_forwards = {}  # {user_id: {"message": str, "step": str, "selected_groups": [], "interval": int}}

    def set_account_handler(self, account_handler):
        """Set the account handler for debugging purposes"""
        self.account_handler = account_handler

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
                    logger.info(f"Skipping active forwards for user {user_id} - no client available")
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
                
                # Initialize tasks dict for user
                if user_id not in self.forwarding_tasks:
                    self.forwarding_tasks[user_id] = {}
                
                for forward in active_forwards:
                    message_data = {
                        "message": forward['message'],
                        "message_obj": None,  # No message object available from database
                        "target_groups": forward['target_groups'],
                        "message_id": forward['message_id'],
                        "interval": forward.get('interval', 1800)  # Default 30 minutes
                    }
                    
                    self.messages_to_forward[user_id].append(message_data)
                    
                    # Create independent task for each message
                    message_id = forward['message_id']
                    task = asyncio.create_task(
                        self.schedule_message_forwards(user_id, message_id, message_data)
                    )
                    self.forwarding_tasks[user_id][message_id] = task
                    logger.info(f"Restored forwarding task for message {message_id} of user {user_id}")

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

        # Validate session before proceeding
        if not await self.require_valid_session(event, user_id, self.user_clients, "message forwarding"):
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

        # Start forwarding process - store the entire message object for formatting preservation
        self.pending_forwards[user_id] = {
            "message": reply_msg.text,
            "message_obj": reply_msg,  # Store full message object to preserve formatting
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
            
            # Store interval in pending forward data
            self.pending_forwards[user_id]["interval"] = minutes * 60

            # Get batch information
            total_groups = len(self.pending_forwards[user_id]["selected_groups"])
            batch_info = self.get_batch_info(total_groups)

            # Start forwarding
            keyboard = [
                [Button.inline("📊 View Status", data="forward_status")],
                [Button.inline("📤 Forward Another", data="forward_new")]
            ]
            success_msg = (
                f"✅ Message scheduled for forwarding every {minutes} minutes!\n\n"
                f"📊 **Batch Sending Info:**\n"
                f"{batch_info}\n\n"
                "Use /status to monitor forwarding progress."
            )

            try:
                await event.delete()  # Delete the user's message with interval
                await event.respond(success_msg, buttons=keyboard)
            except Exception as e:
                if "MessageIdInvalidError" in str(e):
                    await event.reply(success_msg, buttons=keyboard)

            # Initialize forwarding
            await self.start_forwarding(user_id, self.pending_forwards[user_id])

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
                # Stop all forwards for this user
                if user_id in self.forwarding_tasks:
                    # Cancel all individual message tasks
                    for message_id, task in self.forwarding_tasks[user_id].items():
                        task.cancel()
                        logger.info(f"Cancelled task for message {message_id} of user {user_id}")
                    del self.forwarding_tasks[user_id]
                
                # Clear messages list
                self.messages_to_forward[user_id] = []
                keyboard = [[Button.inline("📤 New Forward", data="forward_new")]]
                await event.edit("✅ Stopped all forwards.", buttons=keyboard)
            else:
                # Stop specific forward
                try:
                    idx = int(index)
                    if 0 <= idx < len(self.messages_to_forward[user_id]):
                        # Get the message to stop
                        message_to_stop = self.messages_to_forward[user_id][idx]
                        message_id = message_to_stop["message_id"]
                        
                        # Cancel the specific task
                        if user_id in self.forwarding_tasks and message_id in self.forwarding_tasks[user_id]:
                            self.forwarding_tasks[user_id][message_id].cancel()
                            del self.forwarding_tasks[user_id][message_id]
                            logger.info(f"Cancelled task for message {message_id} of user {user_id}")
                            
                            # If no more tasks for this user, cleanup the user entry
                            if not self.forwarding_tasks[user_id]:
                                del self.forwarding_tasks[user_id]
                        
                        # Remove from messages list
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
                forward_data["interval"] = minutes * 60
                
                # Get batch information
                total_groups = len(forward_data["selected_groups"])
                batch_info = self.get_batch_info(total_groups)
                
                await self.start_forwarding(user_id, forward_data)
                
                # Show success message with batch information
                keyboard = [
                    [Button.inline("📊 View Status", data="forward_status")],
                    [Button.inline("📤 Forward Another", data="forward_new")]
                ]
                success_msg = (
                    f"✅ Message scheduled for forwarding every {minutes} minutes!\n\n"
                    f"📊 **Batch Sending Info:**\n"
                    f"{batch_info}\n\n"
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

    async def start_forwarding(self, user_id: int, forward_data: dict):
        """Start forwarding messages with per-message interval - each message gets its own task"""
        # Initialize user's messages list
        if user_id not in self.messages_to_forward:
            self.messages_to_forward[user_id] = []

        # Add message to forwarding queue with interval
        message_entry = {
            "message": forward_data["message"],
            "message_obj": forward_data.get("message_obj"),  # Store message object for formatting
            "target_groups": forward_data["selected_groups"],
            "message_id": forward_data["message_id"],
            "interval": forward_data["interval"]
        }
        
        self.messages_to_forward[user_id].append(message_entry)

        # Clear pending forward
        del self.pending_forwards[user_id]

        # Initialize forwarding tasks dict for user if needed
        if user_id not in self.forwarding_tasks:
            self.forwarding_tasks[user_id] = {}

        # Create independent task for this specific message
        message_id = forward_data["message_id"]
        task = asyncio.create_task(self.schedule_message_forwards(user_id, message_id, message_entry))
        self.forwarding_tasks[user_id][message_id] = task
        
        logger.info(f"Started independent forwarding task for message {message_id} of user {user_id}")

        # Send the first forward immediately for instant gratification
        await self.send_immediate_forward(user_id, message_entry)

    async def schedule_forwards(self, user_id: int):
        """Legacy method - now replaced by individual message tasks"""
        # This method is kept for backward compatibility during initialization
        # but actual forwarding now uses schedule_message_forwards for each message
        logger.info(f"Legacy schedule_forwards called for user {user_id} - using new independent task system")

    async def send_immediate_forward(self, user_id: int, message_data: dict):
        """Send the first forward immediately when user sets up forwarding"""
        try:
            message_id = message_data["message_id"]
            group_ids = message_data["target_groups"]
            
            logger.info(f"Sending immediate forward for message {message_id} to {len(group_ids)} groups")
            
            # Validate session before sending
            is_valid, error_msg = await self.validate_user_session(user_id, self.user_clients)
            if not is_valid:
                logger.error(f"Session validation failed during immediate forward for user {user_id}: {error_msg}")
                
                # Clean up the forwarding data since session is invalid
                await self.cleanup_user_forwards_on_session_error(user_id)
                
                # Notify user about session issue
                try:
                    user = self.users_collection.find_one({"user_id": user_id})
                    if user:
                        await self.bot.send_message(
                            user_id,
                            f"❌ **Forwarding Failed - Session Issue**\n\n"
                            f"Message: `{self.get_message_preview(message_data['message'])}`\n\n"
                            f"{error_msg}\n\n"
                            "❌ **All your active forwards have been stopped and removed due to session issues.**\n\n"
                            "Please update your session and set up forwarding again.",
                            buttons=[
                                [Button.inline("🔄 Update Session", data="account_action_update_session")],
                                [Button.inline("❓ Session Help", data="help_category_sessions")]
                            ]
                        )
                except Exception as notify_error:
                    logger.error(f"Failed to notify user {user_id} about session error: {notify_error}")
                return
            
            # Use batched sending to avoid rate limiting
            successful, failed = await self.send_message_to_groups_batched(user_id, message_data, group_ids)
            
            if successful > 0:
                logger.info(f"Immediate forward completed: {successful} successful, {failed} failed")
            else:
                logger.warning(f"Immediate forward failed for all {len(group_ids)} groups")
                    
        except Exception as e:
            logger.error(f"Error in send_immediate_forward for user {user_id}: {e}")

    async def schedule_message_forwards(self, user_id: int, message_id: str, message_data: dict):
        """Schedule forwarding for a specific message - runs independently"""
        try:
            interval = message_data["interval"]
            group_ids = message_data["target_groups"]
            
            while True:
                # Check if message still exists in the user's forwarding list
                if user_id not in self.messages_to_forward:
                    break
                    
                # Check if this specific message still exists
                message_exists = any(
                    msg["message_id"] == message_id 
                    for msg in self.messages_to_forward[user_id]
                )
                if not message_exists:
                    break

                # Wait for the interval
                await asyncio.sleep(interval)
                
                logger.info(f"Scheduled forward time reached for message {message_id} of user {user_id}")
                
                # Validate session before sending
                is_valid, error_msg = await self.validate_user_session(user_id, self.user_clients)
                if not is_valid:
                    logger.error(f"Session validation failed during scheduled forward for user {user_id}: {error_msg}")
                    
                    # Clean up this specific message from forwarding list
                    if user_id in self.messages_to_forward:
                        self.messages_to_forward[user_id] = [
                            msg for msg in self.messages_to_forward[user_id] 
                            if msg["message_id"] != message_id
                        ]
                        # If no more messages for this user, clean up the user entry
                        if not self.messages_to_forward[user_id]:
                            del self.messages_to_forward[user_id]
                    
                    # Clean up the task reference
                    if user_id in self.forwarding_tasks and message_id in self.forwarding_tasks[user_id]:
                        del self.forwarding_tasks[user_id][message_id]
                        # If no more tasks for this user, cleanup the user entry
                        if not self.forwarding_tasks[user_id]:
                            del self.forwarding_tasks[user_id]
                    
                    # Notify user about session issue and inform that forward has been removed
                    try:
                        await self.bot.send_message(
                            user_id,
                            f"⚠️ **Scheduled Forward Stopped - Session Issue**\n\n"
                            f"Message: `{self.get_message_preview(message_data['message'])}`\n\n"
                            f"{error_msg}\n\n"
                            "❌ **This message's forwarding has been permanently stopped and removed from your active forwards.**\n\n"
                            "Please update your session and set up forwarding again for this message.",
                            buttons=[
                                [Button.inline("🔄 Update Session", data="account_action_update_session")],
                                [Button.inline("❓ Session Help", data="help_category_sessions")],
                                [Button.inline("📊 Check Status", data="status_view_messages")]
                            ]
                        )
                    except Exception as notify_error:
                        logger.error(f"Failed to notify user {user_id} about session error: {notify_error}")
                    break  # Stop this forwarding task
                
                # Use batched sending to avoid rate limiting
                successful, failed = await self.send_message_to_groups_batched(user_id, message_data, group_ids)
                
                if successful > 0:
                    logger.info(f"Scheduled forward completed for message {message_id}: {successful} successful, {failed} failed")
                else:
                    logger.warning(f"Scheduled forward failed for all groups for message {message_id}")

        except asyncio.CancelledError:
            logger.info(f"Forwarding task cancelled for user {user_id}, message {message_id}")
        except Exception as e:
            logger.error(f"Error in schedule_message_forwards for user {user_id}, message {message_id}: {e}")
        finally:
            # Cleanup task reference
            if user_id in self.forwarding_tasks and message_id in self.forwarding_tasks[user_id]:
                del self.forwarding_tasks[user_id][message_id]
                # If no more tasks for this user, cleanup the user entry
                if not self.forwarding_tasks[user_id]:
                    del self.forwarding_tasks[user_id]

    async def send_message_to_groups_batched(self, user_id: int, message_data: dict, group_ids: list):
        """Send message to groups in batches to avoid rate limiting"""
        try:
            # Validate session before sending
            is_valid, error_msg = await self.validate_user_session(user_id, self.user_clients)
            if not is_valid:
                logger.error(f"Session validation failed for user {user_id} during forwarding: {error_msg}")
                return 0, len(group_ids)
            
            client = self.user_clients.get(user_id)
            if not client or not client.is_connected():
                logger.warning(f"Client not available for batched sending for user {user_id}")
                return 0, len(group_ids)
            
            message_id = message_data["message_id"]
            total_groups = len(group_ids)
            successful_sends = 0
            failed_sends = 0
            
            logger.info(f"Starting batched send for message {message_id} to {total_groups} groups (batch size: {self.BATCH_SIZE})")
            
            # Process groups in batches
            for i in range(0, total_groups, self.BATCH_SIZE):
                batch = group_ids[i:i + self.BATCH_SIZE]
                batch_number = (i // self.BATCH_SIZE) + 1
                total_batches = (total_groups + self.BATCH_SIZE - 1) // self.BATCH_SIZE
                
                logger.info(f"Processing batch {batch_number}/{total_batches} ({len(batch)} groups) for user {user_id}")
                
                # Create tasks for concurrent sending within the batch
                batch_tasks = []
                for group_id_str in batch:
                    group_id = int(group_id_str)
                    
                    # Check if group still exists
                    group = self.groups_collection.find_one({
                        "user_id": user_id,
                        "group_id": group_id
                    })
                    if not group:
                        logger.warning(f"Group {group_id} not found for user {user_id}, skipping")
                        continue
                    
                    # Create task for sending to this group
                    task = self.send_to_single_group(client, user_id, message_data, group_id)
                    batch_tasks.append(task)
                
                # Execute batch tasks with limited concurrency
                if batch_tasks:
                    # Limit concurrent operations to avoid overwhelming the API
                    semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_SENDS)
                    
                    async def limited_send(task):
                        async with semaphore:
                            return await task
                    
                    # Execute batch with limited concurrency
                    batch_results = await asyncio.gather(
                        *[limited_send(task) for task in batch_tasks],
                        return_exceptions=True
                    )
                    
                    # Count results
                    for result in batch_results:
                        if isinstance(result, Exception):
                            failed_sends += 1
                            logger.error(f"Batch send error: {result}")
                        elif result:
                            successful_sends += 1
                        else:
                            failed_sends += 1
                
                # Wait between batches (except for the last batch)
                if i + self.BATCH_SIZE < total_groups:
                    logger.info(f"Waiting {self.BATCH_DELAY} seconds before next batch...")
                    await asyncio.sleep(self.BATCH_DELAY)
            
            logger.info(f"Batched send completed for message {message_id}: {successful_sends} successful, {failed_sends} failed")
            return successful_sends, failed_sends
            
        except Exception as e:
            logger.error(f"Error in batched sending for user {user_id}: {e}")
            return 0, len(group_ids)

    async def send_to_single_group(self, client, user_id: int, message_data: dict, group_id: int):
        """Send message to a single group"""
        try:
            message_id = message_data["message_id"]
            
            # Use the original message object to preserve formatting
            message_obj = message_data.get("message_obj")
            if message_obj:
                # Forward using the original message object which preserves all formatting
                await client.send_message(
                    group_id,
                    message_obj.message,
                    formatting_entities=message_obj.entities
                )
            else:
                # Fallback to plain text if message object is not available
                await client.send_message(group_id, message_data["message"])
            
            # Update last forward time
            if user_id not in self.last_forward_time:
                self.last_forward_time[user_id] = {}
            if message_id not in self.last_forward_time[user_id]:
                self.last_forward_time[user_id][message_id] = {}
            self.last_forward_time[user_id][message_id][group_id] = time.time()
            
            logger.debug(f"Successfully sent message to group {group_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending to group {group_id} for user {user_id}: {e}")
            return False

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

    def get_batch_info(self, total_groups: int) -> str:
        """Get information about how batching will work for the given number of groups"""
        if total_groups <= self.BATCH_SIZE:
            return f"All {total_groups} groups will receive the message instantly."
        
        total_batches = (total_groups + self.BATCH_SIZE - 1) // self.BATCH_SIZE
        total_time = (total_batches - 1) * self.BATCH_DELAY
        
        return (
            f"Message will be sent to {total_groups} groups in {total_batches} batches:\n"
            f"• {self.BATCH_SIZE} groups per batch\n"
            f"• {self.BATCH_DELAY} second delay between batches\n"
            f"• Total sending time: ~{total_time} seconds"
        )

    async def cleanup_user_forwards_on_session_error(self, user_id: int):
        """Clean up all forwarding data when user's session becomes invalid"""
        try:
            # Cancel all forwarding tasks for this user
            if user_id in self.forwarding_tasks:
                for message_id, task in self.forwarding_tasks[user_id].items():
                    task.cancel()
                    logger.info(f"Cancelled task for message {message_id} due to session error for user {user_id}")
                del self.forwarding_tasks[user_id]
            
            # Clear all messages from forwarding list
            if user_id in self.messages_to_forward:
                message_count = len(self.messages_to_forward[user_id])
                del self.messages_to_forward[user_id]
                logger.info(f"Cleared {message_count} forwarding messages for user {user_id} due to session error")
            
            # Clear any pending forwards
            if user_id in self.pending_forwards:
                del self.pending_forwards[user_id]
                logger.info(f"Cleared pending forward for user {user_id} due to session error")
                
            # Clear last forward times
            if user_id in self.last_forward_time:
                del self.last_forward_time[user_id]
                logger.info(f"Cleared forward time tracking for user {user_id} due to session error")
                
        except Exception as e:
            logger.error(f"Error cleaning up forwards for user {user_id}: {e}")