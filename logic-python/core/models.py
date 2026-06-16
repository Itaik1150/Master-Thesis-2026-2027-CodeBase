from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class UserContext:
    user_id: str
    name: str
    fcm_token: str
    # last_interaction: datetime
    # interests: List[str]


@dataclass
class DecisionResult:
    should_send: bool
    score: int
    reason: str
    context_data: Optional[str] = None


@dataclass
class NudgeContext:
    """
    Strict Context Isolation (see PROACTIVE_NOTIFICATIONS.md § 3a).

    Built by the single winning heuristic for a user in a cycle. Carries ONLY the
    data relevant to that heuristic — never the full proactiveMemory — so the LLM
    personalization call can't bleed unrelated context into the message.

    `payload` allowed fields by trigger_source:
      - affective       : emotion, intensity, insight
      - behavioural_gap : intent_text, stated_at
      - temporal        : mention_text, hours_until
      - topic           : topic_label only (the single pool topic chosen this cycle)
    """
    trigger_source: str           # affective | behavioural_gap | temporal | topic
    name: str
    preferred_language: str       # "he" | "en"
    seed_message: str             # base text/instruction + fallback if LLM fails
    topic_label: str
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)