# Import from our modular structure
from core.data_loader import UserDataLoader
from logic.decision_engine import DecisionEngine
from services.llm_service import LLMService
from services.fcm_service import FCMService


def run_system():
    print("--- 🏁 System Cycle Started ---")

    # 1. Initialize Components (Dependency Injection)
    loader = UserDataLoader()
    brain = DecisionEngine()
    voice = LLMService()

    # Tip: start with dry_run=True so you can test without actually sending
    hands = FCMService(dry_run=True)

    # 2. Load User (Simulate Loop)
    user_context = loader.get_user_context("user_123")

    # 3. Decision Phase (Logic)
    decision = brain.evaluate_user(user_context)

    if decision.should_send:
        print("✅ Decision: SEND")

        # 4. Content Generation Phase (LLM)
        message_text = voice.generate_notification_text(
            user_name=user_context.name,
            reason=decision.reason,
            context_data=decision.context_data,
        )
        print(f"📝 Generated Copy: {message_text}")

        # 5. Delivery Phase (FCM)
        hands.send_to_token(token=user_context.fcm_token, body=message_text)

    else:
        print(f"❌ Decision: WAIT ({decision.reason})")


if __name__ == "__main__":
    run_system()
