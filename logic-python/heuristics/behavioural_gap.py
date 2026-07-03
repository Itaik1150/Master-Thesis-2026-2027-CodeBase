"""
Behavioural Gap Heuristic

Fires a gentle follow-up when a user stated an explicit intention
but hasn't mentioned whether they followed through after 24–48 hours.

BehaviouralGapHeuristic.create_memory() scans for new stated intents and
checks existing ones for completion; get_proactive_message() generates the
follow-up message if a gap is currently pending.

MongoDB fields used (inside proactiveMemory):
  open_intents: List[{intent, stated_at, checked}]
  pending_gap_followup: {intent_text, stated_at}
  last_intent_scan_conversation_id: str  — prevents re-scanning the same conversation
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional, List

from bson import ObjectId as _ObjectId

from heuristics.base_heuristic import BaseHeuristic


# Hours after stating an intent before we check for completion.
GAP_MIN_HOURS: float = 24   # don't check if intent is less than 24h old
GAP_MAX_HOURS: float = 48   # stop checking after 48h (too stale to be useful)


def clear_followup(user_id: str, mongodb_client) -> None:
    """
    Remove pending_gap_followup after a nudge is successfully sent.
    Uses $unset so no other proactiveMemory fields are touched.
    Opens and closes its own MongoDB connection.
    """
    from bson import ObjectId

    try:
        if not mongodb_client.connect():
            print(f"⚠️  gap.clear_followup: could not connect for {user_id}")
            return
        mongodb_client.db[mongodb_client.users_collection].update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"proactiveMemory.pending_gap_followup": ""}},
        )
        print(f"🔍 Gap followup cleared for user {user_id}")
    except Exception as e:
        print(f"⚠️  gap.clear_followup error for {user_id}: {e}")
    finally:
        mongodb_client.disconnect()


class BehaviouralGapHeuristic(BaseHeuristic):
    """
    Detects when a user stated an explicit intention but has not followed up.
    Generates a gentle follow-up asking if they went through with it.

    Memory fields (inside proactiveMemory):
      open_intents:                     List[{intent, stated_at, checked}]
      pending_gap_followup:             {intent_text, stated_at}
      last_intent_scan_conversation_id: str — prevents rescanning the same conversation

    Returns None from get_proactive_message() when no gap is detected this cycle.
    """

    DEFAULT_MEMORY_PROMPT = (
        "You analyze conversation messages from a user.\n"
        "Extract only EXPLICIT, concrete plans or commitments the user expressed.\n\n"
        "Valid examples:\n"
        "  - 'I'll go to the gym tomorrow'\n"
        "  - 'I'm starting that online course next week'\n"
        "  - 'I plan to call my mom tonight'\n\n"
        "Invalid (too vague — do NOT include):\n"
        "  - 'I want to be healthier'\n"
        "  - 'Maybe I'll try that someday'\n"
        "  - 'I should exercise more'\n\n"
        "Return JSON with a single key 'intents': a list of objects, each with "
        "key 'intent' (concise English description, e.g. 'go to the gym'). "
        'Return {"intents": []} if no clear commitments are found.'
    )

    DEFAULT_MESSAGE_PROMPT = (
        "You are a supportive, caring assistant.\n"
        "Generate a gentle, friendly follow-up message in {language} (max 15 words) "
        "asking whether the user followed through on their stated plan.\n"
        "Do NOT assume success or failure — stay curious and supportive.\n"
        "You MAY use the user's name once. "
        "Return ONLY the final message, no quotes or explanations."
    )

    def create_memory(self) -> None:
        """
        Scan for new stated intents and check existing ones for completion.
        Equivalent to the module-level scan_for_gaps() but class-based, and using
        self.memory_prompt for intent extraction instead of the hardcoded prompt.
        """
        memory = self._memory
        last_scanned: str = memory.get("last_intent_scan_conversation_id", "")
        existing_intents: List[dict] = list(memory.get("open_intents") or [])

        # ── Phase A: Read ──────────────────────────────────────────────────────
        new_conv_messages:    List[str] = []
        recent_user_messages: List[str] = []
        last_scanned_to_save: str       = last_scanned

        try:
            if not self.mongodb_client.connect():
                return

            latest_meta = self.mongodb_client.db["metadata_conversations"].find_one(
                {"userId": self.user_id},
                sort=[("createdAt", -1)],
            )
            if latest_meta:
                conv_id = str(latest_meta["_id"])
                if conv_id != last_scanned:
                    raw = list(self.mongodb_client.db["conversations"].find(
                        {"conversationId": conv_id, "role": "user"},
                        sort=[("messageNumber", 1)],
                    ))
                    new_conv_messages    = [m.get("content", "") for m in raw if m.get("content")]
                    last_scanned_to_save = conv_id
                    if new_conv_messages:
                        print(f"   🔍 gap: scanning conv {conv_id[:8]}... "
                              f"({len(new_conv_messages)} msgs)")

            recent_metas = list(self.mongodb_client.db["metadata_conversations"].find(
                {"userId": self.user_id},
                sort=[("createdAt", -1)],
                limit=3,
            ))
            for meta in recent_metas:
                raw = list(self.mongodb_client.db["conversations"].find(
                    {"conversationId": str(meta["_id"]), "role": "user"},
                    sort=[("messageNumber", 1)],
                ))
                recent_user_messages.extend(
                    [m.get("content", "") for m in raw if m.get("content")]
                )
        except Exception as e:
            print(f"⚠️  BehaviouralGapHeuristic.create_memory read ({self.username}): {e}")
            return
        finally:
            self.mongodb_client.disconnect()

        # ── Phase B-1: LLM intent extraction ──────────────────────────────────
        new_intents: List[dict] = []
        if new_conv_messages:
            try:
                joined = "\n".join(f"- {m}" for m in new_conv_messages[-30:] if m)
                raw_text = self.llm_service.call_with_prompt(
                    system=self.memory_prompt,
                    user_content=f"Participant messages:\n{joined}",
                    json_mode=True,
                    max_tokens=300,
                )
                parsed = json.loads(raw_text)
                intents_raw = parsed.get("intents") or []
                existing_texts = {i.get("intent", "").lower() for i in existing_intents}
                now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                for item in intents_raw:
                    text = (item.get("intent") or "").strip()
                    if text and text.lower() not in existing_texts:
                        new_intents.append(
                            {"intent": text, "stated_at": now_iso, "checked": False}
                        )
                        existing_texts.add(text.lower())
            except Exception as e:
                print(f"⚠️  BehaviouralGapHeuristic intent extraction ({self.username}): {e}")

        # ── Phase B-2: Check completion for intents in the 24–48h window ──────
        all_intents              = existing_intents + new_intents
        now                      = datetime.now(timezone.utc)
        pending_gap: Optional[dict]  = None
        indices_to_mark: List[int]   = []

        for idx, intent in enumerate(all_intents):
            if intent.get("checked"):
                continue
            stated_at_raw = intent.get("stated_at")
            if not stated_at_raw:
                continue
            try:
                stated_at = datetime.fromisoformat(
                    str(stated_at_raw).replace("Z", "+00:00")
                )
                if stated_at.tzinfo is None:
                    stated_at = stated_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            hours_ago = (now - stated_at).total_seconds() / 3600.0

            if hours_ago < GAP_MIN_HOURS:
                continue                          # too recent — wait
            if hours_ago > GAP_MAX_HOURS:
                indices_to_mark.append(idx)       # expired — archive silently
                continue

            # Intent is in the 24–48h window: check for completion
            if not recent_user_messages:
                # No follow-up messages available — fire the nudge
                pending_gap = {
                    "intent_text": intent["intent"],
                    "stated_at":   intent["stated_at"],
                }
                indices_to_mark.append(idx)
                break

            try:
                result  = self.llm_service.check_intent_completion(
                    intent["intent"], recent_user_messages, self.language
                )
                outcome = result.get("outcome", "unknown")
                indices_to_mark.append(idx)
                if outcome == "unknown":
                    pending_gap = {
                        "intent_text": intent["intent"],
                        "stated_at":   intent["stated_at"],
                    }
                    break  # Only one gap nudge per user per cycle
            except Exception as e:
                print(f"⚠️  BehaviouralGapHeuristic completion check ({self.username}): {e}")

        # ── Phase C: Write ─────────────────────────────────────────────────────
        nothing_changed = (
            not new_intents
            and pending_gap is None
            and not indices_to_mark
            and last_scanned_to_save == last_scanned
        )
        if nothing_changed:
            return

        for idx in indices_to_mark:
            if idx < len(all_intents):
                all_intents[idx]["checked"] = True

        try:
            if not self.mongodb_client.connect():
                return
            update: dict = {
                "$set": {
                    "proactiveMemory.open_intents":                     all_intents,
                    "proactiveMemory.last_intent_scan_conversation_id": last_scanned_to_save,
                }
            }
            if pending_gap:
                update["$set"]["proactiveMemory.pending_gap_followup"] = pending_gap
                print(f"🔍 Gap followup queued for {self.user_id}: "
                      f"'{pending_gap['intent_text'][:50]}'")
            self.mongodb_client.db[self.mongodb_client.users_collection].update_one(
                {"_id": _ObjectId(self.user_id)}, update
            )
        except Exception as e:
            print(f"⚠️  BehaviouralGapHeuristic.create_memory write ({self.username}): {e}")
        finally:
            self.mongodb_client.disconnect()

    def get_proactive_message(self) -> Optional[str]:
        """
        Returns a message if a pending gap followup exists, otherwise None.
        """
        self.create_memory()
        self._reload_user()

        followup = self._memory.get("pending_gap_followup")
        if not followup or not isinstance(followup, dict):
            return None

        intent_text = (followup.get("intent_text") or "").strip()
        if not intent_text:
            return None

        system = self.message_prompt.replace("{language}", self._target_lang)
        user_content = (
            f"USER NAME: {self.name}\n"
            f"STATED PLAN: {intent_text}\n\n"
            "Generate a gentle follow-up asking if they went through with this plan."
        )
        try:
            text = self.llm_service.call_with_prompt(
                system=system,
                user_content=user_content,
                temperature=0.5,
                max_tokens=80,
            )
            if text and len(text) >= 2 and text[0] in ('"', "'") and text[0] == text[-1]:
                text = text[1:-1].strip()
            return text or f"Hi {self.name}, did you end up {intent_text}?"
        except Exception as e:
            print(f"⚠️  BehaviouralGapHeuristic message LLM ({self.username}): {e}")
            return f"Hi {self.name}, did you end up {intent_text}?"

    def clear_after_send(self) -> None:
        """Remove pending_gap_followup after a successful send."""
        clear_followup(self.user_id, self.mongodb_client)
