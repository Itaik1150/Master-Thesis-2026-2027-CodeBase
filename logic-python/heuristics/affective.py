"""
Affective Heuristic

Detects emotionally charged conversations and schedules a follow-up check-in.
Follows the same two-step pattern as temporal.py and behavioural_gap.py:

  1. analyze_and_schedule(user, mongodb_client, llm_service)
       Side-effect only. Reads the last N conversations, runs LLM emotion
       analysis, and writes a pending followup to MongoDB when emotional
       intensity >= INTENSITY_THRESHOLD.

  2. evaluate(user) → AffectiveNudge | None
       Fire check. Returns an AffectiveNudge if a scheduled followup is now
       due, otherwise None.

  3. clear_followup(user_id, mongodb_client)
       Called after a successful FCM send to remove the pending followup.

Note: the experiment-specific affective default message (cold-start / context-rich
emotional check-in for Group 1) lives in ResearchService._generate_affective_default_message,
not here. This module is experiment-agnostic.

MongoDB fields used (all inside proactiveMemory):
  pending_affective_followup: {emotion, intensity, scheduled_for}
  last_affective_analyzed_msg_count: int — total user messages seen at last analysis.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


# Minimum LLM-rated intensity (0–1) required to schedule a followup.
INTENSITY_THRESHOLD: float = 0.7

# Override delay for testing: set AFFECTIVE_DELAY_HOURS=0 in .env to fire
# the check-in in the very next cycle rather than waiting 2-8 hours.
# Leave unset in production so the LLM's suggested delay is used.
_DELAY_OVERRIDE = os.getenv("AFFECTIVE_DELAY_HOURS")
DELAY_OVERRIDE_HOURS: float | None = float(_DELAY_OVERRIDE) if _DELAY_OVERRIDE is not None else None


@dataclass
class AffectiveNudge:
    emotion: str           # e.g. "stressed", "anxious", "sad", "frustrated"
    intensity: float       # 0.0 – 1.0
    conversation_id: str   # the conversation that triggered this


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate(user: dict) -> Optional[AffectiveNudge]:
    """
    Check if a previously scheduled affective followup is now due.
    Reads from the user dict loaded at the start of the cycle.
    Returns an AffectiveNudge if it is time to send, otherwise None.
    """
    memory  = user.get("proactiveMemory") or {}
    followup = memory.get("pending_affective_followup")
    if not followup or not isinstance(followup, dict):
        return None

    scheduled_raw = followup.get("scheduled_for")
    if not scheduled_raw:
        return None

    try:
        scheduled_for = datetime.fromisoformat(
            str(scheduled_raw).replace("Z", "+00:00")
        )
        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

    if datetime.now(timezone.utc) >= scheduled_for:
        return AffectiveNudge(
            emotion=followup.get("emotion", "stressed"),
            intensity=float(followup.get("intensity", INTENSITY_THRESHOLD)),
            conversation_id=followup.get("conversation_id", ""),
        )

    return None


_CONV_SCAN_LIMIT = 3   # how many recent conversations to scan (same as extract_conversation_memory)


def analyze_and_schedule(user: dict, mongodb_client, llm_service) -> None:
    """
    Scan the last N conversations for emotional content and schedule a check-in
    if the combined emotional intensity is high enough.

    Uses the same multi-conversation scan approach as extract_conversation_memory
    so it is immune to empty metadata entries that happen to sort first.

    Deduplication: stores last_affective_analyzed_msg_count (total user messages
    across the scanned conversations). Re-analysis is triggered only when new
    messages arrive.

    Opens and closes its own MongoDB connections.
    llm_service must be a ProactiveLogic instance.
    """
    from bson import ObjectId

    user_id  = str(user["_id"])
    memory   = user.get("proactiveMemory") or {}
    language = memory.get("preferred_language", "he")
    last_count = int(memory.get("last_affective_analyzed_msg_count") or 0)

    # ── Phase A: Read messages from the last N conversations ──────────────────
    all_user_texts = []

    try:
        if not mongodb_client.connect():
            print(f"⚠️  affective.analyze_and_schedule: could not connect for {user_id}")
            return

        # Sort by createdAt (same as extract_conversation_memory) so we reach
        # the conversations that actually contain messages.
        recent_metas = list(mongodb_client.db["metadata_conversations"].find(
            {"userId": user_id},
            sort=[("createdAt", -1)],
            limit=_CONV_SCAN_LIMIT,
        ))

        if not recent_metas:
            return

        for meta in recent_metas:
            conv_id = str(meta["_id"])
            raw = list(mongodb_client.db["conversations"].find(
                {"conversationId": conv_id, "role": "user"},
                sort=[("messageNumber", 1)],
            ))
            all_user_texts.extend([m.get("content", "") for m in raw if m.get("content")])

    except Exception as e:
        print(f"⚠️  affective.analyze_and_schedule: DB read error for {user_id}: {e}")
        return

    current_count = len(all_user_texts)

    if current_count == 0 or current_count <= last_count:
        return

    # ── Phase B: LLM  emotion analysis (outside DBconnection) ─────────────────
    try:
        result = llm_service.analyze_conversation_emotion(all_user_texts[-20:], language)
    except Exception as e:
        print(f"⚠️  affective.analyze_and_schedule: LLM error for {user_id}: {e}")
        return

    intensity      = float(result.get("intensity", 0.0))
    needs_followup = result.get("needs_followup", False)

    # ── Phase C: Write result to MongoDB ──────────────────────────────────────
    try:
        if not mongodb_client.connect():
            return

        if intensity >= INTENSITY_THRESHOLD and needs_followup:
            delay_hours = (
                DELAY_OVERRIDE_HOURS
                if DELAY_OVERRIDE_HOURS is not None
                else float(result.get("suggested_delay_hours", 4))
            )
            scheduled_for = (
                datetime.now(timezone.utc).replace(microsecond=0)
                + timedelta(hours=delay_hours)
            )
            mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "proactiveMemory.pending_affective_followup": {
                            "emotion":        result.get("primary_emotion", "stressed"),
                            "intensity":      intensity,
                            "scheduled_for":  scheduled_for.isoformat(),
                        },
                        "proactiveMemory.last_affective_analyzed_msg_count": current_count,
                    }
                },
            )
            print(
                f"💛 Affective followup scheduled for {user_id}: "
                f"{result.get('primary_emotion')} ({intensity:.2f}), "
                f"fires in {delay_hours}h at {scheduled_for.strftime('%H:%M UTC')}"
            )
        else:
            mongodb_client.db[mongodb_client.users_collection].update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"proactiveMemory.last_affective_analyzed_msg_count": current_count}},
            )

    except Exception as e:
        print(f"⚠️  affective.analyze_and_schedule: DB write error for {user_id}: {e}")


def clear_followup(user_id: str, mongodb_client) -> None:
    """
    Remove pending_affective_followup after a nudge is successfully sent.
    Uses $unset so no other proactiveMemory fields are disturbed.
    Opens and closes its own MongoDB connection.
    """
    from bson import ObjectId

    try:
        if not mongodb_client.connect():
            print(f"⚠️  affective.clear_followup: could not connect for {user_id}")
            return
        mongodb_client.db[mongodb_client.users_collection].update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"proactiveMemory.pending_affective_followup": ""}},
        )
        print(f"💛 Affective followup cleared for user {user_id}")
    except Exception as e:
        print(f"⚠️  affective.clear_followup error for {user_id}: {e}")


# ── AffectiveHeuristic class (Task 3.2) ───────────────────────────────────────
# The module-level functions above (analyze_and_schedule, evaluate, clear_followup)
# are kept for backward compatibility and will be removed in Task 5.2.

import json
from bson import ObjectId as _ObjectId

from heuristics.base_heuristic import BaseHeuristic


class AffectiveHeuristic(BaseHeuristic):
    """
    Detects emotional content in recent conversations and generates an
    empathetic check-in. Always produces a message (cold-start fallback
    ensures there is always something to send when affective is selected).

    Memory field: proactiveMemory.emotional_memories
      List of {content, affective_score (1-10), timestamp_iso, used: bool}

    Deduplication: last_affective_analyzed_msg_count tracks how many user
    messages have been processed; create_memory() skips if none are new.
    """

    DEFAULT_MEMORY_PROMPT = (
        "You analyze conversation messages for deep emotional content.\n"
        "Extract emotional expressions, personal struggles, vulnerable shares, "
        "and meaningful life events shared by the user.\n\n"
        "For each genuine emotional share, produce an object with:\n"
        '  "content":        exact quote or close paraphrase of the emotional share\n'
        '  "affective_score": integer 1–10 (1=mildly emotional, 10=deeply personal/distressing)\n'
        '  "timestamp_iso":  use today\'s ISO datetime for all items\n'
        '  "used":           false\n\n'
        "Return ONLY valid JSON: {\"emotional_memories\": [...]}\n"
        "Exclude casual mentions, surface-level topics, or purely factual statements.\n"
        'Return {"emotional_memories": []} if no genuine emotional content is present.'
    )

    DEFAULT_MESSAGE_PROMPT = (
        "You are an empathetic assistant that encourages emotional sharing.\n"
        "Generate a warm, personal emotional check-in in {language} (max 15 words) "
        "that directly references the specific emotional memory the user shared.\n"
        "Acknowledge their feelings without being dramatic or clinical.\n"
        "Invite them to share how they are feeling about it now.\n"
        "You MAY use the user's name once if it feels natural.\n"
        "Return ONLY the final message, no quotes or explanations."
    )

    _COLD_START_PROMPT = (
        "You are an empathetic assistant that encourages emotional sharing.\n"
        "Generate a gentle, warm invitation in {language} (max 15 words) "
        "focused on emotional support and being a listening ear today.\n"
        "Use the user's name naturally.\n"
        "Return ONLY the final message, no quotes or explanations."
    )

    _MEMORY_EXPIRY_HOURS: int = 72
    _CONV_SCAN_LIMIT: int = 3

    def create_memory(self) -> None:
        """
        Scan the last N conversations for unprocessed user messages.
        Extract emotional_memories via LLM and push new ones to MongoDB.
        Skips entirely if no new messages since the last analysis run.
        """
        memory = self._memory
        last_count = int(memory.get("last_affective_analyzed_msg_count") or 0)
        all_texts = []

        # ── Phase A: Read messages ─────────────────────────────────────────────
        try:
            if not self.mongodb_client.connect():
                return
            recent_metas = list(self.mongodb_client.db["metadata_conversations"].find(
                {"userId": self.user_id},
                sort=[("createdAt", -1)],
                limit=self._CONV_SCAN_LIMIT,
            ))
            if not recent_metas:
                return
            for meta in recent_metas:
                conv_id = str(meta["_id"])
                raw = list(self.mongodb_client.db["conversations"].find(
                    {"conversationId": conv_id, "role": "user"},
                    sort=[("messageNumber", 1)],
                ))
                all_texts.extend([m.get("content", "") for m in raw if m.get("content")])
        except Exception as e:
            print(f"⚠️  AffectiveHeuristic.create_memory read ({self.username}): {e}")
            return
        finally:
            self.mongodb_client.disconnect()

        current_count = len(all_texts)
        if current_count == 0 or current_count <= last_count:
            return  # No new messages to analyze

        # ── Phase B: LLM extraction (outside DB connection) ────────────────────
        today_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        joined = "\n".join(f"- {m}" for m in all_texts[-20:] if m)
        system = self.memory_prompt.replace("{today_iso}", today_iso)

        new_memories = []
        try:
            raw_text = self.llm_service.call_with_prompt(
                system=system,
                user_content=f"User messages:\n{joined}",
                json_mode=True,
                max_tokens=600,
            )
            parsed = json.loads(raw_text)
            for item in (parsed.get("emotional_memories") or []):
                content = (item.get("content") or "").strip()
                if content:
                    new_memories.append({
                        "content":        content,
                        "affective_score": max(1, min(10, int(item.get("affective_score") or 1))),
                        "timestamp_iso":  item.get("timestamp_iso") or today_iso,
                        "used":           False,
                    })
        except Exception as e:
            print(f"⚠️  AffectiveHeuristic.create_memory LLM ({self.username}): {e}")

        # ── Phase C: Write to MongoDB ──────────────────────────────────────────
        try:
            if not self.mongodb_client.connect():
                return
            update: dict = {
                "$set": {"proactiveMemory.last_affective_analyzed_msg_count": current_count}
            }
            if new_memories:
                update["$push"] = {
                    "proactiveMemory.emotional_memories": {"$each": new_memories}
                }
                print(f"💛 [{self.username}] Extracted {len(new_memories)} new emotional memory(ies)")
            self.mongodb_client.db[self.mongodb_client.users_collection].update_one(
                {"_id": _ObjectId(self.user_id)}, update
            )
        except Exception as e:
            print(f"⚠️  AffectiveHeuristic.create_memory write ({self.username}): {e}")
        finally:
            self.mongodb_client.disconnect()

    def get_proactive_message(self) -> Optional[str]:
        """
        Always returns a message string:
        - context-rich path: picks the best unused emotional memory and generates
          a personalised empathetic check-in referencing it
        - cold-start path: no memories available → warm generic invitation to share
        """
        self.create_memory()
        self._reload_user()

        emotional_memories = list(self._memory.get("emotional_memories") or [])
        now = datetime.now(timezone.utc)
        expiry_threshold = now - timedelta(hours=self._MEMORY_EXPIRY_HOURS)

        # Expire stale unused memories so old content is never resurfaced
        try:
            if emotional_memories and self.mongodb_client.connect():
                self.mongodb_client.db[self.mongodb_client.users_collection].update_many(
                    {
                        "_id": _ObjectId(self.user_id),
                        "proactiveMemory.emotional_memories": {
                            "$elemMatch": {
                                "used": False,
                                "timestamp_iso": {"$lt": expiry_threshold.isoformat()},
                            }
                        },
                    },
                    {"$set": {"proactiveMemory.emotional_memories.$[elem].used": True}},
                    array_filters=[{
                        "elem.used": False,
                        "elem.timestamp_iso": {"$lt": expiry_threshold.isoformat()},
                    }],
                )
        except Exception as e:
            print(f"⚠️  AffectiveHeuristic expire memories ({self.username}): {e}")
        finally:
            self.mongodb_client.disconnect()

        # Pick best unused memory (highest affective_score, then most recent)
        unused = [m for m in emotional_memories if not m.get("used", False)]
        has_context = bool(unused)

        if has_context:
            best = max(unused, key=lambda m: (
                m.get("affective_score", 1),
                m.get("timestamp_iso", "1900-01-01"),
            ))
            content = best.get("content", "")
            score   = best.get("affective_score", 1)
            system  = self.message_prompt.replace("{language}", self._target_lang)
            user_content = (
                f"USER NAME: {self.name}\n"
                f"EMOTIONAL MEMORY: {content}\n"
                f"AFFECTIVE DEPTH: {score}/10\n\n"
                "Craft a highly personalised empathetic check-in referencing this memory."
            )
            # Mark this memory as used before generating (fire-once guarantee)
            try:
                if self.mongodb_client.connect():
                    self.mongodb_client.db[self.mongodb_client.users_collection].update_one(
                        {
                            "_id": _ObjectId(self.user_id),
                            "proactiveMemory.emotional_memories": {
                                "$elemMatch": {"content": content, "used": False}
                            },
                        },
                        {"$set": {"proactiveMemory.emotional_memories.$.used": True}},
                    )
                    print(f"💛 [{self.username}] Marked emotional memory as used: '{content[:50]}'")
            except Exception as e:
                print(f"⚠️  AffectiveHeuristic mark-used ({self.username}): {e}")
            finally:
                self.mongodb_client.disconnect()
        else:
            # Cold start: no unused memories → generic warm invitation
            system = self._COLD_START_PROMPT.replace("{language}", self._target_lang)
            user_content = (
                f"USER NAME: {self.name}\n\n"
                "Generate a gentle emotional invitation letting them know you are "
                "here as a listening ear today."
            )

        try:
            text = self.llm_service.call_with_prompt(
                system=system,
                user_content=user_content,
                temperature=0.7,
                max_tokens=80,
            )
            if text and len(text) >= 2 and text[0] in ('"', "'") and text[0] == text[-1]:
                text = text[1:-1].strip()
            if not text:
                raise ValueError("empty LLM response")
            return text
        except Exception as e:
            print(f"⚠️  AffectiveHeuristic message LLM ({self.username}): {e}")
            return (
                f"Hi {self.name}, I was thinking about what you shared. "
                "How are you feeling about it now?"
                if has_context else
                f"Hi {self.name}, just checking in — I'm here if you need a listening ear."
            )

    def clear_after_send(self) -> None:
        """Clear pending_affective_followup if it still exists (backward compat)."""
        clear_followup(self.user_id, self.mongodb_client)



