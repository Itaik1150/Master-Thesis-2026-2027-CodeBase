"""
Research Service - Proactive injection and FCM functionality
"""
import os
import random
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from bson import ObjectId
import requests as http_requests

MAX_DAILY_NOTIFICATIONS = 3        # max notifications per user per day

LEXI_SERVER_URL  = os.getenv("LEXI_SERVER_URL", "https://lexi-server-1rx9.onrender.com")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://master-thesis-2026-2027-code-base.vercel.app")

# ── Conference Demo Bypass ────────────────────────────────────────────────────
# DEMO_EXPERIMENT_ID = "6a32e516d3d79d396942bff3"

# DEMO_MESSAGES = [
#     {
#         "send_after": "2026-06-25T15:30:00+01:00", 
#         "text": "Hi! You've made it through four intense keynotes today. 🧠 Make sure to grab a coffee during the break! How are you finding the cognitive AI discussions so far?"
#     },
#     {
#         "send_after": "2026-06-25T19:15:00+01:00", 
#         "text": "Day 1 of EIF CogAI is almost in the books! 🥂 Enjoy the reception and the formal dinner. What was your favorite moment or insight from today?"
#     },
#     {
#         "send_after": "2026-06-26T11:45:00+01:00", 
#         "text": "Good morning! Hope you're having a great Day 2. Enjoy the lunch break and the upcoming afternoon panels! Thank you for experiencing Lexi."
#     }
# ]




from utils.mongodb_client import mongodb_client
from services.fcm_service import FCMService
from services.llm_service import ProactiveLogic

