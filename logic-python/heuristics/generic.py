"""
GenericHeuristic — sends a neutral, emotionless chat invitation.

No memory extraction. Always produces a message (never returns None).
Used as a control/baseline condition when the researcher assigns a non-zero
probability weight to "generic" in the experiment's heuristicWeights.
"""
from __future__ import annotations

from typing import Optional

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
        """Generic heuristic needs no memory extraction."""
        pass

    def get_proactive_message(self) -> Optional[str]:
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
            return text or f"Hi {self.name}, how are you today?"
        except Exception as e:
            print(f"⚠️  GenericHeuristic.get_proactive_message({self.username}): {e}")
            return f"Hi {self.name}, how are you today?"
