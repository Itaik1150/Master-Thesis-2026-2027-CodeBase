"""
Research Service - Proactive Notification Orchestration
"""
import os
from datetime import datetime
from typing import List, Optional
from core.models import UserContext
from core.data_loader import UserDataLoader
from services.fcm_service import FCMService
from utils.mongodb_client import mongodb_client

class ResearchService:
    """
    Orchestrates proactive research experiments including:
    - Random user assignment (isProactive)
    - Prompt injection for research
    - FCM notification delivery
    """
    
    def __init__(self):
        """Initialize research service with dependencies"""
        self.data_loader = UserDataLoader()
        self.fcm_service = FCMService()
    
    def get_proactive_users(self) -> List[UserContext]:
        """Get all proactive users with FCM tokens"""
        return self.data_loader.get_users_with_fcm_tokens()
    
    def inject_prompt_and_notify(self, user_id: str, custom_message: str, 
                                notification_title: str = "Research Update",
                                notification_body: str = "Check your conversation!") -> Optional[str]:
        """
        Inject custom prompt and send FCM notification
        
        Args:
            user_id: MongoDB user ID
            custom_message: New firstChatSentence for prompt injection
            notification_title: FCM notification title
            notification_body: FCM notification body
            
        Returns:
            FCM message ID if successful, None otherwise
        """
        print(f"=== Prompt Injection Research ===")
        print(f"Target User: {user_id}")
        print(f"Custom Message: {custom_message}")
        
        # 1. Update user's agent firstChatSentence
        injection_success = mongodb_client.update_user_first_message(user_id, custom_message)
        
        if injection_success:
            print(f"+ Prompt injection successful for user {user_id}")
            
            # 2. Get user context for FCM
            user_data = mongodb_client.get_user_context(user_id)
            if not user_data or not user_data.get('fcmToken'):
                print(f"X No FCM token found for user {user_id}")
                return None
            
            user_context = UserContext(
                user_id=user_data.get('_id'),
                name=user_data.get('username', 'Unknown'),
                fcm_token=user_data.get('fcmToken', '')
            )
            
            # 3. Send FCM notification
            message_id = self.fcm_service.send_to_user(
                user=user_context,
                title=notification_title,
                body=notification_body
            )
            
            if message_id:
                print(f"+ FCM notification sent! Message ID: {message_id}")
                return message_id
            else:
                print("X FCM notification failed")
                return None
        else:
            print(f"X Prompt injection failed for user {user_id}")
            return None
    
    def run_proactive_experiment(self, custom_message: str) -> dict:
        """
        Run proactive experiment on all proactive users
        
        Args:
            custom_message: Custom prompt to inject
            
        Returns:
            Experiment results summary
        """
        print(f"=== Running Proactive Experiment ===")
        print(f"Custom Message: {custom_message}")
        
        proactive_users = self.get_proactive_users()
        
        if not proactive_users:
            return {
                "total_users": 0,
                "successful_injections": 0,
                "successful_notifications": 0,
                "message": "No proactive users found with FCM tokens"
            }
        
        print(f"Found {len(proactive_users)} proactive users")
        
        successful_injections = 0
        successful_notifications = 0
        
        for user in proactive_users:
            print(f"\nProcessing user: {user.name}")
            
            message_id = self.inject_prompt_and_notify(
                user_id=user.user_id,
                custom_message=custom_message,
                notification_title="Research Experiment Active",
                notification_body=f"Hi {user.name}! Your conversation has been updated with a research prompt."
            )
            
            if message_id:
                successful_injections += 1
                successful_notifications += 1
        
        results = {
            "total_users": len(proactive_users),
            "successful_injections": successful_injections,
            "successful_notifications": successful_notifications,
            "timestamp": datetime.now().isoformat(),
            "custom_message": custom_message
        }
        
        print(f"\n=== Experiment Results ===")
        print(f"Total Users: {results['total_users']}")
        print(f"Successful Injections: {results['successful_injections']}")
        print(f"Successful Notifications: {results['successful_notifications']}")
        
        return results
    
    def get_research_statistics(self) -> dict:
        """Get current research statistics"""
        # Get all users with FCM tokens
        all_users_data = mongodb_client.get_users_with_fcm_tokens()
        
        if not all_users_data:
            return {
                "total_users_with_fcm": 0,
                "proactive_users": 0,
                "control_users": 0,
                "proactive_percentage": 0
            }
        
        proactive_count = sum(1 for user in all_users_data if user.get('isProactive', False))
        control_count = len(all_users_data) - proactive_count
        
        return {
            "total_users_with_fcm": len(all_users_data),
            "proactive_users": proactive_count,
            "control_users": control_count,
            "proactive_percentage": round((proactive_count / len(all_users_data)) * 100, 2),
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
research_service = ResearchService()
