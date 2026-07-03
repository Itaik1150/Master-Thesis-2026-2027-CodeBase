from dataclasses import dataclass


@dataclass
class UserContext:
    user_id: str
    name: str
    fcm_token: str