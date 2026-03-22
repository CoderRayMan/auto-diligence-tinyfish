"""
Reusable TinyFish Web Agent runner for AutoDiligence.

Demonstrates and verifies that requests actually hit the TinyFish platform
by printing every SSE event as they arrive in real-time.

Usage (standalone):
    python -m src.tinyfish_runner

Usage (imported):
    from src.tinyfish_runner import run_agent, run_agent_async

Requires:
    TINYFISH_API_KEY in .env or environment
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

# Load .env automatically when run as a script
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from tinyfish import TinyFish, BrowserProfile
from tinyfish.agent.types import (
    CompleteEvent,
    EventType,
    HeartbeatEvent,
    ProgressEvent,
    StartedEvent,
    StreamingUrlEvent,
)
from tinyfish.runs.types import RunStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tinyfish_runner")


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_agent(
    url: str,
    goal: str,
    browser_profile: BrowserProfile = BrowserProfile.LITE,
    verbose: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Call the TinyFish Web Agent streaming API and return the structured result.

    Streams all SSE events live and returns the parsed result dict on success,
    or None if the run fails.

    Event flow confirmed by TinyFish SDK (tinyfish.agent.types.EventType):
        STARTED → STREAMING_URL → PROGRESS (×N) → HEARTBEAT (×N) → COMPLETE

    Note: There is NO "ERROR" event type in the TinyFish SDK.
    Failures arrive as COMPLETE with status != COMPLETED.

    Args:
        url: Target website URL (must include https://)
        goal: Natural language instruction for the agent
        browser_profile: BrowserProfile.LITE (default) or BrowserProfile.STEALTH
        verbose: Print events to stdout in real-time

    Returns:
        Dict parsed from the COMPLETE event's result_json, or None on failure.

    Raises:
        tinyfish.AuthenticationError: If TINYFISH_API_KEY is invalid
        tinyfish.RateLimitError: If the rate limit is exceeded
    """
    api_key = os.environ.get("TINYFISH_API_KEY")
    if not api_key:
        raise RuntimeError(
            "TINYFISH_API_KEY not found in environment. "
            "Add it to your .env file: TINYFISH_API_KEY=sk-tinyfish-..."
        )

    client = TinyFish()  # auto-reads TINYFISH_API_KEY from env

    if verbose:
        print(f"\n{'='*60}")
        print(f"  TinyFish Agent Run")
        print(f"  URL   : {url}")
        print(f"  Goal  : {goal[:80]}{'...' if len(goal) > 80 else ''}")
        print(f"  Mode  : {browser_profile.value}")
        print(f"{'='*60}\n")

    result: Optional[Dict[str, Any]] = None

    with client.agent.stream(
        url=url,
        goal=goal,
        browser_profile=browser_profile,
    ) as stream:
        for event in stream:

            if event.type == EventType.STARTED:
                if verbose:
                    print(f"[▶ STARTED]  run_id={event.run_id}")

            elif event.type == EventType.STREAMING_URL:
                if verbose:
                    print(f"[🔴 LIVE]    Browser stream: {event.streaming_url}")

            elif event.type == EventType.PROGRESS:
                if verbose:
                    print(f"[→ STEP]     {event.purpose}")

            elif event.type == EventType.HEARTBEAT:
                # Keepalive ping from the server — no action needed
                pass

            elif event.type == EventType.COMPLETE:
                if event.status == RunStatus.COMPLETED:
                    result = event.result_json  # Dict[str, Any] | None
                    if verbose:
                        print(f"\n[✓ COMPLETE] status={event.status}")
                        print(f"Result:\n{json.dumps(result, indent=2)}")
                else:
                    err = event.error.message if event.error else f"status={event.status}"
                    if verbose:
                        print(f"\n[✗ FAILED]  {err}")
                    logger.error(f"TinyFish run failed: {err}")

    return result


