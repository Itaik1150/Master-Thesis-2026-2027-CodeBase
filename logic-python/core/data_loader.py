from datetime import datetime, timedelta
from core.models import UserContext
from utils.mongodb_client import mongodb_client

class UserDataLoader:
    def __init__(self):
        """Initialize with MongoDB connection"""
        if not mongodb_client.connect():
            raise Exception("Failed to connect to MongoDB")
    
    def get_user_context(self, user_id: str) -> UserContext:
        """Get single user context from MongoDB"""
        user_data = mongodb_client.get_user_context(user_id)
        
        if user_data is None:
            raise Exception(f"User {user_id} not found")
            
        return UserContext(
            user_id=user_data.get('_id', user_id),
            name=user_data.get('username', 'Unknown'),
            fcm_token=user_data.get('fcmToken', ''),
            last_interaction=datetime.now() - timedelta(hours=28),
            interests=["Sports", "Music"],  # Default interests, could be enhanced later
        )
    
    def get_users_with_fcm_tokens(self):
        """Get all users with valid FCM tokens"""
        users_data = mongodb_client.get_users_with_fcm_tokens()
        
        users = []
        for user_data in users_data:
            user_context = UserContext(
                user_id=user_data.get('_id'),
                name=user_data.get('username'),
                fcm_token=user_data.get('fcmToken', ''),
            )
            users.append(user_context)
            
        return users
