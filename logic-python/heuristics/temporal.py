"""
Temporal Heuristic — Phase 4.3

Fires a nudge when a future event the user mentioned is approaching.

Signal source: user["proactiveMemory"]["future_mentions"]
Each item is already in the shape: {"text": str, "when_iso": str | null}
(written by extract_user_memory in Phase 3.4b)

Logic:
  - If any future mention has a when_iso that is 6–24 hours away (the lead-time
    window), and has not already been fired, return a TemporalNudge.
  - After a successful FCM send, call mark_fired() to stamp the mention so it
    never triggers a second time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


# ── Configuration ─────────────────────────────────────────────────────────────
# Window in which we consider an upcoming event "close enough" to act on.
# Events further than LEAD_TIME_MAX_HOURS away are skipped this cycle (they'll
# be caught in a later cycle). Events closer than LEAD_TIME_MIN_HOURS are also
# skipped — too close to meaningfully prepare the user.
LEAD_TIME_MIN_HOURS: float = 6
LEAD_TIME_MAX_HOURS: float = 24
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class TemporalNudge:
    mention_text: str   # what the user said they have coming up
    when_iso: str       # the anchor datetime string as stored in memory
    hours_until: float  # how many hours until the event (for message tone)


def evaluate(user: dict) -> Optional[TemporalNudge]:
    """
    Check if any future mention in the user's proactiveMemory falls inside
    the lead-time window and has not been fired yet.

    Returns the first qualifying TemporalNudge, or None.
    """
    memory = user.get("proactiveMemory") or {}
    future_mentions = memory.get("future_mentions") or []
    if not future_mentions:
        return None

    fired_keys: set = set(memory.get("fired_temporal_mentions") or [])
    now = datetime.now(timezone.utc)

    for mention in future_mentions:
        if not isinstance(mention, dict):
            continue

        text = (mention.get("text") or "").strip()
        when_iso = mention.get("when_iso")

        if not text or not when_iso:
            continue

        # Skip mentions we already acted on
        key = _make_key(text, when_iso)
        if key in fired_keys:
            continue

        try:
            when = datetime.fromisoformat(str(when_iso).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        hours_until = (when - now).total_seconds() / 3600.0

        if LEAD_TIME_MIN_HOURS <= hours_until <= LEAD_TIME_MAX_HOURS:
            return TemporalNudge(
                mention_text=text,
                when_iso=str(when_iso),
                hours_until=hours_until,
            )

    return None


def mark_fired(user_id: str, mention_text: str, when_iso: str, mongodb_client) -> None:
    """
    Stamp a temporal mention as fired on the user's MongoDB document so it
    cannot trigger a second notification. Uses $addToSet so duplicate calls
    are safe.

    mongodb_client must be the module-level singleton from utils/mongodb_client.py.
    This method opens and closes its own connection.
    """
    from bson import ObjectId

    key = _make_key(mention_text, when_iso)
    try:
        if not mongodb_client.connect():
            print(f"⚠️  temporal.mark_fired: could not connect to MongoDB for {user_id}")
            return
        mongodb_client.db[mongodb_client.users_collection].update_one(
            {"_id": ObjectId(user_id)},
            {"$addToSet": {"proactiveMemory.fired_temporal_mentions": key}},
        )
        print(f"🕐 Temporal mention marked as fired for user {user_id}: '{mention_text[:40]}'")
    except Exception as e:
        print(f"⚠️  temporal.mark_fired error for {user_id}: {e}")
    finally:
        mongodb_client.disconnect()


def _make_key(text: str, when_iso: str) -> str:
    """
    Stable, collision-resistant key for a (mention, datetime) pair.
    Used to track which temporal mentions have already triggered a nudge.
    """
    return f"{text[:50].strip()}|{when_iso}"
