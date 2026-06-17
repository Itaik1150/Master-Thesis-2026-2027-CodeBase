"""
Minimal Research Service - Basic injection and FCM functionality
"""
import os
import random
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from bson import ObjectId
import requests as http_requests

MAX_DAILY_NOTIFICATIONS = 9999     # TEMP for testing 3.4d — revert to 3 before pilot
MAX_CANDIDATES = 6                 # max pool size per cycle (news + topic fill)
MEMORY_TOPICS_LIMIT = 5            # how many recent sent topics to remember per user (for memory display)
BLOCK_LAST_N_TOPICS = 1            # don't repeat this many most-recent topics back-to-back
MEMORY_CONVERSATIONS_LIMIT = 10    # how many past conversations to read per user (3.4b)

LEXI_SERVER_URL  = os.getenv("LEXI_SERVER_URL", "https://lexi-server-1rx9.onrender.com")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://master-thesis-2026-2027-code-base.vercel.app")

# ── Conference Demo Bypass ────────────────────────────────────────────────────
DEMO_EXPERIMENT_ID = "6a32e516d3d79d396942bff3"

DEMO_MESSAGES = [
    {"send_after": "2026-06-12T14:00:00", "text": "DEMO MSG 1 PLACEHOLDER"},
    {"send_after": "2026-06-13T16:00:00", "text": "DEMO MSG 2 PLACEHOLDER"},
    {"send_after": "2026-06-14T11:00:00", "text": "DEMO MSG 3 PLACEHOLDER"},
]
# ─────────────────────────────────────────────────────────────────────────────

from utils.mongodb_client import mongodb_client
from services.fcm_service import FCMService
from services.llm_service import ProactiveLogic
from heuristics import temporal, affective, behavioural_gap
from core.models import NudgeContext

