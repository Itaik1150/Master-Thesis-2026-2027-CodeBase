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


# ── TemporalHeuristic class (Task 3.2) ────────────────────────────────────────
# The module-level functions above (evaluate, mark_fired) are kept for backward
# compatibility and will be removed in Task 5.2.

import json
from bson import ObjectId as _ObjectId

from heuristics.base_heuristic import BaseHeuristic


class TemporalHeuristic(BaseHeuristic):
    """
    Detects upcoming events the user has mentioned and sends a timely reminder
    or question when the event falls within the lead-time window (6–24 hours).

    Memory field: proactiveMemory.future_mentions
      List of {text, when_iso}

    Fired-once: proactiveMemory.fired_temporal_mentions (set of keys) ensures
    each event triggers at most one notification.

    Returns None from get_proactive_message() when no qualifying event is found.
    """

    DEFAULT_MEMORY_PROMPT = (
        "You analyze conversation messages for mentions of upcoming events, "
        "plans, appointments, or activities.\n\n"
        "For each future event found, extract:\n"
        '  "text":     concise description (e.g. "job interview", "doctor appointment")\n'
        '  "when_iso": ISO 8601 datetime string if timing is mentioned, or null if unclear\n\n'
        "Today is {today_iso}. Resolve all relative dates against today.\n"
        "Return ONLY valid JSON: {\"future_mentions\": [...]}\n"
        'Return {"future_mentions": []} if no future events are mentioned.'
    )

    DEFAULT_MESSAGE_PROMPT = (
        "You are a friendly assistant. Generate a warm, timely message in {language} "
        "(max 15 words) about the user's upcoming event or plan.\n"
        "If the event is still ahead: ask if they are ready or excited.\n"
        "If the event just passed: ask how it went.\n"
        "Never confuse past and future timing. "
        "You MAY use the user's name once. "
        "Return ONLY the final message, no quotes or explanations."
    )

    _CONV_SCAN_LIMIT: int = 5

    def __init__(self, user, llm_service, mongodb_client, prompts_from_db=None):
        super().__init__(user, llm_service, mongodb_client, prompts_from_db)
        self._fired_nudge: Optional[dict] = None  # set in get_proactive_message

    def create_memory(self) -> None:
        """
        Extract future_mentions from recent conversations and merge them into
        proactiveMemory.future_mentions, deduplicating by text.
        Already-fired mentions are not re-added.
        """
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
            print(f"⚠️  TemporalHeuristic.create_memory read ({self.username}): {e}")
            return
        finally:
            self.mongodb_client.disconnect()

        if not all_texts:
            return

        # ── Phase B: LLM extraction ────────────────────────────────────────────
        today_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        joined = "\n".join(f"- {m}" for m in all_texts[-40:] if m)
        system = self.memory_prompt.replace("{today_iso}", today_iso)

        new_mentions = []
        try:
            raw_text = self.llm_service.call_with_prompt(
                system=system,
                user_content=f"User messages:\n{joined}",
                json_mode=True,
                max_tokens=400,
            )
            parsed = json.loads(raw_text)
            for item in (parsed.get("future_mentions") or []):
                if isinstance(item, dict):
                    text_val = (item.get("text") or "").strip()
                    if text_val:
                        new_mentions.append({
                            "text":     text_val,
                            "when_iso": item.get("when_iso"),
                        })
        except Exception as e:
            print(f"⚠️  TemporalHeuristic.create_memory LLM ({self.username}): {e}")
            return

        if not new_mentions:
            return

        # ── Phase C: Merge into MongoDB (deduplicate by text, skip fired keys) ─
        try:
            if not self.mongodb_client.connect():
                return
            user_doc = self.mongodb_client.db[self.mongodb_client.users_collection].find_one(
                {"_id": _ObjectId(self.user_id)},
                {"proactiveMemory.future_mentions": 1,
                 "proactiveMemory.fired_temporal_mentions": 1},
            )
            existing = (user_doc or {}).get("proactiveMemory", {}).get("future_mentions") or []
            fired_keys = set(
                (user_doc or {}).get("proactiveMemory", {}).get("fired_temporal_mentions") or []
            )
            existing_texts = {(m.get("text") or "").lower() for m in existing}
            to_add = [
                m for m in new_mentions
                if m["text"].lower() not in existing_texts
                and _make_key(m["text"], m.get("when_iso") or "") not in fired_keys
            ]
            if to_add:
                self.mongodb_client.db[self.mongodb_client.users_collection].update_one(
                    {"_id": _ObjectId(self.user_id)},
                    {"$push": {"proactiveMemory.future_mentions": {"$each": to_add}}},
                )
                print(f"🕐 [{self.username}] Added {len(to_add)} new future mention(s)")
        except Exception as e:
            print(f"⚠️  TemporalHeuristic.create_memory write ({self.username}): {e}")
        finally:
            self.mongodb_client.disconnect()

    def get_proactive_message(self) -> Optional[str]:
        """
        Returns a message if a future mention falls in the 6–24h window,
        otherwise returns None (heuristic has nothing to send this cycle).
        """
        self.create_memory()
        self._reload_user()

        future_mentions = self._memory.get("future_mentions") or []
        fired_keys = set(self._memory.get("fired_temporal_mentions") or [])
        now = datetime.now(timezone.utc)

        # Find first qualifying mention
        for mention in future_mentions:
            if not isinstance(mention, dict):
                continue
            text     = (mention.get("text") or "").strip()
            when_iso = mention.get("when_iso")
            if not text or not when_iso:
                continue
            if _make_key(text, when_iso) in fired_keys:
                continue
            try:
                when = datetime.fromisoformat(str(when_iso).replace("Z", "+00:00"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
            hours_until = (when - now).total_seconds() / 3600.0
            if LEAD_TIME_MIN_HOURS <= hours_until <= LEAD_TIME_MAX_HOURS:
                self._fired_nudge = {
                    "mention_text": text,
                    "when_iso":     str(when_iso),
                    "hours_until":  hours_until,
                }
                break

        if not self._fired_nudge:
            return None  # Nothing in the lead-time window this cycle

        n = self._fired_nudge
        print(f"🕐 [{self.username}] Temporal event in window: '{n['mention_text'][:40]}' "
              f"({n['hours_until']:.1f}h away)")

        system = self.message_prompt.replace("{language}", self._target_lang)
        user_content = (
            f"USER NAME: {self.name}\n"
            f"EVENT: {n['mention_text']}\n"
            f"HOURS UNTIL EVENT (negative = already passed): {n['hours_until']:.1f}"
        )
        try:
            text = self.llm_service.call_with_prompt(
                system=system,
                user_content=user_content,
                temperature=0.6,
                max_tokens=80,
            )
            if text and len(text) >= 2 and text[0] in ('"', "'") and text[0] == text[-1]:
                text = text[1:-1].strip()
            return text or f"Hi {self.name}, your event '{n['mention_text']}' is coming up!"
        except Exception as e:
            print(f"⚠️  TemporalHeuristic message LLM ({self.username}): {e}")
            return f"Hi {self.name}, your event '{n['mention_text']}' is coming up!"

    def clear_after_send(self) -> None:
        """Mark the fired temporal mention so it never triggers again."""
        if self._fired_nudge:
            mark_fired(
                self.user_id,
                self._fired_nudge["mention_text"],
                self._fired_nudge["when_iso"],
                self.mongodb_client,
            )
