import time
import threading
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv


# .\venv\Scripts\activate

# טעינת המשתנים
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

class ProactiveAgent:
    def __init__(self, api_key, proactivity_threshold=10):
        if not api_key:
            raise ValueError("API Key is missing! Check your .env file.")
        
        # --- השינוי הגדול: הכוונה לשרתים של Groq במקום OpenAI ---
        self.client = OpenAI(
            api_key=api_key, 
            base_url="https://api.groq.com/openai/v1"
        )
        
        self.name = "ThesisBot"
        self.proactivity_threshold = proactivity_threshold
        self.last_interaction_time = datetime.now()
        self.running = True
        
        # מודל חינמי ומהיר מאוד (Llama 3)
        self.model_name = "llama-3.3-70b-versatile"
        
        self.history = [
            {"role": "system", "content": (
                "You are a helpful research assistant. "
                "Keep your answers concise and conversational."
            )}
        ]

    def generate_response(self, user_input=None, trigger_type="reactive"):
        messages_to_send = list(self.history)
        
        if trigger_type == "proactive_silence":
            print(f"\n[System Log: Silence detected. Triggering Proactivity...]")
            messages_to_send.append({
                "role": "system", 
                "content": (
                    "The user has been silent. "
                    "Proactively initiate a new topic related to the context. "
                    "Be gentle, not pushy."
                )
            })
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name, # שימוש במודל החינמי
                messages=messages_to_send
            )
            content = response.choices[0].message.content
            return content
        except Exception as e:
            return f"Error: {e}"

    def user_speaks(self, text):
        self.last_interaction_time = datetime.now()
        self.history.append({"role": "user", "content": text})
        
        response_text = self.generate_response(user_input=text, trigger_type="reactive")
        
        print(f"\n{self.name}: {response_text}")
        self.history.append({"role": "assistant", "content": response_text})
        self.last_interaction_time = datetime.now()

    def background_monitor(self):
        print(f"[{self.name} Monitor] Active. Threshold: {self.proactivity_threshold}s")
        while self.running:
            time.sleep(1)
            time_since_last_talk = (datetime.now() - self.last_interaction_time).total_seconds()
            
            if time_since_last_talk > self.proactivity_threshold:
                proactive_msg = self.generate_response(trigger_type="proactive_silence")
                print(f"\n{self.name} (Proactive): {proactive_msg}")
                self.history.append({"role": "assistant", "content": proactive_msg})
                self.last_interaction_time = datetime.now() 
                print("You: ", end="", flush=True)

    def stop(self):
        self.running = False

if __name__ == "__main__":
    try:
        bot = ProactiveAgent(api_key=api_key, proactivity_threshold=10)
        
        monitor_thread = threading.Thread(target=bot.background_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()

        print(f"--- Chat Started using {bot.model_name} (Free Tier) ---")
        
        while True:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                bot.stop()
                break
            
            if user_input.strip():
                bot.user_speaks(user_input)
                
    except ValueError as e:
        print(f"Setup Error: {e}")
    except KeyboardInterrupt:
        bot.stop()