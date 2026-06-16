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

    def override_model(self, model: str):
        """
        Temporarily switch the active model for the current proactive cycle.
        If the model prefix implies a different provider (claude-* → anthropic,
        gpt-* / o* → openai), the provider is switched as well.
        Called once per user when the experiment's proactiveSettings.llmModel
        differs from the env-configured default.
        """
        if model == self.model:
            return  # nothing to do

        if model.startswith("claude"):
            self.provider = "anthropic"
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        else:
            self.provider = "openai"
            self.api_key  = os.getenv("OPENAI_API_KEY", "")

        self.model = model
        print(f"🔄 LLM overridden by experiment settings: {self.provider.upper()} / {self.model}")

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
            system_prompt = """You are a social interaction assistant. Evaluate if this news headline can be used to start a friendly conversation in Hebrew.

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
        unanalyzed_only: bool = False,
        mongodb_client = None,
        user_id: str = "",
    ) -> Dict[str, Any]:
        """
        3.4b: Extract structured insights from a user's past conversation messages.
        One LLM call. Returns:
            {
                "interests": List[str],
                "future_mentions": List[Dict],   # [{"text": str, "when_iso": str|None}]
                "conversation_insight": str,
                "sensitivity_score": int         # 1-10 scale for emotional expressions
                "emotional_memories": List[Dict] # Only NEWLY extracted (not previously analyzed)
            }
        On any failure (network/JSON/parse), returns the same shape with empty values
        so the caller can merge it safely.

        `unanalyzed_only`: If True, only extracts emotional_memories from messages 
        that haven't been analyzed yet (analyzed_for_memory != True).
        After successful extraction, marks those messages with analyzed_for_memory: True.
        """
        empty = {"interests": [], "future_mentions": [], "conversation_insight": "", "sensitivity_score": 1, "emotional_memories": []}
        if not user_messages:
            return empty

        capped = user_messages[-60:]
        
        # STEP 1: Smart Extraction — if unanalyzed_only, fetch from DB messages not yet analyzed
        if unanalyzed_only and mongodb_client and user_id:
            try:
                from bson import ObjectId
                if not mongodb_client.connect():
                    capped = user_messages[-60:]
                else:
                    # Fetch recent conversations where analyzed_for_memory != True
                    recent_metas = list(mongodb_client.db["metadata_conversations"].find(
                        {"userId": user_id},
                        sort=[("createdAt", -1)],
                        limit=5,  # Check last 5 conversations for unanalyzed messages
                    ))
                    
                    unanalyzed_messages = []
                    analyzed_msg_ids = []
                    
                    for meta in recent_metas:
                        conv_id = str(meta["_id"])
                        raw = list(mongodb_client.db["conversations"].find(
                            {
                                "conversationId": conv_id,
                                "role": "user",
                                "analyzed_for_memory": {"$ne": True},  # Only unanalyzed
                            },
                            sort=[("messageNumber", 1)],
                        ))
                        for msg in raw:
                            if msg.get("content"):
                                unanalyzed_messages.append(msg.get("content"))
                                analyzed_msg_ids.append(msg["_id"])
                    
                    if not unanalyzed_messages:
                        return empty  # Skip LLM call if no unanalyzed messages
                    
                    capped = unanalyzed_messages[-60:]
                    
            except Exception as e:
                print(f"⚠️  unanalyzed_only fetch failed: {e}")
                capped = user_messages[-60:]
        
        joined = "\n".join(f"- {m}" for m in capped if m)

        today_label = today_iso or datetime.now().isoformat(timespec="minutes")
        insight_lang_label = "Hebrew" if language == "he" else "English"
        system_prompt = (
            "You analyze conversation history for a conversational assistant.\n"
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
            "  their communication style and personality.\n"
            "- sensitivity_score: integer from 1-10 rating how much emotional expression,\n"
            "  sensitive topics, or personal struggles are present (1=neutral/factual, 10=highly emotional).\n"
            "- emotional_memories: array of objects for deep personal/emotional shares, each with:\n"
            '    {"content": "<exact quote or paraphrase of the emotional/personal share>",\n'
            '     "affective_score": <1-10 rating of depth/relevance to inner emotional world>,\n'
            f'     "timestamp_iso": "<{today_label} for when this was shared>",\n'
            '     "used": false}\n'
            "  Only include genuine emotional expressions, personal struggles, meaningful life events,\n"
            "  or vulnerable shares. Exclude casual mentions or surface-level topics.\n\n"
            "Return ONLY valid JSON with exactly these keys: interests, future_mentions, conversation_insight, sensitivity_score, emotional_memories.\n"
            "If a field has no signal, return an empty list, empty string, or 1 for sensitivity_score."
        )
        user_prompt = f"User messages (most recent last):\n{joined}"

        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
        try:
            text   = self._call_llm(msgs, temperature=0.2, max_tokens=800, json_mode=True)
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

            # Normalize emotional_memories to ensure proper structure
            normalized_emotional: List[Dict[str, Any]] = []
            for item in parsed.get("emotional_memories", []) or []:
                if isinstance(item, dict):
                    content = (item.get("content") or "").strip()
                    if content:
                        normalized_emotional.append({
                            "content": content,
                            "affective_score": max(1, min(10, int(item.get("affective_score", 1)))),
                            "timestamp_iso": item.get("timestamp_iso") or today_label,
                            "used": False,  # Always initialize as unused
                        })

            # STEP 2: Mark messages as analyzed AFTER successful LLM extraction
            if unanalyzed_only and mongodb_client and user_id and 'analyzed_msg_ids' in locals():
                try:
                    if mongodb_client.connect():
                        from bson import ObjectId
                        for msg_id in analyzed_msg_ids:
                            mongodb_client.db["conversations"].update_one(
                                {"_id": ObjectId(msg_id)},
                                {"$set": {"analyzed_for_memory": True}},
                            )
                        if analyzed_msg_ids:
                            print(f"✅ Marked {len(analyzed_msg_ids)} messages as analyzed_for_memory")
                except Exception as e:
                    print(f"⚠️  Failed to mark messages as analyzed: {e}")

            return {
                "interests": parsed.get("interests", []) or [],
                "future_mentions": normalized_future,
                "conversation_insight": parsed.get("conversation_insight", "") or "",
                "sensitivity_score": max(1, min(10, int(parsed.get("sensitivity_score", 1)))),  # Clamp to 1-10
                "emotional_memories": normalized_emotional,
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

    def personalize_from_context(self, ctx, framing: str = "standard") -> str:
        """
        Context-isolated personalization (see PROACTIVE_NOTIFICATIONS.md § 3a).

        Builds the prompt using ONLY the fields carried in the winning heuristic's
        NudgeContext — never the full proactiveMemory — so unrelated signals can't
        bleed into the message.

        `framing`:
          - "standard": confident, concise opener (current behavior).
          - "ethical":  epistemic-humility framing — added in Step 3 (see § 3b).
            Until then, "ethical" falls through to the standard prompt.

        Returns the personalized sentence, or ctx.seed_message on any LLM failure.
        """
        seed = (getattr(ctx, "seed_message", "") or "")
        payload = getattr(ctx, "payload", {}) or {}
        name = getattr(ctx, "name", "") or ""
        trigger = getattr(ctx, "trigger_source", "topic")
        language = getattr(ctx, "preferred_language", "he")
        target_lang = "Hebrew" if language == "he" else "English"

        self._last_personalization_focus = trigger  # exposed for logging

        # ── Build a focused instruction + details strictly from ctx.payload ──
        if trigger == "affective":
            focus = (
                "Send a warm, gentle emotional check-in. Acknowledge how they seemed "
                "without being dramatic or clinical. Invite them to share how they feel now."
            )
            details = (
                f"OBSERVED EMOTION: {payload.get('emotion', 'unspecified')}\n"
                f"COMMUNICATION STYLE: {payload.get('insight') or 'unknown'}"
            )
        elif trigger == "behavioural_gap":
            focus = (
                "Gently ask how the plan they mentioned went. Do NOT assume it "
                "succeeded or failed. Keep it light and supportive."
            )
            details = f"PLAN THEY MENTIONED: {payload.get('intent_text', '')}"
        elif trigger == "temporal":
            focus = (
                "React to the event. If it is ahead, ask warmly if they're ready or "
                "excited; if it just passed, ask how it went. Never confuse the timing."
            )
            details = (
                f"EVENT: {payload.get('mention_text', '')}\n"
                f"HOURS UNTIL EVENT (negative = already passed): {payload.get('hours_until')}"
            )
        else:  # topic — personalize using ONLY the selected pool topic + seed
            topic = (payload.get("topic_label") or getattr(ctx, "topic_label", "") or "").strip()
            self._last_personalization_focus = f"topic:{topic}" if topic else "topic"
            focus = (
                f"Rewrite the seed as a warm, personal opener about ONLY this topic: "
                f"\"{topic}\". You may use the user's name once. "
                f"Stay on the seed's angle within that single topic."
            )
            details = f"SELECTED TOPIC (the only subject allowed): {topic or 'unknown'}"

        system_prompt = (
            f"You write a short personal conversation starter in {target_lang} for a conversational assistant.\n\n"
            f"FOCUS: {focus}\n\n"
            "HARD RULES (always apply):\n"
            f"- Output MUST be in {target_lang}.\n"
            "- Maximum 15 words.\n"
            "- Friendly and open-ended (must invite a reply).\n"
            "- You MAY use the user's name once if it feels natural; otherwise don't.\n"
            "- Do NOT mention age or gender.\n"
            "- Do NOT add quotes, labels, prefixes, or explanations.\n"
            "- Return ONLY the final sentence."
        )
        if trigger == "topic":
            system_prompt += (
                "\n\nTOPIC-ONLY RULES (critical):\n"
                "- You have NO access to the user's other interests, plans, weddings, or past chats.\n"
                "- Do NOT introduce any subject except the SELECTED TOPIC and what is already in the SEED.\n"
                "- If the seed is about technology, the output must stay about technology — never pivot "
                "to weddings, health, family, or any other theme."
            )

        user_payload = (
            f"{details}\n"
            f"USER NAME: {name or 'unknown'}\n"
            f"SEED MESSAGE: {seed}"
        )

        msgs_payload = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_payload},
        ]
        try:
            temp = 0.35 if trigger == "topic" else 0.7
            text = self._call_llm(msgs_payload, temperature=temp, max_tokens=80)
            # Strip wrapping quotes the model sometimes adds
            if (text.startswith('"') and text.endswith('"')) or (
                text.startswith("'") and text.endswith("'")
            ):
                text = text[1:-1].strip()
            return text or seed
        except requests.exceptions.RequestException as e:
            print(f"❌ personalize_from_context: network error: {e}")
            return seed
        except Exception as e:
            print(f"❌ personalize_from_context: unexpected error: {e}")
            return seed

    def analyze_conversation_emotion(
        self,
        messages: List[str],
        language: str = "he",
    ) -> Dict[str, Any]:
        """
        Phase 4.4: Assess the emotional load of a user's conversation messages.
        Returns:
            {
              "primary_emotion": str,    e.g. "stressed", "anxious", "sad", "neutral"
              "intensity": float,        0.0 (neutral) – 1.0 (extreme distress)
              "needs_followup": bool,    True only when intensity >= 0.7
              "suggested_delay_hours": int  hours before sending the check-in (2–8)
            }
        On any failure returns safe defaults (intensity=0, needs_followup=False)
        so the affective heuristic is silently skipped rather than crashing.
        """
        empty: Dict[str, Any] = {
            "primary_emotion": "neutral",
            "intensity": 0.0,
            "needs_followup": False,
            "suggested_delay_hours": 4,
        }
        if not messages:
            return empty

        lang_label = "Hebrew" if language == "he" else "English"
        joined = "\n".join(f"- {m}" for m in messages if m)

        system_prompt = (
            "You are analyzing conversation messages from a user "
            "to understand their emotional state.\n\n"
            "From the messages, assess:\n"
            "- primary_emotion: the dominant emotion "
            "(stressed, anxious, sad, frustrated, angry, happy, neutral).\n"
            "- intensity: float 0.0–1.0 representing emotional load "
            "(0.0 = completely neutral, 1.0 = extremely distressed).\n"
            "- needs_followup: true ONLY if intensity >= 0.7 AND the emotion "
            "suggests the person might benefit from a gentle supportive check-in "
            "a few hours later.\n"
            "- suggested_delay_hours: integer 2–8, hours to wait before sending "
            "the check-in (shorter for more acute emotions).\n\n"
            "Return ONLY valid JSON with exactly these four keys."
        )
        user_prompt = f"Participant messages ({lang_label}):\n{joined}"

        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
        try:
            text   = self._call_llm(msgs, temperature=0.2, max_tokens=120, json_mode=True)
            parsed = json.loads(text)
            return {
                "primary_emotion":      str(parsed.get("primary_emotion", "neutral")),
                "intensity":            float(parsed.get("intensity", 0.0)),
                "needs_followup":       bool(parsed.get("needs_followup", False)),
                "suggested_delay_hours": int(parsed.get("suggested_delay_hours", 4)),
            }
        except json.JSONDecodeError as e:
            print(f"⚠️  analyze_conversation_emotion: invalid JSON: {e}")
            return empty
        except Exception as e:
            print(f"⚠️  analyze_conversation_emotion: error: {e}")
            return empty

    def extract_stated_intents(
        self,
        messages: List[str],
        language: str = "he",
    ) -> List[Dict[str, Any]]:
        """
        Phase 4.5: Extract explicit concrete plans or commitments from conversation messages.

        Returns a list of {"intent": str} objects where each intent is a concise
        English description of what the user committed to (e.g. "go to the gym").
        Returns [] on any failure or when no clear commitments are found.

        Only extracts concrete, time-bound-ish plans — not vague wishes.
        """
        if not messages:
            return []

        joined = "\n".join(f"- {m}" for m in messages[-30:] if m)

        system_prompt = (
            "You analyze conversation messages from a user.\n"
            "Extract only EXPLICIT, concrete plans or commitments the user expressed.\n\n"
            "Valid examples:\n"
            "  - 'I'll go to the gym tomorrow'\n"
            "  - 'I'm starting that online course next week'\n"
            "  - 'I plan to call my mom tonight'\n\n"
            "Invalid examples (too vague — do NOT include):\n"
            "  - 'I want to be healthier'\n"
            "  - 'Maybe I'll try that someday'\n"
            "  - 'I should exercise more'\n\n"
            "Return JSON with a single key 'intents': a list of objects, each with "
            "key 'intent' (concise English description, e.g. 'go to the gym'). "
            "Return {\"intents\": []} if no clear commitments are found."
        )
        user_prompt = f"Participant messages:\n{joined}"

        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
        try:
            text   = self._call_llm(msgs, temperature=0.2, max_tokens=200, json_mode=True)
            parsed = json.loads(text)
            intents = parsed.get("intents", []) or []
            return [i for i in intents if isinstance(i, dict) and i.get("intent")]
        except Exception as e:
            print(f"⚠️  extract_stated_intents: error: {e}")
            return []

    def check_intent_completion(
        self,
        intent_text: str,
        recent_messages: List[str],
        language: str = "he",
    ) -> Dict[str, Any]:
        """
        Phase 4.5: Determine if a user's recent messages indicate they followed
        through on a previously stated intent.

        Returns:
            {
              "resolved": bool,
              "outcome": "positive" | "negative" | "unknown"
            }
        - positive:  user mentioned doing it / completing it
        - negative:  user explicitly mentioned NOT doing it / cancelling
        - unknown:   messages give no signal either way → triggers the nudge

        Returns {"resolved": False, "outcome": "unknown"} on any failure.
        """
        default: Dict[str, Any] = {"resolved": False, "outcome": "unknown"}
        if not intent_text or not recent_messages:
            return default

        joined = "\n".join(f"- {m}" for m in recent_messages[-30:] if m)

        system_prompt = (
            f"A user previously intended to: '{intent_text}'.\n\n"
            "Based on their recent messages, determine whether they followed through:\n"
            "- outcome: 'positive' if they mentioned doing it or completing it\n"
            "- outcome: 'negative' if they explicitly mentioned NOT doing it or cancelling\n"
            "- outcome: 'unknown' if their messages give no clear signal either way\n"
            "- resolved: true only when outcome is 'positive' or 'negative'\n\n"
            "Return ONLY valid JSON with exactly two keys: resolved, outcome."
        )
        user_prompt = f"Recent messages:\n{joined}"

        msgs = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ]
        try:
            text   = self._call_llm(msgs, temperature=0.1, max_tokens=80, json_mode=True)
            parsed = json.loads(text)
            outcome = str(parsed.get("outcome", "unknown"))
            if outcome not in ("positive", "negative", "unknown"):
                outcome = "unknown"
            return {
                "resolved": bool(parsed.get("resolved", False)),
                "outcome":  outcome,
            }
        except Exception as e:
            print(f"⚠️  check_intent_completion: error: {e}")
            return default

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
                    "You are a conversational assistant. "
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
