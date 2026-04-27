"""
Minimal Research Service - Basic injection and FCM functionality
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bson import ObjectId

from utils.mongodb_client import mongodb_client
from services.fcm_service import FCMService
from services.news_service import NewsService
from services.llm_service import ProactiveLogic

class ResearchService:
    """
    Minimal research service for testing proactive loop
    """
    
    def __init__(self):
        """Initialize research service"""
        # Provide the correct service account file path
        service_account_path = os.path.join(os.path.dirname(__file__), 'lexi-72330-firebase-adminsdk-fbsvc-49c2c6ee82.json')
        self.fcm_service = FCMService(service_account_json=service_account_path, dry_run=False)
        
        # Initialize new services
        self.news_service = NewsService()
        self.llm_service = ProactiveLogic()
        
        # Timing and caching attributes
        self.last_news_fetch = None
        self.news_fetch_interval = 30 * 60  # 30 minutes in seconds
        self.cached_headlines = []
        self.headline_cache_expiry = None
    
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
            print(f"🔍 Looking for user with ID: {user_id}")
            print(f"🔍 Type of user_id: {type(user_id)}")
            
            result = mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(user_id)},
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
            
            user_data = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": ObjectId(str(user_id))})
            
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
            
            user_data = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": ObjectId(str(user_id))})
            
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

    # === NEW PROACTIVE CYCLE METHODS ===
    
    def should_fetch_news(self) -> bool:
        """Check if enough time has passed since last news fetch"""
        if not self.last_news_fetch:
            return True
        return (datetime.now() - self.last_news_fetch).total_seconds() > self.news_fetch_interval
    
    def get_fresh_headlines(self) -> List[str]:
        """Get fresh headlines or return cached if still valid"""
        if self.should_fetch_news():
            print("📰 Fetching fresh headlines...")
            headlines_data = self.news_service.fetch_israel_headlines(max_results=5)
            self.cached_headlines = [h['title'] for h in headlines_data]
            self.last_news_fetch = datetime.now()
            self.headline_cache_expiry = datetime.now() + timedelta(hours=1)
            print(f"✅ Fetched {len(self.cached_headlines)} fresh headlines")
        else:
            print(f"📋 Using cached headlines ({len(self.cached_headlines)} available)")
        
        return self.cached_headlines
    
    def process_headlines(self, headlines: List[str]) -> List[Dict]:
        """Process headlines through LLM and return approved messages"""
        approved_messages = []
        
        for headline in headlines:
            print(f"🧠 Analyzing: {headline}")
            analysis = self.llm_service.analyze_headline(headline)
            
            if analysis.get("should_send"):
                approved_messages.append({
                    "original_headline": headline,
                    "generated_message": analysis["message"],
                    "timestamp": datetime.now(),
                    "llm_response": analysis
                })
                print(f"✅ Approved: {analysis['message']}")
            else:
                print(f"❌ Rejected: Not suitable for proactive messaging")
        
        return approved_messages
    
    def select_best_message(self, approved_messages: List[Dict]) -> Optional[Dict]:
        """Select the single best message based on social potential"""
        if not approved_messages:
            return None
        
        # For now, select the first approved message
        # In future, could implement scoring based on message length, keywords, etc.
        best_message = approved_messages[0]
        print(f"🎯 Selected best message: {best_message['generated_message']}")
        return best_message
    
    def get_proactive_users_with_rate_limit(self, cycle_id: str) -> List[Dict]:
        """Get proactive users with rate limiting (one message per cycle)"""
        users = self.get_all_proactive_users()
        
        if not users:
            return []
        
        eligible_users = []
        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB for rate limiting")
                return []
            
            for user in users:
                user_id = str(user["_id"])
                
                # Check if user already received message in this cycle
                recent_message = mongodb_client.db["proactive_logs"].find_one({
                    "user_id": user_id,
                    "cycle_id": cycle_id,
                    "status": "sent"
                })
                
                if not recent_message:
                    eligible_users.append(user)
                else:
                    print(f"⏭️ User {user.get('username')} already received message this cycle")
                    
        except Exception as e:
            print(f"❌ Error in rate limiting: {e}")
        finally:
            mongodb_client.disconnect()
        
        print(f"👥 Found {len(eligible_users)} eligible users out of {len(users)} total proactive users")
        return eligible_users
    
    def coordinated_send_and_inject(self, message: Dict, users: List[Dict], cycle_id: str) -> Dict:
        """Coordinate FCM send with database injection"""
        results = {
            "fcm_sent": 0,
            "fcm_failed": 0,
            "injected": 0,
            "injection_failed": 0,
            "details": []
        }
        
        print(f"📱 Sending FCM notifications to {len(users)} users...")
        
        for user in users:
            user_id = str(user["_id"])
            fcm_token = user["fcmToken"]
            
            try:
                # Step 1: Send FCM notification
                from core.models import UserContext
                notification_result = self.fcm_service.send_to_user(
                    user=UserContext(
                        user_id=user_id,
                        name=user.get('username', 'Unknown'),
                        fcm_token=fcm_token
                    ),
                    body=message["generated_message"],
                    title="נושא שיחה חדש"
                )
                
                if notification_result:
                    results["fcm_sent"] += 1
                    print(f"✅ FCM sent to {user.get('username')}")
                    
                    # Step 2: Inject message only after successful FCM
                    injection_result = self.inject_prompt(user_id, message["generated_message"])
                    
                    if injection_result:
                        results["injected"] += 1
                        print(f"💬 Message injected for {user.get('username')}")
                        
                        # Step 3: Log success
                        self.log_proactive_event(cycle_id, user_id, message, "sent", notification_result)
                    else:
                        results["injection_failed"] += 1
                        print(f"❌ Injection failed for {user.get('username')}")
                        
                else:
                    results["fcm_failed"] += 1
                    print(f"❌ FCM failed for {user.get('username')}")
                    
            except Exception as e:
                results["fcm_failed"] += 1
                print(f"❌ Error processing user {user.get('username')}: {e}")
        
        return results
    
    def log_proactive_event(self, cycle_id: str, user_id: str, message: Dict, status: str, notification_id: str = None):
        """Log proactive event for research analysis"""
        try:
            log_entry = {
                "cycle_id": cycle_id,
                "timestamp": datetime.now(),
                "user_id": user_id,
                "original_headline": message["original_headline"],
                "generated_message": message["generated_message"],
                "status": status,
                "notification_id": notification_id,
                "llm_response": message.get("llm_response", {})
            }
            
            mongodb_client.db["proactive_logs"].insert_one(log_entry)
            
        except Exception as e:
            print(f"❌ Error logging proactive event: {e}")
    
    def run_full_proactive_cycle(self) -> Dict:
        """Main orchestrator for proactive research cycle"""
        cycle_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        print(f"\n=== 🚀 Starting Proactive Cycle {cycle_id[:8]}... ===")
        
        try:
            # Step 1: Get fresh headlines
            headlines = self.get_fresh_headlines()
            
            if not headlines:
                print("❌ No headlines available")
                return {"success": False, "message": "No headlines available"}
            
            # Step 2: Process through LLM — retry with fresh fetch if all rejected
            approved_messages = self.process_headlines(headlines)

            if not approved_messages:
                print("⚠️ First batch rejected — fetching fresh headlines and retrying...")
                self.last_news_fetch = None  # bypass cache
                headlines = self.get_fresh_headlines()
                approved_messages = self.process_headlines(headlines)

            if not approved_messages:
                print("⚠️ News rejected — generating topic-based message as fallback...")
                import random
                fallback_topics = [
                    "artificial intelligence", "travel", "food and cooking",
                    "music", "books", "sport", "movies", "nature",
                ]
                topic = random.choice(fallback_topics)
                print(f"🎲 Selected topic: {topic}")
                fallback_message = self.llm_service.generate_topic_message(topic)
                if fallback_message:
                    approved_messages = [{
                        "original_headline": f"[topic fallback: {topic}]",
                        "generated_message": fallback_message,
                        "timestamp": datetime.now(),
                        "llm_response": {"should_send": True, "message": fallback_message}
                    }]
                    print(f"✅ Fallback message: {fallback_message}")
                else:
                    print("❌ No messages approved by LLM after retry and fallback")
                    return {"success": False, "message": "No messages approved by LLM"}
            
            # Step 3: Select single best message (one per cycle)
            best_message = self.select_best_message(approved_messages)
            
            if not best_message:
                print("❌ No best message selected")
                return {"success": False, "message": "No best message selected"}
            
            # Step 4: Get eligible users
            eligible_users = self.get_proactive_users_with_rate_limit(cycle_id)
            
            if not eligible_users:
                print("❌ No eligible users found")
                return {"success": False, "message": "No eligible users found"}
            
            # Step 5: Send and inject
            results = self.coordinated_send_and_inject(best_message, eligible_users, cycle_id)
            
            # Step 6: Log cycle completion
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n✅ Proactive Cycle Complete!")
            print(f"📊 Results: {results['fcm_sent']} FCM sent, {results['injected']} injected")
            print(f"⏱️ Duration: {duration:.2f} seconds")
            
            return {
                "success": True,
                "cycle_id": cycle_id,
                "results": results,
                "duration": duration,
                "message_used": best_message
            }
            
        except Exception as e:
            print(f"❌ Proactive cycle failed: {e}")
            return {
                "success": False,
                "cycle_id": cycle_id,
                "error": str(e)
            }

# Singleton instance
research_service = ResearchService()
