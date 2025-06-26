from telethon import events
from telethon.tl.custom import Button
import logging
from .base_handler import BaseHandler

class HelpHandler(BaseHandler):
    """Handler for help and documentation"""
    
    def __init__(self, bot, users_collection, groups_collection):
        super().__init__(bot, users_collection, groups_collection)
        self.help_state = {}  # {user_id: {"category": str, "section": str}}

    async def register_handlers(self):
        """Register all help-related handlers"""
        self.bot.add_event_handler(
            self.start_command,
            events.NewMessage(pattern=r'^/start$')
        )
        self.bot.add_event_handler(
            self.help_command,
            events.NewMessage(pattern=r'^/help$')
        )
        self.bot.add_event_handler(
            self.help_callback,
            events.CallbackQuery(pattern=r'^help_')
        )

    async def start_command(self, event):
        """Enhanced start command handler with step-by-step guide"""
        user = await self.check_registered(event.sender_id)
        
        if user:
            # User is registered, show main menu
            welcome_message = (
                "👋 **Welcome Back!**\n\n"
                "What would you like to do?\n\n"
                "• Forward messages\n"
                "• Manage groups\n"
                "• Check status\n"
                "• View your account"
            )
            keyboard = [
                [
                    Button.inline("📤 Forward Message", data="forward_new"),
                    Button.inline("👥 Manage Groups", data="group_action_view")
                ],
                [
                    Button.inline("📊 Check Status", data="status_main_menu"),
                    Button.inline("👤 My Account", data="account_action_view")
                ],
                [Button.inline("📚 Help & Tips", data="help_category_main")]
            ]
        else:
            # New user, show getting started guide
            welcome_message = (
                "👋 **Welcome to Auto Message Forwarder!**\n\n"
                "This bot helps you automatically forward messages to multiple groups "
                "at specified intervals.\n\n"
                "**Getting Started:**\n"
                "1️⃣ Register your account\n"
                "2️⃣ Add your groups\n"
                "3️⃣ Start forwarding messages\n\n"
                "Let's begin by registering your account!"
            )
            keyboard = [
                [Button.inline("📝 Register Now", data="help_category_register")],
                [Button.inline("❓ How It Works", data="help_category_guide")]
            ]

        await event.reply(welcome_message, buttons=keyboard)

    async def help_command(self, event):
        """Enhanced help command with categories and step-by-step guides"""
        help_message = (
            "📚 **Bot Help & Documentation**\n\n"
            "Choose a category to learn more:"
        )

        keyboard = [
            [
                Button.inline("🔰 Getting Started", data="help_category_guide"),
                Button.inline("📝 Registration", data="help_category_register")
            ],
            [
                Button.inline("👥 Group Management", data="help_category_groups"),
                Button.inline("📤 Message Forwarding", data="help_category_forward")
            ],
            [
                Button.inline("📊 Status & Settings", data="help_category_status"),
                Button.inline("❓ FAQ", data="help_category_faq")
            ],
            [Button.inline("🔍 Search Help", data="help_category_search")]
        ]

        await event.reply(help_message, buttons=keyboard)

    async def help_callback(self, event):
        """Handle help button callbacks"""
        try:
            user_id = event.sender_id
            data = event.data.decode('utf-8').replace('help_', '')

            if data.startswith('category_'):
                category = data.replace('category_', '')
                await self.show_help_category(event, category)
            elif data.startswith('section_'):
                section = data.replace('section_', '')
                await self.show_help_section(event, section)
            elif data == 'back_to_categories':
                await self.help_command(event)
        except Exception as e:
            if "MessageIdInvalidError" in str(e):
                # Message is too old to edit, handle gracefully in show_help_category
                pass
            else:
                # Log other errors and notify user
                logging.error(f"Error in help_callback: {str(e)}")
                await event.respond("Sorry, there was an error processing your request. Please try again.")

    async def show_help_category(self, event, category):
        try:
            if category == 'main':
                text = (
                    '📚 **Main Help Menu**\n\n'
                    '**Key Features:**\n'
                    '• Forward messages to multiple groups\n'
                    '• Set custom intervals for each group\n'
                    '• Monitor forwarding status\n\n'
                    '**Basic Commands:**\n'
                    '• /help - Show this help menu\n'
                    '• /register - Register your account\n'
                    '• /addgroup - Add a new group\n'
                    '• /fwd - Forward a message\n'
                    '• /status - Check forwarding status'
                )
            elif category == 'faq':
                text = (
                    '❓ **Frequently Asked Questions**\n\n'
                    '**Q: How do I start using the bot?**\n'
                    'A: Register first with /register, then add groups with /addgroup\n\n'
                    '**Q: How do I get a session string?**\n'
                    'A: Use @SessionStringZBot and choose Telethon\n\n'
                    '**Q: How do I forward messages?**\n'
                    'A: Reply to any message with /fwd command\n\n'
                    '**Q: Can I set different intervals?**\n'
                    'A: Yes, each group can have its own interval\n\n'
                    '**Q: How do I stop forwarding?**\n'
                    'A: Use /stopfwd command'
                )
            elif category == 'forward':
                text = (
                    '📤 **Message Forwarding Help**\n\n'
                    '1️⃣ **Starting a Forward**\n'
                    '• Find the message you want to forward\n'
                    '• Reply to it with /fwd command\n'
                    '• Select target groups\n'
                    '• Choose forwarding interval\n\n'
                    '2️⃣ **Managing Forwards**\n'
                    '• Use /status to check active forwards\n'
                    '• Use /stopfwd to stop forwarding\n'
                    '• Use /setinterval to change timing\n\n'
                    '3️⃣ **Forward Settings**\n'
                    '• Each group can have different intervals\n'
                    '• Intervals: 1 min to 24 hours\n'
                    '• Multiple forwards can run simultaneously'
                )
            elif category == 'status':
                text = (
                    '📊 **Status & Monitoring Help**\n\n'
                    '1️⃣ **Checking Status**\n'
                    '• Use /status to see active forwards\n'
                    '• View next forward time for each group\n'
                    '• Monitor success/failure rates\n\n'
                    '2️⃣ **Managing Forwards**\n'
                    '• Pause/resume specific forwards\n'
                    '• Stop all forwards with /stopfwd\n'
                    '• View detailed statistics\n\n'
                    '3️⃣ **Troubleshooting**\n'
                    '• Check group permissions\n'
                    '• Verify bot admin status\n'
                    '• Monitor error messages'
                )
            elif category == 'groups':
                text = (
                    '📚 Groups Help\n\n'
                    '• Use /addgroup to add a new source group\n'
                    '• Use /listgroups to see your configured groups\n'
                    '• Use /removegroup to remove a source group'
                )
            elif category == 'accounts':
                text = (
                    '📱 Accounts Help\n\n'
                    '• Use /addaccount to add a new account\n'
                    '• Use /listaccounts to see your configured accounts\n'
                    '• Use /removeaccount to remove an account'
                )
            elif category == 'forwards':
                text = (
                    '↪️ Forwards Help\n\n'
                    '• Use /addforward to create a new forward rule\n'
                    '• Use /listforwards to see your configured forwards\n'
                    '• Use /removeforward to remove a forward rule'
                )
            elif category == 'register':
                text = (
                    '📝 **How to Register**\n\n'
                    '1️⃣ **Get Your Session String**\n'
                    '• Use @SessionStringZBot\n'
                    '• Choose Telethon\n'
                    '• Enter your phone number\n'
                    '• Enter the verification code\n'
                    '• Copy the generated session string\n\n'
                    '2️⃣ **Register with Bot**\n'
                    '• Use /register command\n'
                    '• Paste your session string\n'
                    '• Wait for confirmation\n\n'
                    '❓ Need help? Use the buttons below!'
                )
            elif category == 'guide':
                text = (
                    '🔰 **Getting Started Guide**\n\n'
                    '1️⃣ **Registration**\n'
                    '• First, register your account\n'
                    '• You\'ll need a session string\n'
                    '• Use /register command\n\n'
                    '2️⃣ **Add Groups**\n'
                    '• Add bot to your groups\n'
                    '• Use /addgroup command\n'
                    '• Set forwarding intervals\n\n'
                    '3️⃣ **Start Forwarding**\n'
                    '• Reply to message with /fwd\n'
                    '• Choose target groups\n'
                    '• Messages will auto-forward\n\n'
                    '4️⃣ **Monitor & Manage**\n'
                    '• Check status with /status\n'
                    '• Stop forwards with /stopfwd\n'
                    '• View groups with /mygroups'
                )
            else:
                text = '❌ Invalid help category selected'
                logging.warning(f"Invalid help category requested: {category}")
            
            markup = self.get_help_markup()
            await event.edit(text, buttons=markup)
            
        except Exception as e:
            error_msg = '❌ An error occurred while showing help information'
            logging.error(f"Error in show_help_category: {str(e)}")
            await event.edit(error_msg)

    async def show_help_section(self, event, section: str):
        """Show detailed help for a specific section"""
        help_sections = {
            "register": (
                "📝 **How to Register**\n\n"
                "1️⃣ **Get Session String**\n"
                "• Open @SessionStringZBot\n"
                "• Click Start\n"
                "• Choose Telethon\n"
                "• Enter your phone\n"
                "• Enter the code\n"
                "• Copy the session string\n\n"
                "2️⃣ **Register with Bot**\n"
                "• Use /register command\n"
                "• Paste the session string\n"
                "• Wait for confirmation\n\n"
                "Need help? Click below!"
            ),
            "add_groups": (
                "➕ **Adding Groups**\n\n"
                "1️⃣ **Prepare the Group**\n"
                "• Add bot to group as admin\n"
                "• Grant message permissions\n\n"
                "2️⃣ **Get Group ID or Username**\n"
                "• **Group ID**: Forward group message to @username_to_id_bot\n"
                "• **Username**: Use public group username (e.g., @mygroupname)\n"
                "• **From link**: Extract from t.me/groupname\n\n"
                "3️⃣ **Add to Bot**\n"
                "• Use /addgroup for single group\n"
                "• Use /bulkaddgroups for multiple groups\n"
                "• Enter group ID or username\n"
                "• Groups will be added to your list"
            ),
            "how_forward": (
                "📤 **How to Forward Messages**\n\n"
                "1️⃣ **Start Forwarding**\n"
                "• Find message to forward\n"
                "• Reply with /fwd command\n"
                "• Select target groups\n"
                "• Choose interval\n\n"
                "2️⃣ **Monitor Status**\n"
                "• Use /status to check\n"
                "• View forwarding schedule\n"
                "• Monitor progress\n\n"
                "3️⃣ **Stop Forwarding**\n"
                "• Use /stopfwd command\n"
                "• Select message to stop"
            ),
            # Add more sections as needed
        }

        if section not in help_sections:
            await self.show_error(event, "Help section not found.")
            return

        # Add relevant action buttons based on section
        keyboard = []
        if section == "register":
            keyboard.extend([
                [Button.inline("📝 Register Now", data="register_start")],
                [Button.inline("❓ Registration FAQ", data="help_section_reg_issues")]
            ])
        elif section == "add_groups":
            keyboard.extend([
                [Button.inline("➕ Add Group", data="group_action_add")],
                [Button.inline("❓ Group FAQ", data="help_section_group_issues")]
            ])
        elif section == "how_forward":
            keyboard.extend([
                [Button.inline("📤 Start Forwarding", data="forward_new")],
                [Button.inline("❓ Forwarding FAQ", data="help_section_forward_issues")]
            ])

        # Add navigation buttons
        keyboard.extend([
            [Button.inline("« Back", data="help_category_main")],
            [Button.inline("🔍 Search Help", data="help_category_search")]
        ])

        await event.edit(help_sections[section], buttons=keyboard)

    def get_help_markup(self):
        """Generate help navigation keyboard markup"""
        keyboard = [
            [
                Button.inline("« Back to Categories", data="help_back_to_categories"),
                Button.inline("🏠 Main Menu", data="help_category_main")
            ],
            [Button.inline("❓ FAQ", data="help_category_faq")]
        ]
        return keyboard