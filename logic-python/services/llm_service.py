from __future__ import annotations

import os
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
        return f"Hey {user_name} 👋 quick check-in: anything you want to tackle today?"
