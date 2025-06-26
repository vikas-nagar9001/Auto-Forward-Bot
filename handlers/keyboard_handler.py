from telethon import events
from telethon.tl.custom import Button
from .base_handler import BaseHandler

class KeyboardHandler(BaseHandler):
    """Handler for keyboard shortcuts and quick actions"""
    
    def __init__(self, bot, users_collection, groups_collection):
        super().__init__(bot, users_collection, groups_collection)
        self.quick_actions = {}  # {user_id: {"action": str, "data": dict}}

    async def register_handlers(self):
        """Register keyboard-related handlers"""
        self.bot.add_event_handler(
            self.show_keyboard_command,
            events.NewMessage(pattern=r'^/keyboard$')
        )
        self.bot.add_event_handler(
            self.keyboard_callback,
            events.CallbackQuery(pattern=r'^kb_')
        )

    async def show_keyboard_command(self, event):
        """Show quick action keyboard"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        await self.show_quick_actions(event)

    async def show_quick_actions(self, event):
        """Show quick action keyboard with common functions"""
        keyboard = [
            [
                Button.inline("📤 Forward", data="kb_quick_forward"),
                Button.inline("🛑 Stop All", data="kb_quick_stop"),
                Button.inline("📊 Status", data="kb_quick_status")
            ],
            [
                Button.inline("➕ Add Group", data="kb_quick_add_group"),
                Button.inline("📥 Bulk Add", data="kb_quick_bulk_add"),
                Button.inline("👥 Groups", data="kb_quick_groups")
            ],
            [
                Button.inline("📋 Active Tasks", data="kb_quick_tasks"),
                Button.inline("⚙️ Settings", data="kb_quick_settings"),
                Button.inline("❓ Help", data="kb_quick_help")
            ]
        ]

        await event.reply(
            "⌨️ **Quick Actions**\n\n"
            "Use these shortcuts for quick access to common functions:",
            buttons=keyboard
        )

    async def keyboard_callback(self, event):
        """Handle keyboard shortcut callbacks"""
        user_id = event.sender_id
        data = event.data.decode('utf-8').replace('kb_quick_', '')

        if data == "forward":
            # Show quick forward options
            keyboard = [
                [
                    Button.inline("📝 Last Message", data="forward_last"),
                    Button.inline("📱 From Phone", data="forward_from_phone")
                ],
                [
                    Button.inline("📋 Template", data="forward_template"),
                    Button.inline("🔄 Recent", data="forward_recent")
                ],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "📤 **Quick Forward**\n\n"
                "Choose what to forward:",
                buttons=keyboard
            )

        elif data == "stop":
            # Show stop options
            keyboard = [
                [Button.inline("🛑 Stop All", data="forward_stop_all")],
                [Button.inline("📝 Select Message", data="forward_stop_select")],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "🛑 **Stop Forwarding**\n\n"
                "What would you like to stop?",
                buttons=keyboard
            )

        elif data == "status":
            # Show quick status options
            keyboard = [
                [
                    Button.inline("📊 Overview", data="status_main_menu"),
                    Button.inline("📝 Messages", data="status_view_messages")
                ],
                [
                    Button.inline("⏱️ Schedules", data="status_view_schedules"),
                    Button.inline("📈 Stats", data="status_view_stats")
                ],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "📊 **Quick Status**\n\n"
                "Choose what to view:",
                buttons=keyboard
            )

        elif data == "add_group":
            # Show add group wizard
            keyboard = [
                [
                    Button.inline("➕ New Group", data="group_action_add"),
                    Button.inline("📱 From Phone", data="group_action_from_phone")
                ],
                [
                    Button.inline("🔍 Find Group", data="group_action_find"),
                    Button.inline("📋 Recent", data="group_action_recent")
                ],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "➕ **Add Group**\n\n"
                "Choose how to add a group:",
                buttons=keyboard
            )

        elif data == "bulk_add":
            # Start bulk add process
            keyboard = [
                [Button.inline("📥 Start Bulk Add", data="group_action_bulk_add")],
                [Button.inline("📝 View Example", data="group_action_bulk_example")],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "📥 **Bulk Add Groups**\n\n"
                "Add multiple groups at once!\n\n"
                "• Support for Group IDs and usernames\n"
                "• Up to 10 groups per batch\n"
                "• Mix IDs and usernames freely\n\n"
                "Ready to start?",
                buttons=keyboard
            )

        elif data == "intervals":
            # Show interval management options
            keyboard = [
                [Button.inline(f"{mins}min", data=f"kb_set_interval_{mins}") 
                 for mins in [30, 60, 120]]
            ]
            keyboard.extend([
                [
                    Button.inline("⚡️ Quick Set", data="group_action_quick_interval"),
                    Button.inline("⏱️ Custom", data="group_action_custom_interval")
                ],
                [Button.inline("« Back", data="kb_main")]
            ])
            await event.edit(
                "⏱️ **Interval Settings**\n\n"
                "Choose an action:",
                buttons=keyboard
            )

        elif data == "groups":
            # Show group management options
            keyboard = [
                [
                    Button.inline("👥 View All", data="group_action_view"),
                    Button.inline("🗑️ Remove", data="group_action_remove")
                ],
                [
                    Button.inline("⏱️ Intervals", data="group_action_intervals"),
                    Button.inline("📊 Stats", data="group_action_stats")
                ],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "👥 **Group Management**\n\n"
                "Choose an action:",
                buttons=keyboard
            )

        elif data == "tasks":
            # Show active tasks management
            keyboard = [
                [
                    Button.inline("📋 View All", data="status_view_messages"),
                    Button.inline("🛑 Stop", data="forward_stop_select")
                ],
                [
                    Button.inline("⏱️ Schedules", data="status_view_schedules"),
                    Button.inline("🔄 Refresh", data="status_refresh")
                ],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "📋 **Active Tasks**\n\n"
                "Choose what to view:",
                buttons=keyboard
            )

        elif data == "settings":
            # Show settings options
            keyboard = [
                [
                    Button.inline("👤 Account", data="account_action_view"),
                    Button.inline("⚙️ Preferences", data="settings_preferences")
                ],
                [
                    Button.inline("🔔 Notifications", data="settings_notifications"),
                    Button.inline("📊 Defaults", data="settings_defaults")
                ],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "⚙️ **Quick Settings**\n\n"
                "Choose a category:",
                buttons=keyboard
            )

        elif data == "help":
            # Show quick help options
            keyboard = [
                [
                    Button.inline("📚 Guide", data="help_category_guide"),
                    Button.inline("❓ FAQ", data="help_category_faq")
                ],
                [
                    Button.inline("🔍 Search", data="help_category_search"),
                    Button.inline("📝 Commands", data="help_category_commands")
                ],
                [Button.inline("« Back", data="kb_main")]
            ]
            await event.edit(
                "❓ **Quick Help**\n\n"
                "Choose a help topic:",
                buttons=keyboard
            )

        elif data == "main":
            # Show main quick actions keyboard
            await self.show_quick_actions(event)