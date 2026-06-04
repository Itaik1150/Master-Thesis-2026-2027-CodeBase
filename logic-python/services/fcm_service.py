from __future__ import annotations

import json
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging

from core.models import UserContext



class FCMService:
    """
    Sends push notifications via Firebase Cloud Messaging (FCM).

    Env vars (in order of preference):
    - SERVICE_ACCOUNT_JSON_CONTENT: full Firebase service account JSON as a string (Render)
    - SERVICE_ACCOUNT_JSON: file path locally, OR full JSON if value starts with '{'
    - FCM_DEFAULT_TITLE: default notification title (optional)
    """

    def __init__(
        self,
        service_account_json: Optional[str] = None,
        default_title: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.default_title = default_title or os.getenv("FCM_DEFAULT_TITLE", "Lexi")
        self.dry_run = dry_run

        # Initialize Firebase only once
        if not firebase_admin._apps:
            cred = self._load_credentials(service_account_json)
            
            # Initialize Firebase app with default name (not specifying name)
            firebase_admin.initialize_app(cred, {
                'projectId': 'lexi-72330',
            })
            print("✅ Firebase initialized (credentials from env)")
        else:
            print("✅ Firebase already initialized")

    @staticmethod
    def _load_credentials(service_account_json: Optional[str] = None):
        """Load Firebase credentials from env JSON string or local file path."""
        json_content = (os.getenv("SERVICE_ACCOUNT_JSON_CONTENT") or "").strip()
        if not json_content:
            sa_env = (os.getenv("SERVICE_ACCOUNT_JSON") or "").strip()
            if sa_env.startswith("{"):
                json_content = sa_env

        if json_content:
            try:
                return credentials.Certificate(json.loads(json_content))
            except json.JSONDecodeError as e:
                raise ValueError(
                    "SERVICE_ACCOUNT_JSON_CONTENT is set but is not valid JSON. "
                    "Paste the full service account file as one line, or use Render Secret Files."
                ) from e

        # Render Secret Files are mounted under /etc/secrets/
        for secret_path in (
            "/etc/secrets/firebase.json",
            "/etc/secrets/service_account.json",
            "/etc/secrets/SERVICE_ACCOUNT_JSON_CONTENT",
        ):
            if os.path.isfile(secret_path):
                return credentials.Certificate(secret_path)

        sa_path = (service_account_json or os.getenv("SERVICE_ACCOUNT_JSON") or "").strip()
        if not sa_path:
            raise ValueError(
                "Missing Firebase credentials. On Render set SERVICE_ACCOUNT_JSON_CONTENT "
                "to the full JSON from your Firebase service account file."
            )
        if not os.path.isabs(sa_path):
            sa_path = os.path.join(os.path.dirname(__file__), sa_path)
        if not os.path.isfile(sa_path):
            raise FileNotFoundError(
                f"Firebase service account file not found: {sa_path}. "
                "On Render, use SERVICE_ACCOUNT_JSON_CONTENT (paste full JSON), not a file path."
            )
        return credentials.Certificate(sa_path)

    def send_to_user(self, user: UserContext, body: str, title: Optional[str] = None, extra_data: Optional[dict] = None) -> Optional[str]:
        """
        Convenience: send notification using user.fcm_token
        Returns message id string (or None if dry_run).
        """
        return self.send_to_token(token=user.fcm_token, body=body, title=title, extra_data=extra_data)

    def send_to_token(self, token: str, body: str, title: Optional[str] = None, extra_data: Optional[dict] = None) -> Optional[str]:
        """
        Sends a push notification to a specific FCM token.
        Returns message id string (or None if dry_run).
        """
        if not token:
            raise ValueError("FCM token is empty.")
        
        # Validate token format
        if len(token) < 100:
            print(f"⚠️ FCM token seems too short: {len(token)} chars")
            raise ValueError(f"FCM token appears invalid (too short: {len(token)} chars)")

        final_title = title or self.default_title

        if self.dry_run:
            print(f"[DRY_RUN] FCM -> title={final_title!r}, body={body!r}, token={token[:12]}...")
            return None

        try:
            data_payload = {"click_action": "FLUTTER_NOTIFICATION_CLICK"}
            if extra_data:
                # All FCM data values must be strings.
                data_payload.update({k: str(v) for k, v in extra_data.items()})

            msg = messaging.Message(
                notification=messaging.Notification(title=final_title, body=body),
                token=token,
                data=data_payload,
            )
            resp = messaging.send(msg)
            print(f"🚀 FCM Service: Sent! ID: {resp}")
            return resp
        except Exception as e:
            error_msg = str(e)
            print(f"❌ FCM Error: {error_msg}")
            
            # Provide specific guidance based on error type
            if "registration token" in error_msg.lower():
                print("💡 Token Issue: The FCM token may be expired or invalid")
                print("   - User may need to restart the app")
                print("   - Token might be from different Firebase project")
            elif "not found" in error_msg.lower():
                print("💡 Project Issue: Firebase project configuration problem")
                print("   - Check service account file")
                print("   - Verify project ID matches mobile app")
            elif "unauthenticated" in error_msg.lower():
                print("💡 Auth Issue: Firebase service account problem")
                print("   - Check service account permissions")
                print("   - Verify service account file is valid")
            
            raise
