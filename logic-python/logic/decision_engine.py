from datetime import datetime
import random
from core.models import UserContext, DecisionResult


class DecisionEngine:
    def __init__(self):
        self.threshold = 60  # Minimum score required to send a notification

    def evaluate_user(self, user: UserContext) -> DecisionResult:
        """
        Main function to evaluate if a specific user needs a notification.
        """
        # 1. Calculate Scores based on different factors
        time_score = self._calc_time_score(user.last_interaction)
        content_score, content_text = self._calc_content_score(user.interests)

        total_score = time_score + content_score

        print(f"📊 Analysis for {user.name}: Time={time_score}, Content={content_score} -> Total={total_score}")

        # 2. Make Decision
        if total_score >= self.threshold:
            # Determine the primary reason for the notification
            reason = "General check-in"
            if content_text:
                reason = "New content found"
            elif time_score > 40:
                reason = "Long period of inactivity"

            return DecisionResult(
                should_send=True,
                score=total_score,
                reason=reason,
                context_data=content_text,
            )

        # If threshold not met
        return DecisionResult(should_send=False, score=total_score, reason="Score too low")

    def _calc_time_score(self, last_seen):
        """Calculates urgency based on hours since last visit"""
        hours = (datetime.now() - last_seen).total_seconds() / 3600

        if hours < 4:
            return -50  # Too soon, don't disturb
        if 24 < hours < 72:
            return 35  # Sweet spot for re-engagement
        if hours > 72:
            return 55  # High urgency
        return 10  # Neutral zone

    def _calc_content_score(self, interests):
        interest = random.choice(interests) if interests else "general"
        context = f"Tell about Something new is happening in the world of {interest}."
        return 40, context
