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