class ResearchService:
    """
    Minimal research service for testing proactive loop
    """
    
    def __init__(self):
        """Initialize research service"""
        # Credentials: SERVICE_ACCOUNT_JSON_CONTENT on Render, or local JSON file via env/path
        self.fcm_service = FCMService(dry_run=False)
        
        self.llm_service = ProactiveLogic()
    
    # How long (hours) the proactive firstChatSentence stays before reverting.
    PROMPT_EXPIRY_HOURS = float(os.getenv("PROMPT_EXPIRY_HOURS", "2"))

    def inject_prompt(self, user_id: str, message: str) -> bool:
        """
        Overwrite agent.firstChatSentence with the proactive message.
        Also saves the original sentence and a reset timestamp (now + PROMPT_EXPIRY_HOURS)
        in proactiveMemory so expire_injected_prompts() can restore it later.
        """
        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB")
                return False

            user = mongodb_client.db[mongodb_client.users_collection].find_one(
                {"_id": ObjectId(user_id)},
                {"agent.firstChatSentence": 1, "proactiveMemory.injected_prompt_original": 1},
            )
            if not user:
                print(f"❌ inject_prompt: user {user_id} not found")
                return False

            # Preserve the true default greeting across multiple injections:
            # if there's already a saved original (from a previous un-reset injection),
            # keep it so we never overwrite the real default with another proactive message.
            existing_original = (user.get("proactiveMemory") or {}).get("injected_prompt_original")
            original = existing_original if existing_original else (user.get("agent") or {}).get("firstChatSentence", "")
            reset_after = datetime.now(timezone.utc) + timedelta(hours=self.PROMPT_EXPIRY_HOURS)

            mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "agent.firstChatSentence": message,
                    "proactiveMemory.injected_prompt_original": original,
                    "proactiveMemory.injected_prompt_reset_after": reset_after,
                }},
            )
            return True

        except Exception as e:
            print(f"❌ Error injecting prompt: {e}")
            return False
        finally:
            mongodb_client.disconnect()

    def expire_injected_prompts(self) -> None:
        """
        Called at the start of every cycle.
        For any user whose injected prompt expiry time has passed,
        restore firstChatSentence to the saved original value.
        """
        try:
            if not mongodb_client.connect():
                return

            now = datetime.now(timezone.utc)
            expired_users = list(mongodb_client.db[mongodb_client.users_collection].find(
                {"proactiveMemory.injected_prompt_reset_after": {"$lte": now}},
                {"_id": 1, "username": 1,
                 "proactiveMemory.injected_prompt_original": 1},
            ))

            for u in expired_users:
                original = (u.get("proactiveMemory") or {}).get("injected_prompt_original", "")
                mongodb_client.db[mongodb_client.users_collection].update_one(
                    {"_id": u["_id"]},
                    {
                        "$set":  {"agent.firstChatSentence": original},
                        "$unset": {
                            "proactiveMemory.injected_prompt_original": "",
                            "proactiveMemory.injected_prompt_reset_after": "",
                        },
                    },
                )
                print(f"⏰ Reset expired prompt for {u.get('username', u['_id'])}")

        except Exception as e:
            print(f"⚠️  expire_injected_prompts error: {e}")
        finally:
            try:
                mongodb_client.disconnect()
            except Exception:
                pass
    
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
        Get all proactive users with FCM tokens whose experiment has proactive enabled.
        Joins users → experiments to filter out experiments where proactive is disabled.
        """
        try:
            if not mongodb_client.connect():
                print("❌ Failed to connect to MongoDB")
                return []

            # Step 1: find all experiment IDs that have proactiveSettings.enabled = true
            enabled_experiments = list(mongodb_client.db["experiments"].find(
                {"experimentFeatures.proactiveSettings.enabled": True},
                {"_id": 1}
            ))
            enabled_ids = [exp["_id"] for exp in enabled_experiments]

            if not enabled_ids:
                print("📊 No experiments with proactive enabled")
                return []

            # experimentId may be stored as a string or as an ObjectId depending on
            # how the client saved it — include both forms to be safe.
            id_variants = []
            for eid in enabled_ids:
                id_variants.append(str(eid))
                id_variants.append(eid)  # ObjectId form

            # Step 2: find users in those experiments with a token where the
            # isProactive field was never set (field missing entirely).
            # These are users who registered before proactive was enabled on
            # the experiment — heal them first, then query the proper set.
            unset_result = mongodb_client.db[mongodb_client.users_collection].update_many(
                {
                    "experimentId": {"$in": id_variants},
                    "fcmToken": {"$exists": True, "$ne": ""},
                    "isProactive": {"$exists": False},
                },
                {"$set": {"isProactive": True}},
            )
            if unset_result.modified_count > 0:
                print(f"🔧 Auto-set isProactive=True for {unset_result.modified_count} user(s) missing the field")

            # Step 3: fetch only users who are explicitly marked proactive=true.
            # Users set to false (e.g. via dashboard toggle) are excluded.
            # Also exclude users in the 'reactive' proactive group (no notifications).
            # Demo experiment users are handled exclusively by run_oxford_demo_cycle().
            demo_id_variants = [DEMO_EXPERIMENT_ID, ObjectId(DEMO_EXPERIMENT_ID)]
            proactive_users = list(mongodb_client.db[mongodb_client.users_collection].find({
                "experimentId": {"$in": id_variants, "$nin": demo_id_variants},
                "fcmToken": {"$exists": True, "$ne": ""},
                "isProactive": True,
                "proactiveGroup": {"$ne": "reactive"},  # Exclude reactive group
            }))

            print(f"📊 Found {len(proactive_users)} proactive users with FCM tokens "
                  f"(across {len(enabled_ids)} proactive experiment(s))")
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
        # topics = ["technology", "health", "travel", "culture", "sport",
        #           "nature", "food", "music", "books", "cinema"]
        topics = ["technology"]
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
        
        **NEW:** Only extracts emotional_memories from messages that haven't been 
        analyzed yet (analyzed_for_memory != True). Marks those messages as 
        analyzed_for_memory: True after successful extraction.
        
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

        # NEW: Call with unanalyzed_only=True to skip re-analyzing and mark as analyzed
        extracted = self.llm_service.extract_user_memory(
            all_user_messages,
            preferred_language,
            today_iso=datetime.now().isoformat(timespec="minutes"),
            unanalyzed_only=True,
            mongodb_client=mongodb_client,
            user_id=user_id,
        )
        extracted["preferred_language"] = preferred_language
        return extracted

    def save_user_memory(self, user_id: str, memory: Dict) -> bool:
        """
        3.4c: Persist the merged proactive memory on the user document so it can be
        inspected in MongoDB Atlas and reused across cycles.

        Caller must hold an open MongoDB connection.
        Uses flattened $set for all fields and $push with $each for emotional_memories
        to avoid MongoDB path conflicts.
        """
        try:
            emotional_memories = memory.pop("emotional_memories", [])
            now_utc = datetime.now(timezone.utc)
            
            # Flatten $set to avoid "Updating the path 'proactiveMemory' would create a conflict" error.
            # MongoDB requires setting individual nested fields, not the parent, when using $push on a sibling.
            set_doc = {
                "proactiveMemory.interests": memory.get("interests", []),
                "proactiveMemory.future_mentions": memory.get("future_mentions", []),
                "proactiveMemory.conversation_insight": memory.get("conversation_insight", ""),
                "proactiveMemory.sensitivity_score": memory.get("sensitivity_score", 1),
                "proactiveMemory.demographics": memory.get("demographics", {}),
                "proactiveMemory.topics_sent_recently": memory.get("topics_sent_recently", []),
                "proactiveMemory.preferred_language": memory.get("preferred_language", "he"),
                "proactiveMemory.fired_temporal_mentions": memory.get("fired_temporal_mentions", []),
                "proactiveMemory.pending_affective_followup": memory.get("pending_affective_followup"),
                "proactiveMemory.last_affective_analyzed_msg_count": memory.get("last_affective_analyzed_msg_count"),
                "proactiveMemory.open_intents": memory.get("open_intents", []),
                "proactiveMemory.pending_gap_followup": memory.get("pending_gap_followup"),
                "proactiveMemory.last_intent_scan_conversation_id": memory.get("last_intent_scan_conversation_id"),
                "proactiveMemory.injected_prompt_original": memory.get("injected_prompt_original"),
                "proactiveMemory.injected_prompt_reset_after": memory.get("injected_prompt_reset_after"),
                "proactiveMemory.last_updated": now_utc,
            }
            
            update_doc = {"$set": set_doc}
            
            # Append new emotional memories instead of replacing
            if emotional_memories:
                update_doc["$push"] = {"proactiveMemory.emotional_memories": {"$each": emotional_memories}}
            
            result = mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(user_id)},
                update_doc,
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
            chosen = candidates[0]

        print(f"🎯 Selected [{chosen['source']}:{chosen['topic_label']}]")
        return chosen

    def _personalize_context(self, ctx: NudgeContext) -> Dict:
        """
        Strict Context Isolation (PROACTIVE_NOTIFICATIONS.md § 3a).

        Takes the winning heuristic's isolated NudgeContext, runs the LLM
        personalization on it (the LLM sees ONLY ctx — never the full
        proactiveMemory), and returns the standard candidate dict shape used
        downstream (inject / FCM / logging).

        On any LLM failure the seed_message is used verbatim, so the cycle never
        breaks.
        """
        seed = (ctx.seed_message or "").strip()

        try:
            text = self.llm_service.personalize_from_context(ctx)
        except Exception as e:
            print(f"❌ _personalize_context error: {e}")
            text = seed
        text = (text or seed).strip()

        return {
            "trigger_source": ctx.trigger_source,
            "source": ctx.source,
            "topic_label": ctx.topic_label,
            "generated_message": text,
            "original_message": seed,
            "personalized": bool(text) and text != seed,
            "focus": ctx.trigger_source,
            "timestamp": datetime.now(),
            "llm_response": {},
        }

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

    def _reset_first_chat_sentence(self, user: dict) -> None:
        """
        Restore user.agent.firstChatSentence to the canonical value from the
        agents collection, clearing the proactive override written by inject_prompt.
        Called after _create_conversation (success or failure) so the proactive
        message is never re-used as the opener for manually-started conversations.
        """
        try:
            agent = user.get("agent") or {}
            agent_id = agent.get("_id")
            if not agent_id:
                return
            if not mongodb_client.connect():
                return
            canonical = mongodb_client.db["agents"].find_one(
                {"_id": ObjectId(str(agent_id))},
                {"firstChatSentence": 1},
            )
            if not canonical:
                return
            original = canonical.get("firstChatSentence", "")
            mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(str(user["_id"]))},
                {"$set": {"agent.firstChatSentence": original}},
            )
        except Exception as e:
            print(f"⚠️  _reset_first_chat_sentence failed: {e}")
        finally:
            try:
                mongodb_client.disconnect()
            except Exception:
                pass

    def _create_conversation(self, user_id: str, experiment_id: str, num_conversations: int) -> Optional[str]:
        """
        Pre-creates a conversation on the Lexi server so we can send its ID
        in the FCM data payload for deep-linking.
        Returns the conversationId string, or None on any failure.
        Must be called AFTER inject_prompt so firstChatSentence is already set.
        """
        try:
            resp = http_requests.post(
                f"{LEXI_SERVER_URL}/conversations/create",
                json={
                    "userId": user_id,
                    "experimentId": experiment_id,
                    "numberOfConversations": num_conversations,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                conversation_id = resp.text.strip().strip('"')
                return conversation_id
            elif resp.status_code == 403:
                print(f"⚠️  Conversation limit reached for user {user_id} — skipping pre-create")
            else:
                print(f"⚠️  /conversations/create returned {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"⚠️  _create_conversation failed for user {user_id}: {e}")
        return None

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
            proactive_group = user.get('proactiveGroup', 'generic')  # Default to generic for existing users

            # ── Load experiment heuristic settings for this user ──────────────
            # Defaults: all heuristics ON, model = env-configured LLM
            heuristic_flags = {"temporal": True, "affective": True, "behaviouralGap": True}
            experiment_llm_model = None  # None → fall back to env LLM_MODEL
            try:
                experiment_id = user.get("experimentId")
                if experiment_id and mongodb_client.connect():
                    exp_doc = mongodb_client.db["experiments"].find_one(
                        {"_id": ObjectId(str(experiment_id))},
                        {"experimentFeatures.proactiveSettings": 1},
                    )
                    if exp_doc:
                        ps = (exp_doc.get("experimentFeatures") or {}).get("proactiveSettings") or {}
                        if ps.get("heuristics"):
                            heuristic_flags.update(ps["heuristics"])
                        if ps.get("llmModel"):
                            experiment_llm_model = ps["llmModel"]
            except Exception as e:
                print(f"⚠️  Could not load experiment settings for {username}: {e}")
            finally:
                try:
                    mongodb_client.disconnect()
                except Exception:
                    pass

            if experiment_llm_model:
                self.llm_service.override_model(experiment_llm_model)

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
                    # empty lists. Also carry forward heuristic-managed fields
                    # (fired_temporal_mentions, pending_affective_followup,
                    # last_analyzed_conversation_id) which are written by the
                    # heuristic modules themselves and must survive memory saves.
                    existing_pm = user.get("proactiveMemory") or {}
                    for field in ("future_mentions", "interests", "conversation_insight", "emotional_memories"):
                        if not memory.get(field) and existing_pm.get(field):
                            memory[field] = existing_pm[field]
                    
                    # Special handling for emotional_memories: merge new with existing unused ones
                    if memory.get("emotional_memories") and existing_pm.get("emotional_memories"):
                        existing_unused = [mem for mem in existing_pm["emotional_memories"] if not mem.get("used", False)]
                        new_memories = memory["emotional_memories"]
                        # Combine and deduplicate by content
                        seen_content = set()
                        merged_memories = []
                        for mem_list in [existing_unused, new_memories]:
                            for mem in mem_list:
                                content = mem.get("content", "").strip()
                                if content and content not in seen_content:
                                    merged_memories.append(mem)
                                    seen_content.add(content)
                        memory["emotional_memories"] = merged_memories
                    for field in (
                        "fired_temporal_mentions",
                        "pending_affective_followup",
                        "last_affective_analyzed_msg_count",
                        "open_intents",
                        "pending_gap_followup",
                        "last_intent_scan_conversation_id",
                    ):
                        if existing_pm.get(field):
                            memory[field] = existing_pm[field]

                    self.save_user_memory(user_id, memory)
                    print(
                        f"🧠 [{username}] interests={len(memory.get('interests') or [])} "
                        f"future_mentions={len(memory.get('future_mentions') or [])} "
                        f"lang={memory.get('preferred_language', 'he')}"
                    )
            except Exception as e:
                print(f"⚠️  Could not build memory for {username}: {e}")
            finally:
                mongodb_client.disconnect()

            # ── Phase 4.3–4.5: Heuristics — priority: affective → gap → temporal → topic
            #
            # Step 1 (side-effects): run scans that may schedule future nudges.
            # These only write to MongoDB and never fire a message on their own.
            # Each scan is gated by the per-experiment heuristic flags.
            if heuristic_flags.get("affective", True):
                affective.analyze_and_schedule(user, mongodb_client, self.llm_service)
            if heuristic_flags.get("behaviouralGap", True):
                behavioural_gap.scan_for_gaps(user, mongodb_client, self.llm_service)

            # Step 2: reload proactiveMemory from MongoDB before evaluate().
            # The user dict was loaded at the START of the cycle, before save_user_memory
            # and the heuristic scans wrote new data.  Without a reload, evaluate()
            # would read stale state — e.g. future_mentions saved this cycle would be
            # invisible to temporal.evaluate(), and pending followups written by the
            # scans would be missed entirely.
            # ALSO: Update the in-memory `memory` dict so generate_affective_default()
            # sees fresh emotional_memories from the heuristic scans.
            try:
                if mongodb_client.connect():
                    fresh_doc = mongodb_client.db[mongodb_client.users_collection].find_one(
                        {"_id": ObjectId(user_id)},
                        {"proactiveMemory": 1},
                    )
                    if fresh_doc:
                        fresh_pm = fresh_doc.get("proactiveMemory") or {}
                        user = {**user, "proactiveMemory": fresh_pm}
                        # Also update the in-memory memory dict to prevent stale data
                        # from being used by generate_affective_default()
                        memory.update(fresh_pm)
            except Exception as e:
                print(f"⚠️  Could not reload proactiveMemory for {username}: {e}")
            finally:
                mongodb_client.disconnect()

            # Step 3: check if any heuristic should fire RIGHT NOW.
            # Evaluate all three before branching so we can log clearly.
            # Each evaluate is gated by the per-experiment heuristic flags.
            affective_nudge = affective.evaluate(user)      if heuristic_flags.get("affective", True)      else None
            gap_nudge       = behavioural_gap.evaluate(user) if heuristic_flags.get("behaviouralGap", True) else None
            temporal_nudge  = temporal.evaluate(user)       if heuristic_flags.get("temporal", True)       else None

            memory_pm = user.get("proactiveMemory") or {}
            print(
                f"\n🔎 [{username}] affective={'🔥' if affective_nudge else '—'} "
                f"gap={'🔥' if gap_nudge else '—'} "
                f"temporal={'🔥' if temporal_nudge else '—'} "
                f"| future_mentions={len(memory_pm.get('future_mentions') or [])} "
                f"open_intents={len(memory_pm.get('open_intents') or [])}"
            )

            # ── Strict Context Isolation (PROACTIVE_NOTIFICATIONS.md § 3a) ──
            # The ONE winning heuristic builds a self-contained NudgeContext
            # carrying only the fields its message needs. The LLM never sees the
            # full proactiveMemory, so unrelated signals can't bleed in.
            name = (memory.get("demographics") or {}).get("name") or username
            language = memory.get("preferred_language", "he")

            if affective_nudge:
                print(
                    f"💛 Affective heuristic fired for {username}: "
                    f"{affective_nudge.emotion} ({affective_nudge.intensity:.2f})"
                )
                seed = (
                    f"The user seemed {affective_nudge.emotion} in their last "
                    f"conversation. Send a warm, gentle check-in in the user's language."
                )
                ctx = NudgeContext(
                    trigger_source="affective",
                    name=name,
                    preferred_language=language,
                    seed_message=seed,
                    topic_label="affective",
                    source="affective",
                    payload={
                        "emotion": affective_nudge.emotion,
                        "intensity": affective_nudge.intensity,
                        "insight": memory.get("conversation_insight", ""),
                    },
                )
                message = self._personalize_context(ctx)

            elif gap_nudge:
                print(
                    f"🔍 Behavioural-gap heuristic fired for {username}: "
                    f"'{gap_nudge.intent_text[:50]}'"
                )
                seed = (
                    f"The user said they planned to '{gap_nudge.intent_text}' "
                    f"but hasn't mentioned it since. Ask gently how it went, "
                    f"in the user's language."
                )
                ctx = NudgeContext(
                    trigger_source="behavioural_gap",
                    name=name,
                    preferred_language=language,
                    seed_message=seed,
                    topic_label="behavioural_gap",
                    source="behavioural_gap",
                    payload={"intent_text": gap_nudge.intent_text},
                )
                message = self._personalize_context(ctx)

            elif temporal_nudge:
                print(
                    f"🕐 Temporal heuristic fired for {username}: "
                    f"'{temporal_nudge.mention_text[:40]}' "
                    f"({temporal_nudge.hours_until:.1f}h away)"
                )
                seed = (
                    f"The user mentioned '{temporal_nudge.mention_text}' "
                    f"is coming up in about {int(temporal_nudge.hours_until)} hours."
                )
                ctx = NudgeContext(
                    trigger_source="temporal",
                    name=name,
                    preferred_language=language,
                    seed_message=seed,
                    topic_label="temporal",
                    source="temporal",
                    payload={
                        "mention_text": temporal_nudge.mention_text,
                        "hours_until": round(temporal_nudge.hours_until, 1),
                    },
                )
                message = self._personalize_context(ctx)

            else:
                # ── No heuristic fired: use existing topic-based logic (will be overridden by gatekeeper) ─
                chosen = self.select_message_for_user(candidates, memory)
                if chosen:
                    ctx = NudgeContext(
                        trigger_source="topic",
                        name=name,
                        preferred_language=language,
                        seed_message=chosen.get("generated_message", ""),
                        topic_label=chosen.get("topic_label", "topic"),
                        source=chosen.get("source", "topic"),
                        payload={"topic_label": chosen.get("topic_label", "topic")},
                    )
                    message = self._personalize_context(ctx)
                else:
                    message = None
            
            # ── GATEKEEPER: Proactive Group Safety Filter ────────────────────────────
            # Respect which heuristics are on/off via dashboard, BUT apply final group override
            
            if proactive_group == 'reactive':
                # Reactive group: NEVER send proactive notifications
                print(f"🚫 [{username}] Reactive group - aborting proactive notification")
                continue
                
            elif proactive_group == 'generic':
                # Generic group: Override with standard assistant prompt (zero emotional weight)
                print(f"🔄 [{username}] Generic group override - replacing with standard invitation")
                seed = f"Hi {name}, I'm here if you'd like to chat today."
                ctx = NudgeContext(
                    trigger_source="generic_override",
                    name=name,
                    preferred_language=language,
                    seed_message=seed,
                    topic_label="generic_standard",
                    source="generic",
                    payload={"group": "generic"},
                )
                # Use personalize_from_context with generic framing
                system_prompt = (
                    f"You are a standard assistant. Generate a completely generic, "
                    f"standard invitation to chat in {'Hebrew' if language == 'he' else 'English'} with zero emotional weight "
                    f"and no specific topics (max 15 words). You MAY use the user's name once. "
                    f"Return ONLY the final message."
                )
                user_prompt = f"USER NAME: {name}\n\nGenerate a friendly but neutral chat invitation."
                
                msgs = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                try:
                    generic_text = self.llm_service._call_llm(msgs, temperature=0.3, max_tokens=50)
                    if (generic_text.startswith('"') and generic_text.endswith('"')):
                        generic_text = generic_text[1:-1].strip()
                    message = {
                        "trigger_source": "generic_override",
                        "source": "generic",
                        "topic_label": "generic_standard", 
                        "generated_message": generic_text or f"Hi {name}, how are you today?",
                        "personalized": False,
                    }
                except Exception as e:
                    print(f"⚠️ Generic override LLM error: {e}")
                    message = {
                        "trigger_source": "generic_override",
                        "source": "generic", 
                        "topic_label": "generic_standard",
                        "generated_message": f"Hi {name}, how are you today?",
                        "personalized": False,
                    }
                
            elif proactive_group == 'affective':
                # Affective group: Use affective heuristic for strict emotional framing
                if not (affective_nudge or gap_nudge or temporal_nudge):
                    # No heuristic fired - use affective default generator
                    print(f"🧠 [{username}] Affective group - generating empathetic default")
                    affective_result = affective.generate_affective_default(memory, name, user_id, self.llm_service, mongodb_client)
                    message = {
                        "trigger_source": affective_result["trigger_source"],
                        "source": affective_result["source"],
                        "topic_label": affective_result["topic_label"],
                        "generated_message": affective_result["generated_message"],
                        "personalized": affective_result["personalized"],
                        "has_context": affective_result["has_context"],
                    }
                # If heuristic already fired, keep the existing message (already processed above)
            if not message:
                print(f"⚠️  No candidate available for {username}, skipping")
                continue

            tag = "✨personalized" if message.get("personalized") else "default"
            focus = message.get("focus")
            focus_str = f" focus={focus}" if focus else ""
            print(f"\n👤 {username} [group:{proactive_group}] → [{message['source']}:{message['topic_label']}] ({tag}{focus_str}) {message['generated_message']}")
            if message.get("personalized"):
                print(f"   ↪ original was: {message.get('original_message', '')}")

            try:
                from core.models import UserContext

                # Step 1: Set firstChatSentence on the user doc so the server
                # picks it up as the first message when it creates the conversation.
                injection_result = self.inject_prompt(user_id, message["generated_message"])
                if injection_result:
                    results["injected"] += 1
                    print(f"💬 Message injected for {username}")
                else:
                    results["injection_failed"] += 1
                    print(f"⚠️  inject_prompt failed for {username} — will still send FCM")

                # Step 2: Pre-create the conversation so we have a conversationId
                # to embed in the FCM data for direct deep-linking.
                experiment_id_str = str(user.get("experimentId", ""))
                num_convs = int(user.get("numberOfConversations") or 0)
                conversation_id = self._create_conversation(user_id, experiment_id_str, num_convs)
                if conversation_id:
                    print(f"📝 Pre-created conversation {conversation_id} for {username}")
                else:
                    print(f"⚠️  Could not pre-create conversation for {username} — FCM will open home screen")


                # Step 3: Send FCM.  Include conversationId + experimentId so the
                # Android app can deep-link directly into the conversation.
                fcm_extra = {}
                if conversation_id and experiment_id_str:
                    fcm_extra = {
                        "conversationId": conversation_id,
                        "experimentId": experiment_id_str,
                    }

                notification_result = self.fcm_service.send_to_user(
                    user=UserContext(
                        user_id=user_id,
                        name=username,
                        fcm_token=fcm_token,
                    ),
                    body=message["generated_message"],
                    title="Lexi",
                    extra_data=fcm_extra if fcm_extra else None,
                )

                if notification_result:
                    results["fcm_sent"] += 1
                    print(f"✅ FCM sent to {username}")

                    # Step 4: heuristic post-send cleanup
                    if affective_nudge:
                        affective.clear_followup(user_id, mongodb_client)
                    elif gap_nudge:
                        behavioural_gap.clear_followup(user_id, mongodb_client)
                    elif temporal_nudge:
                        temporal.mark_fired(
                            user_id,
                            temporal_nudge.mention_text,
                            temporal_nudge.when_iso,
                            mongodb_client,
                        )

                    # Step 5: Log success
                    self.log_proactive_event(cycle_id, user_id, message, "sent", notification_result, proactive_group)
                else:
                    results["fcm_failed"] += 1
                    print(f"❌ FCM failed for {username}")

            except Exception as e:
                results["fcm_failed"] += 1
                error_msg = str(e)
                print(f"❌ Error processing user {username}: {e}")

                # Auto-cleanup: stale token (app reinstalled / cache cleared).
                # FCM returns several error strings for invalid tokens:
                stale_signals = ("notregistered", "not registered", "not found",
                                 "registration-token-not-registered",
                                 "invalid-registration-token",
                                 "invalid registration token")
                if any(s in error_msg.lower() for s in stale_signals):
                    print(f"🗑️  Stale token detected for {username} — removing from DB")
                    self.clear_stale_fcm_token(user_id, username)

        return results
    
    def log_proactive_event(self, cycle_id: str, user_id: str, message: Dict, status: str, notification_id: str = None, proactive_group: str = None):
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
                "proactive_group": proactive_group,
                "llm_response": message.get("llm_response", {})
            }

            mongodb_client.db["proactive_logs"].insert_one(log_entry)

        except Exception as e:
            print(f"❌ Error logging proactive event: {e}")
        finally:
            mongodb_client.disconnect()
    
    def run_oxford_demo_cycle(self) -> Dict:
        """
        Conference Demo Bypass.

        Sends 3 hardcoded FCM messages to all users in DEMO_EXPERIMENT_ID
        at fixed wall-clock times, completely bypassing LLM personalisation.
        Tracks progress via `demo_msgs_sent_count` on the user document.
        Sets `is_demo_finished: True` after the 3rd message is delivered.
        
        **IMPORTANT:** Assumes MongoDB connection is already open by the caller
        (e.g., run_cycle.py or scheduler.py). Does NOT call connect() or disconnect()
        to avoid interfering with the shared connection lifecycle.
        
        For each demo message:
        1. Inject the message into agent.firstChatSentence (same as standard cycle)
        2. Pre-create a conversation so we have a conversationId for deep-linking
        3. Send FCM with conversationId in the data payload
        4. Update demo progress tracking
        """
        now = datetime.now()
        sent_count = 0

        print(f"\n=== 🎯 Oxford Demo Cycle ({now.strftime('%Y-%m-%d %H:%M:%S')}) ===")

        try:
            # Ensure MongoDB connection is established
            if mongodb_client.db is None:
                if not mongodb_client.connect():
                    print("❌ Demo cycle: failed to connect to MongoDB")
                    return {"success": False, "error": "MongoDB connect failed"}

            demo_id_variants = [DEMO_EXPERIMENT_ID, ObjectId(DEMO_EXPERIMENT_ID)]
            demo_users = list(mongodb_client.db[mongodb_client.users_collection].find({
                "experimentId": {"$in": demo_id_variants},
                "fcmToken": {"$exists": True, "$ne": ""},
                "is_demo_finished": {"$ne": True},
            }))

            print(f"👥 Demo cycle: {len(demo_users)} active demo participant(s)")

            for user in demo_users:
                user_id   = str(user["_id"])
                username  = user.get("username", "Unknown")
                fcm_token = user.get("fcmToken", "")
                msgs_sent = user.get("demo_msgs_sent_count", 0)
                experiment_id_str = str(user.get("experimentId", ""))
                num_convs = int(user.get("numberOfConversations") or 0)

                print(f"\n👤 Demo user: {username} (messages sent so far: {msgs_sent}/{len(DEMO_MESSAGES)})")

                for idx, msg in enumerate(DEMO_MESSAGES):
                    # Safety check: Skip if already sent
                    if idx < msgs_sent:
                        continue

                    # Time check: Skip if not yet due
                    send_after = datetime.fromisoformat(msg["send_after"])
                    if now < send_after:
                        break  # scheduled time not yet reached for this message

                    try:
                        # Step 1: Inject the demo message as firstChatSentence
                        injection_result = self.inject_prompt(user_id, msg["text"])
                        if injection_result:
                            print(f"💬 Demo: message injected for {username}")
                        else:
                            print(f"⚠️  Demo: inject_prompt failed for {username} — will still send FCM")

                        # Step 2: Pre-create conversation for deep-linking
                        conversation_id = self._create_conversation(user_id, experiment_id_str, num_convs)
                        if conversation_id:
                            print(f"📝 Demo: pre-created conversation {conversation_id}")
                        else:
                            print(f"⚠️  Demo: could not pre-create conversation for {username}")

                        # Step 3: Send FCM with deep-link data
                        from core.models import UserContext
                        fcm_extra = {}
                        if conversation_id and experiment_id_str:
                            fcm_extra = {
                                "conversationId": conversation_id,
                                "experimentId": experiment_id_str,
                            }

                        notification_result = self.fcm_service.send_to_user(
                            user=UserContext(
                                user_id=user_id,
                                name=username,
                                fcm_token=fcm_token,
                            ),
                            body=msg["text"],
                            title="Lexi",
                            extra_data=fcm_extra if fcm_extra else None,
                        )

                        if not notification_result:
                            print(f"❌ Demo: FCM failed for {username}")
                            break  # Stop this user's messages on FCM failure

                        # The injection helper functions likely closed the connection internally.
                        # We must forcefully re-establish it before our atomic update.
                        mongodb_client.connect()

                        # Step 4: IMMEDIATELY update database with new count
                        new_count = idx + 1
                        is_complete = (new_count >= len(DEMO_MESSAGES))

                        # ATOMIC UPDATE: Always update demo_msgs_sent_count, and set is_demo_finished if complete
                        update_payload = {"$set": {"demo_msgs_sent_count": new_count}}
                        if is_complete:
                            update_payload["$set"]["is_demo_finished"] = True

                        mongodb_client.db[mongodb_client.users_collection].update_one(
                            {"_id": user["_id"]},
                            update_payload,
                        )

                        print(f"✅ Demo: FCM sent (message #{idx + 1}/{len(DEMO_MESSAGES)}) for {username}")

                        if is_complete:
                            print(f"🔒 Demo: LOCKED OUT after all {len(DEMO_MESSAGES)} messages for {username} (is_demo_finished=True)")
                            break  # Stop message loop, move to next user

                        sent_count += 1
                        msgs_sent = new_count

                    except Exception as fcm_err:
                        print(f"❌ Demo error for {username}: {fcm_err}")
                        break  # stop processing this user on failure

            print(f"=== 🎯 Demo Cycle done — {sent_count} FCM sent ===\n")
            return {"success": True, "sent": sent_count}

        except Exception as e:
            print(f"❌ Demo cycle unhandled error: {e}")
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def run_full_proactive_cycle(self) -> Dict:
        """Main orchestrator for proactive research cycle"""
        cycle_id = str(uuid.uuid4())
        start_time = datetime.now()

        print(f"\n=== 🚀 Starting Proactive Cycle {cycle_id[:8]}... ===")

        try:
            # Step 0: Restore any firstChatSentence overrides whose 2-hour window
            # has expired since the last cycle.
            self.expire_injected_prompts()

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
            traceback.print_exc()
            return {
                "success": False,
                "cycle_id": cycle_id,
                "error": str(e)
            }

_instance: Optional["ResearchService"] = None


def get_research_service() -> "ResearchService":
    """Lazy singleton — avoids Firebase init at import time (important on Render)."""
    global _instance
    if _instance is None:
        _instance = ResearchService()
    return _instance


class _LazyResearchService:
    """Backward-compatible module-level `research_service` for scripts/tests."""

    def __getattr__(self, name):
        return getattr(get_research_service(), name)


research_service = _LazyResearchService()
