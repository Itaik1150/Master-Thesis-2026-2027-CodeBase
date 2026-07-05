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

LEXI_SERVER_URL  = os.getenv("LEXI_SERVER_URL", "https://lexi-server-1rx9.onrender.com")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://master-thesis-2026-2027-code-base.vercel.app")


from utils.mongodb_client import mongodb_client
from services.fcm_service import FCMService
from services.llm_service import ProactiveLogic

class ResearchService:

    
    def __init__(self):
        """Initialize research service"""
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
    
    def get_all_proactive_users(self):
        """
        Get all proactive users with FCM tokens whose experiment has proactive enabled.
        Joins users → experiments to filter out experiments where proactive is disabled.

        Task 6.1: The proactiveGroup filter has been removed — routing is now
        determined entirely by experiment-level heuristicWeights, not by a user-level
        group field. The Reactive gate is enforced inside _select_heuristic().
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

            id_variants = []
            for eid in enabled_ids:
                id_variants.append(str(eid))
                id_variants.append(eid)

            # Step 2: auto-heal users who were registered before proactive was enabled
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
            # No proactiveGroup filter — experiment heuristicWeights determine behaviour.
            proactive_users = list(mongodb_client.db[mongodb_client.users_collection].find({
                "experimentId": {"$in": id_variants},
                "fcmToken": {"$exists": True, "$ne": ""},
                "isProactive": True,
            }))

            print(f"📊 Found {len(proactive_users)} proactive users with FCM tokens "
                  f"(across {len(enabled_ids)} proactive experiment(s))")
            return proactive_users

        except Exception as e:
            print(f"❌ Error fetching proactive users: {e}")
            return []
        finally:
            mongodb_client.disconnect()

    # === PROACTIVE CYCLE METHODS ===

    def get_proactive_users_with_rate_limit(self, cycle_id: str) -> List[Dict]:
        """
        Return all proactive users who have not yet received a notification in
        the current scheduler cycle. Notification frequency is controlled
        entirely by the schedule fire-times set by the researcher; there is no
        separate daily-count cap.
        """
        users = self.get_all_proactive_users()

        if not users:
            return []

        eligible_users = []

        for user in users:
            user_id  = str(user["_id"])
            username = user.get("username", "Unknown")

            try:
                if not mongodb_client.connect():
                    print(f"❌ Failed to connect to MongoDB for rate limiting {username}")
                    continue

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
                print(f"❌ Error in rate limiting for {username}: {e}")
            finally:
                try:
                    mongodb_client.disconnect()
                except Exception:
                    pass

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
        Read heuristicWeights, heuristicPrompts, schedule, llmModel, and
        defaultLanguage from the experiment doc.

        Returns (5-tuple):
          heuristic_weights — {"affective": int, ...} (sum = 100)
          heuristic_prompts — {"affective": {"memoryPrompt": str, ...}, ...}
          schedule          — {"allowedDays": [...], "mode": ..., ...}
          llm_model         — str | None
          default_language  — str (Task 6.3)

        Falls back gracefully: reactive=100, schedule=all-days, lang="he"
        if the experiment doc is missing or cannot be read.
        """
        _DEFAULT_WEIGHTS  = {
            "affective": 0, "temporal": 0, "behaviouralGap": 0,
            "generic": 0, "reactive": 100,
        }
        _DEFAULT_SCHEDULE = {
            "allowedDays": list(range(7)), "mode": "exact",
            "fireTimes": [], "randomWindows": []
        }

        heuristic_weights: dict = dict(_DEFAULT_WEIGHTS)
        heuristic_prompts: dict = {}
        schedule: dict          = dict(_DEFAULT_SCHEDULE)
        experiment_llm_model    = None
        default_language        = "he"

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
                    # Task 6.3: experiment-level default language
                    if ps.get("defaultLanguage"):
                        default_language = ps["defaultLanguage"]
        except Exception as e:
            print(f"⚠️  Could not load experiment settings for "
                  f"{user.get('username', 'Unknown')}: {e}")
        finally:
            try:
                mongodb_client.disconnect()
            except Exception:
                pass

        return (
            heuristic_weights,
            heuristic_prompts,
            schedule,
            experiment_llm_model,
            default_language,
        )

    @staticmethod
    def _is_today_allowed(schedule: dict) -> bool:
        """
        Per-user safety net: check whether today's day-of-week is in this
        user's own experiment schedule.allowedDays. 0=Sun .. 6=Sat.
        Runs in Jerusalem time to match scheduler.py.
        """
        from zoneinfo import ZoneInfo
        allowed_days = schedule.get("allowedDays") or list(range(7))
        py_weekday = datetime.now(ZoneInfo("Asia/Jerusalem")).weekday()
        today_sun0 = (py_weekday + 1) % 7
        return today_sun0 in allowed_days

    def _select_heuristic(self, weights: dict) -> str:
        """
        Randomly select one heuristic name according to probability weights.
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
        default_language: str = "he",
    ) -> tuple:
        """
        Instantiate the selected heuristic class, call get_proactive_message(),
        and return (message_dict, heuristic_instance).

        The heuristic instance is returned so the caller can invoke
        heuristic.clear_after_send() after a successful FCM send.

        Task 6.3: default_language is passed to the heuristic constructor.
        Task 6.7: used_fallback, memory_content, and language are read from the
                  heuristic instance and included in the returned message dict.

        Returns (None, None) when:
          - The heuristic class is unknown
          - get_proactive_message() unexpectedly returns None (should never happen
            after Task 6.2 guaranteed fallbacks)
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
            default_language=default_language,
        )

        try:
            text = h.get_proactive_message()
        except Exception as e:
            print(f"❌ [{h.username}] {selected} heuristic raised an exception: {e}")
            traceback.print_exc()
            return None, None

        if not text:
            print(f"❌ UNEXPECTED: [{h.username}] {selected} returned None after fallback — "
                  f"check heuristic implementation")
            return None, None

        return {
            "trigger_source":    selected,
            "source":            selected,
            "topic_label":       selected,
            "generated_message": text,
            "personalized":      True,
            # Task 6.7: logging metadata from heuristic instance
            "was_fallback":      h.used_fallback,
            "memory_content":    h.memory_content,
            "language":          h.language,
        }, h

    def coordinated_send_and_inject(self, users: List[Dict], cycle_id: str) -> Dict:
        """
        Per-user orchestration loop (Task 3.2 clean architecture):

        For each eligible user:
          1. _load_experiment_settings()  → weights + prompts + schedule + LLM + lang
          2. _is_today_allowed(schedule)  → per-user day-of-week safety net
          3. _select_heuristic(weights)   → one heuristic name
          4. _run_selected_heuristic()    → instantiate class, call get_proactive_message()
          5. inject_prompt + _create_conversation + FCM send
          6. heuristic.clear_after_send() + log
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
            user_id  = str(user["_id"])
            username = user.get('username', 'Unknown')
            fcm_token = user["fcmToken"]

            # ── Load experiment settings (live MongoDB read, Task 4.5) ────────
            (heuristic_weights, heuristic_prompts, schedule,
             experiment_llm_model, default_language) = \
                self._load_experiment_settings(user)

            active_weights     = {k: v for k, v in heuristic_weights.items() if v > 0}
            has_custom_prompts = list(heuristic_prompts.keys())
            print(
                f"⚖️  [{username}] weights={active_weights} "
                f"custom_prompts={has_custom_prompts or 'none'} "
                f"schedule_days={schedule.get('allowedDays')} "
                f"lang={default_language}"
            )

            if not self._is_today_allowed(schedule):
                print(f"📅 [{username}] Today not in allowed days ({schedule.get('allowedDays')}) — skipping")
                continue

            if experiment_llm_model:
                self.llm_service.override_model(experiment_llm_model)

            # Task 6.1: derive experiment_type from dominant non-reactive heuristic weight
            non_reactive = {k: v for k, v in heuristic_weights.items() if k != "reactive" and v > 0}
            experiment_type = (
                max(non_reactive, key=lambda k: non_reactive[k])
                if non_reactive else "reactive"
            )

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
                default_language=default_language,
            )

            if not message:
                print(f"⏭️  [{username}] {selected} heuristic returned no message — skipping")
                continue

            print(f"\n👤 {username} [type:{experiment_type}] → [{selected}] {message['generated_message']}")

            try:
                from core.models import UserContext

                injection_result = self.inject_prompt(user_id, message["generated_message"])
                if injection_result:
                    results["injected"] += 1
                    print(f"💬 Message injected for {username}")
                else:
                    results["injection_failed"] += 1
                    print(f"⚠️  inject_prompt failed for {username} — will still send FCM")

                experiment_id_str = str(user.get("experimentId", ""))
                num_convs = int(user.get("numberOfConversations") or 0)
                conversation_id = self._create_conversation(user_id, experiment_id_str, num_convs)
                if conversation_id:
                    print(f"📝 Pre-created conversation {conversation_id} for {username}")
                else:
                    print(f"⚠️  Could not pre-create conversation for {username} — FCM will open home screen")

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

                    if heuristic:
                        heuristic.clear_after_send()

                    self.log_proactive_event(
                        cycle_id, user_id, message, "sent", notification_result,
                        experiment_type=experiment_type,
                        experiment_id=experiment_id_str,
                        heuristic_weights=active_weights,
                        llm_model=experiment_llm_model,
                    )
                else:
                    results["fcm_failed"] += 1
                    print(f"❌ FCM failed for {username}")

            except Exception as e:
                results["fcm_failed"] += 1
                error_msg = str(e)
                print(f"❌ Error processing user {username}: {e}")

                stale_signals = ("notregistered", "not registered", "not found",
                                 "registration-token-not-registered",
                                 "invalid-registration-token",
                                 "invalid registration token")
                if any(s in error_msg.lower() for s in stale_signals):
                    print(f"🗑️  Stale token detected for {username} — removing from DB")
                    self.clear_stale_fcm_token(user_id, username)

        return results
    
    def log_proactive_event(
        self,
        cycle_id: str,
        user_id: str,
        message: Dict,
        status: str,
        notification_id: str = None,
        experiment_type: str = None,
        experiment_id: str = None,
        heuristic_weights: dict = None,
        llm_model: str = None,
    ):
        """
        Log a proactive notification event for research analysis.

        Task 6.7: Extended log schema includes experiment_id, experiment_type,
        heuristic_selected, was_fallback, memory_content, language,
        heuristic_weights_snapshot, and llm_model for comprehensive thesis analysis.

        Deducible metrics:
          - Heuristic selection frequency (GROUP BY heuristic_selected)
          - Cold-start rate (WHERE was_fallback = true)
          - Notification volume per user per day (GROUP BY user_id, date(timestamp))
          - Language distribution (GROUP BY language)
          - LLM cost attribution (GROUP BY llm_model)
          - Delivery success rate (WHERE status = "sent" / total)
        """
        try:
            if not mongodb_client.connect():
                print("❌ Could not connect to MongoDB for logging")
                return

            log_entry = {
                "cycle_id":                   cycle_id,
                "timestamp":                  datetime.now(timezone.utc),
                "user_id":                    user_id,
                "experiment_id":              experiment_id or "",
                "experiment_type":            experiment_type or "",
                "trigger_source":             message.get("trigger_source", "unknown"),
                "heuristic_selected":         message.get("trigger_source", "unknown"),
                "generated_message":          message["generated_message"],
                "was_fallback":               message.get("was_fallback", False),
                "memory_content":             message.get("memory_content", ""),
                "language":                   message.get("language", "he"),
                "topic_label":                message.get("topic_label", "general"),
                "status":                     status,
                "notification_id":            notification_id,
                "heuristic_weights_snapshot": heuristic_weights or {},
                "llm_model":                  llm_model or "",
            }

            mongodb_client.db["proactive_logs"].insert_one(log_entry)

        except Exception as e:
            print(f"❌ Error logging proactive event: {e}")
        finally:
            mongodb_client.disconnect()
    
    def run_full_proactive_cycle(self) -> Dict:
        """
        Main orchestrator. Called by run_cycle.py and scheduler.py.

        Step 0 — expire any injected firstChatSentence overrides whose window has passed.
        Step 1 — get eligible users (rate-limited, per-experiment cap from Task 6.8).
        Step 2 — for each user: randomly select one heuristic by probability weight,
                  run that heuristic (guaranteed message via Task 6.2 fallbacks),
                  inject + send FCM.
        """
        cycle_id   = str(uuid.uuid4())
        start_time = datetime.now()

        print("\n" + "=" * 60)
        print(f"🚀  PROACTIVE CYCLE START")
        print(f"    Cycle ID  : {cycle_id[:8]}")
        print(f"    Timestamp : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    LLM engine: {self.llm_service.provider.upper()} / {self.llm_service.model}")
        print(f"    Config    : heuristic weights, prompts, schedule, and language "
              f"read live per user from MongoDB")
        print("=" * 60)

        try:
            self.expire_injected_prompts()

            eligible_users = self.get_proactive_users_with_rate_limit(cycle_id)

            if not eligible_users:
                print("❌ No eligible users found — cycle complete (nothing to send)")
                print("=" * 60 + "\n")
                return {"success": False, "message": "No eligible users found"}

            print(f"\n👥  Eligible users this cycle: {len(eligible_users)}")
            print(f"    Per-user heuristic selection logged inline below.\n")

            results = self.coordinated_send_and_inject(eligible_users, cycle_id)

            duration = (datetime.now() - start_time).total_seconds()

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
