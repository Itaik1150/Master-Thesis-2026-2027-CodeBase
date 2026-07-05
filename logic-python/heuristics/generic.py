"""
GenericHeuristic — sends a neutral, emotionless chat invitation.

No topic-specific memory extraction. Always produces a message (never returns None).
Used as a control/baseline condition when the researcher assigns a non-zero
probability weight to "generic" in the experiment's heuristicWeights.

Task 6.3: create_memory() reads recent messages solely for language detection
so that the user's preferred language is persisted and used in the message prompt.
"""
from __future__ import annotations

from typing import Optional

from bson import ObjectId as _ObjectId

from heuristics.base_heuristic import BaseHeuristic


class GenericHeuristic(BaseHeuristic):
    """
    Sends a simple, friendly invitation to chat with zero emotional weight
    and no specific topic. The researcher can override the message prompt
    from the dashboard (Task 4.2) to customise the tone.

    Task 6.7: used_fallback is always False for Generic — this heuristic has
    no memory path, so it never uses a cold-start in the sense of a fallback.
    memory_content is always "" since no specific memory is referenced.
    """

    DEFAULT_MESSAGE_PROMPT = (
        "You are a standard assistant. Generate a completely neutral, friendly "
        "invitation to chat in {language} with zero emotional weight and no specific "
        "topics (max 15 words). You MAY use the user's name once if it feels natural."
    )

    def create_memory(self) -> None:
        """
        Task 6.3: No topic extraction needed, but we read recent messages to
        auto-detect the user's preferred language and persist it to MongoDB so
        subsequent heuristics (and future cycles) cascade to the correct language.
        """
        try:
            if not self.mongodb_client.connect():
                return
            metas = list(self.mongodb_client.db["metadata_conversations"].find(
                {"userId": self.user_id},
                sort=[("createdAt", -1)],
                limit=2,
            ))
            texts: list = []
            for meta in metas:
                msgs = list(self.mongodb_client.db["conversations"].find(
                    {"conversationId": str(meta["_id"]), "role": "user"},
                    sort=[("messageNumber", 1)],
                    limit=20,
                ))
                texts.extend(m.get("content", "") for m in msgs if m.get("content"))

            detected = self._detect_language(texts)
            if detected:
                self.language = detected
                self.mongodb_client.db[self.mongodb_client.users_collection].update_one(
                    {"_id": _ObjectId(self.user_id)},
                    {"$set": {"proactiveMemory.preferred_language": detected}},
                )
        except Exception as e:
            print(f"⚠️  GenericHeuristic.create_memory ({self.username}): {e}")
        finally:
            self.mongodb_client.disconnect()

    def get_proactive_message(self) -> Optional[str]:
        # Task 6.3: run create_memory + _reload_user so language is always detected
        # and fresh before the prompt is built.
        self.create_memory()
        self._reload_user()

        # Task 6.7: Generic never uses a fallback — it's always a deliberate generic path
        self.used_fallback  = False
        self.memory_content = ""

        prompt = self._safe_message_prompt(
            self.message_prompt.replace("{language}", self._target_lang)
        )
        try:
            text = self.llm_service.call_with_prompt(
                system=prompt,
                user_content=f"USER NAME: {self.name}",
                temperature=0.3,
                max_tokens=60,
            )
            if text and len(text) >= 2 and text[0] in ('"', "'") and text[0] == text[-1]:
                text = text[1:-1].strip()
            if text:
                return text
            raise ValueError("empty LLM response")
        except Exception as e:
            print(f"⚠️  GenericHeuristic.get_proactive_message({self.username}): {e}")
            if self.language == "he":
                return f"היי {self.name}, איך אתה היום?"
            return f"Hi {self.name}, how are you today?"
