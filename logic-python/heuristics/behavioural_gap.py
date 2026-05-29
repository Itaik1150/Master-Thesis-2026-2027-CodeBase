"""
Behavioural Gap Heuristic — Phase 4.5

Fires a gentle follow-up when a user stated an explicit intention
but hasn't mentioned whether they followed through after 24–48 hours.

Two-step per cycle per user (same pattern as Affective):
  1. scan_for_gaps() — side-effect only:
       - Reads the most recent conversation for stated intents.
       - Appends new intents to proactiveMemory.open_intents.
       - Checks each intent in the 24–48h window for completion via LLM.
       - If unresolved, writes pending_gap_followup to MongoDB.
  2. evaluate() — fire check:
       - If pending_gap_followup exists in the user dict, returns a GapNudge.

MongoDB fields used (inside proactiveMemory):
  open_intents: List[{intent, stated_at, checked}]
  pending_gap_followup: {intent_text, stated_at}
  last_intent_scan_conversation_id: str  — prevents re-scanning the same conversation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict


# Hours after stating an intent before we check for completion.
GAP_MIN_HOURS: float = 24   # don't check if intent is less than 24h old
GAP_MAX_HOURS: float = 48   # stop checking after 48h (too stale to be useful)


@dataclass
class GapNudge:
    intent_text: str   # what the user said they would do
    stated_at: str     # ISO timestamp of when they stated it


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate(user: dict) -> Optional[GapNudge]:
    """
    Check if a previously detected behavioural gap followup is queued for this user.
    Reads from the user dict loaded at the start of the cycle — no MongoDB needed.
    Returns a GapNudge if one is pending, otherwise None.
    """
    memory  = user.get("proactiveMemory") or {}
    followup = memory.get("pending_gap_followup")
    if not followup or not isinstance(followup, dict):
        return None

    intent_text = (followup.get("intent_text") or "").strip()
    if not intent_text:
        return None

    return GapNudge(
        intent_text=intent_text,
        stated_at=followup.get("stated_at", ""),
    )


def scan_for_gaps(user: dict, mongodb_client, llm_service) -> None:
    """
    Scan for new stated intents and check existing ones for completion.

    Phase A — Read:
      Fetches the latest finished conversation not yet scanned, plus recent
      messages from the last 3 conversations (for completion checking).

    Phase B — LLM:
      Extracts new intents from the latest conversation.
      Checks each open intent in the 24–48h window against recent messages.

    Phase C — Write:
      Appends new intents to open_intents (deduplicated by text).
      Marks checked/resolved intents. Writes pending_gap_followup if a gap found.

    Opens and closes its own MongoDB connections.
    llm_service must be a ProactiveLogic instance.
    """
    from bson import ObjectId

    user_id       = str(user["_id"])
    memory        = user.get("proactiveMemory") or {}
    last_scanned  = memory.get("last_intent_scan_conversation_id", "")
    existing_intents: List[Dict] = list(memory.get("open_intents") or [])
    language      = memory.get("preferred_language", "he")

    # ── Phase A: Read ─────────────────────────────────────────────────────────
    new_conv_messages:    List[str] = []
    recent_user_messages: List[str] = []
    last_scanned_to_save: str       = last_scanned

    try:
        if not mongodb_client.connect():
            return

        # Sort by createdAt (same as extract_conversation_memory) to reach
        # the conversations that actually contain messages.
        latest_meta = mongodb_client.db["metadata_conversations"].find_one(
            {"userId": user_id},
            sort=[("createdAt", -1)],
        )
        if latest_meta:
            conv_id = str(latest_meta["_id"])
            if conv_id != last_scanned:
                raw = list(mongodb_client.db["conversations"].find(
                    {"conversationId": conv_id, "role": "user"},
                    sort=[("messageNumber", 1)],
                ))
                new_conv_messages    = [m.get("content", "") for m in raw if m.get("content")]
                last_scanned_to_save = conv_id
                if new_conv_messages:
                    print(f"   🔍 gap: scanning conv {conv_id[:8]}... ({len(new_conv_messages)} msgs)")

        # Recent messages from last 3 conversations (for completion checking)
        recent_metas = list(mongodb_client.db["metadata_conversations"].find(
            {"userId": user_id},
            sort=[("createdAt", -1)],
            limit=3,
        ))
        for meta in recent_metas:
            raw = list(mongodb_client.db["conversations"].find(
                {"conversationId": str(meta["_id"]), "role": "user"},
                sort=[("messageNumber", 1)],
            ))
            recent_user_messages.extend(
                [m.get("content", "") for m in raw if m.get("content")]
            )

    except Exception as e:
        print(f"⚠️  gap.scan_for_gaps: read error for {user_id}: {e}")
        return
    finally:
        mongodb_client.disconnect()

    # ── Phase B: LLM ──────────────────────────────────────────────────────────
    # B-1: Extract new intents from the latest conversation
    new_intents: List[Dict] = []
    if new_conv_messages:
        try:
            extracted = llm_service.extract_stated_intents(new_conv_messages, language)
            existing_texts = {i.get("intent", "").lower() for i in existing_intents}
            now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            for item in extracted:
                text = (item.get("intent") or "").strip()
                if text and text.lower() not in existing_texts:
                    new_intents.append({"intent": text, "stated_at": now_iso, "checked": False})
                    existing_texts.add(text.lower())
        except Exception as e:
            print(f"⚠️  gap.scan_for_gaps: intent extraction error for {user_id}: {e}")

    # B-2: Check completion for intents in the 24–48h window
    all_intents  = existing_intents + new_intents
    now          = datetime.now(timezone.utc)
    pending_gap: Optional[Dict] = None
    indices_to_mark_checked:  List[int] = []

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
            continue   # too recent — wait for the gap window

        if hours_ago > GAP_MAX_HOURS:
            indices_to_mark_checked.append(idx)   # expired — archive silently
            continue

        # In window: run completion check
        if not recent_user_messages:
            # No messages to check — fire the nudge (we can't know if resolved)
            pending_gap = {"intent_text": intent["intent"], "stated_at": intent["stated_at"]}
            indices_to_mark_checked.append(idx)
            break

        try:
            result = llm_service.check_intent_completion(
                intent["intent"], recent_user_messages, language
            )
            outcome = result.get("outcome", "unknown")
            indices_to_mark_checked.append(idx)

            if outcome == "unknown":
                pending_gap = {
                    "intent_text": intent["intent"],
                    "stated_at":   intent["stated_at"],
                }
                break   # only one gap nudge per user per cycle

        except Exception as e:
            print(f"⚠️  gap.scan_for_gaps: completion check error for {user_id}: {e}")

    # ── Phase C: Write ────────────────────────────────────────────────────────
    nothing_changed = (
        not new_intents
        and pending_gap is None
        and not indices_to_mark_checked
        and last_scanned_to_save == last_scanned
    )
    if nothing_changed:
        return

    for idx in indices_to_mark_checked:
        if idx < len(all_intents):
            all_intents[idx]["checked"] = True

    try:
        if not mongodb_client.connect():
            return

        update: Dict = {
            "$set": {
                "proactiveMemory.open_intents": all_intents,
                "proactiveMemory.last_intent_scan_conversation_id": last_scanned_to_save,
            }
        }
        if pending_gap:
            update["$set"]["proactiveMemory.pending_gap_followup"] = pending_gap
            print(
                f"🔍 Gap followup queued for {user_id}: "
                f"'{pending_gap['intent_text'][:50]}'"
            )

        mongodb_client.db[mongodb_client.users_collection].update_one(
            {"_id": ObjectId(user_id)},
            update,
        )

    except Exception as e:
        print(f"⚠️  gap.scan_for_gaps: write error for {user_id}: {e}")
    finally:
        mongodb_client.disconnect()


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