class ResearchService:

    
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
    
    # def send_notification(self, user_id: str, message: str) -> bool:
        # """
        # Send FCM notification to user
        
        # Args:
        #     user_id: MongoDB user ID
        #     message: Message content for notification
            
        # Returns:
        #     True if successful, False otherwise
        # """
        # try:
        #     # Get user data from MongoDB
        #     if not mongodb_client.connect():
        #         print("❌ Failed to connect to MongoDB")
        #         return False
            
        #     user_data = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": ObjectId(str(user_id))})
            
        #     if not user_data:
        #         print(f"❌ User {user_id} not found")
        #         return False
            
        #     fcm_token = user_data.get('fcmToken', '')
        #     username = user_data.get('username', 'Unknown')
            
        #     if not fcm_token:
        #         print(f"❌ No FCM token for user {username}")
        #         return False
            
        #     # Send FCM notification
        #     notification_title = "📰 New Message Available"
        #     notification_body = f"Hi {username}! You have a new message waiting."
            
        #     result = self.fcm_service.send_to_token(
        #         token=fcm_token,
        #         body=f"{notification_title}: {notification_body}"
        #     )
            
        #     if result:
        #         print(f"✅ FCM notification sent to {username}")
        #         return True
        #     else:
        #         print(f"❌ Failed to send FCM to {username}")
        #         return False
                
        # except Exception as e:
        #     print(f"❌ Error sending notification: {e}")
        #     return False
        # finally:
        #     mongodb_client.disconnect()
    
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
            # Reactive group users are excluded here as an extra safety net
            # (they are also handled inside _resolve_message).
            proactive_users = list(mongodb_client.db[mongodb_client.users_collection].find({
                "experimentId": {"$in": id_variants},
                "fcmToken": {"$exists": True, "$ne": ""},
                "isProactive": True,
                "proactiveGroup": {"$ne": "reactive"},
            }))

            print(f"📊 Found {len(proactive_users)} proactive users with FCM tokens "
                  f"(across {len(enabled_ids)} proactive experiment(s))")
            return proactive_users

        except Exception as e:
            print(f"❌ Error fetching proactive users: {e}")
            return []
        finally:
            mongodb_client.disconnect()
    
    # run_proactive_cycle() — removed (stale: used a hardcoded message string,
    # replaced entirely by run_full_proactive_cycle + coordinated_send_and_inject)
    
    # def diagnose_user(self, user_id: str):
        # """
        # Diagnose user data and configuration issues
        
        # Args:
        #     user_id: MongoDB user ID
        # """
        # try:
        #     if not mongodb_client.connect():
        #         print("❌ Failed to connect to MongoDB")
        #         return
            
        #     user_data = mongodb_client.db[mongodb_client.users_collection].find_one({"_id": ObjectId(str(user_id))})
            
        #     if not user_data:
        #         print(f"❌ User {user_id} not found in database")
        #         return
            
        #     print(f"\n🔍 User Diagnosis for: {user_data.get('username', 'Unknown')}")
        #     print(f"📋 User ID: {user_id}")
        #     print(f"📱 FCM Token: {'✅ Present' if user_data.get('fcmToken') else '❌ Missing'}")
        #     print(f"🔔 isProactive: {user_data.get('isProactive', False)}")
            
        #     # Check agent structure
        #     agent = user_data.get('agent', {})
        #     print(f"🤖 Agent exists: {'✅ Yes' if agent else '❌ No'}")
            
        #     if agent:
        #         print(f"💬 firstChatSentence: '{agent.get('firstChatSentence', 'N/A')}'")
        #         print(f"📝 Agent fields: {list(agent.keys())}")
            
        #     # Check FCM token format
        #     fcm_token = user_data.get('fcmToken', '')
        #     if fcm_token:
        #         print(f"📱 FCM Token length: {len(fcm_token)}")
        #         print(f"📱 FCM Token format: {'✅ Valid length' if len(fcm_token) > 50 else '❌ Too short'}")
            
        # except Exception as e:
        #     print(f"❌ Error diagnosing user: {e}")
        # finally:
        #     mongodb_client.disconnect()
    
    # def test_fcm_connection(self):
        # """Test FCM service connection and configuration"""
        # try:
        #     print(f"\n🔍 FCM Service Diagnosis")
        #     print(f"📱 Dry run mode: {self.fcm_service.dry_run}")
            
        #     # Test with a dummy token
        #     test_token = "test_token_12345"
        #     test_title = "Test Notification"
        #     test_body = "This is a test message"
            
        #     print(f"🧪 Testing FCM with dummy token...")
            
        #     try:
        #         result = self.fcm_service.send_to_token(test_token, test_title, test_body)
        #         print(f"✅ FCM service initialized successfully")
        #         print(f"📊 Test result: {result}")
        #     except Exception as e:
        #         print(f"❌ FCM service error: {e}")
        #         print(f"🔧 Check Firebase service account configuration")
                
        # except Exception as e:
        #     print(f"❌ Error testing FCM: {e}")
    
    # def check_user_token_distribution(self):
        # """Check distribution of users with and without FCM tokens"""
        # try:
        #     if not mongodb_client.connect():
        #         print("❌ Failed to connect to MongoDB")
        #         return
            
        #     print(f"\n🔍 User Token Distribution Analysis")
            
        #     # Count all users
        #     total_users = mongodb_client.db[mongodb_client.users_collection].count_documents({})
        #     print(f"📊 Total users: {total_users}")
            
        #     # Count proactive users
        #     proactive_users = mongodb_client.db[mongodb_client.users_collection].count_documents({"isProactive": True})
        #     print(f"🔔 Proactive users: {proactive_users}")
            
        #     # Count users with FCM tokens
        #     users_with_tokens = mongodb_client.db[mongodb_client.users_collection].count_documents({
        #         "fcmToken": {"$exists": True, "$ne": ""}
        #     })
        #     print(f"📱 Users with FCM tokens: {users_with_tokens}")
            
        #     # Count proactive users with FCM tokens
        #     proactive_with_tokens = mongodb_client.db[mongodb_client.users_collection].count_documents({
        #         "isProactive": True,
        #         "fcmToken": {"$exists": True, "$ne": ""}
        #     })
        #     print(f"🎯 Proactive users with tokens: {proactive_with_tokens}")
            
        #     # Show sample users without tokens
        #     users_without_tokens = list(mongodb_client.db[mongodb_client.users_collection].find({
        #         "fcmToken": {"$exists": False}
        #     }).limit(3))
            
        #     if users_without_tokens:
        #         print(f"\n📋 Sample users WITHOUT FCM tokens:")
        #         for user in users_without_tokens:
        #             username = user.get('username', 'Unknown')
        #             is_proactive = user.get('isProactive', False)
        #             user_id = user.get('_id', 'Unknown')
        #             print(f"   👤 {username} (ID: {user_id}) - Proactive: {is_proactive}")
            
        #     # Show sample users with tokens
        #     users_with_tokens_list = list(mongodb_client.db[mongodb_client.users_collection].find({
        #         "fcmToken": {"$exists": True, "$ne": ""}
        #     }).limit(3))
            
        #     if users_with_tokens_list:
        #         print(f"\n📋 Sample users WITH FCM tokens:")
        #         for user in users_with_tokens_list:
        #             username = user.get('username', 'Unknown')
        #             is_proactive = user.get('isProactive', False)
        #             user_id = user.get('_id', 'Unknown')
        #             token_length = len(user.get('fcmToken', ''))
        #             print(f"   👤 {username} (ID: {user_id}) - Proactive: {is_proactive} - Token: {token_length} chars")
                
        # except Exception as e:
        #     print(f"❌ Error checking token distribution: {e}")
        # finally:
        #     mongodb_client.disconnect()
    
    # def check_mongodb_schema(self):
        # try:
        #     if not mongodb_client.connect():
        #         print("❌ Failed to connect to MongoDB")
        #         return
            
        #     print(f"\n🔍 MongoDB Schema Check")
        #     print(f"📊 Database: {mongodb_client.db_name}")
        #     print(f"📋 Collection: {mongodb_client.users_collection}")
            
        #     # Check a sample user
        #     sample_user = mongodb_client.db[mongodb_client.users_collection].find_one()
            
        #     if sample_user:
        #         print(f"👤 Sample user: {sample_user.get('username', 'Unknown')}")
        #         print(f"📋 User fields: {list(sample_user.keys())}")
                
        #         agent = sample_user.get('agent', {})
        #         if agent:
        #             print(f"🤖 Agent fields: {list(agent.keys())}")
        #             print(f"💬 firstChatSentence type: {type(agent.get('firstChatSentence', 'N/A'))}")
        #         else:
        #             print(f"❌ No agent field found")
        #     else:
        #         print(f"❌ No users found in collection")
                
        # except Exception as e:
        #     print(f"❌ Error checking schema: {e}")
        # finally:
        #     mongodb_client.disconnect()

    # === PROACTIVE CYCLE METHODS ===

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

    # def _reset_first_chat_sentence(self, user: dict) -> None:
        # """
        # Restore user.agent.firstChatSentence to the canonical value from the
        # agents collection, clearing the proactive override written by inject_prompt.
        # Called after _create_conversation (success or failure) so the proactive
        # message is never re-used as the opener for manually-started conversations.
        # """
        # try:
        #     agent = user.get("agent") or {}
        #     agent_id = agent.get("_id")
        #     if not agent_id:
        #         return
        #     if not mongodb_client.connect():
        #         return
        #     canonical = mongodb_client.db["agents"].find_one(
        #         {"_id": ObjectId(str(agent_id))},
        #         {"firstChatSentence": 1},
        #     )
        #     if not canonical:
        #         return
        #     original = canonical.get("firstChatSentence", "")
        #     mongodb_client.db[mongodb_client.users_collection].update_one(
        #         {"_id": ObjectId(str(user["_id"]))},
        #         {"$set": {"agent.firstChatSentence": original}},
        #     )
        # except Exception as e:
        #     print(f"⚠️  _reset_first_chat_sentence failed: {e}")
        # finally:
        #     try:
        #         mongodb_client.disconnect()
        #     except Exception:
        #         pass

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

    def _load_experiment_settings(self, user: dict) -> tuple:
        """
        Read heuristicWeights, heuristicPrompts, schedule, and llmModel from the
        experiment doc — the single MongoDB read that drives all per-user
        proactive behaviour this cycle (Task 4.5: verified live, never cached).

        Returns:
          heuristic_weights  — {"affective": int, "temporal": int, ...} (sum = 100)
          heuristic_prompts  — {"affective": {"memoryPrompt": str, "messagePrompt": str}, ...}
          schedule           — {"allowedDays": [int], "mode": str, "fireTimes": [...], "randomWindows": [...]}
          llm_model          — str | None

        Falls back gracefully: reactive=100 (no notifications), schedule=all-days
        if the experiment doc is missing or cannot be read; converts old boolean
        heuristics flags to equal weights for backward compatibility.
        """
        _DEFAULT_WEIGHTS = {
            "affective": 0, "temporal": 0, "behaviouralGap": 0,
            "generic": 0, "reactive": 100,
        }
        _DEFAULT_SCHEDULE = {"allowedDays": list(range(7)), "mode": "exact", "fireTimes": [], "randomWindows": []}

        heuristic_weights: dict = dict(_DEFAULT_WEIGHTS)
        heuristic_prompts: dict = {}
        schedule: dict          = dict(_DEFAULT_SCHEDULE)
        experiment_llm_model    = None

        try:
            experiment_id = user.get("experimentId")
            if experiment_id and mongodb_client.connect():
                exp_doc = mongodb_client.db["experiments"].find_one(
                    {"_id": ObjectId(str(experiment_id))},
                    {"experimentFeatures.proactiveSettings": 1},
                )
                if exp_doc:
                    ps = (exp_doc.get("experimentFeatures") or {}).get("proactiveSettings") or {}
                    if ps.get("heuristicWeights"):
                        heuristic_weights.update(ps["heuristicWeights"])
                    elif ps.get("heuristics"):
                        # Backward compat: convert boolean flags to equal-weight distribution
                        old_flags  = ps["heuristics"]
                        active_old = [k for k, v in old_flags.items() if v]
                        if active_old:
                            w         = 100 // len(active_old)
                            remainder = 100 - w * len(active_old)
                            heuristic_weights = {k: 0 for k in _DEFAULT_WEIGHTS}
                            for i, k in enumerate(active_old):
                                heuristic_weights[k] = w + (remainder if i == 0 else 0)
                            heuristic_weights["reactive"] = 0
                    if ps.get("heuristicPrompts"):
                        heuristic_prompts = ps["heuristicPrompts"]
                    if ps.get("schedule"):
                        schedule.update(ps["schedule"])
                    if ps.get("llmModel"):
                        experiment_llm_model = ps["llmModel"]
        except Exception as e:
            print(f"⚠️  Could not load experiment settings for "
                  f"{user.get('username', 'Unknown')}: {e}")
        finally:
            try:
                mongodb_client.disconnect()
            except Exception:
                pass

        return heuristic_weights, heuristic_prompts, schedule, experiment_llm_model

    @staticmethod
    def _is_today_allowed(schedule: dict) -> bool:
        """
        Per-user safety net (Task 4.5): check whether today's day-of-week is in
        this user's own experiment schedule.allowedDays. 0=Sun .. 6=Sat, matching
        the dashboard's day picker. Runs in Jerusalem time to match scheduler.py.
        """
        from zoneinfo import ZoneInfo
        allowed_days = schedule.get("allowedDays") or list(range(7))
        # Python's weekday(): Mon=0..Sun=6. Convert to Sun=0..Sat=6 (dashboard convention).
        py_weekday = datetime.now(ZoneInfo("Asia/Jerusalem")).weekday()
        today_sun0 = (py_weekday + 1) % 7
        return today_sun0 in allowed_days

    def _select_heuristic(self, weights: dict) -> str:
        """
        Randomly select one heuristic name according to probability weights.
        weights: e.g. {"affective": 50, "temporal": 30, "generic": 20, "reactive": 0}
        Returns "reactive" if all weights are 0 or the dict is empty.
        """
        active = {k: v for k, v in weights.items() if isinstance(v, (int, float)) and v > 0}
        if not active:
            return "reactive"
        total = sum(active.values())
        rand = random.uniform(0, total)
        cumulative = 0.0
        for name, weight in active.items():
            cumulative += weight
            if rand <= cumulative:
                return name
        return list(active.keys())[-1]

    def _run_selected_heuristic(
        self,
        selected: str,
        user: dict,
        heuristic_prompts: dict,
    ) -> tuple:
        """
        Instantiate the selected heuristic class, call get_proactive_message(),
        and return (message_dict, heuristic_instance).

        The heuristic instance is returned so the caller can invoke
        heuristic.clear_after_send() after a successful FCM send.

        Returns (None, None) when:
          - The heuristic class is unknown
          - get_proactive_message() returns None (nothing to send this cycle)
          - An unhandled exception is raised inside the heuristic
        """
        from heuristics.affective import AffectiveHeuristic
        from heuristics.temporal import TemporalHeuristic
        from heuristics.behavioural_gap import BehaviouralGapHeuristic
        from heuristics.generic import GenericHeuristic

        cls_map = {
            "affective":      AffectiveHeuristic,
            "temporal":       TemporalHeuristic,
            "behaviouralGap": BehaviouralGapHeuristic,
            "generic":        GenericHeuristic,
        }

        cls = cls_map.get(selected)
        if not cls:
            print(f"⚠️  _run_selected_heuristic: unknown heuristic '{selected}'")
            return None, None

        h = cls(
            user=user,
            llm_service=self.llm_service,
            mongodb_client=mongodb_client,
            prompts_from_db=heuristic_prompts.get(selected, {}),
        )

        try:
            text = h.get_proactive_message()
        except Exception as e:
            print(f"❌ [{h.username}] {selected} heuristic raised an exception: {e}")
            traceback.print_exc()
            return None, None

        if not text:
            return None, None

        return {
            "trigger_source":    selected,
            "source":            selected,
            "topic_label":       selected,
            "generated_message": text,
            "personalized":      True,
        }, h

    def coordinated_send_and_inject(self, users: List[Dict], cycle_id: str) -> Dict:
        """
        Per-user orchestration loop (Task 3.2 clean architecture):

        For each eligible user:
          1. _load_experiment_settings()  → heuristic weights + prompts + schedule + LLM model
          2. _is_today_allowed(schedule)  → per-user day-of-week safety net
          3. Read name/language from existing proactiveMemory  (0 LLM calls)
          4. _select_heuristic(weights)   → one heuristic name
          5. _run_selected_heuristic()    → instantiate class, call get_proactive_message()
          6. inject_prompt + _create_conversation + FCM send
          7. heuristic.clear_after_send() + log
        """
        results = {
            "fcm_sent": 0,
            "fcm_failed": 0,
            "injected": 0,
            "injection_failed": 0,
            "details": []
        }

        print(f"📱 Sending to {len(users)} users")

        for user in users:
            user_id = str(user["_id"])
            username = user.get('username', 'Unknown')
            fcm_token = user["fcmToken"]
            proactive_group = user.get('proactiveGroup', 'generic')  # Default to generic for existing users

            # ── Load experiment settings (live MongoDB read, Task 4.5) ────────
            heuristic_weights, heuristic_prompts, schedule, experiment_llm_model = \
                self._load_experiment_settings(user)
            active_weights = {k: v for k, v in heuristic_weights.items() if v > 0}
            has_custom_prompts = list(heuristic_prompts.keys())
            print(
                f"⚖️  [{username}] weights={active_weights} "
                f"custom_prompts={has_custom_prompts or 'none'} "
                f"schedule_days={schedule.get('allowedDays')}"
            )

            # Per-user safety net: skip if today isn't an allowed day for this
            # user's own experiment (the scheduler's cron trigger is a coarse
            # pre-filter; this is the precise, per-experiment enforcement).
            if not self._is_today_allowed(schedule):
                print(f"📅 [{username}] Today not in allowed days ({schedule.get('allowedDays')}) — skipping")
                continue

            if experiment_llm_model:
                self.llm_service.override_model(experiment_llm_model)

            # Read name/language from existing proactiveMemory — no LLM, no MongoDB call.
            # Each heuristic's create_memory() updates these for future cycles.
            existing_pm = user.get("proactiveMemory") or {}
            name     = (existing_pm.get("demographics") or {}).get("name") or username
            language = existing_pm.get("preferred_language", "he")

            # ── Probability-based heuristic selection ─────────────────────────
            selected = self._select_heuristic(heuristic_weights)
            print(f"\n🎲 [{username}] Selected heuristic: {selected}")

            if selected == "reactive":
                print(f"🚫 [{username}] Reactive — skipping")
                continue

            message, heuristic = self._run_selected_heuristic(
                selected=selected,
                user=user,
                heuristic_prompts=heuristic_prompts,
            )

            if not message:
                print(f"⏭️  [{username}] {selected} heuristic returned no message — skipping")
                continue

            print(f"\n👤 {username} [group:{proactive_group}] → [{selected}] {message['generated_message']}")

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
                    if heuristic:
                        heuristic.clear_after_send()

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
    
    # def run_oxford_demo_cycle(self) -> Dict:
        # """
        # Conference Demo Bypass.

        # Sends 3 hardcoded FCM messages to all users in DEMO_EXPERIMENT_ID
        # at fixed wall-clock times, completely bypassing LLM personalisation.
        # Tracks progress via `demo_msgs_sent_count` on the user document.
        # Sets `is_demo_finished: True` after the 3rd message is delivered.
        
        # **IMPORTANT:** Assumes MongoDB connection is already open by the caller
        # (e.g., run_cycle.py or scheduler.py). Does NOT call connect() or disconnect()
        # to avoid interfering with the shared connection lifecycle.
        
        # For each demo message:
        # 1. Inject the message into agent.firstChatSentence (same as standard cycle)
        # 2. Pre-create a conversation so we have a conversationId for deep-linking
        # 3. Send FCM with conversationId in the data payload
        # 4. Update demo progress tracking
        # """
        # now = datetime.now()
        # sent_count = 0

        # print(f"\n=== 🎯 Oxford Demo Cycle ({now.strftime('%Y-%m-%d %H:%M:%S')}) ===")

        # try:
        #     # Ensure MongoDB connection is established
        #     if mongodb_client.db is None:
        #         if not mongodb_client.connect():
        #             print("❌ Demo cycle: failed to connect to MongoDB")
        #             return {"success": False, "error": "MongoDB connect failed"}

        #     demo_id_variants = [DEMO_EXPERIMENT_ID, ObjectId(DEMO_EXPERIMENT_ID)]
        #     demo_users = list(mongodb_client.db[mongodb_client.users_collection].find({
        #         "experimentId": {"$in": demo_id_variants},
        #         "fcmToken": {"$exists": True, "$ne": ""},
        #         "is_demo_finished": {"$ne": True},
        #     }))

        #     print(f"👥 Demo cycle: {len(demo_users)} active demo participant(s)")

        #     for user in demo_users:
        #         user_id   = str(user["_id"])
        #         username  = user.get("username", "Unknown")
        #         fcm_token = user.get("fcmToken", "")
        #         msgs_sent = user.get("demo_msgs_sent_count", 0)
        #         experiment_id_str = str(user.get("experimentId", ""))
        #         num_convs = int(user.get("numberOfConversations") or 0)

        #         print(f"\n👤 Demo user: {username} (messages sent so far: {msgs_sent}/{len(DEMO_MESSAGES)})")

        #         for idx, msg in enumerate(DEMO_MESSAGES):
        #             # Safety check: Skip if already sent
        #             if idx < msgs_sent:
        #                 continue

        #             # Time check: Skip if not yet due
        #             send_after = datetime.fromisoformat(msg["send_after"])
        #             if now < send_after:
        #                 break  # scheduled time not yet reached for this message

        #             try:
        #                 # Step 1: Inject the demo message as firstChatSentence
        #                 injection_result = self.inject_prompt(user_id, msg["text"])
        #                 if injection_result:
        #                     print(f"💬 Demo: message injected for {username}")
        #                 else:
        #                     print(f"⚠️  Demo: inject_prompt failed for {username} — will still send FCM")

        #                 # Step 2: Pre-create conversation for deep-linking
        #                 conversation_id = self._create_conversation(user_id, experiment_id_str, num_convs)
        #                 if conversation_id:
        #                     print(f"📝 Demo: pre-created conversation {conversation_id}")
        #                 else:
        #                     print(f"⚠️  Demo: could not pre-create conversation for {username}")

        #                 # Step 3: Send FCM with deep-link data
        #                 from core.models import UserContext
        #                 fcm_extra = {}
        #                 if conversation_id and experiment_id_str:
        #                     fcm_extra = {
        #                         "conversationId": conversation_id,
        #                         "experimentId": experiment_id_str,
        #                     }

        #                 notification_result = self.fcm_service.send_to_user(
        #                     user=UserContext(
        #                         user_id=user_id,
        #                         name=username,
        #                         fcm_token=fcm_token,
        #                     ),
        #                     body=msg["text"],
        #                     title="Lexi",
        #                     extra_data=fcm_extra if fcm_extra else None,
        #                 )

        #                 if not notification_result:
        #                     print(f"❌ Demo: FCM failed for {username}")
        #                     break  # Stop this user's messages on FCM failure

        #                 # The injection helper functions likely closed the connection internally.
        #                 # We must forcefully re-establish it before our atomic update.
        #                 mongodb_client.connect()

        #                 # Step 4: IMMEDIATELY update database with new count
        #                 new_count = idx + 1
        #                 is_complete = (new_count >= len(DEMO_MESSAGES))

        #                 # ATOMIC UPDATE: Always update demo_msgs_sent_count, and set is_demo_finished if complete
        #                 update_payload = {"$set": {"demo_msgs_sent_count": new_count}}
        #                 if is_complete:
        #                     update_payload["$set"]["is_demo_finished"] = True

        #                 mongodb_client.db[mongodb_client.users_collection].update_one(
        #                     {"_id": user["_id"]},
        #                     update_payload,
        #                 )

        #                 print(f"✅ Demo: FCM sent (message #{idx + 1}/{len(DEMO_MESSAGES)}) for {username}")

        #                 if is_complete:
        #                     print(f"🔒 Demo: LOCKED OUT after all {len(DEMO_MESSAGES)} messages for {username} (is_demo_finished=True)")
        #                     break  # Stop message loop, move to next user

        #                 sent_count += 1
        #                 msgs_sent = new_count

        #             except Exception as fcm_err:
        #                 print(f"❌ Demo error for {username}: {fcm_err}")
        #                 break  # stop processing this user on failure

        #     print(f"=== 🎯 Demo Cycle done — {sent_count} FCM sent ===\n")
        #     return {"success": True, "sent": sent_count}

        # except Exception as e:
        #     print(f"❌ Demo cycle unhandled error: {e}")
        #     traceback.print_exc()
        #     return {"success": False, "error": str(e)}

    def run_full_proactive_cycle(self) -> Dict:
        """
        Main orchestrator. Called by run_cycle.py and scheduler.py.

        Step 0 — expire any injected firstChatSentence overrides whose window has passed.
        Step 1 — get eligible users (rate-limited).
        Step 2 — for each user: build memory, randomly select one heuristic by probability
                  weight (read from experiment doc), run only that heuristic, inject + send FCM.
        """
        cycle_id   = str(uuid.uuid4())
        start_time = datetime.now()

        # ── Cycle-start banner (visible in Render logs) ────────────────────────
        print("\n" + "=" * 60)
        print(f"🚀  PROACTIVE CYCLE START")
        print(f"    Cycle ID  : {cycle_id[:8]}")
        print(f"    Timestamp : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    LLM engine: {self.llm_service.provider.upper()} / {self.llm_service.model}")
        print(f"    Config    : heuristic weights, prompts, and schedule read live per user from MongoDB")
        print("=" * 60)

        try:
            # Step 0: Restore expired firstChatSentence overrides
            self.expire_injected_prompts()

            # Step 1: Get eligible users (rate-limit checked)
            eligible_users = self.get_proactive_users_with_rate_limit(cycle_id)

            if not eligible_users:
                print("❌ No eligible users found — cycle complete (nothing to send)")
                print("=" * 60 + "\n")
                return {"success": False, "message": "No eligible users found"}

            print(f"\n👥  Eligible users this cycle: {len(eligible_users)}")
            print(f"    Per-user heuristic selection logged inline below.\n")

            # Step 2: Per-user probability-based heuristic selection and send
            results = self.coordinated_send_and_inject(eligible_users, cycle_id)

            duration = (datetime.now() - start_time).total_seconds()

            # ── Cycle-end banner ───────────────────────────────────────────────
            print("\n" + "=" * 60)
            print(f"✅  PROACTIVE CYCLE COMPLETE  [{cycle_id[:8]}]")
            print(f"    FCM sent         : {results['fcm_sent']}")
            print(f"    FCM failed       : {results['fcm_failed']}")
            print(f"    Injected         : {results['injected']}")
            print(f"    Injection failed : {results['injection_failed']}")
            print(f"    Duration         : {duration:.2f}s")
            print("=" * 60 + "\n")

            return {
                "success": True,
                "cycle_id": cycle_id,
                "results": results,
                "duration": duration,
            }

        except Exception as e:
            print(f"❌ Proactive cycle failed: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "cycle_id": cycle_id,
                "error": str(e),
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
