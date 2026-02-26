from datetime import datetime, timedelta
from core.models import UserContext


class UserDataLoader:
    def get_user_context(self, user_id: str) -> UserContext:
        # TODO: Replace with real DB call
        return UserContext(
            user_id=user_id,
            name="Itai",
            fcm_token="YOUR_TOKEN...",
            last_interaction=datetime.now() - timedelta(hours=28),
            interests=["Sports", "Music"],
        )
