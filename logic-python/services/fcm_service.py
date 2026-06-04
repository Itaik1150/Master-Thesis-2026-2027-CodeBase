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
        self.default_title = default_title or os.getenv("FCM_DEFAULT_TITLE", "Lexi")
        self.dry_run = dry_run

        # Initialize Firebase only once
        if not firebase_admin._apps:
            # Prefer SERVICE_ACCOUNT_JSON_CONTENT (a JSON string, safe for cloud env vars)
            # over SERVICE_ACCOUNT_JSON (a file path, used locally).
            json_content = os.getenv("SERVICE_ACCOUNT_JSON_CONTENT", "")
            if json_content:
                import json as _json
                import tempfile
                tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
                tmp.write(json_content)
                tmp.flush()
                cred = credentials.Certificate(tmp.name)
                tmp.close()
            else:
                sa_path = service_account_json or os.getenv("SERVICE_ACCOUNT_JSON", "")
                if not sa_path:
                    raise ValueError(
                        "Missing Firebase credentials. Set SERVICE_ACCOUNT_JSON_CONTENT "
                        "(JSON string) or SERVICE_ACCOUNT_JSON (file path)."
                    )
                if not os.path.isabs(sa_path):
                    sa_path = os.path.join(os.path.dirname(__file__), sa_path)
                cred = credentials.Certificate(sa_path)
            
            # Initialize Firebase app with default name (not specifying name)
            firebase_admin.initialize_app(cred, {
                'projectId': 'lexi-72330',
            })
            print(f"✅ Firebase initialized with default app")
        else:
            print(f"✅ Firebase already initialized")

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
