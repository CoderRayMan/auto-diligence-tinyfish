"""
Abstract base agent. All source-specific agents inherit from this.
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from tinyfish import (
    TinyFish,
    BrowserProfile,
    CompleteEvent,
    EventType,
    ProgressEvent,
    StartedEvent,
    StreamingUrlEvent,
)
from tinyfish.runs.types import RunStatus


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

    Correct TinyFish SDK event types (from tinyfish.agent.types.EventType):
      STARTED, STREAMING_URL, PROGRESS, HEARTBEAT, COMPLETE
    There is no ERROR event — failures arrive as COMPLETE with status != COMPLETED.
    """

    def __init__(
        self,
        source: SourceConfig,
        token_vault: Any = None,
        event_callback: Optional[Callable[[str, str, str, Optional[str]], None]] = None,
    ):
        self.source = source
        self.token_vault = token_vault
        # Called with (source_id, tag, message, streaming_url|None)
        self._event_callback = event_callback
        self.client = TinyFish()  # reads TINYFISH_API_KEY from env
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

    def _emit(self, tag: str, message: str, streaming_url: Optional[str] = None) -> None:
        """Forward event to the SSE callback if one is registered."""
        self.logger.info(f"[{self.source.id}][{tag}] {message}")
        if self._event_callback:
            self._event_callback(self.source.id, tag, message, streaming_url)

    def _stream_agent(self, goal: str) -> Optional[Dict[str, Any]]:
        """
        Call the TinyFish streaming API and return result on success.

        Event flow (per SDK docs):
            STARTED → STREAMING_URL → PROGRESS (×N) → HEARTBEAT (×N) → COMPLETE

        The SDK has NO 'ERROR' event type. Failures come as COMPLETE with
        event.status != RunStatus.COMPLETED and event.error set.
        """
        max_retries = self.source.retry_policy.get("max_retries", 3)
        backoff = self.source.retry_policy.get("backoff_seconds", 2)
        jitter_ms = self.source.rate_limit.get("jitter_ms", 0)

        for attempt in range(max_retries):
            if jitter_ms > 0:
                time.sleep(random.randint(0, jitter_ms) / 1000.0)

            try:
                self._emit("RUNNING", f"Starting TinyFish agent (attempt {attempt + 1})")

                with self.client.agent.stream(
                    url=self.source.base_url,
                    goal=goal,
                    browser_profile=self._get_browser_profile(),
                ) as stream:
                    for event in stream:
                        if event.type == EventType.STARTED:
                            self._emit("RUNNING", f"Run started — id={event.run_id}")

                        elif event.type == EventType.STREAMING_URL:
                            # Emit the live browser URL so the UI can embed it
                            self._emit(
                                "STREAMING_URL",
                                f"Browser live: {event.streaming_url}",
                                streaming_url=event.streaming_url,
                            )

                        elif event.type == EventType.PROGRESS:
                            # Forward each agent step to the UI in real-time
                            self._emit("RUNNING", event.purpose)

                        elif event.type == EventType.HEARTBEAT:
                            pass  # keepalive — no action needed

                        elif event.type == EventType.COMPLETE:
                            if event.status == RunStatus.COMPLETED:
                                self._emit("COMPLETED", "Agent run completed successfully")
                                return event.result_json  # Dict[str, Any] | None
                            else:
                                err_msg = (
                                    event.error.message
                                    if event.error
                                    else f"status={event.status}"
                                )
                                self._emit("FAILED", f"Run failed: {err_msg}")
                                # Only retry on SYSTEM_FAILURE
                                if event.error and event.error.category == "SYSTEM_FAILURE":
                                    break  # retry the outer loop
                                return None  # AGENT_FAILURE — do not retry

            except Exception as exc:
                self._emit("FAILED", f"Exception on attempt {attempt + 1}: {exc}")
                if attempt < max_retries - 1:
                    time.sleep(backoff * (attempt + 1))

        return None

    async def research(
        self,
        target: str,
        query: str,
        event_callback: Optional[Callable[[str, str, str, Optional[str]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute research for the given target and return normalised cases.
        Runs synchronous TinyFish stream in a thread via asyncio.to_thread.

        Args:
            target: Entity name to research (e.g. "Acme Corp")
            query: Optional research focus (e.g. "workplace safety violations")
            event_callback: Optional override for SSE event forwarding.
        """
        import asyncio

        if event_callback:
            self._event_callback = event_callback

        goal = self._build_goal(target, query)
        self.logger.info(f"[{self.source.id}] Researching: {target!r}")
        self._emit("RUNNING", f"Goal: {goal[:120]}…" if len(goal) > 120 else f"Goal: {goal}")

        raw = await asyncio.to_thread(self._stream_agent, goal)
        if raw is None:
            return []

        return self._normalize_result(raw)
