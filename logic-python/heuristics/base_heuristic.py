"""
BaseHeuristic — Abstract base class for all proactive heuristics.

Each concrete subclass is responsible for:
  create_memory()          — extract and persist heuristic-relevant memories
                             from recent conversations into proactiveMemory (MongoDB).
  get_proactive_message()  — call create_memory(), reload fresh state, then generate
                             and return a proactive message string.  Returns None if
                             this heuristic has nothing to send this cycle.
  clear_after_send()       — post-FCM cleanup hook (default: no-op).

Prompts are loaded in priority order:
  1. experiments.proactiveSettings.heuristicPrompts (researcher override via dashboard)
  2. DEFAULT_MEMORY_PROMPT / DEFAULT_MESSAGE_PROMPT class attributes (hardcoded fallback)

All LLM calls go through llm_service._call_llm() via llm_service.call_with_prompt().
No heuristic file makes direct HTTP requests.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from bson import ObjectId


class BaseHeuristic(ABC):
    """Abstract base for all proactive heuristics (Task 3.2)."""

    DEFAULT_MEMORY_PROMPT: str = ""
    DEFAULT_MESSAGE_PROMPT: str = ""

    def __init__(
        self,
        user: dict,
        llm_service,
        mongodb_client,
        prompts_from_db: dict = None,
    ):
        self.user           = user
        self.user_id        = str(user["_id"])
        self.username       = user.get("username", "Unknown")
        self.llm_service    = llm_service
        self.mongodb_client = mongodb_client

        memory        = user.get("proactiveMemory") or {}
        self.language = memory.get("preferred_language", "he")
        self.name     = (memory.get("demographics") or {}).get("name") or self.username

        # Prompt loading: DB override takes priority over hardcoded default
        prompts = prompts_from_db or {}
        self.memory_prompt  = prompts.get("memoryPrompt")  or self.DEFAULT_MEMORY_PROMPT
        self.message_prompt = prompts.get("messagePrompt") or self.DEFAULT_MESSAGE_PROMPT

    # ── Convenience properties ─────────────────────────────────────────────────

    @property
    def _memory(self) -> dict:
        """Live snapshot of the user's proactiveMemory sub-document."""
        return self.user.get("proactiveMemory") or {}

    @property
    def _target_lang(self) -> str:
        return "Hebrew" if self.language == "he" else "English"

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _reload_user(self) -> None:
        """
        Re-read proactiveMemory from MongoDB into self.user.
        Must be called at the start of get_proactive_message() after create_memory()
        has written new data, so the message-generation step sees the fresh state.
        """
        try:
            if self.mongodb_client.connect():
                fresh = self.mongodb_client.db[
                    self.mongodb_client.users_collection
                ].find_one(
                    {"_id": ObjectId(self.user_id)},
                    {"proactiveMemory": 1},
                )
                if fresh:
                    self.user = {
                        **self.user,
                        "proactiveMemory": fresh.get("proactiveMemory") or {},
                    }
        except Exception as e:
            print(f"⚠️  {self.__class__.__name__}._reload_user({self.username}): {e}")
        finally:
            self.mongodb_client.disconnect()

    # ── Abstract interface ─────────────────────────────────────────────────────

    @abstractmethod
    def create_memory(self) -> None:
        """
        Scan recent conversations and write heuristic-relevant memories to MongoDB.
        Uses self.memory_prompt for the LLM extraction call.
        Must be idempotent — use message counters or conversation IDs to deduplicate.
        """
        ...

    @abstractmethod
    def get_proactive_message(self) -> Optional[str]:
        """
        Refresh memory (create_memory → _reload_user), then generate and return
        the proactive message string.
        Returns None if this heuristic has nothing to send this cycle.
        """
        ...

    def clear_after_send(self) -> None:
        """
        Post-send cleanup called by research_service after a successful FCM send.
        Default: no-op.  Override in subclasses that write pending state to MongoDB.
        """
        pass