async def run_agent_async(
    url: str,
    goal: str,
    browser_profile: BrowserProfile = BrowserProfile.LITE,
    verbose: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Async wrapper around run_agent — runs in a thread pool to avoid blocking
    the event loop (TinyFish SDK uses synchronous HTTP streaming).

    Returns the result dict or None.
    """
    import asyncio

    return await asyncio.to_thread(
        run_agent,
        url=url,
        goal=goal,
        browser_profile=browser_profile,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# Pre-built tasks for the AutoDiligence sources
# ---------------------------------------------------------------------------

DEMO_TASKS = [
    {
        "name": "OSHA — Acme Corp safety violations",
        "url": "https://www.osha.gov/ords/imis/establishment.html",
        "goal": (
            "Search for workplace safety violations and enforcement actions for the company "
            "'Acme Corp'. Return a JSON object with a 'cases' array. Each case should include: "
            "case_id, violation_type, penalty_amount, decision_date, status, description."
        ),
        "profile": BrowserProfile.LITE,
    },
    {
        "name": "SEC EDGAR — enforcement actions",
        "url": "https://efts.sec.gov/LATEST/search-index?q=%22Acme+Corp%22&dateRange=custom&startdt=2020-01-01&forms=34-1&entity=",
        "goal": (
            "Find SEC enforcement actions, litigation releases, and administrative proceedings "
            "related to 'Acme Corp'. Return a JSON object with a 'cases' array containing: "
            "case_id, violation_type, penalty_amount, decision_date, status, description, source_url."
        ),
        "profile": BrowserProfile.LITE,
    },
    {
        "name": "FDA — import alerts and enforcement",
        "url": "https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts",
        "goal": (
            "Search for FDA safety alerts, recalls, and enforcement actions related to 'Acme Corp'. "
            "Return a JSON object with a 'cases' array containing: "
            "case_id, violation_type, penalty_amount, decision_date, status, description."
        ),
        "profile": BrowserProfile.LITE,
    },
]


def run_all_demo_tasks(entity: str = "Acme Corp") -> Dict[str, Any]:
    """
    Run all pre-built AutoDiligence demo tasks and return aggregated results.

    Args:
        entity: Company name to research

    Returns:
        Dict mapping task name → result
    """
    results = {}
    for task in DEMO_TASKS:
        # Inject the entity name into the goal
        goal = task["goal"].replace("Acme Corp", entity)
        print(f"\n{'─'*60}")
        print(f"Task: {task['name'].replace('Acme Corp', entity)}")
        print(f"{'─'*60}")
        result = run_agent(
            url=task["url"],
            goal=goal,
            browser_profile=task["profile"],
            verbose=True,
        )
        results[task["name"]] = result
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run TinyFish Web Agent tasks for AutoDiligence"
    )
    parser.add_argument("--url", help="Target URL (overrides demo task)")
    parser.add_argument("--goal", help="Natural language goal (overrides demo task)")
    parser.add_argument(
        "--profile",
        choices=["lite", "stealth"],
        default="lite",
        help="Browser profile (default: lite)",
    )
    parser.add_argument(
        "--entity",
        default="Acme Corp",
        help="Entity name for demo tasks (default: Acme Corp)",
    )
    parser.add_argument(
        "--task",
        type=int,
        choices=range(len(DEMO_TASKS)),
        help=f"Run a single demo task by index 0-{len(DEMO_TASKS)-1}",
    )
    args = parser.parse_args()

    profile = BrowserProfile.STEALTH if args.profile == "stealth" else BrowserProfile.LITE

    if args.url and args.goal:
        # Custom run
        result = run_agent(url=args.url, goal=args.goal, browser_profile=profile)
        sys.exit(0 if result is not None else 1)
    elif args.task is not None:
        # Single demo task
        task = DEMO_TASKS[args.task]
        goal = task["goal"].replace("Acme Corp", args.entity)
        result = run_agent(url=task["url"], goal=goal, browser_profile=task["profile"])
        sys.exit(0 if result is not None else 1)
    else:
        # All demo tasks
        results = run_all_demo_tasks(entity=args.entity)
        succeeded = sum(1 for v in results.values() if v is not None)
        print(f"\n{'='*60}")
        print(f"Summary: {succeeded}/{len(DEMO_TASKS)} tasks succeeded")
        sys.exit(0 if succeeded > 0 else 1)
