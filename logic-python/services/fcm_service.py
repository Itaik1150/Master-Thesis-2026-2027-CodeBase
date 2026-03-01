from __future__ import annotations

import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

from core.models import UserContext



class FCMService:
    """
    Sends push notifications via Firebase Cloud Messaging (FCM).

    Env vars:
    - SERVICE_ACCOUNT_JSON: path to Firebase service account JSON file
    - FCM_DEFAULT_TITLE: default notification title (optional)
    """

    def __init__(
        self,
        service_account_json: Optional[str] = None,
        default_title: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.service_account_json = service_account_json or os.getenv("SERVICE_ACCOUNT_JSON", "")
        if not self.service_account_json:
            raise ValueError(
                "Missing SERVICE_ACCOUNT_JSON. Provide service_account_json=... or set env var SERVICE_ACCOUNT_JSON."
            )
        
        # Fix path: ensure it's a proper file path
        if not os.path.isabs(self.service_account_json):
            # If relative path, make it absolute from current directory
            self.service_account_json = os.path.join(os.path.dirname(__file__), self.service_account_json)
        
        self.default_title = default_title or os.getenv("FCM_DEFAULT_TITLE", "Lexi")
        self.dry_run = dry_run

        # Initialize Firebase only once
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.service_account_json)
            firebase_admin.initialize_app(cred)

    def send_to_user(self, user: UserContext, body: str, title: Optional[str] = None) -> Optional[str]:
        """
        Convenience: send notification using user.fcm_token
        Returns message id string (or None if dry_run).
        """
        return self.send_to_token(token=user.fcm_token, body=body, title=title)

    def send_to_token(self, token: str, body: str, title: Optional[str] = None) -> Optional[str]:
        """
        Sends a push notification to a specific FCM token.
        Returns message id string (or None if dry_run).
        """
        if not token:
            raise ValueError("FCM token is empty.")

        final_title = title or self.default_title

        if self.dry_run:
            print(f"[DRY_RUN] FCM -> title={final_title!r}, body={body!r}, token={token[:12]}...")
            return None

        try:
            msg = messaging.Message(
                notification=messaging.Notification(title=final_title, body=body),
                token=token,
                data={"click_action": "FLUTTER_NOTIFICATION_CLICK"},
            )
            resp = messaging.send(msg)
            print(f"🚀 FCM Service: Sent! ID: {resp}")
            return resp
        except Exception as e:
            print(f"❌ FCM Error: {e}")
            raise
