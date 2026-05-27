"""
Minimal Research Service - Basic injection and FCM functionality
"""
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from bson import ObjectId

MAX_DAILY_NOTIFICATIONS = 9999     # TEMP for testing 3.4d — revert to 3 before pilot
MAX_CANDIDATES = 6                 # max pool size per cycle (news + topic fill)
MEMORY_TOPICS_LIMIT = 5            # how many recent sent topics to remember per user (for memory display)
BLOCK_LAST_N_TOPICS = 1            # don't repeat this many most-recent topics back-to-back
MEMORY_CONVERSATIONS_LIMIT = 10    # how many past conversations to read per user (3.4b)

from utils.mongodb_client import mongodb_client
from services.fcm_service import FCMService
from services.llm_service import ProactiveLogic
from heuristics import temporal

class ResearchService:
    """
    Minimal research service for testing proactive loop
    """
    
    def __init__(self):
        """Initialize research service"""
        # Provide the correct service account file path
        service_account_path = os.path.join(os.path.dirname(__file__), 'lexi-72330-firebase-adminsdk-fbsvc-49c2c6ee82.json')
        self.fcm_service = FCMService(service_account_json=service_account_path, dry_run=False)
        
        self.llm_service = ProactiveLogic()
    
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

    # === PROACTIVE CYCLE METHODS ===

    def build_candidate_pool(self) -> List[Dict]:
        """
        Build a pool of up to MAX_CANDIDATES topic-based messages per cycle.

        News-triggered candidates were removed in Phase 4.1. Heuristic-sourced
        candidates (temporal / affective / behavioural-gap) will be prepended
        here in Phase 4.3–4.5 before the topic fill runs.

        Each candidate dict has:
          trigger_source, generated_message, source ("topic"),
          topic_label, timestamp, llm_response
        """
        candidates: List[Dict] = []

        # ── Heuristic candidates will be injected here in Phase 4.3–4.5 ────

        # ── Topic-based fill (up to MAX_CANDIDATES total) ────────────────────
        topics = ["technology", "health", "travel", "culture", "sport",
                  "nature", "food", "music", "books", "cinema"]
        random.shuffle(topics)
        for topic in topics:
            if len(candidates) >= MAX_CANDIDATES:
                break
            msg = self.llm_service.generate_topic_message(topic)
            if msg:
                candidates.append({
                    "trigger_source": "topic",
                    "generated_message": msg,
                    "source": "topic",
                    "topic_label": topic,
                    "timestamp": datetime.now(),
                    "llm_response": {"should_send": True, "message": msg},
                })
                print(f"💡 Topic candidate [{topic}]: {msg}")

        print(f"🎯 Pool ready: {len(candidates)} topic candidates")
        return candidates

    def build_basic_memory(self, user: Dict) -> Dict:
        """
        3.4a: Build lightweight memory for a user with no LLM calls.
        Reads demographics from the user document and recent sent topics
        from proactive_logs. MongoDB must already be connected by the caller.
        """
        user_id = str(user["_id"])
        recent_logs = list(mongodb_client.db["proactive_logs"].find(
            {"user_id": user_id, "status": "sent"},
            sort=[("timestamp", -1)],
            limit=MEMORY_TOPICS_LIMIT
        ))
        topics_sent = [log.get("topic_label", "general") for log in recent_logs]

        return {
            "demographics": {
                "name": user.get("username", ""),
                "age": user.get("age"),
                "gender": user.get("gender"),
            },
            "topics_sent_recently": topics_sent,
        }

    def extract_conversation_memory(self, user_id: str) -> Dict:
        """
        3.4b: Read this user's last N conversations and run ONE LLM call to extract
        interests / future_mentions / conversation_insight.
        Also detects preferred_language from the message text (Hebrew vs Latin).

        Caller must hold an open MongoDB connection.
        On any failure (no conversations, query error, LLM error) returns the same
        shape with empty values so it can be merged safely with basic memory.
        """
        empty = {
            "interests": [],
            "future_mentions": [],
            "conversation_insight": "",
            "preferred_language": "he",
        }

        try:
            recent_meta = list(mongodb_client.db["metadata_conversations"].find(
                {"userId": user_id},
                sort=[("createdAt", -1)],
                limit=MEMORY_CONVERSATIONS_LIMIT,
            ))
        except Exception as e:
            print(f"⚠️  metadata_conversations query failed for {user_id}: {e}")
            return empty

        if not recent_meta:
            return empty

        all_user_messages: List[str] = []
        for meta in recent_meta:
            conv_id = str(meta["_id"])
            try:
                messages = list(mongodb_client.db["conversations"].find(
                    {"conversationId": conv_id, "role": "user"}
                ))
            except Exception as e:
                print(f"⚠️  conversations query failed for {conv_id}: {e}")
                continue
            all_user_messages.extend([
                m.get("content", "") for m in messages if m.get("content")
            ])

        if not all_user_messages:
            return empty

        # Detect language by Hebrew character ratio over the combined text
        combined = " ".join(all_user_messages)
        hebrew_chars = sum(1 for c in combined if '\u05d0' <= c <= '\u05ea')
        preferred_language = "he" if hebrew_chars > len(combined) * 0.1 else "en"

        extracted = self.llm_service.extract_user_memory(
            all_user_messages,
            preferred_language,
            today_iso=datetime.now().isoformat(timespec="minutes"),
        )
        extracted["preferred_language"] = preferred_language
        return extracted

    def save_user_memory(self, user_id: str, memory: Dict) -> bool:
        """
        3.4c: Persist the merged proactive memory on the user document so it can be
        inspected in MongoDB Atlas and reused across cycles.

        Caller must hold an open MongoDB connection.
        """
        try:
            memory_with_ts = {**memory, "last_updated": datetime.now(timezone.utc)}
            result = mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"proactiveMemory": memory_with_ts}},
            )
            return result.matched_count > 0
        except Exception as e:
            print(f"⚠️  Failed to save proactive memory for {user_id}: {e}")
            return False

    def select_message_for_user(self, candidates: List[Dict], memory: Dict) -> Optional[Dict]:
        """
        Pick the best candidate for a specific user using their basic memory.
        Blocks ONLY the last BLOCK_LAST_N_TOPICS topics from being repeated back-to-back.
        Older topics may resurface — variety is good as long as it's not consecutive.
        Falls back to candidates[0] if every available topic is currently blocked.
        """
        if not candidates:
            return None

        recent_list = memory.get("topics_sent_recently", []) or []
        # `topics_sent_recently` is sorted most-recent-first, so the head is the freshest.
        blocked = set(recent_list[:BLOCK_LAST_N_TOPICS])

        unused = [c for c in candidates if c["topic_label"] not in blocked]

        if unused:
            news = [c for c in unused if c["source"] == "news"]
            chosen = news[0] if news else unused[0]
        else:
            print(f"⚠️  All candidate topics are currently blocked, using fallback")
            chosen = candidates[0]

        print(f"🎯 Selected [{chosen['source']}:{chosen['topic_label']}] "
              f"(blocked-last: {blocked or 'none'})")
        return chosen

    def select_personalized_message(self, candidates: List[Dict], memory: Dict) -> Optional[Dict]:
        """
        3.4d: Pick a candidate (using basic memory to avoid repeats), then rewrite
        its message text via the LLM using the user's rich memory.

        Falls back to the deterministic select_message_for_user when:
          - memory has no rich signal (no interests / future_mentions / insight), or
          - the LLM personalization call fails.

        Always returns the same candidate dict shape, with `generated_message`
        possibly replaced by the personalized version. The original is preserved
        in `original_message` and a `personalized` boolean is added for logging.
        """
        chosen = self.select_message_for_user(candidates, memory)
        if not chosen:
            return None

        has_rich_signal = (
            bool(memory.get("interests")) or
            bool(memory.get("future_mentions")) or
            bool(memory.get("conversation_insight"))
        )
        if not has_rich_signal:
            return chosen

        personalized_text = self.llm_service.personalize_message_for_user(
            candidate_message=chosen.get("generated_message", ""),
            memory=memory,
        )
        if not personalized_text or not personalized_text.strip():
            return chosen

        # Return a shallow copy so we don't mutate the shared candidate pool
        result = dict(chosen)
        result["original_message"] = chosen.get("generated_message", "")
        result["generated_message"] = personalized_text.strip()
        result["personalized"] = result["generated_message"] != result["original_message"]
        # Surface which signal the LLM was told to focus on (for monitoring variety).
        result["focus"] = getattr(self.llm_service, "_last_personalization_focus", None)
        return result

    def get_proactive_users_with_rate_limit(self, cycle_id: str) -> List[Dict]:
        """Get proactive users, skipping those who already hit their daily notification cap."""
        users = self.get_all_proactive_users()

        if not users:
            return []

        eligible_users = []
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB for rate limiting")
                return []

            for user in users:
                user_id = str(user["_id"])
                username = user.get("username", "Unknown")

                # Check daily cap
                daily_count = mongodb_client.db["proactive_logs"].count_documents({
                    "user_id": user_id,
                    "status": "sent",
                    "timestamp": {"$gte": today_start}
                })

                if daily_count >= MAX_DAILY_NOTIFICATIONS:
                    print(f"⏭️  {username} hit daily cap ({daily_count}/{MAX_DAILY_NOTIFICATIONS}), skipping")
                    continue

                # Also skip if already received a message in this exact cycle
                in_cycle = mongodb_client.db["proactive_logs"].find_one({
                    "user_id": user_id,
                    "cycle_id": cycle_id,
                    "status": "sent"
                })
                if in_cycle:
                    print(f"⏭️  {username} already received message this cycle, skipping")
                    continue

                eligible_users.append(user)

        except Exception as e:
            print(f"❌ Error in rate limiting: {e}")
        finally:
            mongodb_client.disconnect()

        print(f"👥 {len(eligible_users)} eligible out of {len(users)} proactive users")
        return eligible_users
    
    def clear_stale_fcm_token(self, user_id: str, username: str):
        """Remove an invalid FCM token from MongoDB so it isn't retried."""
        try:
            if not mongodb_client.connect():
                return
            mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(user_id)},
                {"$unset": {"fcmToken": ""}, "$set": {"isProactive": False}}
            )
            print(f"🗑️  Cleared stale FCM token for {username}")
        except Exception as e:
            print(f"❌ Error clearing stale token for {username}: {e}")
        finally:
            mongodb_client.disconnect()

    def coordinated_send_and_inject(self, candidates: List[Dict], users: List[Dict], cycle_id: str) -> Dict:
        """
        For each eligible user, pick the best candidate from the pool,
        send FCM, and inject the message as firstChatSentence.
        """
        results = {
            "fcm_sent": 0,
            "fcm_failed": 0,
            "injected": 0,
            "injection_failed": 0,
            "details": []
        }

        print(f"📱 Sending to {len(users)} users from pool of {len(candidates)} candidates...")

        for user in users:
            user_id = str(user["_id"])
            username = user.get('username', 'Unknown')
            fcm_token = user["fcmToken"]

            # Build memory:
            #   3.4a — demographics + recent sent topics (no LLM)
            #   3.4b — interests / future_mentions / insight / language (one LLM call)
            #   3.4c — persist merged memory to the user document
            # All MongoDB work happens inside one connect/disconnect block.
            memory = {}
            try:
                if mongodb_client.connect():
                    basic     = self.build_basic_memory(user)
                    extracted = self.extract_conversation_memory(user_id)
                    memory    = {**basic, **extracted}

                    # ── Guard: preserve existing rich fields when LLM extraction
                    # fails (e.g. timeout) so we don't overwrite good data with
                    # empty lists. Also always carry forward fired_temporal_mentions
                    # so temporal nudges can't re-fire after a failed extraction.
                    existing_pm = user.get("proactiveMemory") or {}
                    for field in ("future_mentions", "interests", "conversation_insight"):
                        if not memory.get(field) and existing_pm.get(field):
                            memory[field] = existing_pm[field]
                    if existing_pm.get("fired_temporal_mentions"):
                        memory["fired_temporal_mentions"] = existing_pm["fired_temporal_mentions"]

                    self.save_user_memory(user_id, memory)
                    print(
                        f"🧠 Memory for {username}: "
                        f"sent={memory.get('topics_sent_recently', [])}, "
                        f"interests={memory.get('interests', [])}, "
                        f"future_mentions={len(memory.get('future_mentions') or [])}, "
                        f"lang={memory.get('preferred_language', 'he')}"
                    )
            except Exception as e:
                print(f"⚠️  Could not build memory for {username}: {e}")
            finally:
                mongodb_client.disconnect()

            # ── Phase 4.3: Temporal heuristic ────────────────────────────────
            # Check before the topic pool. If a future mention is within its
            # lead-time window, build a temporal candidate and use it directly.
            temporal_nudge = temporal.evaluate(user)
            if temporal_nudge:
                print(
                    f"🕐 Temporal heuristic fired for {username}: "
                    f"'{temporal_nudge.mention_text[:40]}' "
                    f"({temporal_nudge.hours_until:.1f}h away)"
                )
                seed = (
                    f"The user mentioned '{temporal_nudge.mention_text}' "
                    f"is coming up in about {int(temporal_nudge.hours_until)} hours."
                )
                temporal_candidate = {
                    "trigger_source": "temporal",
                    "generated_message": seed,
                    "source": "temporal",
                    "topic_label": "temporal",
                    "timestamp": datetime.now(),
                    "llm_response": {},
                }
                message = self.select_personalized_message([temporal_candidate], memory)
            else:
                # ── Default: pick + personalize from topic pool ───────────────
                message = self.select_personalized_message(candidates, memory)
            if not message:
                print(f"⚠️  No candidate available for {username}, skipping")
                continue

            tag = "✨personalized" if message.get("personalized") else "default"
            focus = message.get("focus")
            focus_str = f" focus={focus}" if focus else ""
            print(f"\n👤 {username} → [{message['source']}:{message['topic_label']}] ({tag}{focus_str}) {message['generated_message']}")
            if message.get("personalized"):
                print(f"   ↪ original was: {message.get('original_message', '')}")

            try:
                # Step 1: Send FCM notification
                from core.models import UserContext
                notification_result = self.fcm_service.send_to_user(
                    user=UserContext(
                        user_id=user_id,
                        name=username,
                        fcm_token=fcm_token
                    ),
                    body=message["generated_message"],
                    title="Lexi"
                )

                if notification_result:
                    results["fcm_sent"] += 1
                    print(f"✅ FCM sent to {username}")

                    # Step 2: Inject message only after successful FCM
                    injection_result = self.inject_prompt(user_id, message["generated_message"])

                    if injection_result:
                        results["injected"] += 1
                        print(f"💬 Message injected for {username}")

                        # Step 3: If temporal heuristic fired, stamp the mention
                        if temporal_nudge:
                            temporal.mark_fired(
                                user_id,
                                temporal_nudge.mention_text,
                                temporal_nudge.when_iso,
                                mongodb_client,
                            )

                        # Step 4: Log success (reconnect — inject_prompt closed the client)
                        self.log_proactive_event(cycle_id, user_id, message, "sent", notification_result)
                    else:
                        results["injection_failed"] += 1
                        print(f"❌ Injection failed for {username}")
                else:
                    results["fcm_failed"] += 1
                    print(f"❌ FCM failed for {username}")

            except Exception as e:
                results["fcm_failed"] += 1
                error_msg = str(e)
                print(f"❌ Error processing user {username}: {e}")

                # Auto-cleanup: stale token (app reinstalled / cache cleared)
                if "not found" in error_msg.lower() or "registration-token-not-registered" in error_msg.lower():
                    print(f"🗑️  Stale token detected for {username} — removing from DB")
                    self.clear_stale_fcm_token(user_id, username)

        return results
    
    def log_proactive_event(self, cycle_id: str, user_id: str, message: Dict, status: str, notification_id: str = None):
        """Log proactive event for research analysis"""
        try:
            if not mongodb_client.connect():
                print("❌ Could not connect to MongoDB for logging")
                return

            log_entry = {
                "cycle_id": cycle_id,
                "timestamp": datetime.now(timezone.utc),
                "user_id": user_id,
                "trigger_source": message.get("trigger_source", "topic"),
                "generated_message": message["generated_message"],
                "topic_label": message.get("topic_label", "general"),
                "status": status,
                "notification_id": notification_id,
                "llm_response": message.get("llm_response", {})
            }

            mongodb_client.db["proactive_logs"].insert_one(log_entry)

        except Exception as e:
            print(f"❌ Error logging proactive event: {e}")
        finally:
            mongodb_client.disconnect()
    
    def run_full_proactive_cycle(self) -> Dict:
        """Main orchestrator for proactive research cycle"""
        cycle_id = str(uuid.uuid4())
        start_time = datetime.now()

        print(f"\n=== 🚀 Starting Proactive Cycle {cycle_id[:8]}... ===")

        try:
            # Step 1: Build candidate pool (news + topic fill)
            candidates = self.build_candidate_pool()

            if not candidates:
                print("❌ Could not build any candidates")
                return {"success": False, "message": "No candidates generated"}

            # Step 2: Get eligible users (rate-limit checked)
            eligible_users = self.get_proactive_users_with_rate_limit(cycle_id)

            if not eligible_users:
                print("❌ No eligible users found")
                return {"success": False, "message": "No eligible users found"}

            # Step 3: Send and inject (per-user candidate selection inside)
            results = self.coordinated_send_and_inject(candidates, eligible_users, cycle_id)

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
                "candidates_built": len(candidates),
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
