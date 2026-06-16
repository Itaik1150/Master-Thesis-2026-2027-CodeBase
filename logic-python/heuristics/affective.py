"""
Affective Heuristic — Phase 4.4 + Task 2 Strict Emotional Framing

Fires empathetic check-ins for users in the 'affective' proactive group.

Two-step per cycle per user:
  1. analyze_and_schedule() — reads the last N conversations, runs emotion analysis,
     and writes a pending followup when intensity >= INTENSITY_THRESHOLD.
  2. evaluate() — checks if a previously scheduled followup is now due.
     Returns an AffectiveNudge if it is, otherwise None.

NEW: Strict Emotional Framing for Group 1 (Affective Proactive):
  - generate_affective_default() — creates empathetic prompts based on sensitivity_score
  - Cold Start: gentle emotional invitation when no high-sensitivity data exists
  - Context-Rich: personalized check-in using highest sensitivity memories

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
    last_count = int(memory.get("last_affective_analyzed_msg_count", 0))

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
    finally:
        mongodb_client.disconnect()

    current_count = len(all_user_texts)

    if current_count == 0 or current_count <= last_count:
        return

    print(f"   💛 affective: {current_count} msgs ({last_count}→{current_count}), analyzing...")

    # ── Phase B: LLM emotion analysis (outside DB connection) ─────────────────
    try:
        result = llm_service.analyze_conversation_emotion(all_user_texts[-20:], language)
    except Exception as e:
        print(f"⚠️  affective.analyze_and_schedule: LLM error for {user_id}: {e}")
        return

    intensity      = float(result.get("intensity", 0.0))
    needs_followup = result.get("needs_followup", False)
    print(f"   💛 affective: {result.get('primary_emotion')} intensity={intensity:.2f} needs_followup={needs_followup}")

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
    finally:
        mongodb_client.disconnect()


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
    finally:
        mongodb_client.disconnect()


def generate_affective_default(user_memory: dict, user_name: str, user_id: str, llm_service, mongodb_client) -> dict:
    """
    Generate affective proactive notification for Group 1 (Affective Proactive).
    
    Strict Emotional Framing Rules:
    1. Context-Rich: If unused emotional_memories exist, select the best one by 
       affective_score (desc) then timestamp (desc), generate personalized check-in,
       and mark it as used in MongoDB.
    2. Cold Start: If no unused emotional memories, generate gentle emotional invitation
       purely focused on emotional sharing with user's name.
    
    Args:
        user_memory: proactiveMemory dict containing emotional_memories array
        user_name: user's display name
        user_id: user's MongoDB _id for DB updates
        llm_service: ProactiveLogic instance for LLM calls
        mongodb_client: MongoDB client for marking memories as used
        
    Returns:
        dict with generated_message, topic_label, personalized flag
    """
    from bson import ObjectId
    
    preferred_language = user_memory.get('preferred_language', 'he')
    target_lang = "Hebrew" if preferred_language == "he" else "English"
    emotional_memories = user_memory.get('emotional_memories', [])
    
    # Filter to find unused emotional memories
    unused_memories = [mem for mem in emotional_memories if not mem.get('used', False)]
    
    # Determine if we have unused emotional context for personalization
    has_emotional_context = bool(unused_memories)
    
    if has_emotional_context:
        # Context-Rich: Select best unused emotional memory and personalize
        # Sort by affective_score (desc), then by timestamp_iso (desc for most recent)
        best_memory = max(unused_memories, key=lambda m: (
            m.get('affective_score', 1), 
            m.get('timestamp_iso', '1900-01-01')
        ))
        
        memory_content = best_memory.get('content', '')
        affective_score = best_memory.get('affective_score', 1)
        
        system_prompt = (
            f"You are an empathetic agent that encourages emotional sharing. "
            f"Generate a warm, personal emotional check-in in {target_lang} (max 15 words) "
            f"that directly references this specific emotional memory the user shared. "
            f"Acknowledge their feelings without being dramatic or clinical. "
            f"Invite them to share how they're feeling now about this or related topics. "
            f"You MAY use the user's name once if it feels natural. "
            f"Return ONLY the final message, no quotes or explanations."
        )
        
        user_prompt = (
            f"USER NAME: {user_name}\n"
            f"SPECIFIC EMOTIONAL MEMORY: {memory_content}\n"
            f"AFFECTIVE DEPTH: {affective_score}/10\n\n"
            f"Craft a highly personalized empathetic check-in directly referencing "
            f"this specific emotional memory. Show that you remember and care about "
            f"what they shared."
        )
        
        topic_label = "affective_context_rich"
        
        # Mark this memory as used in MongoDB
        try:
            if mongodb_client.connect():
                mongodb_client.db[mongodb_client.users_collection].update_one(
                    {
                        "_id": ObjectId(user_id),
                        "proactiveMemory.emotional_memories.content": memory_content
                    },
                    {
                        "$set": {
                            "proactiveMemory.emotional_memories.$.used": True
                        }
                    }
                )
                print(f"💛 Marked emotional memory as used for {user_name}: '{memory_content[:50]}...'")
        except Exception as e:
            print(f"⚠️ Failed to mark emotional memory as used for {user_id}: {e}")
        finally:
            try:
                mongodb_client.disconnect()
            except Exception:
                pass
        
    else:
        # Cold Start: Gentle emotional invitation with user's name
        system_prompt = (
            f"You are an empathetic agent that encourages emotional sharing. "
            f"Generate a gentle, warm invitation in {target_lang} (max 15 words) "
            f"purely focused on emotional sharing and being a listening ear. "
            f"Use the user's name naturally. "
            f"Return ONLY the final message, no quotes or explanations."
        )
        
        user_prompt = (
            f"USER NAME: {user_name}\n\n"
            f"Generate a gentle emotional invitation that lets them know you're here "
            f"if they need a listening ear today. Focus purely on emotional support."
        )
        
        topic_label = "affective_cold_start"
    
    # Call LLM to generate the message
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    
    try:
        generated_message = llm_service._call_llm(messages, temperature=0.7, max_tokens=80)
        
        # Strip wrapping quotes if LLM added them
        if (generated_message.startswith('"') and generated_message.endswith('"')) or (
            generated_message.startswith("'") and generated_message.endswith("'")
        ):
            generated_message = generated_message[1:-1].strip()
            
        # Fallback if generation failed
        if not generated_message:
            if has_emotional_context:
                generated_message = f"Hi {user_name}, I was thinking about what you shared earlier. How are you feeling about it now?"
            else:
                generated_message = f"Hi {user_name}, just checking in. I'm here if you need a listening ear today."
                
    except Exception as e:
        print(f"❌ generate_affective_default LLM error: {e}")
        # Safe fallback
        if has_emotional_context:
            generated_message = f"Hi {user_name}, I was thinking about what you shared earlier. How are you feeling about it now?"
        else:
            generated_message = f"Hi {user_name}, just checking in. I'm here if you need a listening ear today."
    
    return {
        "generated_message": generated_message,
        "topic_label": topic_label,
        "personalized": has_emotional_context,
        "trigger_source": "affective_default",
        "source": "affective",
        "has_context": has_emotional_context,
        "selected_memory": best_memory.get('content', '') if has_emotional_context else '',
    }


