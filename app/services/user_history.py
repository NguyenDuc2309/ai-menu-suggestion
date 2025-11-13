"""User history service for tracking previously suggested dishes."""
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta


class UserHistoryService:
    """Service for tracking user's previously suggested dishes."""
    
    def __init__(self):
        """Initialize in-memory storage for user history."""
        # Format: {user_id: {"dishes": [dish_names], "timestamp": unix_timestamp}}
        self._history: Dict[str, Dict] = {}
        self._max_history_days = 7  # Auto-cleanup after 7 days
    
    def add_dishes(self, user_id: str, dishes: List[str]) -> None:
        """
        Add dishes to user's history.
        
        Args:
            user_id: Unique identifier for the user
            dishes: List of dish names to add
        """
        if not user_id or not dishes:
            return
        
        current_time = time.time()
        
        if user_id in self._history:
            # Append to existing history
            existing_dishes = self._history[user_id]["dishes"]
            existing_dishes.extend(dishes)
            # Keep only last 20 dishes to prevent memory bloat
            self._history[user_id]["dishes"] = existing_dishes[-20:]
            self._history[user_id]["timestamp"] = current_time
        else:
            # Create new history entry
            self._history[user_id] = {
                "dishes": dishes,
                "timestamp": current_time
            }
        
        # Cleanup old entries
        self._cleanup_old_entries()
    
    def get_recent_dishes(self, user_id: str, limit: int = 10) -> List[str]:
        """
        Get user's recently suggested dishes.
        
        Args:
            user_id: Unique identifier for the user
            limit: Maximum number of recent dishes to return
            
        Returns:
            List of recent dish names (most recent first)
        """
        if not user_id or user_id not in self._history:
            return []
        
        dishes = self._history[user_id]["dishes"]
        # Return most recent dishes (last items in list)
        return dishes[-limit:][::-1]  # Reverse to get most recent first
    
    def _cleanup_old_entries(self) -> None:
        """Remove history entries older than max_history_days."""
        current_time = time.time()
        cutoff_time = current_time - (self._max_history_days * 24 * 60 * 60)
        
        # Find users to remove
        users_to_remove = []
        for user_id, data in self._history.items():
            if data["timestamp"] < cutoff_time:
                users_to_remove.append(user_id)
        
        # Remove old entries
        for user_id in users_to_remove:
            del self._history[user_id]
        
        if users_to_remove:
            print(f"[USER_HISTORY] Cleaned up {len(users_to_remove)} old user history entries")
    
    def clear_history(self, user_id: str) -> None:
        """
        Clear history for a specific user.
        
        Args:
            user_id: Unique identifier for the user
        """
        if user_id in self._history:
            del self._history[user_id]
    
    def get_all_users_count(self) -> int:
        """Get total number of users with history."""
        return len(self._history)


# Singleton instance
_user_history_service: Optional[UserHistoryService] = None


def get_user_history_service() -> UserHistoryService:
    """Get or create user history service instance."""
    global _user_history_service
    if _user_history_service is None:
        _user_history_service = UserHistoryService()
    return _user_history_service

