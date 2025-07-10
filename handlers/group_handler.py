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
            self.bulk_add_groups_command,
            events.NewMessage(pattern=r'^/bulkaddgroups$')
        )
        self.bot.add_event_handler(
            self.remove_group_command,
            events.NewMessage(pattern=r'^/removegroup$')
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
            "Choose how to add your group:\n\n"
            "**Option 1: Send Username**\n"
            "• Example: `@mygroupname`\n\n"
            "**Option 2: Send t.me Link**\n"
            "• Example: `https://t.me/mygroupname`\n\n"
            "**Option 3: Send Group ID**\n"
            "• Get ID from @username_to_id_bot\n"
            "• Example: `-1001234567890`\n\n"
            "*Send your group username, link, or ID:*"
        )

        keyboard = [
            [Button.inline("❓ How to Add Groups", data="group_action_help_id")],
            [Button.inline("❌ Cancel", data="group_action_cancel")]
        ]
        await event.reply(instructions, buttons=keyboard)

    async def bulk_add_groups_command(self, event):
        """Bulk add multiple groups command handler"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        # Start bulk group addition process
        self.pending_group_actions[user_id] = {
            "action": "bulk_add",
            "step": "group_list"
        }

        instructions = (
            "➕ **Bulk Add Multiple Groups**\n\n"
            "Add multiple groups at once! Follow these steps:\n\n"
            "1️⃣ First, join all groups with your session account\n"
            "2️⃣ Prepare your group list in one of these formats:\n\n"
            "**Format 1: Group IDs (one per line)**\n"
            "`-1001234567890`\n"
            "`-1001234567891`\n"
            "`-1001234567892`\n\n"
            "**Format 2: Usernames (one per line)**\n"
            "`@group1name`\n"
            "`@group2name`\n"
            "`group3name`\n\n"
            "**Format 3: t.me Links (one per line)**\n"
            "`https://t.me/group1name`\n"
            "`t.me/group2name`\n"
            "`https://t.me/group3name`\n\n"
            "**Format 4: Mixed (IDs, usernames, and links)**\n"
            "`-1001234567890`\n"
            "`@group2name`\n"
            "`https://t.me/group3name`\n"
            "`group4name`\n\n"
            "3️⃣ Send all group IDs/usernames/links in a single message\n\n"
            "*Send your group list now (max 10 groups per batch):*"
        )

        keyboard = [
            [Button.inline("📝 Example Format", data="group_action_bulk_example")],
            [Button.inline("❓ How to Get Group IDs", data="group_action_help_id")],
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
                    # Try to parse as group ID first
                    group_id = None
                    if text.lstrip('-').isdigit():
                        group_id = int(text)
                    elif text.startswith('@'):
                        # It's a username, try to resolve it
                        username = text[1:]  # Remove the @ prefix
                        group_id = await self.resolve_username_to_id(username)
                        if group_id is None:
                            keyboard = [
                                [Button.inline("🔄 Try Again", data="group_action_retry")],
                                [Button.inline("❓ Help", data="group_action_help_id")],
                                [Button.inline("❌ Cancel", data="group_action_cancel")]
                            ]
                            await event.reply(
                                f"❌ **Username Resolution Failed**\n\n"
                                f"Could not find a group with username @{username}.\n"
                                "Make sure the username is correct and the group is public.\n\n"
                                "Please try again with a group ID or a valid username.",
                                buttons=keyboard
                            )
                            return
                    elif text.startswith('t.me/'):
                        # Extract username from t.me link
                        username = text.replace('t.me/', '')
                        if username.startswith('+'):
                            # It's a private group link, can't handle this
                            keyboard = [
                                [Button.inline("🔄 Try Again", data="group_action_retry")],
                                [Button.inline("❓ Help", data="group_action_help_id")],
                                [Button.inline("❌ Cancel", data="group_action_cancel")]
                            ]
                            await event.reply(
                                f"❌ **Private Group Link**\n\n"
                                f"Private group links (t.me/+...) cannot be resolved.\n"
                                "Please use the group ID or public username instead.",
                                buttons=keyboard
                            )
                            return
                        else:
                            group_id = await self.resolve_username_to_id(username)
                            if group_id is None:
                                keyboard = [
                                    [Button.inline("🔄 Try Again", data="group_action_retry")],
                                    [Button.inline("❓ Help", data="group_action_help_id")],
                                    [Button.inline("❌ Cancel", data="group_action_cancel")]
                                ]
                                await event.reply(
                                    f"❌ **Username Resolution Failed**\n\n"
                                    f"Could not find a group with username {username}.\n"
                                    "Make sure the username is correct and the group is public.\n\n"
                                    "Please try again with a group ID or a valid username.",
                                    buttons=keyboard
                                )
                                return
                    else:
                        # Try to resolve as username without @ prefix
                        group_id = await self.resolve_username_to_id(text)
                        if group_id is None:
                            keyboard = [
                                [Button.inline("🔄 Try Again", data="group_action_retry")],
                                [Button.inline("❓ Help", data="group_action_help_id")],
                                [Button.inline("❌ Cancel", data="group_action_cancel")]
                            ]
                            await event.reply(
                                f"❌ **Invalid Input**\n\n"
                                f"'{text}' is not a valid group ID or username.\n\n"
                                "Please provide:\n"
                                "• A group ID (e.g., -1001234567890)\n"
                                "• A username (e.g., @mygroupname or mygroupname)\n"
                                "• A public group link (e.g., t.me/mygroupname)",
                                buttons=keyboard
                            )
                            return

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
                            "Please try again with a different group ID or username.",
                            buttons=keyboard
                        )
                        return

                    # Check if group already exists
                    existing_group = self.groups_collection.find_one({"user_id": user_id, "group_id": group_id})
                    if existing_group:
                        keyboard = [
                            [Button.inline("🔄 Add Different Group", data="group_action_retry")],
                            [Button.inline("❌ Cancel", data="group_action_cancel")]
                        ]
                        await progress_msg.edit(
                            f"❌ Group {group_id} is already in your list.\n"
                            "Please try adding a different group.",
                            buttons=keyboard
                        )
                        return

                    # Group is valid, add it directly without asking for interval
                    group_title = self.group_validation_cache[user_id][group_id]["title"]
                    
                    # Add group to database without interval (interval will be set during forwarding)
                    try:
                        self.groups_collection.insert_one({
                            "user_id": user_id,
                            "group_id": group_id,
                            "title": group_title,
                            "added_at": time.time()
                        })
                    except Exception as e:
                        # Handle duplicate key error or other database errors
                        if "duplicate key error" in str(e).lower() or "11000" in str(e):
                            keyboard = [
                                [Button.inline("🔄 Add Different Group", data="group_action_retry")],
                                [Button.inline("❌ Cancel", data="group_action_cancel")]
                            ]
                            await progress_msg.edit(
                                f"❌ Group {group_id} is already in your list.\n"
                                "Please try adding a different group.",
                                buttons=keyboard
                            )
                            return
                        else:
                            logger.error(f"Error adding group to database: {e}")
                            keyboard = [
                                [Button.inline("🔄 Try Again", data="group_action_retry")],
                                [Button.inline("❌ Cancel", data="group_action_cancel")]
                            ]
                            await progress_msg.edit(
                                f"❌ **Database Error**\n\n"
                                f"Failed to add group to database. Please try again.\n"
                                f"Error: {str(e)}",
                                buttons=keyboard
                            )
                            return

                    # Clear all pending data
                    del self.pending_group_actions[user_id]
                    if user_id in self.group_validation_cache:
                        del self.group_validation_cache[user_id]

                    keyboard = [
                        [Button.inline("👥 View All Groups", data="group_action_view")],
                        [Button.inline("➕ Add Another Group", data="group_action_add")],
                        [Button.inline("📤 Start Forwarding", data="forward_new")]
                    ]
                    await progress_msg.edit(
                        f"✅ **Group Added Successfully!**\n\n"
                        f"Group: {group_title}\n"
                        f"ID: `{group_id}`\n\n"
                        "The group has been added to your list. You can now forward messages to it!\n\n"
                        "What would you like to do next?",
                        buttons=keyboard
                    )

                except ValueError:
                    keyboard = [
                        [Button.inline("❓ How to Get Group ID/Username", data="group_action_help_id")],
                        [Button.inline("❌ Cancel", data="group_action_cancel")]
                    ]
                    await event.reply(
                        "❌ Invalid group ID format.\n\n"
                        "Example: `-1001234567890`",
                        buttons=keyboard
                    )
                    return

        elif action_data["action"] == "bulk_add":
            if action_data["step"] == "group_list":
                # Process bulk group addition
                group_ids = []
                usernames = []
                errors = []
                
                # Split input by new lines and process each line
                lines = text.split('\n')
                for line in lines:
                    if len(group_ids) + len(usernames) >= 10:
                        break  # Limit to 10 groups
                    
                    entry = line.strip()
                    if not entry:
                        continue  # Skip empty lines
                    elif entry.lstrip('-').isdigit():
                        # It's a group ID
                        group_id = int(entry)
                        group_ids.append(group_id)
                    elif entry.startswith('@'):
                        # It's a username
                        username = entry[1:]  # Remove the @
                        usernames.append(username)
                    elif 't.me/' in entry:
                        # It's a t.me link, extract username
                        if '+' in entry:
                            # Private group link, can't handle this
                            errors.append(f"Private group link not supported: {entry}")
                        else:
                            # Extract username from t.me link
                            if entry.startswith('https://'):
                                username = entry.replace('https://t.me/', '')
                            elif entry.startswith('http://'):
                                username = entry.replace('http://t.me/', '')
                            elif entry.startswith('t.me/'):
                                username = entry.replace('t.me/', '')
                            else:
                                # Contains t.me/ but in unexpected format
                                try:
                                    username = entry.split('t.me/')[-1]
                                except:
                                    errors.append(f"Invalid t.me link format: {entry}")
                                    continue
                            
                            # Clean up username (remove trailing slashes, parameters, etc.)
                            username = username.split('?')[0]  # Remove URL parameters
                            username = username.strip('/')  # Remove trailing slashes
                            
                            if username:
                                usernames.append(username)
                            else:
                                errors.append(f"Could not extract username from: {entry}")
                    else:
                        # Try to treat as plain username without @ prefix
                        if entry.replace('_', '').replace('-', '').isalnum():
                            usernames.append(entry)
                        else:
                            errors.append(f"Invalid entry: {entry}")

                # Resolve usernames to IDs
                for username in usernames:
                    if len(group_ids) >= 10:
                        break  # Limit to 10 groups
                    
                    group_id = await self.resolve_username_to_id(username)
                    if group_id:
                        group_ids.append(group_id)
                    else:
                        errors.append(f"Could not resolve username: {username}")

                # Remove duplicates
                group_ids = list(set(group_ids))

                if not group_ids and not errors:
                    await event.reply(
                        "❌ No valid group IDs or usernames found. Please send a list of group IDs or usernames.",
                        buttons=[[Button.inline("🔄 Try Again", data="group_action_bulk_retry"), Button.inline("❌ Cancel", data="group_action_cancel")]]
                    )
                    return

                if errors and not group_ids:
                    # All entries had errors, show them to the user
                    error_message = "❌ **All Entries Had Errors**\n\n" + "\n".join(errors[:10])  # Limit to 10 errors for readability
                    if len(errors) > 10:
                        error_message += f"\n... and {len(errors) - 10} more errors"
                    keyboard = [
                        [Button.inline("🔄 Try Again", data="group_action_bulk_retry")],
                        [Button.inline("❓ Help", data="group_action_help_id")],
                        [Button.inline("❌ Cancel", data="group_action_cancel")]
                    ]
                    await event.reply(error_message, buttons=keyboard)
                    return

                if errors and group_ids:
                    # Some entries had errors, but we have valid group IDs to process
                    logger.warning(f"Bulk add had {len(errors)} errors but {len(group_ids)} valid groups for user {user_id}")
                    # Continue processing the valid groups, errors will be shown in final result

                # Show validation progress
                progress_msg = await event.reply(
                    "🔄 Validating group access for multiple groups...\n"
                    "Please wait while I check permissions."
                )

                # Validate each group ID
                valid_groups = []
                invalid_groups = []
                for group_id in group_ids:
                    is_valid, error = await self.validate_group_id(user_id, group_id)
                    if is_valid:
                        valid_groups.append(group_id)
                    else:
                        invalid_groups.append((group_id, error))

                # Prepare result message
                result_message = "✅ **Bulk Add Results**\n\n"

                # Show parsing errors if any
                if errors:
                    result_message += f"⚠️ **Parsing Errors ({len(errors)}):**\n"
                    for error in errors[:5]:  # Show first 5 errors
                        result_message += f"• {error}\n"
                    if len(errors) > 5:
                        result_message += f"... and {len(errors) - 5} more errors\n"
                    result_message += "\n"

                if valid_groups:
                    result_message += "Successfully validated group IDs:\n"
                    for group_id in valid_groups:
                        result_message += f"• {group_id}\n"
                else:
                    result_message += "No valid group IDs found.\n"

                if invalid_groups:
                    result_message += "\n❌ Invalid group IDs:\n"
                    for group_id, error in invalid_groups:
                        result_message += f"• {group_id}: {error}\n"

                # Check for duplicates in the user's groups
                existing_groups = list(self.groups_collection.find({"user_id": user_id, "group_id": {"$in": valid_groups}}))
                existing_group_ids = [group["group_id"] for group in existing_groups]

                if existing_group_ids:
                    result_message += "\n⚠️ The following group IDs are already in your list and will be skipped:\n"
                    for group_id in existing_group_ids:
                        result_message += f"• {group_id}\n"
                    # Remove existing groups from the valid list
                    valid_groups = [gid for gid in valid_groups if gid not in existing_group_ids]

                if not valid_groups:
                    result_message += "\n❌ No new groups to add (all groups already exist)."
                    await progress_msg.edit(result_message)
                    del self.pending_group_actions[user_id]
                    return

                # Add new groups to the database
                added_groups = []
                failed_groups = []
                
                for group_id in valid_groups:
                    group_title = f"Group {group_id}"  # Default title
                    # Check if we can get the title from the group info
                    try:
                        client = self.user_clients.get(user_id)
                        if client and client.is_connected() and await client.is_user_authorized():
                            chat = await client.get_entity(group_id)
                            group_title = getattr(chat, "title", f"Group {group_id}")
                    except:
                        pass  # Ignore errors and use default title
                    
                    # Add group to the database
                    try:
                        self.groups_collection.insert_one({
                            "user_id": user_id,
                            "group_id": group_id,
                            "title": group_title,
                            "added_at": time.time()
                        })
                        added_groups.append(group_id)
                    except Exception as e:
                        # Handle duplicate key error or other database errors
                        if "duplicate key error" in str(e).lower() or "11000" in str(e):
                            failed_groups.append((group_id, "Already exists"))
                        else:
                            logger.error(f"Error adding group {group_id} to database: {e}")
                            failed_groups.append((group_id, "Database error"))

                # Finalize the message
                if added_groups:
                    result_message += f"\n✅ Successfully added {len(added_groups)} groups:\n"
                    for group_id in added_groups:
                        result_message += f"• {group_id}\n"
                
                if failed_groups:
                    result_message += f"\n❌ Failed to add {len(failed_groups)} groups:\n"
                    for group_id, error in failed_groups:
                        result_message += f"• {group_id}: {error}\n"

                # Add summary
                total_processed = len(group_ids)
                total_added = len(added_groups)
                total_failed = len(failed_groups) + len(existing_group_ids) + len(invalid_groups)
                
                result_message += f"\n📊 **Summary:**\n"
                result_message += f"• Total processed: {total_processed}\n"
                result_message += f"• Successfully added: {total_added}\n"
                result_message += f"• Failed/Skipped: {total_failed}\n"
                
                if errors:
                    result_message += f"• Parsing errors: {len(errors)}\n"

                await progress_msg.edit(result_message)

                # Clear pending actions
                del self.pending_group_actions[user_id]

            else:
                await event.reply("❌ Invalid step in bulk add process.", buttons=[[Button.inline("❌ Cancel", data="group_action_cancel")]])

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
                    "Choose how to add your group:\n\n"
                    "**Option 1: Send Username**\n"
                    "• Example: `@mygroupname`\n\n"
                    "**Option 2: Send t.me Link**\n"
                    "• Example: `https://t.me/mygroupname`\n\n"
                    "**Option 3: Send Group ID**\n"
                    "• Get ID from @username_to_id_bot\n"
                    "• Example: `-1001234567890`\n\n"
                    "*Send your group username, link, or ID:*"
                )

                keyboard = [
                    [Button.inline("❓ How to Add Groups", data="group_action_help_id")],
                    [Button.inline("❌ Cancel", data="group_action_cancel")]
                ]
                await event.edit(instructions, buttons=keyboard)
                return

            if data == "view":
                groups = await self.get_user_groups(user_id)
                if not groups:
                    keyboard = [
                        [Button.inline("➕ Add Group", data="group_action_add")],
                        [Button.inline("📥 Bulk Add Groups", data="group_action_bulk_add")],
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
                    group_title = group.get('title', f'Group {group_id}')
                    message += f"• {group_title} ({group_id})\n"
                    keyboard.append([
                        Button.inline(f"⚙️ {group_title}", data=f"group_action_manage_{group_id}")
                    ])

                message += "\nSelect a group to manage, or add new ones:"
                keyboard.extend([
                    [Button.inline("➕ Add Group", data="group_action_add"), Button.inline("📥 Bulk Add", data="group_action_bulk_add")],
                    [Button.inline("« Back to Menu", data="account_action_view")]
                ])
                
                await event.edit(message, buttons=keyboard)

            elif data == "add":
                # Start group addition process
                self.pending_group_actions[user_id] = {
                    "action": "add",
                    "step": "group_id"
                }

                instructions = (
                    "➕ **Add a New Group**\n\n"
                    "Choose how to add your group:\n\n"
                    "**Option 1: Send Username**\n"
                    "• Example: `@mygroupname`\n\n"
                    "**Option 2: Send t.me Link**\n"
                    "• Example: `https://t.me/mygroupname`\n\n"
                    "**Option 3: Send Group ID**\n"
                    "• Get ID from @username_to_id_bot\n"
                    "• Example: `-1001234567890`\n\n"
                    "*Send your group username, link, or ID:*"
                )

                keyboard = [
                    [Button.inline("❓ How to Add Groups", data="group_action_help_id")],
                    [Button.inline("❌ Cancel", data="group_action_cancel")]
                ]
                await event.edit(instructions, buttons=keyboard)

            elif data == "bulk_add":
                # Start bulk group addition process
                self.pending_group_actions[user_id] = {
                    "action": "bulk_add",
                    "step": "group_list"
                }

                instructions = (
                    "📥 **Bulk Add Multiple Groups**\n\n"
                    "Add multiple groups at once! Send your group list:\n\n"
                    "**Group IDs** (one per line): `-1001234567890`\n"
                    "**Usernames** (one per line): `@groupname` or `groupname`\n"
                    "**Mixed**: Both IDs and usernames\n\n"
                    "*Send your group list now (max 10 groups):*"
                )

                keyboard = [
                    [Button.inline("📝 Example Format", data="group_action_bulk_example")],
                    [Button.inline("❓ How to Get Group IDs", data="group_action_help_id")],
                    [Button.inline("❌ Cancel", data="group_action_cancel")]
                ]
                await event.edit(instructions, buttons=keyboard)

            elif data.startswith("manage_"):
                group_id = int(data.replace("manage_", ""))
                group = await self.get_group(user_id, group_id)
                if not group:
                    await self.show_error(event, "Group not found.")
                    return

                group_title = group.get('title', f'Group {group_id}')
                keyboard = [
                    [Button.inline("🗑️ Remove Group", data=f"group_action_remove_{group_id}")],
                    [Button.inline("« Back to Groups", data="group_action_view")]
                ]
                
                await event.edit(
                    f"⚙️ **{group_title} Settings**\n\n"
                    f"Group ID: `{group_id}`\n\n"
                    "What would you like to do?",
                    buttons=keyboard
                )

            elif data.startswith("remove_"):
                group_id = int(data.replace("remove_", ""))
                # Get group details to show title
                group = await self.get_group(user_id, group_id)
                group_title = group.get('title', f"Group {group_id}") if group else f"Group {group_id}"
                
                keyboard = [
                    [Button.inline("⚠️ Yes, Remove", data=f"group_action_confirm_remove_{group_id}")],
                    [Button.inline("❌ No, Keep", data=f"group_action_manage_{group_id}")]
                ]
                await event.edit(
                    f"⚠️ **Remove Group**\n\n"
                    f"**Group:** {group_title}\n"
                    f"**ID:** `{group_id}`\n\n"
                    "Are you sure you want to remove this group?\n"
                    "All active forwards to this group will be stopped.",
                    buttons=keyboard
                )

            elif data.startswith("confirm_remove_"):
                group_id = int(data.replace("confirm_remove_", ""))
                # Get group details before removing
                group = await self.get_group(user_id, group_id)
                group_title = group.get('title', f"Group {group_id}") if group else f"Group {group_id}"
                
                if await self.remove_group(user_id, group_id):
                    keyboard = [
                        [Button.inline("👥 View Groups", data="group_action_view")],
                        [Button.inline("➕ Add New Group", data="group_action_add")]
                    ]
                    await event.edit(
                        f"✅ **Group Removed Successfully!**\n\n"
                        f"**{group_title}** has been removed from your list.\n"
                        f"All active forwards to this group have been stopped.",
                        buttons=keyboard
                    )
                else:
                    await self.show_error(event, "Failed to remove group. Please try again.")

            elif data == "help_id":
                help_text = (
                    "❓ **How to Add Groups**\n\n"
                    "**Method 1: Username (Easiest)**\n"
                    "• Send: `@mygroupname`\n"
                    "• Works for public groups only\n\n"
                    "**Method 2: t.me Link**\n"
                    "• Send: `https://t.me/mygroupname`\n"
                    "• Works for public groups only\n\n"
                    "**Method 3: Group ID**\n"
                    "• Forward any message from your group to @username_to_id_bot\n"
                    "• Copy the ID (e.g., -1001234567890)\n"
                    "• Works for all groups (public & private)\n\n"
                    "**Note:** You must be a member of the group first!"
                )
                keyboard = [
                    [Button.inline("« Back", data="group_action_retry")],
                    [Button.inline("❌ Cancel", data="group_action_cancel")]
                ]
                await event.edit(help_text, buttons=keyboard)

            elif data == "bulk_example":
                example_text = (
                    "📝 **Bulk Add Format Examples**\n\n"
                    "**Example 1: Group IDs only**\n"
                    "```\n"
                    "-1001234567890\n"
                    "-1001234567891\n"
                    "-1001234567892\n"
                    "```\n\n"
                    "**Example 2: Usernames only**\n"
                    "```\n"
                    "@cryptogroup\n"
                    "@tradingchat\n"
                    "technews\n"
                    "```\n\n"
                    "**Example 3: t.me Links only**\n"
                    "```\n"
                    "https://t.me/cryptogroup\n"
                    "t.me/tradingchat\n"
                    "https://t.me/technews\n"
                    "```\n\n"
                    "**Example 4: Mixed format**\n"
                    "```\n"
                    "-1001234567890\n"
                    "@cryptogroup\n"
                    "https://t.me/tradingchat\n"
                    "technews\n"
                    "-1001234567892\n"
                    "```\n\n"
                    "**Tips:**\n"
                    "• One group per line\n"
                    "• Max 10 groups per batch\n"
                    "• Empty lines are ignored\n"
                    "• Mix IDs, usernames, and links freely\n"
                    "• Private links (t.me/+...) are not supported"
                )
                keyboard = [
                    [Button.inline("« Back", data="group_action_bulk_retry")],
                    [Button.inline("❌ Cancel", data="group_action_cancel")]
                ]
                await event.edit(example_text, buttons=keyboard)

            elif data == "bulk_retry":
                # Reset bulk group addition process
                self.pending_group_actions[user_id] = {
                    "action": "bulk_add",
                    "step": "group_list"
                }
                
                instructions = (
                    "➕ **Bulk Add Multiple Groups**\n\n"
                    "Send your group list in one of these formats:\n\n"
                    "**Group IDs** (one per line): `-1001234567890`\n"
                    "**Usernames** (one per line): `@groupname` or `groupname`\n"
                    "**Mixed**: Both IDs and usernames\n\n"
                    "*Send your group list now (max 10 groups):*"
                )

                keyboard = [
                    [Button.inline("📝 Example Format", data="group_action_bulk_example")],
                    [Button.inline("❓ How to Get Group IDs", data="group_action_help_id")],
                    [Button.inline("❌ Cancel", data="group_action_cancel")]
                ]
                await event.edit(instructions, buttons=keyboard)

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

    async def my_groups_command(self, event):
        """Enhanced my groups command handler"""
        user_id = event.sender_id
        if not await self.check_registered(user_id):
            await self.show_error(event, "You are not registered. Use /register first.")
            return

        groups = await self.get_user_groups(user_id)
        if not groups:
            keyboard = [
                [Button.inline("➕ Add First Group", data="group_action_add")],
                [Button.inline("📥 Bulk Add Groups", data="group_action_bulk_add")]
            ]
            await event.reply(
                "❌ You don't have any groups configured.",
                buttons=keyboard
            )
            return

        groups_message = "📋 **Your Groups**\n\n"
        keyboard = []

        for group in groups:
            group_title = group.get('title', f"Group {group['group_id']}")
            groups_message += f"🔹 **{group_title}**\n"
            groups_message += f"   ID: `{group['group_id']}`\n\n"
            
            keyboard.append([
                Button.inline(f"⚙️ {group_title}", data=f"group_action_manage_{group['group_id']}")
            ])

        keyboard.append([
            Button.inline("➕ Add New Group", data="group_action_add"),
            Button.inline("📥 Bulk Add", data="group_action_bulk_add")
        ])
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
            # Use group title if available, otherwise use group ID
            group_title = group.get('title', f"Group {group['group_id']}")
            keyboard.append([
                Button.inline(f"🗑️ {group_title}", 
                            data=f"group_action_remove_{group['group_id']}")
            ])
        keyboard.append([Button.inline("❌ Cancel", data="group_action_cancel")])

        await event.reply(
            "🗑️ **Remove Group**\n\n"
            "Select a group to remove from your list:",
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

    async def resolve_username_to_id(self, username: str) -> int:
        """Resolve a username to a group/channel ID"""
        try:
            # Use any available client to resolve the username
            for user_id, client in self.user_clients.items():
                if not client:
                    continue
                    
                try:
                    # Ensure client is connected
                    if not client.is_connected():
                        await client.connect()
                        
                    if not await client.is_user_authorized():
                        continue
                    
                    # Try to get entity by username
                    entity = await client.get_entity(username)
                    
                    # Check if it's a group or channel
                    if hasattr(entity, 'id') and (hasattr(entity, 'megagroup') or hasattr(entity, 'broadcast')):
                        # Convert to the proper group ID format
                        group_id = entity.id
                        if hasattr(entity, 'megagroup') and entity.megagroup:
                            # Supergroup - make it negative
                            group_id = -1000000000000 - entity.id
                        elif hasattr(entity, 'broadcast') and entity.broadcast:
                            # Channel - make it negative
                            group_id = -1000000000000 - entity.id
                        else:
                            # Regular group - make it negative
                            group_id = -entity.id
                            
                        return group_id
                        
                except Exception as e:
                    logger.debug(f"Failed to resolve username {username} with client {user_id}: {e}")
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"Error resolving username {username}: {e}")
            return None