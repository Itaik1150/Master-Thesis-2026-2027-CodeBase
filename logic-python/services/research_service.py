"""
Minimal Research Service - Basic injection and FCM functionality
"""
import os
from utils.mongodb_client import mongodb_client
from services.fcm_service import FCMService

class ResearchService:
    """
    Minimal research service for testing proactive loop
    """
    
    def __init__(self):
        """Initialize research service"""
        # Provide the correct service account file path
        service_account_path = os.path.join(os.path.dirname(__file__), 'lexi-72330-firebase-adminsdk-fbsvc-49c2c6ee82.json')
        self.fcm_service = FCMService(service_account_json=service_account_path, dry_run=False)
    
    def inject_prompt(self, user_id: str, message: str) -> bool:
        """
        Inject message into agent.firstChatSentence
        
        Args:
            user_id: MongoDB user ID
            message: Simple string message to inject
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB")
                return False
            
            # Update agent.firstChatSentence with simple string
            result = mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": user_id},
                {"$set": {"agent.firstChatSentence": message}}
            )
            
            # Use matched_count to detect if user was found and updated
            if result.matched_count > 0:
                if result.modified_count > 0:
                    print(f"✅ Successfully injected message for user {user_id}")
                    print(f"📝 Message: '{message}'")
                else:
                    print(f"ℹ️ Message already exists for user {user_id} (no change needed)")
                return True
            else:
                print(f"❌ User {user_id} not found in database")
                return False
                
        except Exception as e:
            print(f"❌ Error injecting prompt: {e}")
            return False
        finally:
            mongodb_client.disconnect()
    
    def send_notification(self, user_id: str, message: str) -> bool:
        """
        Send FCM notification to user
        
        Args:
            user_id: MongoDB user ID
            message: Message content for notification
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get user data from MongoDB
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB")
                return False
            
            user_data = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": user_id})
            
            if not user_data:
                print(f"❌ User {user_id} not found")
                return False
            
            fcm_token = user_data.get('fcmToken', '')
            username = user_data.get('username', 'Unknown')
            
            if not fcm_token:
                print(f"❌ No FCM token for user {username}")
                return False
            
            # Send FCM notification
            notification_title = "📰 New Message Available"
            notification_body = f"Hi {username}! You have a new message waiting."
            
            result = self.fcm_service.send_to_token(
                token=fcm_token,
                body=f"{notification_title}: {notification_body}"
            )
            
            if result:
                print(f"✅ FCM notification sent to {username}")
                return True
            else:
                print(f"❌ Failed to send FCM to {username}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending notification: {e}")
            return False
        finally:
            mongodb_client.disconnect()
    
    def get_all_proactive_users(self):
        """
        Get all proactive users with FCM tokens
        
        Returns:
            List of proactive users with FCM tokens
        """
        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB")
                return []
            
            # Find all users with isProactive: true and fcmToken exists
            proactive_users = list(mongodb_client.db[mongodb_client.users_collection].find({
                "isProactive": True,
                "fcmToken": {"$exists": True, "$ne": ""}
            }))
            
            print(f"📊 Found {len(proactive_users)} proactive users with FCM tokens")
            return proactive_users
            
        except Exception as e:
            print(f"❌ Error fetching proactive users: {e}")
            return []
        finally:
            mongodb_client.disconnect()
    
    def run_proactive_cycle(self, message: str) -> dict:
        """
        Run complete proactive cycle: inject message and send FCM to all proactive users
        
        Args:
            message: Message to inject and send
            
        Returns:
            Dictionary with results
        """
        try:
            # Get all proactive users
            proactive_users = self.get_all_proactive_users()
            
            if not proactive_users:
                print("❌ No proactive users found")
                return {
                    "success": False,
                    "message": "No proactive users found",
                    "injected_count": 0,
                    "notification_count": 0
                }
            
            print(f"🚀 Starting proactive cycle for {len(proactive_users)} users...")
            print(f"📝 Message: '{message}'")
            
            injected_count = 0
            notification_count = 0
            
            # Process each user
            for user in proactive_users:
                user_id = user['_id']
                username = user.get('username', 'Unknown')
                
                print(f"\n👤 Processing user: {username}")
                
                # Inject message
                injection_success = self.inject_prompt(user_id, message)
                if injection_success:
                    injected_count += 1
                    print(f"✅ Injection successful for {username}")
                else:
                    print(f"❌ Injection failed for {username}")
                
                # Send notification
                notification_success = self.send_notification(user_id, message)
                if notification_success:
                    notification_count += 1
                    print(f"✅ FCM sent to {username}")
                else:
                    print(f"❌ FCM failed for {username}")
            
            results = {
                "success": True,
                "message": f"Processed {len(proactive_users)} proactive users",
                "total_users": len(proactive_users),
                "injected_count": injected_count,
                "notification_count": notification_count
            }
            
            print(f"\n🎯 Cycle Complete!")
            print(f"📊 Results: {injected_count}/{len(proactive_users)} injected, {notification_count}/{len(proactive_users)} notifications sent")
            
            return results
            
        except Exception as e:
            print(f"❌ Error in proactive cycle: {e}")
            return {
                "success": False,
                "message": f"Error: {e}",
                "injected_count": 0,
                "notification_count": 0
            }
    
    def diagnose_user(self, user_id: str):
        """
        Diagnose user data and configuration issues
        
        Args:
            user_id: MongoDB user ID
        """
        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB")
                return
            
            user_data = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": user_id})
            
            if not user_data:
                print(f"❌ User {user_id} not found in database")
                return
            
            print(f"\n🔍 User Diagnosis for: {user_data.get('username', 'Unknown')}")
            print(f"📋 User ID: {user_id}")
            print(f"📱 FCM Token: {'✅ Present' if user_data.get('fcmToken') else '❌ Missing'}")
            print(f"🔔 isProactive: {user_data.get('isProactive', False)}")
            
            # Check agent structure
            agent = user_data.get('agent', {})
            print(f"🤖 Agent exists: {'✅ Yes' if agent else '❌ No'}")
            
            if agent:
                print(f"💬 firstChatSentence: '{agent.get('firstChatSentence', 'N/A')}'")
                print(f"📝 Agent fields: {list(agent.keys())}")
            
            # Check FCM token format
            fcm_token = user_data.get('fcmToken', '')
            if fcm_token:
                print(f"📱 FCM Token length: {len(fcm_token)}")
                print(f"📱 FCM Token format: {'✅ Valid length' if len(fcm_token) > 50 else '❌ Too short'}")
            
        except Exception as e:
            print(f"❌ Error diagnosing user: {e}")
        finally:
            mongodb_client.disconnect()
    
    def test_fcm_connection(self):
        """Test FCM service connection and configuration"""
        try:
            print(f"\n🔍 FCM Service Diagnosis")
            print(f"📱 Dry run mode: {self.fcm_service.dry_run}")
            
            # Test with a dummy token
            test_token = "test_token_12345"
            test_title = "Test Notification"
            test_body = "This is a test message"
            
            print(f"🧪 Testing FCM with dummy token...")
            
            try:
                result = self.fcm_service.send_to_token(test_token, test_title, test_body)
                print(f"✅ FCM service initialized successfully")
                print(f"📊 Test result: {result}")
            except Exception as e:
                print(f"❌ FCM service error: {e}")
                print(f"🔧 Check Firebase service account configuration")
                
        except Exception as e:
            print(f"❌ Error testing FCM: {e}")
    
    def check_user_token_distribution(self):
        """Check distribution of users with and without FCM tokens"""
        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB")
                return
            
            print(f"\n🔍 User Token Distribution Analysis")
            
            # Count all users
            total_users = mongodb_client.db[mongodb_client.users_collection].count_documents({})
            print(f"📊 Total users: {total_users}")
            
            # Count proactive users
            proactive_users = mongodb_client.db[mongodb_client.users_collection].count_documents({"isProactive": True})
            print(f"🔔 Proactive users: {proactive_users}")
            
            # Count users with FCM tokens
            users_with_tokens = mongodb_client.db[mongodb_client.users_collection].count_documents({
                "fcmToken": {"$exists": True, "$ne": ""}
            })
            print(f"📱 Users with FCM tokens: {users_with_tokens}")
            
            # Count proactive users with FCM tokens
            proactive_with_tokens = mongodb_client.db[mongodb_client.users_collection].count_documents({
                "isProactive": True,
                "fcmToken": {"$exists": True, "$ne": ""}
            })
            print(f"🎯 Proactive users with tokens: {proactive_with_tokens}")
            
            # Show sample users without tokens
            users_without_tokens = list(mongodb_client.db[mongodb_client.users_collection].find({
                "fcmToken": {"$exists": False}
            }).limit(3))
            
            if users_without_tokens:
                print(f"\n📋 Sample users WITHOUT FCM tokens:")
                for user in users_without_tokens:
                    username = user.get('username', 'Unknown')
                    is_proactive = user.get('isProactive', False)
                    user_id = user.get('_id', 'Unknown')
                    print(f"   👤 {username} (ID: {user_id}) - Proactive: {is_proactive}")
            
            # Show sample users with tokens
            users_with_tokens_list = list(mongodb_client.db[mongodb_client.users_collection].find({
                "fcmToken": {"$exists": True, "$ne": ""}
            }).limit(3))
            
            if users_with_tokens_list:
                print(f"\n📋 Sample users WITH FCM tokens:")
                for user in users_with_tokens_list:
                    username = user.get('username', 'Unknown')
                    is_proactive = user.get('isProactive', False)
                    user_id = user.get('_id', 'Unknown')
                    token_length = len(user.get('fcmToken', ''))
                    print(f"   👤 {username} (ID: {user_id}) - Proactive: {is_proactive} - Token: {token_length} chars")
                
        except Exception as e:
            print(f"❌ Error checking token distribution: {e}")
        finally:
            mongodb_client.disconnect()
    
    def check_mongodb_schema(self):
        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB")
                return
            
            print(f"\n🔍 MongoDB Schema Check")
            print(f"📊 Database: {mongodb_client.db_name}")
            print(f"📋 Collection: {mongodb_client.users_collection}")
            
            # Check a sample user
            sample_user = mongodb_client.db[mongodb_client.users_collection].find_one()
            
            if sample_user:
                print(f"👤 Sample user: {sample_user.get('username', 'Unknown')}")
                print(f"📋 User fields: {list(sample_user.keys())}")
                
                agent = sample_user.get('agent', {})
                if agent:
                    print(f"🤖 Agent fields: {list(agent.keys())}")
                    print(f"💬 firstChatSentence type: {type(agent.get('firstChatSentence', 'N/A'))}")
                else:
                    print(f"❌ No agent field found")
            else:
                print(f"❌ No users found in collection")
                
        except Exception as e:
            print(f"❌ Error checking schema: {e}")
        finally:
            mongodb_client.disconnect()

# Singleton instance
research_service = ResearchService()
