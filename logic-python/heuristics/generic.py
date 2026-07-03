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
    """

    DEFAULT_MESSAGE_PROMPT = (
        "You are a standard assistant. Generate a completely neutral, friendly "
        "invitation to chat in {language} with zero emotional weight and no specific "
        "topics (max 15 words). You MAY use the user's name once if it feels natural. "
        "Return ONLY the final message, no quotes, labels, or explanations."
    )

    def create_memory(self) -> None:
        """Generic heuristic needs no memory extraction."""
        pass

    def get_proactive_message(self) -> Optional[str]:
        prompt = self.message_prompt.replace("{language}", self._target_lang)
        try:
            text = self.llm_service.call_with_prompt(
                system=prompt,
                user_content=f"USER NAME: {self.name}",
                temperature=0.3,
                max_tokens=60,
            )
            # Strip wrapping quotes the model sometimes adds
            if text and len(text) >= 2 and text[0] in ('"', "'") and text[0] == text[-1]:
                text = text[1:-1].strip()
            return text or f"Hi {self.name}, how are you today?"
        except Exception as e:
            print(f"⚠️  GenericHeuristic.get_proactive_message({self.username}): {e}")
            return f"Hi {self.name}, how are you today?"
