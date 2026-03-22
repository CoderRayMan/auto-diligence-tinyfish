"""
Abstract base agent. All source-specific agents inherit from this.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tinyfish import TinyFish, BrowserProfile, EventType, RunStatus


@dataclass
class SourceConfig:
    """Configuration for a single regulatory data source."""
    id: str
    name: str
    base_url: str
    category: str
    login_flow: str  # "none" | "username_password"
    browser_profile: str  # "LITE" | "STEALTH"
    search_goal_template: str
    proxy: Dict[str, Any]
    rate_limit: Dict[str, Any]
    retry_policy: Dict[str, Any]


class BaseAgent(ABC):
    """
    Abstract base for all TinyFish-powered site agents.

    Subclasses must implement `_build_goal` and `_normalize_result`.
    The base class handles streaming, error handling, and retry logic.
    """

    def __init__(self, source: SourceConfig, token_vault: Any = None):
        self.source = source
        self.token_vault = token_vault
        self.client = TinyFish()
        self.tokens_used: int = 0
        self.logger = logging.getLogger(f"agent.{source.id}")

    @abstractmethod
    def _build_goal(self, target: str, query: str) -> str:
        """Return the natural-language goal string for TinyFish."""

    @abstractmethod
    def _normalize_result(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert raw TinyFish result_json into a list of normalised case dicts."""

    def _get_browser_profile(self) -> BrowserProfile:
        profile = self.source.browser_profile.upper()
        return BrowserProfile.STEALTH if profile == "STEALTH" else BrowserProfile.LITE

    def _stream_agent(self, goal: str) -> Optional[Dict[str, Any]]:
        """Run TinyFish stream and return result_json on success, None on failure."""
        max_retries = self.source.retry_policy.get("max_retries", 3)
        backoff = self.source.retry_policy.get("backoff_seconds", 2)

        import time
        import random

        for attempt in range(max_retries):
            jitter = self.source.rate_limit.get("jitter_ms", 0)
            if jitter > 0:
                time.sleep(random.randint(0, jitter) / 1000.0)

            try:
                with self.client.agent.stream(
                    url=self.source.base_url,
                    goal=goal,
                    browser_profile=self._get_browser_profile(),
                    timeout_seconds=120,
                ) as stream:
                    for event in stream:
                        if event.type == EventType.ERROR:
                            self.logger.warning(
                                f"[{self.source.id}] Agent warning: {event.error}"
                            )
                        elif event.type == EventType.COMPLETE:
                            if event.status == RunStatus.COMPLETED:
                                return event.result_json
                            else:
                                self.logger.error(
                                    f"[{self.source.id}] Task failed: {event.error}"
                                )
                                break
            except Exception as exc:
                self.logger.error(
                    f"[{self.source.id}] Attempt {attempt + 1} error: {exc}"
                )
                if attempt < max_retries - 1:
                    time.sleep(backoff * (attempt + 1))

        return None

    async def research(self, target: str, query: str) -> List[Dict[str, Any]]:
        """
        Execute research for the given target and return normalised cases.
        Runs synchronous TinyFish stream in a thread via asyncio.to_thread.
        """
        import asyncio

        goal = self._build_goal(target, query)
        self.logger.info(f"[{self.source.id}] Researching: {target!r}")

        raw = await asyncio.to_thread(self._stream_agent, goal)
        if raw is None:
            return []

        return self._normalize_result(raw)
