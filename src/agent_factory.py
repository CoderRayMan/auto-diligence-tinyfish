"""
AgentFactory — instantiates and caches the correct BaseAgent subclass
for each regulatory source ID, loading source config from YAML.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .sources.base import BaseAgent, SourceConfig
from .sources.osha_agent import OshaAgent
from .sources.fda_agent import FdaAgent
from .sources.sec_agent import SecAgent
from .token_vault import TokenVault

_AGENT_REGISTRY: Dict[str, type] = {
    "us_osha": OshaAgent,
    "us_fda": FdaAgent,
    "us_sec": SecAgent,
}

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "sources.yaml"


def _load_source_configs() -> Dict[str, SourceConfig]:
    """Load source definitions from config/sources.yaml."""
    if not _CONFIG_PATH.exists():
        return {}

    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    configs: Dict[str, SourceConfig] = {}
    for source in data.get("sources", []):
        cfg = SourceConfig(
            id=source["id"],
            name=source["name"],
            base_url=source["base_url"],
            category=source.get("category", "general"),
            login_flow=source.get("login_flow", "none"),
            browser_profile=source.get("browser_profile", "LITE"),
            search_goal_template=source.get("search_goal_template", ""),
            proxy=source.get("proxy", {}),
            rate_limit=source.get("rate_limit", {}),
            retry_policy=source.get("retry_policy", {}),
        )
        configs[cfg.id] = cfg
    return configs


class AgentFactory:
    """
    Creates and caches agent instances per source.

    Agents are cached so a single TinyFish client is reused within a scan run,
    but a new factory is created per scan to avoid cross-contamination.
    """

    def __init__(
        self,
        token_vault: Optional[TokenVault] = None,
        default_profile: Optional[str] = None,
    ):
        self.token_vault = token_vault
        self.default_profile = default_profile
        self._source_configs = _load_source_configs()
        self._agent_cache: Dict[str, BaseAgent] = {}
        self.logger = logging.getLogger(__name__)

    def get_agent(self, source_id: str) -> BaseAgent:
        """Return a cached or newly created agent for the given source ID."""
        if source_id in self._agent_cache:
            return self._agent_cache[source_id]

        agent = self._create_agent(source_id)
        self._agent_cache[source_id] = agent
        return agent

    def _create_agent(self, source_id: str) -> BaseAgent:
        """Instantiate the appropriate agent class for a source."""
        agent_class = _AGENT_REGISTRY.get(source_id)
        source_config = self._source_configs.get(source_id)

        if source_config is None:
            # Create a minimal fallback config so the factory never hard-crashes
            self.logger.warning(
                f"No source config found for '{source_id}'. Using minimal fallback."
            )
            source_config = SourceConfig(
                id=source_id,
                name=source_id,
                base_url=f"https://{source_id}",
                category="unknown",
                login_flow="none",
                browser_profile="LITE",
                search_goal_template="",
                proxy={},
                rate_limit={},
                retry_policy={"max_retries": 2, "backoff_seconds": 1},
            )

        if agent_class is None:
            # Fallback to a generic OSHA-style agent for unknown sources
            from .sources.osha_agent import OshaAgent as _Fallback
            agent_class = _Fallback
            self.logger.warning(
                f"No specific agent class for '{source_id}'. Using generic fallback."
            )

        return agent_class(source=source_config, token_vault=self.token_vault)

    def active_count(self) -> int:
        return len(self._agent_cache)

    def clear(self) -> None:
        self._agent_cache.clear()
