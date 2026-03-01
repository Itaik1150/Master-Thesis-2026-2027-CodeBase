from dataclasses import dataclass
from typing import List, Optional
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