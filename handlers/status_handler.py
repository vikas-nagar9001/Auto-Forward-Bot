from telethon import events
from telethon.tl.custom import Button
import time
from .base_handler import BaseHandler

class StatusHandler(BaseHandler):
    """Handler for forwarding status management"""
    
    def __init__(self, bot, users_collection, groups_collection, forward_handler):
        super().__init__(bot, users_collection, groups_collection)
        self.forward_handler = forward_handler

    async def register_handlers(self):
        """Register all status-related handlers"""
        self.bot.add_event_handler(
            self.status_command,
            events.NewMessage(pattern=r'^/status$')
        )
        self.bot.add_event_handler(
            self.status_callback,
            events.CallbackQuery(pattern=r'^status_')
        )

    async def status_command(self, event):
        """Enhanced status command handler"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        # Show main status menu
        await self.show_status_menu(event, user_id)

    async def show_status_menu(self, event, user_id: int):
        """Show interactive status menu"""
        messages = self.forward_handler.messages_to_forward.get(user_id, [])
        groups = await self.get_user_groups(user_id)
        
        # Build status overview
        status_message = "📊 **Forwarding Status**\n\n"
        
        if not messages:
            status_message += "❌ No active forwarding tasks\n\n"
            keyboard = [
                [Button.inline("📤 Start Forwarding", data="forward_new")],
                [Button.inline("👥 Manage Groups", data="group_action_view")],
                [Button.inline("👤 My Account", data="account_action_view")]
            ]
        else:
            status_message += f"✅ Active Tasks: {len(messages)}\n"
            status_message += f"📝 Total Groups: {len(groups)}\n\n"
            status_message += "Select an option to view details:"
            
            keyboard = [
                [Button.inline("📋 View Active Messages", data="status_view_messages")],
                [Button.inline("⏱️ View Schedules", data="status_view_schedules")],
                [Button.inline("📊 View Statistics", data="status_view_stats")]
            ]
            if len(messages) > 1:
                keyboard.append([Button.inline("🛑 Stop All Forwards", data="forward_stop_all")])

        await event.reply(status_message, buttons=keyboard)

    async def show_message_details(self, event, user_id: int, message_index: int = None):
        """Show detailed view of forwarding messages"""
        messages = self.forward_handler.messages_to_forward.get(user_id, [])
        if not messages:
            await self.show_error(event, "No active forwarding tasks.")
            return

        if message_index is not None:
            # Show specific message details
            if message_index >= len(messages):
                await self.show_error(event, "Invalid message selection.")
                return

            message = messages[message_index]
            preview = self.forward_handler.get_message_preview(message["message"], 100)
            details = (
                f"📝 **Message {message_index + 1} Details**\n\n"
                f"Message:\n`{preview}`\n\n"
                f"Target Groups:\n"
            )

            for group_id in message["target_groups"]:
                group = self.groups_collection.find_one({"user_id": user_id, "group_id": int(group_id)})
                if group:
                    minutes = group["interval"] // 60
                    last_time = self.forward_handler.last_forward_time.get(user_id, {}).get(
                        int(group_id), {}).get(message["message_id"], 0)
                    
                    if last_time:
                        time_ago = time.time() - last_time
                        if time_ago < 60:
                            time_str = "just now"
                        elif time_ago < 3600:
                            time_str = f"{int(time_ago/60)}m ago"
                        else:
                            time_str = f"{int(time_ago/3600)}h ago"
                    else:
                        time_str = "never"

                    details += f"• Group {group_id} (every {minutes}min)\n"
                    details += f"  Last forwarded: {time_str}\n"

            keyboard = [
                [Button.inline("🛑 Stop This Forward", data=f"forward_stop_{message_index}")],
                [Button.inline("« Back to Messages", data="status_view_messages")],
                [Button.inline("« Main Menu", data="status_main_menu")]
            ]
            await event.edit(details, buttons=keyboard)

        else:
            # Show message list
            message_list = "📋 **Active Messages**\n\n"
            keyboard = []

            for i, message in enumerate(messages, 1):
                preview = self.forward_handler.get_message_preview(message["message"])
                message_list += f"{i}. \"{preview}\"\n"
                message_list += f"   Groups: {len(message['target_groups'])}\n\n"
                keyboard.append([
                    Button.inline(f"📝 Message {i} Details", data=f"status_message_{i-1}")
                ])

            keyboard.extend([
                [Button.inline("« Main Menu", data="status_main_menu")],
                [Button.inline("🔄 Refresh", data="status_view_messages")]
            ])

            await event.edit(message_list, buttons=keyboard)

    async def show_schedules(self, event, user_id: int):
        """Show forwarding schedules for all groups"""
        groups = await self.get_user_groups(user_id)
        if not groups:
            await self.show_error(event, "No groups configured.")
            return

        schedule_msg = "⏱️ **Forwarding Schedules**\n\n"
        for group in groups:
            minutes = group["interval"] // 60
            schedule_msg += f"🔹 **Group {group['group_id']}**\n"
            schedule_msg += f"   Interval: Every {minutes} minutes\n"
            
            # Get active forwards for this group
            active_forwards = sum(
                1 for msg in self.forward_handler.messages_to_forward.get(user_id, [])
                if str(group["group_id"]) in msg["target_groups"]
            )
            schedule_msg += f"   Active forwards: {active_forwards}\n\n"

        keyboard = [
            [Button.inline("⏱️ Update Intervals", data="group_action_intervals")],
            [Button.inline("« Main Menu", data="status_main_menu")]
        ]
        await event.edit(schedule_msg, buttons=keyboard)

    async def show_statistics(self, event, user_id: int):
        """Show forwarding statistics"""
        try:
            messages = self.forward_handler.messages_to_forward.get(user_id, [])
            groups = await self.get_user_groups(user_id)
            
            stats_msg = "📊 **Forwarding Statistics**\n\n"
            
            if messages and groups:
                total_forwards = 0
                for group_id in self.forward_handler.last_forward_time.get(user_id, {}):
                    total_forwards += len(self.forward_handler.last_forward_time[user_id][group_id])

                stats_msg += f"📝 Active Messages: {len(messages)}\n"
                stats_msg += f"👥 Total Groups: {len(groups)}\n"
                stats_msg += f"📤 Total Forwards: {total_forwards}\n\n"
                
                # Most active groups
                group_forwards = {}
                for group in groups:
                    group_id = group["group_id"]
                    count = len(self.forward_handler.last_forward_time.get(user_id, {}).get(group_id, {}))
                    group_forwards[group_id] = count
                
                if group_forwards:
                    stats_msg += "🏆 Most Active Groups:\n"
                    sorted_groups = sorted(group_forwards.items(), key=lambda x: x[1], reverse=True)
                    for group_id, count in sorted_groups[:3]:
                        stats_msg += f"• Group {group_id}: {count} forwards\n"

            else:
                stats_msg += "❌ No forwarding activity yet\n"

            keyboard = [
                [Button.inline("🔄 Refresh Stats", data="status_view_stats")],
                [Button.inline("« Main Menu", data="status_main_menu")]
            ]

            try:
                # Add a small change to avoid MessageNotModifiedError
                stats_msg += f"\nLast updated: {time.strftime('%H:%M:%S')}"
                await event.edit(stats_msg, buttons=keyboard)
            except Exception as e:
                if "messagenotmodified" not in str(e).lower():
                    raise
                
        except Exception as e:
            if "messagenotmodified" not in str(e).lower():
                await self.handle_error(event, e, "Failed to show statistics.")

    async def status_callback(self, event):
        """Handle status-related callbacks"""
        try:
            user_id = event.sender_id
            data = event.data.decode('utf-8').replace('status_', '')

            if data == "main_menu":
                await self.show_status_menu(event, user_id)

            elif data == "view_messages":
                await self.show_message_details(event, user_id)

            elif data.startswith("message_"):
                index = int(data.replace("message_", ""))
                await self.show_message_details(event, user_id, index)

            elif data == "view_schedules":
                await self.show_schedules(event, user_id)

            elif data == "view_stats":
                await self.show_statistics(event, user_id)
                
        except Exception as e:
            error_msg = str(e).lower()
            if "messagenotmodified" in error_msg:
                # Ignore this error since the content hasn't changed
                return
            else:
                await self.handle_error(event, e, "Failed to update status view.")