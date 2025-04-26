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