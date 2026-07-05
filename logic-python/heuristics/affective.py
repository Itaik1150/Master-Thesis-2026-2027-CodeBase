"""
Affective Heuristic

Detects emotionally charged conversations and generates an empathetic
check-in referencing the user's shared emotional content.

create_memory() extracts emotional_memories via LLM; get_proactive_message()
picks the best unused memory (or falls back to a warm cold-start invitation)
and generates the check-in message. Memories are marked used as soon as they
are selected, so each one fires at most once.

MongoDB fields used (all inside proactiveMemory):
  emotional_memories: [{content, affective_score, timestamp_iso, used}]
  last_affective_analyzed_msg_count: int — total user messages seen at last analysis.

Task 6.6 note: last_affective_analyzed_msg_count is PRIVATE to AffectiveHeuristic.
  No other heuristic must read or write this field. Its name is intentionally
  prefixed with "affective_" (abbreviated as "last_affective_") to enforce isolation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

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

    # Task 6.5: researcher-facing prompt — persona/task only, no schema or output constraints.
    # Schema and "Return ONLY valid JSON" are injected automatically by _safe_memory_prompt().
    DEFAULT_MEMORY_PROMPT = (
        "You analyze conversation messages for deep emotional content.\n"
        "Extract emotional expressions, personal struggles, vulnerable shares, "
        "and meaningful life events shared by the user.\n\n"
        "Exclude casual mentions, surface-level topics, or purely factual statements."
    )

    # Task 6.5: structural part — injected by _safe_memory_prompt(), never shown in UI.
    MEMORY_SCHEMA: str = (
        "For each genuine emotional share, produce an object with:\n"
        '  "content":        exact quote or close paraphrase of the emotional share\n'
        '  "affective_score": integer 1\u201310 (1=mildly emotional, 10=deeply personal/distressing)\n'
        '  "timestamp_iso":  use today\'s ISO datetime for all items\n'
        '  "used":           false\n\n'
        'Schema: {"emotional_memories": [{"content": str, "affective_score": int 1\u201310, '
        '"timestamp_iso": str, "used": false}]}\n'
        'Return {"emotional_memories": []} if no genuine emotional content is present.'
    )

    DEFAULT_MESSAGE_PROMPT = (
        "You are an empathetic assistant that encourages emotional sharing.\n"
        "Generate a warm, personal emotional check-in (max 15 words) "
        "that directly references the specific emotional memory the user shared.\n"
        "Acknowledge their feelings without being dramatic or clinical.\n"
        "Invite them to share how they are feeling about it now.\n"
        "You MAY use the user's name once if it feels natural."
    )

    _COLD_START_PROMPT = (
        "You are an empathetic assistant that encourages emotional sharing.\n"
        "Generate a gentle, warm invitation (max 15 words) "
        "focused on emotional support and being a listening ear today.\n"
        "Use the user's name naturally."
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

        # Task 6.3: detect language from the messages collected above.
        # No extra DB call — character analysis only. Result is written to
        # proactiveMemory.preferred_language in Phase C below.
        _detected_lang = self._detect_language(all_texts)
        if _detected_lang:
            self.language = _detected_lang  # Use correct language in this cycle

        # ── Phase B: LLM extraction (outside DB connection) ────────────────────
        today_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        joined = "\n".join(f"- {m}" for m in all_texts[-20:] if m)
        # _safe_memory_prompt appends STRUCTURAL_JSON_SUFFIX (Task 6.5)
        system = self._safe_memory_prompt(
            self.memory_prompt.replace("{today_iso}", today_iso)
        )

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
            # Task 6.3: persist detected language so future cycles read it from
            # proactiveMemory.preferred_language (level 1 of the cascade).
            if _detected_lang:
                update["$set"]["proactiveMemory.preferred_language"] = _detected_lang
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
          (Task 6.2: guaranteed fallback — never returns None)
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

            # Task 6.7: record which memory drove this message
            self.memory_content = content[:120]
            self.used_fallback  = False

            system = self._safe_message_prompt(self.message_prompt)
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
                # Language-aware static fallback
                if self.language == "he":
                    return f"היי {self.name}, חשבתי על מה ששיתפת. איך אתה מרגיש עם זה עכשיו?"
                return f"Hi {self.name}, I was thinking about what you shared. How are you feeling about it now?"
        else:
            # Cold start: no unused memories — Task 6.2: guaranteed fallback
            # Task 6.7: mark as fallback path
            self.memory_content = ""
            self.used_fallback  = True

            print(f"💛 [{self.username}] Affective cold-start — no unused memories")
            prompt = self._COLD_START_PROMPT
            uc = (
                f"USER NAME: {self.name}\n\n"
                "Generate a gentle emotional invitation letting them know you are "
                "here as a listening ear today."
            )
            # Language-aware static fallback if LLM fails
            if self.language == "he":
                fallback = f"היי {self.name}, רק בודק — אני כאן אם צריך אוזן קשבת."
            else:
                fallback = f"Hi {self.name}, just checking in — I'm here if you need a listening ear."
            return self._cold_start_message(
                prompt=prompt,
                static_fallback=fallback,
                user_content=uc,
            )

    # No clear_after_send() override needed: the emotional memory is already
    # marked used the moment it is selected in get_proactive_message(), so
    # there is nothing left to clean up after a successful send.
