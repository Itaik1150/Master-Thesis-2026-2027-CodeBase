from __future__ import annotations

import os
import json
from typing import Optional, List, Dict, Any

import requests

from dotenv import load_dotenv
load_dotenv()



class GroqAgent:
    """
    Thin client for Groq OpenAI-compatible Chat Completions API.

    Env vars supported:
    - GROQ_API_KEY: your Groq API key (recommended)
    - GROQ_MODEL: model id, e.g. "llama3-70b-8192" or "llama-3.3-70b-versatile"
    - GROQ_BASE_URL: default "https://api.groq.com/openai/v1"
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_sec: int = 20,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError("Missing GROQ_API_KEY (set env var or pass api_key=...)")

        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.base_url = (base_url or os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        self.timeout_sec = timeout_sec

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 120) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout_sec)
        resp.raise_for_status()
        data = resp.json()

        # OpenAI-compatible response shape
        return data["choices"][0]["message"]["content"]


class LLMService:
    """
    LLM Service using Groq's API.
    """

    def __init__(self, agent: Optional[GroqAgent] = None):
        # If you don't pass an agent, we build one from env vars (GROQ_API_KEY, GROQ_MODEL, etc.)
        self.agent = agent or GroqAgent()

    def generate_notification_text(
        self,
        user_name: str,
        reason: str,
        context_data: Optional[str] = None,
    ) -> str:
        """
        Generates a short proactive notification (push-friendly).
        Mirrors your old signature exactly.
        """

        system_prompt = (
            "You are Lexi, a proactive assistant that writes SHORT push notifications.\n"
            "Rules:\n"
            "- 1–2 sentences max.\n"
            "- Friendly, casual tone.\n"
            "- No long explanations.\n"
            "- No emojis spam (0–1 emoji max).\n"
            "- If you mention content, make it feel relevant to the user.\n"
        )

        # Build the user instruction exactly like your old logic intended
        user_prompt = f"Write a push notification for {user_name}.\nReason: {reason}."
        if context_data:
            user_prompt += f"\nContext: {context_data}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            text = self.agent.chat(messages=messages, temperature=0.7, max_tokens=120)
            return text.strip()
        except requests.HTTPError as e:
            # Safe fallback (so your pipeline doesn't crash)
            return self._fallback_message(user_name=user_name, reason=reason, context_data=context_data, err=str(e))
        except Exception as e:
            return self._fallback_message(user_name=user_name, reason=reason, context_data=context_data, err=str(e))

    def _fallback_message(self, user_name: str, reason: str, context_data: Optional[str], err: str) -> str:
        # Minimal fallback, but still aligned with your use-case
        if context_data:
            return f"Hey {user_name} 🤞 I found something you might like: {context_data}"
        if "long" in reason.lower() or "inactive" in reason.lower():
            return f"Hey {user_name} 👋 long time no see — want to do a quick check-in?"


class ProactiveLogic:
    """
    Simple LLM-based service for deciding if news headlines are socially proactive
    """
    
    def __init__(self):
        """Initialize proactive logic with OpenAI API configuration"""
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.api_url = "https://api.openai.com/v1/chat/completions"
        
    def analyze_headline(self, headline: str) -> Dict[str, any]:
        """
        Analyze a news headline and decide if it's suitable for proactive conversation
        
        Args:
            headline: News headline to analyze
            
        Returns:
            Dictionary with {"should_send": bool, "message": str}
        """
        try:
            # Real OpenAI API call
            system_prompt = """You are a social interaction assistant for an Israeli research experiment. Evaluate if this news headline can be used to start a friendly conversation in Hebrew.

Rules:
- If the headline is suitable for a friendly conversation, return a short, proactive message in Hebrew (max 15 words)
- If not suitable, return NONE
- Focus on topics that are positive, interesting, or relatable to Israelis
- Avoid controversial, sad, or overly technical topics
- Messages must be in Hebrew language

Respond in this exact JSON format:
{"should_send": true/false, "message": "your message here"}

Examples:
Input: "Local Community Garden Wins National Award"
Output: {"should_send": true, "message": "שמעת על הפרס שהגן הקהילתי קיבל?"}

Input: "Stock Market Declines Sharply"
Output: {"should_send": false, "message": "NONE"}

