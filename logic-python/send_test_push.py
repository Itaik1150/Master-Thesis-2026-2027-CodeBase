"""
Test script to verify MongoDB integration and FCM notification sending
"""
import os
import sys
from datetime import datetime
from core.models import UserContext
from core.data_loader import UserDataLoader
from services.fcm_service import FCMService
from utils.mongodb_client import mongodb_client

def main():
    """Test MongoDB integration and FCM notification sending"""
    print("=== MongoDB Integration Test ===")
    
    # Initialize MongoDB connection
    if not mongodb_client.connect():
        print("X Failed to connect to MongoDB")
        return
    
    # Initialize data loader
    loader = UserDataLoader()
    
    # Get users with FCM tokens
    users = loader.get_users_with_fcm_tokens()
    # print(users)
    
    if not users:
        print("X No users found with FCM tokens")
        return
    
    print(f"+ Found {len(users)} users with FCM tokens")
    
    # Find user 'your' (or any user with FCM token)
    test_user = None
    for user in users:
        if 'your' in user.name.lower() or user.user_id == 'your':
            test_user = user
            break
    
    if not test_user:
        print("X No test user 'your' found, using first user with FCM token")
        test_user = users[0]
    
    print(f"Test User: {test_user.name}")
    print(f"FCM Token: {test_user.fcm_token[:20]}...")
    
    # Initialize FCM service
    fcm_service = FCMService()
    
    # Send test notification
    try:
        message_id = fcm_service.send_to_user(
            user=test_user,
            title="Thesis Test",
            body="Hello Itai! Proactive system is working!"
        )
        
        if message_id:
            print(f"+ Test notification sent successfully! Message ID: {message_id}")
        else:
            print("X Failed to send test notification")
            
    except Exception as e:
        print(f"X Error sending test notification: {e}")
    
    # Disconnect from MongoDB
    mongodb_client.disconnect()
    print("=== Test Complete ===")

if __name__ == "__main__":
    main()
