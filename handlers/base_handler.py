from telethon import events
from telethon.tl.custom import Button
import logging
from typing import Optional, Any, Dict, List, Union

logger = logging.getLogger(__name__)

class BaseHandler:
    """Base handler class with common functionality for all handlers"""
    
    def __init__(self, bot, users_collection, groups_collection):
        self.bot = bot
        self.users_collection = users_collection
        self.groups_collection = groups_collection
        # State management
        self._user_states = {}  # {user_id: {"state": str, "data": dict}}
        self._pending_actions = {}  # {user_id: {"action": str, "step": str, "data": dict}}
        self._forward_handler = None  # Reference to forward handler

    async def register_handlers(self):
        """Register command handlers - to be implemented by subclasses"""
        raise NotImplementedError

    async def check_registered(self, user_id: int) -> Optional[dict]:
        """Check if a user is registered and return their data"""
        return self.users_collection.find_one({"user_id": user_id})

    async def get_user_groups(self, user_id: int) -> List[dict]:
        """Get all groups for a user"""
        return list(self.groups_collection.find({"user_id": user_id}))

    def set_user_state(self, user_id: int, state: str, data: Dict[str, Any] = None):
        """Set user state with optional data"""
        self._user_states[user_id] = {
            "state": state,
            "data": data or {}
        }

    def get_user_state(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get current user state and data"""
        return self._user_states.get(user_id)

    def clear_user_state(self, user_id: int):
        """Clear user state"""
        if user_id in self._user_states:
            del self._user_states[user_id]

    def set_pending_action(self, user_id: int, action: str, step: str, data: Dict[str, Any] = None):
        """Set a pending action for a user"""
        self._pending_actions[user_id] = {
            "action": action,
            "step": step,
            "data": data or {}
        }

    def get_pending_action(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get pending action for a user"""
        return self._pending_actions.get(user_id)

    def clear_pending_action(self, user_id: int):
        """Clear pending action for a user"""
        if user_id in self._pending_actions:
            del self._pending_actions[user_id]

    async def show_error(self, event, message: str, show_help: bool = False):
        """Show error message with optional help button"""
        keyboard = []
        if show_help:
            keyboard.append([Button.inline("❓ Get Help", data="help_category_issues")])
        keyboard.append([Button.inline("🔄 Try Again", data="action_retry")])
        
        await event.reply(
            f"❌ **Error**\n\n{message}",
            buttons=keyboard
        )

    def create_confirm_buttons(self, confirm_data: str, cancel_data: str) -> List[List[Button]]:
        """Create standard confirmation buttons"""
        return [
            [
                Button.inline("✅ Confirm", data=confirm_data),
                Button.inline("❌ Cancel", data=cancel_data)
            ]
        ]

    async def show_success(self, event, message: str, buttons: List[List[Button]] = None):
        """Show success message with optional buttons"""
        await event.reply(
            f"✅ **Success**\n\n{message}",
            buttons=buttons
        )

    async def handle_error(self, update, exception, error_message: str = None):
        """Handle error messages and log exception"""
        logger.error(f"Exception: {exception}")
        if isinstance(update, events.CallbackQuery.Event):
            await update.answer(
                message=error_message or str(exception),
                alert=True
            )
        else:
            await update.reply(
                f"❌ Error: {error_message or str(exception)}\n\n"
                "If you need help, use /help command or contact support."
            )

    def validate_input(self, 
                      value: Any, 
                      validators: List[callable],
                      error_messages: List[str]) -> tuple[bool, Optional[str]]:
        """Validate input using a list of validator functions"""
        for validator, error_msg in zip(validators, error_messages):
            try:
                if not validator(value):
                    return False, error_msg
            except Exception:
                return False, error_msg
        return True, None

    async def handle_timeout(self, event, action: str):
        """Handle timeout for user actions"""
        keyboard = [
            [Button.inline("🔄 Try Again", data=f"action_retry_{action}")],
            [Button.inline("❌ Cancel", data="action_cancel")]
        ]
        
        await event.reply(
            "⏳ **Session Timeout**\n\n"
            "Your session has expired. Please try again.",
            buttons=keyboard
        )
        
        # Clear any pending state
        user_id = event.sender_id
        self.clear_user_state(user_id)
        self.clear_pending_action(user_id)

    async def create_navigation_buttons(self, 
                                     items: List[Any],
                                     page: int,
                                     page_size: int,
                                     callback_prefix: str) -> List[List[Button]]:
        """Create navigation buttons for paginated lists"""
        total_pages = (len(items) + page_size - 1) // page_size
        
        nav_buttons = []
        
        # Add item buttons for current page
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(items))
        for idx in range(start_idx, end_idx):
            item = items[idx]
            nav_buttons.append([
                Button.inline(
                    f"📝 Item {idx + 1}", 
                    data=f"{callback_prefix}_select_{idx}"
                )
            ])
        
        # Add navigation row
        nav_row = []
        if page > 0:
            nav_row.append(
                Button.inline("« Prev", data=f"{callback_prefix}_page_{page-1}")
            )
        nav_row.append(
            Button.inline(f"📄 {page + 1}/{total_pages}", data=f"{callback_prefix}_info")
        )
        if page < total_pages - 1:
            nav_row.append(
                Button.inline("Next »", data=f"{callback_prefix}_page_{page+1}")
            )
        
        if nav_row:
            nav_buttons.append(nav_row)
        
        return nav_buttons

    async def format_time_ago(self, timestamp: float) -> str:
        """Format a timestamp as a human-readable time ago string"""
        from time import time
        
        diff = time() - timestamp
        
        if diff < 60:
            return "just now"
        elif diff < 3600:
            minutes = int(diff / 60)
            return f"{minutes}m ago"
        elif diff < 86400:
            hours = int(diff / 3600)
            return f"{hours}h ago"
        else:
            days = int(diff / 86400)
            return f"{days}d ago"
    
    def create_menu_buttons(self, 
                          options: List[tuple[str, str]], 
                          columns: int = 2) -> List[List[Button]]:
        """Create a menu with buttons arranged in columns"""
        buttons = []
        row = []
        
        for label, callback in options:
            row.append(Button.inline(label, data=callback))
            if len(row) == columns:
                buttons.append(row)
                row = []
        
        if row:  # Add any remaining buttons
            buttons.append(row)
            
        return buttons

    async def validate_user_session(self, user_id: int, user_clients: dict) -> tuple[bool, str]:
        """
        Validate if user's session is working properly
        Returns (is_valid, error_message)
        """
        try:
            # Check if user is registered
            user_data = await self.check_registered(user_id)
            if not user_data:
                return False, "You are not registered. Please use /register first."
            
            # Check if user has a client
            client = user_clients.get(user_id)
            if not client:
                logger.warning(f"No client found for user {user_id}")
                return False, "Your session is not active. Please use /register to update your session."
            
            # Check if client is connected
            if not client.is_connected():
                logger.info(f"Attempting to connect client for user {user_id}")
                try:
                    await client.connect()
                except Exception as e:
                    logger.error(f"Failed to connect client for user {user_id}: {e}")
                    return False, "Failed to connect to Telegram. Please use /register to update your session."
            
            # Check if client is authorized
            try:
                is_authorized = await client.is_user_authorized()
                if not is_authorized:
                    logger.error(f"Client not authorized for user {user_id}")
                    # Use comprehensive cleanup
                    await self.cleanup_user_on_session_error(user_id, user_clients)
                    return False, "Your session has expired or become invalid. All active forwards have been stopped. Please use /register to update your session."
                
                # Try to get user info to verify session is working
                try:
                    me = await client.get_me()
                    if not me:
                        return False, "Unable to verify your account. Please use /register to update your session."
                except Exception as e:
                    logger.error(f"Failed to get user info for {user_id}: {e}")
                    return False, "Your session appears to be invalid. Please use /register to update your session."
                
                return True, None
                
            except Exception as e:
                logger.error(f"Session validation failed for user {user_id}: {e}")
                error_msg = str(e).lower()
                if any(keyword in error_msg for keyword in ['auth_key', 'unauthorized', 'session', 'invalid']):
                    # Use comprehensive cleanup for session-related errors
                    await self.cleanup_user_on_session_error(user_id, user_clients)
                    return False, "Your session has become invalid. All active forwards have been stopped. This can happen when:\n• You logged in from another device\n• Your IP address changed\n• The session expired\n\nPlease use /register to update your session."
                else:
                    return False, f"Session validation error: {str(e)}\n\nPlease try again or use /register if the issue persists."
                
        except Exception as e:
            logger.error(f"Unexpected error validating session for user {user_id}: {e}")
            return False, "An unexpected error occurred while validating your session. Please try again or use /register."

    async def show_session_error(self, event, error_message: str, show_register_button: bool = True):
        """Show session-related error with appropriate action buttons"""
        keyboard = []
        if show_register_button:
            keyboard.append([Button.inline("🔄 Update Session", data="account_action_update_session")])
        keyboard.extend([
            [Button.inline("❓ Get Help", data="help_category_sessions")],
            [Button.inline("🔙 Back to Menu", data="main_menu")]
        ])
        
        await event.reply(
            f"❌ **Session Error**\n\n{error_message}",
            buttons=keyboard
        )

    async def require_valid_session(self, event, user_id: int, user_clients: dict, operation_name: str = "this operation"):
        """
        Require a valid session for an operation. Shows error if session is invalid.
        Returns True if session is valid, False if invalid (and shows error to user)
        """
        is_valid, error_msg = await self.validate_user_session(user_id, user_clients)
        if not is_valid:
            await self.show_session_error(
                event, 
                f"{error_msg}\n\n**Operation:** {operation_name}\n\n"
                "Once you update your session, you can try this operation again."
            )
            return False
        return True

    async def cleanup_user_on_session_error(self, user_id: int, user_clients: dict, forward_handler=None):
        """
        Clean up all user data when session becomes invalid
        This should be called from session validation when a session is determined to be invalid
        """
        try:
            # Remove the invalid client
            if user_id in user_clients:
                try:
                    client = user_clients[user_id]
                    if client.is_connected():
                        await client.disconnect()
                except:
                    pass
                del user_clients[user_id]
                logger.info(f"Removed invalid client for user {user_id}")
            
            # Clean up forwarding data if forward handler is available
            if forward_handler and hasattr(forward_handler, 'cleanup_user_forwards_on_session_error'):
                await forward_handler.cleanup_user_forwards_on_session_error(user_id)
                
                # Notify user about complete cleanup
                try:
                    await forward_handler.bot.send_message(
                        user_id,
                        "🔄 **Session Cleanup Complete**\n\n"
                        "❌ **All your active forwards have been stopped** due to session issues.\n\n"
                        "What happened:\n"
                        "• Your session became invalid\n"
                        "• All active forwarding tasks were stopped\n"
                        "• All forwarding data was cleared\n\n"
                        "**Next steps:**\n"
                        "1️⃣ Update your session using the button below\n"
                        "2️⃣ Set up forwarding again\n\n"
                        "This ensures your account security and prevents failed operations.",
                        buttons=[
                            [Button.inline("🔄 Update Session", data="account_action_update_session")],
                            [Button.inline("❓ Session Help", data="help_category_sessions")],
                            [Button.inline("📖 User Guide", data="help_category_guide")]
                        ]
                    )
                except Exception as notify_error:
                    logger.error(f"Failed to notify user {user_id} about session cleanup: {notify_error}")
                    
        except Exception as e:
            logger.error(f"Error in cleanup_user_on_session_error for user {user_id}: {e}")

    def set_forward_handler_reference(self, forward_handler):
        """Set reference to forward handler for session cleanup"""
        self._forward_handler = forward_handler

    async def validate_user_session_with_cleanup(self, user_id: int, user_clients: dict) -> tuple[bool, str]:
        """
        Enhanced session validation that includes forwarding cleanup when session is invalid
        """
        is_valid, error_msg = await self.validate_user_session(user_id, user_clients)
        if not is_valid and hasattr(self, '_forward_handler') and self._forward_handler:
            # Clean up forwarding data if session is invalid
            await self.cleanup_user_on_session_error(user_id, user_clients, self._forward_handler)
        return is_valid, error_msg