from __future__ import annotations

import os
import json
import random
from datetime import datetime
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
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        self.model    = os.getenv("LLM_MODEL",    "gpt-4o")
        self.api_url  = "https://api.openai.com/v1/chat/completions"

        if self.provider == "anthropic":
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
            if not self.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not found in environment variables "
                    "(required when LLM_PROVIDER=anthropic)"
                )
            self.api_key = ""
        else:
            self.api_key = os.getenv("OPENAI_API_KEY", "")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")

        print(f"🤖 LLM engine: {self.provider.upper()} / {self.model}")
        
    def _call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 120,
        json_mode: bool = False,
    ) -> str:
        """
        Single dispatch point for all LLM calls in ProactiveLogic.
        Routes to OpenAI or Anthropic based on self.provider / self.model.
        Raises on HTTP or network errors — callers handle their own fallbacks.
        """
        if self.provider == "anthropic":
            # Anthropic Messages API — system is a separate top-level field
            system_content = ""
            anthropic_messages = []
            for m in messages:
                if m["role"] == "system":
                    system_content = m["content"]
                else:
                    anthropic_messages.append(m)

            headers = {
                "x-api-key": self.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            if json_mode:
                system_content = (system_content + "\n\nReturn ONLY valid JSON, no other text.").strip()

            body: Dict[str, Any] = {
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": anthropic_messages,
            }
            if system_content:
                body["system"] = system_content

            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=45,
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()

        else:
            # OpenAI-compatible API
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            body = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                body["response_format"] = {"type": "json_object"}

            resp = requests.post(self.api_url, headers=headers, json=body, timeout=45)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

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

            msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Analyze this headline: '{headline}'"},
            ]
            response_text = self._call_llm(msgs, temperature=0.3, max_tokens=100, json_mode=True)
            try:
                analysis = json.loads(response_text)
                if "should_send" in analysis and "message" in analysis:
                    return analysis
                print(f"⚠️ Invalid response format: {analysis}")
                return {"should_send": False, "message": "NONE"}
            except json.JSONDecodeError:
                print(f"⚠️ Could not parse JSON response: {response_text}")
                return {"should_send": False, "message": "NONE"}

        except requests.exceptions.RequestException as e:
            print(f"❌ Network error calling LLM: {e}")
            return {"should_send": False, "message": "NONE"}
        except Exception as e:
            print(f"❌ Error analyzing headline: {e}")
            return {"should_send": False, "message": "NONE"}
    
    def extract_user_memory(
        self,
        user_messages: List[str],
        language: str = "he",
        today_iso: str = "",
    ) -> Dict[str, Any]:
        """
        3.4b: Extract structured insights from a user's past conversation messages.
        One LLM call. Returns:
            {
                "interests": List[str],
                "future_mentions": List[Dict],   # [{"text": str, "when_iso": str|None}]
                "conversation_insight": str
            }
        On any failure (network/JSON/parse), returns the same shape with empty values
        so the caller can merge it safely.

        `today_iso` is used so the LLM can resolve relative dates like "tomorrow",
        "next week", "in 2 hours" into absolute ISO 8601 datetimes. If empty,
        falls back to current local time.
        """
        empty = {"interests": [], "future_mentions": [], "conversation_insight": ""}
        if not user_messages:
            return empty

        capped = user_messages[-60:]
        joined = "\n".join(f"- {m}" for m in capped if m)

        today_label = today_iso or datetime.now().isoformat(timespec="minutes")
        insight_lang_label = "Hebrew" if language == "he" else "English"
        system_prompt = (
            "You analyze conversation history for a research assistant.\n"
            f"Today is {today_label}. Use this to resolve relative dates like "
            "'today', 'tomorrow', 'in 2 hours', 'next week', etc.\n\n"
            "From the user's messages, extract:\n"
            "- interests: short topical labels the user seems to care about (3-7 items max).\n"
            "- future_mentions: list of objects, each with exactly these keys:\n"
            '    {"text": "<concise English description, e.g. \'playing soccer\'>",\n'
            '     "when_iso": "<ISO 8601 datetime like 2026-05-07T18:00:00, or null if no clear timing>"}\n'
            "  Resolve all relative dates against today. Use null for when_iso ONLY if the\n"
            "  user truly gave no usable timing. Always prefer a concrete ISO datetime when possible.\n"
            f"- conversation_insight: ONE short sentence in {insight_lang_label} summarizing\n"
            "  their communication style and personality.\n\n"
            "Return ONLY valid JSON with exactly these keys: interests, future_mentions, conversation_insight.\n"
            "If a field has no signal, return an empty list or empty string."
        )
        user_prompt = f"User messages (most recent last):\n{joined}"

        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
        try:
            text   = self._call_llm(msgs, temperature=0.2, max_tokens=250, json_mode=True)
            parsed = json.loads(text)

            # Normalize future_mentions to the new {text, when_iso} shape.
            # Tolerate legacy plain strings or malformed objects.
            normalized_future: List[Dict[str, Any]] = []
            for item in parsed.get("future_mentions", []) or []:
                if isinstance(item, dict):
                    text_val = (item.get("text") or "").strip()
                    when_val = item.get("when_iso")
                    if not text_val:
                        continue
                    normalized_future.append({
                        "text": text_val,
                        "when_iso": when_val if when_val else None,
                    })
                elif isinstance(item, str) and item.strip():
                    normalized_future.append({"text": item.strip(), "when_iso": None})

            return {
                "interests": parsed.get("interests", []) or [],
                "future_mentions": normalized_future,
                "conversation_insight": parsed.get("conversation_insight", "") or "",
            }
        except json.JSONDecodeError as e:
            print(f"⚠️  extract_user_memory: invalid JSON from LLM: {e}")
            return empty
        except requests.exceptions.RequestException as e:
            print(f"❌ extract_user_memory: network error: {e}")
            return empty
        except Exception as e:
            print(f"❌ extract_user_memory: unexpected error: {e}")
            return empty

    def _tag_future_mentions(self, future_mentions: List, now: datetime) -> List[str]:
        """
        Convert structured future_mentions into time-tagged strings the LLM can act on.
        Tolerates both new shape ({text, when_iso}) and legacy plain strings.
        Drops events older than 7 days so we don't reference stale plans.
        """
        SECONDS_IN_DAY = 86400
        UPCOMING_HORIZON = 30 * SECONDS_IN_DAY    # within 30 days → UPCOMING
        PAST_HORIZON = 7 * SECONDS_IN_DAY          # within 7 days → PAST_RECENT, else drop

        def humanize(seconds: float) -> str:
            seconds = abs(seconds)
            if seconds < 3600:
                return f"~{max(int(seconds // 60), 1)} minutes"
            if seconds < SECONDS_IN_DAY:
                return f"~{int(seconds // 3600)} hours"
            if seconds < 30 * SECONDS_IN_DAY:
                return f"~{int(seconds // SECONDS_IN_DAY)} days"
            return f"~{int(seconds // (7 * SECONDS_IN_DAY))} weeks"

        tags: List[str] = []
        for item in future_mentions or []:
            # Backwards-compat: legacy plain string
            if isinstance(item, str):
                text = item.strip()
                if text:
                    tags.append(f'"{text}" (UNKNOWN timing)')
                continue
            if not isinstance(item, dict):
                continue
            text = (item.get("text") or "").strip()
            if not text:
                continue
            when_iso = item.get("when_iso")
            if not when_iso:
                tags.append(f'"{text}" (UNKNOWN timing)')
                continue
            try:
                when = datetime.fromisoformat(str(when_iso).replace("Z", "+00:00"))
                # Drop tz to compare with naive `now`
                if when.tzinfo is not None:
                    when = when.replace(tzinfo=None)
            except (ValueError, TypeError):
                tags.append(f'"{text}" (UNKNOWN timing)')
                continue

            delta_seconds = (when - now).total_seconds()
            if delta_seconds > 0:
                if delta_seconds <= UPCOMING_HORIZON:
                    tags.append(f'"{text}" (UPCOMING in {humanize(delta_seconds)})')
                else:
                    tags.append(f'"{text}" (FAR-FUTURE in {humanize(delta_seconds)})')
            else:
                if -delta_seconds <= PAST_HORIZON:
                    tags.append(f'"{text}" (PAST {humanize(delta_seconds)} ago)')
                # else: silently drop — too old to reference

        return tags

    def personalize_message_for_user(self, candidate_message: str, memory: Dict) -> str:
        """
        3.4d: Rewrite a candidate conversation starter to feel personal for this user.

        Uses (when available):
          - demographics.name (subtle — never spammy)
          - interests, future_mentions (with time tags), conversation_insight
          - preferred_language ("he" or "en")

        Returns the personalized sentence. On any LLM failure, returns the original
        candidate_message so the cycle never breaks.
        """
        if not candidate_message:
            return ""

        demo = memory.get("demographics", {}) or {}
        name = demo.get("name", "") or ""
        interests = memory.get("interests", []) or []
        future_mentions = memory.get("future_mentions", []) or []
        insight = memory.get("conversation_insight", "") or ""
        language = memory.get("preferred_language", "he")
        target_lang = "Hebrew" if language == "he" else "English"

        future_tags = self._tag_future_mentions(future_mentions, datetime.now())

        # Pick a primary focus for THIS message via weighted random.
        # Goal: variety across cycles instead of always favoring the same signal.
        # Future mentions still slightly preferred when they exist, but interests
        # and the seed (news/topic) get real share of voice.
        options: List[str] = []
        weights: List[float] = []
        if future_tags:
            options.append("future")
            weights.append(2.0)
        if interests:
            options.append("interest")
            weights.append(1.5)
        options.append("seed")
        weights.append(1.0)
        primary_focus = random.choices(options, weights=weights, k=1)[0]
        self._last_personalization_focus = primary_focus  # exposed for logging

        focus_instructions = {
            "future": (
                "Pick exactly ONE future mention and react per its time tag:\n"
                "   - UPCOMING (within 30 days): ask warmly if they're ready, excited, when it is.\n"
                "   - PAST (within last 7 days): ask how it went or what it was like.\n"
                "   - FAR-FUTURE: mention it casually as something to look forward to.\n"
                "   - UNKNOWN timing: ask gently about their plans for it."
            ),
            "interest": (
                "Pick ONE of the listed interests and ask a fresh open question about it.\n"
                "   You may casually nod to a future mention if it fits, but don't make it the focus."
            ),
            "seed": (
                "Take the seed message as inspiration. Rewrite it in the user's voice/style.\n"
                "   Stay close to the seed's topic — don't substitute future mentions or interests for it."
            ),
        }

        system_prompt = (
            f"You write a short personal conversation starter in {target_lang} for a research assistant.\n\n"
            f"PRIMARY FOCUS for this message: {primary_focus.upper()}\n"
            f"{focus_instructions[primary_focus]}\n\n"
            "HARD RULES (always apply):\n"
            f"- Output MUST be in {target_lang}.\n"
            "- Maximum 15 words.\n"
            "- Friendly and open-ended (must invite a reply).\n"
            "- Match the user's communication style described in the insight.\n"
            "- You MAY use the user's name once if it feels natural; otherwise don't.\n"
            "- NEVER ask about a PAST event as if it were upcoming, or vice versa.\n"
            "- Do NOT mention age or gender.\n"
            "- Do NOT add quotes, labels, prefixes, or explanations.\n"
            "- Return ONLY the final sentence."
        )

        future_block = (
            "\n".join(f"  - {t}" for t in future_tags) if future_tags else "  (none)"
        )
        user_payload = (
            "FUTURE MENTIONS:\n"
            f"{future_block}\n"
            f"INTERESTS: {', '.join(interests) if interests else 'none'}\n"
            f"COMMUNICATION STYLE INSIGHT: {insight or 'unknown'}\n"
            f"USER NAME: {name or 'unknown'}\n"
            f"SEED MESSAGE: {candidate_message}\n"
            f"PRIMARY FOCUS for this message: {primary_focus}"
        )

        msgs_payload = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_payload},
        ]
        try:
            text = self._call_llm(msgs_payload, temperature=0.7, max_tokens=80)
            # Strip wrapping quotes the model sometimes adds
            if (text.startswith('"') and text.endswith('"')) or (
                text.startswith("'") and text.endswith("'")
            ):
                text = text[1:-1].strip()
            return text or candidate_message
        except requests.exceptions.RequestException as e:
            print(f"❌ personalize_message_for_user: network error: {e}")
            return candidate_message
        except Exception as e:
            print(f"❌ personalize_message_for_user: unexpected error: {e}")
            return candidate_message

    def generate_topic_message(self, topic: str) -> str:
        """
        Generate a Hebrew conversation starter from a topic (no headline needed).
        Used as fallback when all news headlines are rejected.

        Returns:
            Hebrew message string, or empty string on failure.
        """
        msgs = [
            {
                "role": "system",
                "content": (
                    "You are a social interaction assistant for a research experiment at "
                    "Ben-Gurion University (BGU). "
                    "Generate a short, friendly, open-ended conversation starter in Hebrew (max 15 words) "
                    "about the given topic. The message should feel natural and invite a response. "
                    "Return ONLY the Hebrew sentence, nothing else."
                ),
            },
            {"role": "user", "content": f"Topic: {topic}"},
        ]
        try:
            return self._call_llm(msgs, temperature=0.7, max_tokens=60)
        except Exception as e:
            print(f"❌ Error generating topic message: {e}")
            return ""

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