Input: "New Coffee Shop Opens Downtown"
Output: {"should_send": true, "message": "ראית את בית הקפה החדש שנפתח?"}"""

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this headline: '{headline}'"
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 100
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract the response text
            if "choices" in result and len(result["choices"]) > 0:
                response_text = result["choices"][0]["message"]["content"].strip()
                
                # Try to parse as JSON
                try:
                    analysis = json.loads(response_text)
                    
                    # Validate the response format
                    if "should_send" in analysis and "message" in analysis:
                        return analysis
                    else:
                        print(f"⚠️ Invalid response format: {analysis}")
                        return {"should_send": False, "message": "NONE"}
                        
                except json.JSONDecodeError:
                    print(f"⚠️ Could not parse JSON response: {response_text}")
                    return {"should_send": False, "message": "NONE"}
            else:
                print(f"⚠️ No response from OpenAI")
                return {"should_send": False, "message": "NONE"}
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error calling OpenAI: {e}")
            return {"should_send": False, "message": "NONE"}
        except Exception as e:
            print(f"❌ Error analyzing headline: {e}")
            return {"should_send": False, "message": "NONE"}
    
    def _mock_analysis(self, headline: str) -> Dict[str, any]:
        """
        Mock analysis for testing without API key (generates Hebrew messages)
        """
        # Simple keyword-based mock logic with Hebrew responses
        positive_keywords = ["festival", "breakthrough", "growth", "opens", "announces", "research", "technology", "cultural"]
        negative_keywords = ["crash", "decline", "crisis", "scandal", "conflict"]
        
        headline_lower = headline.lower()
        
        # Check for negative keywords first
        for keyword in negative_keywords:
            if keyword in headline_lower:
                return {"should_send": False, "message": "NONE"}
        
        # Check for positive keywords
        for keyword in positive_keywords:
            if keyword in headline_lower:
                # Generate Hebrew mock messages
                if "technology" in headline_lower:
                    return {"should_send": True, "message": "חדשות טכנולוגיה מעניינים היום, לא?"}
                elif "research" in headline_lower:
                    return {"should_send": True, "message": "ראית את פריצת הדרך במחקר?"}
                elif "festival" in headline_lower:
                    return {"should_send": True, "message": "שמעת על הפסטיבל?"}
                elif "growth" in headline_lower:
                    return {"should_send": True, "message": "חדשות כלכליות טובות היום!"}
                else:
                    return {"should_send": True, "message": "חדשות מעניינות היום!"}
        
        # Default to not sending if no keywords match
        return {"should_send": False, "message": "NONE"}
    
    def print_analysis(self, headline: str, analysis: Dict[str, any]) -> None:
        """
        Print analysis result in readable format
        
        Args:
            headline: Original headline
            analysis: Analysis result
        """
        print(f"\n📰 Headline: {headline}")
        if analysis["should_send"]:
            print(f"✅ Should Send: {analysis['message']}")
        else:
            print(f"❌ Should Not Send: {analysis['message']}")

def main():
    """
    Test the LLM service with sample headlines
    """
    print("=== 🧠 LLM Service Test ===")
    
    # Initialize LLM service
    llm_service = ProactiveLogic()
    
    # Test headlines (same ones from news service)
    test_headlines = [
        "Israel Announces New Technology Initiative",
        "Tel Aviv University Research Breakthrough", 
        "Jerusalem Cultural Festival Begins",
        "Israeli Economy Shows Strong Growth",
        "New Medical Research Center Opens in Haifa"
    ]
    
    print(f"🧪 Analyzing {len(test_headlines)} headlines...")
    
    results = []
    for headline in test_headlines:
        analysis = llm_service.analyze_headline(headline)
        llm_service.print_analysis(headline, analysis)
        results.append({
            "headline": headline,
            "analysis": analysis
        })
    
    # Summary
    send_count = sum(1 for r in results if r["analysis"]["should_send"])
    print(f"\n📊 Summary:")
    print(f"   Total headlines: {len(results)}")
    print(f"   Should send: {send_count}")
    print(f"   Should not send: {len(results) - send_count}")
    
    # Show messages that would be sent
    print(f"\n📤 Messages to send:")
    for i, result in enumerate(results, 1):
        if result["analysis"]["should_send"]:
            print(f"   {i}. {result['analysis']['message']}")
    
    return results

if __name__ == "__main__":
    main()
