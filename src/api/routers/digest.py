"""
/api/digest — AI-powered narrative briefings using TinyFish agent.run().

Uses TinyFish agent.run() (synchronous, blocking) to generate:
  1. Weekly executive briefing for the full portfolio
  2. Entity deep-dive: narrative summary for a single target
  3. Risk spike analysis: explain why a score changed

agent.run() is the RIGHT call here — we need a single, structured answer
(the briefing), not a streaming UX. It blocks until the agent finishes,
returns AgentRunResponse with num_of_steps telemetry included.

Also demonstrates agent.queue() for fire-and-forget batch enrichment.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..store import scan_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/digest", tags=["digest"])

# ------------------------------------------------------------------ helpers

def _get_client():
    from tinyfish import TinyFish
    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="TINYFISH_API_KEY not configured")
    return TinyFish(api_key=api_key)


# ------------------------------------------------------------------ models

class DigestResponse(BaseModel):
    digest_type: str
    target: Optional[str]
    generated_at: str
    briefing: Optional[str]        # narrative text extracted from result
    raw_result: Optional[dict]     # full result_json from TinyFish
    num_steps: int
    duration_seconds: Optional[float]
    run_id: Optional[str]
    streaming_url: Optional[str]


class QueuedEnrichmentResponse(BaseModel):
    message: str
    queued_run_ids: list[str]
    targets_queued: list[str]


# ------------------------------------------------------------------ portfolio digest

@router.post("/portfolio", response_model=DigestResponse)
async def portfolio_digest() -> DigestResponse:
    """
    Generate an AI narrative briefing for the full portfolio.

    Uses TinyFish agent.run() to visit a regulatory news aggregator and
    synthesise a plain-English "weekly briefing" covering the top risk themes
    across all monitored entities.

    Returns num_of_steps so the UI can show agent effort.
    """
    from tinyfish import BrowserProfile

    # Build context from our own data
    all_scans = await scan_store.list_all()
    completed = [s for s in all_scans if s.status == "completed"]

    if not completed:
        raise HTTPException(status_code=404, detail="No completed scans to summarise")

    # Top 5 highest-risk entities
    top5 = sorted(completed, key=lambda s: s.risk_score or 0, reverse=True)[:5]
    entity_lines = "\n".join(
        f"  - {s.target}: risk score {s.risk_score} ({s.risk_label}), "
        f"{s.findings_count} findings"
        for s in top5
    )

    goal = f"""You are a regulatory intelligence analyst writing a concise executive briefing.

Below is a summary of our monitored portfolio (top 5 highest-risk entities):
{entity_lines}

Visit https://www.reuters.com/business/legal/ and scan the headlines for any recent
regulatory enforcement, fines, recalls, or investigations involving these companies:
{', '.join(s.target for s in top5)}.

Return a JSON object with:
{{
  "briefing": "<2-3 paragraph executive summary mentioning the most critical findings and any new news items found>",
  "key_risks": ["<risk 1>", "<risk 2>", ...],
  "recommended_actions": ["<action 1>", "<action 2>", ...]
}}

Be specific, cite company names and risk scores. Keep the briefing under 300 words."""

    client = _get_client()
    t0 = datetime.now(timezone.utc)

    try:
        resp = await asyncio.to_thread(
            client.agent.run,
            url="https://www.reuters.com/business/legal/",
            goal=goal,
            browser_profile=BrowserProfile.LITE,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TinyFish agent error: {exc}")

    duration = (datetime.now(timezone.utc) - t0).total_seconds()

    briefing_text = None
    if resp.result:
        briefing_text = resp.result.get("briefing") or str(resp.result)

    return DigestResponse(
        digest_type="portfolio",
        target=None,
        generated_at=t0.isoformat(),
        briefing=briefing_text,
        raw_result=resp.result,
        num_steps=resp.num_of_steps,
        duration_seconds=round(duration, 1),
        run_id=resp.run_id,
        streaming_url=None,   # agent.run() doesn't expose streaming_url in response
    )


# ------------------------------------------------------------------ entity deep-dive

@router.post("/entity", response_model=DigestResponse)
async def entity_digest(
    target: str = Query(..., description="Entity name to generate briefing for"),
) -> DigestResponse:
    """
    Generate an AI narrative deep-dive for a single entity.

    Uses TinyFish agent.run() to visit SEC/EDGAR and produce a structured
    summary of the entity's regulatory posture, combining our finding data
    with live news context.
    """
    from tinyfish import BrowserProfile

    all_scans = await scan_store.list_all()
    entity_scans = [
        s for s in all_scans
        if s.target.lower() == target.lower() and s.status == "completed"
    ]

    if not entity_scans:
        raise HTTPException(status_code=404, detail=f"No completed scans for '{target}'")

    latest = max(entity_scans, key=lambda s: s.created_at)
    findings = await scan_store.get_findings_async(latest.scan_id)

    critical_findings = [f for f in findings if f.severity == "critical"]
    high_findings = [f for f in findings if f.severity == "high"]

    findings_summary = "\n".join(
        f"  [{f.severity.upper()}] {f.violation_type} — {f.description[:100]}"
        for f in (critical_findings + high_findings)[:8]
    )

    goal = f"""You are a due diligence analyst preparing a risk assessment for {target}.

Our automated scan found the following findings (risk score: {latest.risk_score}/100, label: {latest.risk_label}):
{findings_summary if findings_summary else '  No critical/high findings in latest scan.'}

Visit https://efts.sec.gov/LATEST/search-index?q=%22{target.replace(' ', '+')}%22&forms=8-K,10-K
and check for any recent SEC filings or disclosures related to regulatory or legal matters for {target}.

Return a JSON object with:
{{
  "briefing": "<2-paragraph risk narrative for {target}, covering our findings and any SEC disclosures found>",
  "verdict": "HIGH_RISK | MEDIUM_RISK | LOW_RISK",
  "top_concerns": ["<concern 1>", "<concern 2>", ...],
  "monitoring_recommendation": "<sentence recommending next steps>"
}}"""

    client = _get_client()
    t0 = datetime.now(timezone.utc)

    try:
        resp = await asyncio.to_thread(
            client.agent.run,
            url=f"https://efts.sec.gov/LATEST/search-index?q=%22{target.replace(' ', '+')}%22",
            goal=goal,
            browser_profile=BrowserProfile.LITE,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TinyFish agent error: {exc}")

    duration = (datetime.now(timezone.utc) - t0).total_seconds()

    briefing_text = None
    if resp.result:
        briefing_text = resp.result.get("briefing") or str(resp.result)

    return DigestResponse(
        digest_type="entity",
        target=target,
        generated_at=t0.isoformat(),
        briefing=briefing_text,
        raw_result=resp.result,
        num_steps=resp.num_of_steps,
        duration_seconds=round(duration, 1),
        run_id=resp.run_id,
        streaming_url=None,
    )


# ------------------------------------------------------------------ risk-spike analysis

@router.post("/risk-spike", response_model=DigestResponse)
async def risk_spike_digest(
    target: str = Query(..., description="Entity to explain risk change for"),
) -> DigestResponse:
    """
    Explain WHY a target's risk score changed between its two most recent scans.

    Uses TinyFish agent.run() to research what happened between the two dates
    (new enforcement actions, news, etc.) and returns a narrative explanation.
    """
    from tinyfish import BrowserProfile

    all_scans = await scan_store.list_all()
    entity_scans = sorted(
        [s for s in all_scans if s.target.lower() == target.lower() and s.status == "completed"],
        key=lambda s: s.created_at,
    )

    if len(entity_scans) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least 2 completed scans for '{target}' to detect a risk spike",
        )

    prev, latest = entity_scans[-2], entity_scans[-1]
    delta = (latest.risk_score or 0) - (prev.risk_score or 0)
    direction = "increased" if delta > 0 else "decreased"

    goal = f"""You are a regulatory intelligence analyst explaining a risk score change.

{target}'s risk score {direction} from {prev.risk_score} to {latest.risk_score} 
(delta: {delta:+d} points) between {prev.created_at.date()} and {latest.created_at.date()}.

Visit https://www.reuters.com/search/news?blob={target.replace(' ', '+')}&sortBy=date&dateRange=custom&startDateRange={prev.created_at.date()}&endDateRange={latest.created_at.date()}
and find any news, enforcement actions, or regulatory events involving {target} during this period.

Return a JSON object with:
{{
  "briefing": "<1-2 paragraph explanation of why the risk score {direction}, citing specific events found>",
  "events_found": ["<event 1>", "<event 2>", ...],
  "risk_delta": {delta},
  "assessment": "The score change is JUSTIFIED | UNEXPLAINED based on events found"
}}"""

    client = _get_client()
    t0 = datetime.now(timezone.utc)

    try:
        resp = await asyncio.to_thread(
            client.agent.run,
            url=f"https://www.reuters.com/search/news?blob={target.replace(' ', '+')}",
            goal=goal,
            browser_profile=BrowserProfile.LITE,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TinyFish agent error: {exc}")

    duration = (datetime.now(timezone.utc) - t0).total_seconds()

    briefing_text = None
    if resp.result:
        briefing_text = resp.result.get("briefing") or str(resp.result)

    return DigestResponse(
        digest_type="risk_spike",
        target=target,
        generated_at=t0.isoformat(),
        briefing=briefing_text,
        raw_result=resp.result,
        num_steps=resp.num_of_steps,
        duration_seconds=round(duration, 1),
        run_id=resp.run_id,
        streaming_url=None,
    )


# ------------------------------------------------------------------ batch queue enrichment

@router.post("/queue-enrichment", response_model=QueuedEnrichmentResponse)
async def queue_batch_enrichment(
    targets: str = Query(..., description="Comma-separated list of entity names to enrich"),
) -> QueuedEnrichmentResponse:
    """
    Fire-and-forget enrichment for multiple entities using TinyFish agent.queue().

    agent.queue() is the right call here: we don't want to block the API
    waiting for each agent to finish.  We get a run_id back immediately and
    can poll /api/runs/{run_id} for the result.

    Returns the list of queued run_ids so the frontend can track progress.
    """
    from tinyfish import BrowserProfile

    entity_list = [t.strip() for t in targets.split(",") if t.strip()]
    if not entity_list:
        raise HTTPException(status_code=422, detail="No valid targets provided")
    if len(entity_list) > 10:
        raise HTTPException(status_code=422, detail="Maximum 10 targets per batch")

    client = _get_client()
    queued_run_ids: list[str] = []

    for entity in entity_list:
        goal = f"""Search https://efts.sec.gov/LATEST/search-index?q=%22{entity.replace(' ', '+')}%22
for recent SEC filings, enforcement actions, or regulatory disclosures involving {entity}.
Return JSON: {{"entity": "{entity}", "findings": [...], "risk_indicators": [...]}}"""

        try:
            resp = await asyncio.to_thread(
                client.agent.queue,
                url=f"https://efts.sec.gov/LATEST/search-index?q=%22{entity.replace(' ', '+')}%22",
                goal=goal,
                browser_profile=BrowserProfile.LITE,
            )
            if resp.run_id:
                queued_run_ids.append(resp.run_id)
                logger.info(f"[Digest] Queued enrichment run {resp.run_id} for '{entity}'")
            elif resp.error:
                logger.warning(f"[Digest] Queue failed for '{entity}': {resp.error.message}")
        except Exception as exc:
            logger.error(f"[Digest] Queue error for '{entity}': {exc}")

    return QueuedEnrichmentResponse(
        message=f"Queued {len(queued_run_ids)} enrichment run(s) via TinyFish agent.queue()",
        queued_run_ids=queued_run_ids,
        targets_queued=entity_list[:len(queued_run_ids)],
    )


# ------------------------------------------------------------------ geo-targeted scan

@router.post("/geo-scan", response_model=DigestResponse)
async def geo_targeted_scan(
    target: str = Query(..., description="Entity to research"),
    country_code: str = Query(default="US", description="Proxy country: US|GB|CA|DE|FR|JP|AU"),
) -> DigestResponse:
    """
    Research an entity through a geo-targeted browser proxy.

    Uses ProxyConfig to route the TinyFish browser through a specific country,
    useful for researching international regulatory databases that geo-block or
    show different content based on the visitor's country.

    e.g. UK FCA, EU databases accessed from DE, METI from JP.
    """
    from tinyfish import BrowserProfile, ProxyConfig
    from tinyfish.agent.types import ProxyCountryCode

    valid_codes = {cc.value for cc in ProxyCountryCode}
    if country_code.upper() not in valid_codes:
        raise HTTPException(
            status_code=422,
            detail=f"country_code must be one of: {', '.join(sorted(valid_codes))}"
        )

    # Pick the right regulatory URL for the country
    source_urls = {
        "US": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={target}&type=8-K&dateb=&owner=include&count=10",
        "GB": "https://www.fca.org.uk/search-results?query={target}&category=enforcement+action",
        "CA": "https://www.osc.ca/en/enforcement/enforcement-proceedings?query={target}",
        "DE": "https://www.bafin.de/SiteGlobals/Forms/Suche/EN/Sanktionssuche_Formular.html?query={target}",
        "FR": "https://www.amf-france.org/en/news-publications/news-releases?query={target}",
        "JP": "https://www.fsa.go.jp/en/news/enforcement.html",
        "AU": "https://www.asic.gov.au/online-services/search-asic-s-registers/enforcement-register/?query={target}",
    }
    url = source_urls.get(country_code.upper(), source_urls["US"]).replace("{target}", target.replace(" ", "+"))

    country_names = {
        "US": "United States (SEC)", "GB": "United Kingdom (FCA)",
        "CA": "Canada (OSC)", "DE": "Germany (BaFin)",
        "FR": "France (AMF)", "JP": "Japan (FSA)", "AU": "Australia (ASIC)",
    }

    goal = f"""You are researching {target} in the {country_names.get(country_code.upper(), country_code)} regulatory database.

Navigate to the provided URL and find any enforcement actions, fines, sanctions, or regulatory 
proceedings involving {target} or related subsidiaries.

Return JSON:
{{
  "entity": "{target}",
  "jurisdiction": "{country_names.get(country_code.upper(), country_code)}",
  "briefing": "<1-paragraph summary of regulatory standing in this jurisdiction>",
  "actions_found": [{{"case_id": "...", "type": "...", "date": "...", "penalty": "...", "status": "..."}}],
  "risk_level": "HIGH | MEDIUM | LOW | NONE"
}}"""

    client = _get_client()
    t0 = datetime.now(timezone.utc)

    proxy_config = ProxyConfig(
        enabled=True,
        country_code=ProxyCountryCode(country_code.upper()),
    )

    try:
        resp = await asyncio.to_thread(
            client.agent.run,
            url=url,
            goal=goal,
            browser_profile=BrowserProfile.STEALTH,
            proxy_config=proxy_config,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TinyFish geo-scan error: {exc}")

    duration = (datetime.now(timezone.utc) - t0).total_seconds()

    briefing_text = None
    if resp.result:
        briefing_text = resp.result.get("briefing") or str(resp.result)

    return DigestResponse(
        digest_type=f"geo_scan_{country_code.lower()}",
        target=target,
        generated_at=t0.isoformat(),
        briefing=briefing_text,
        raw_result=resp.result,
        num_steps=resp.num_of_steps,
        duration_seconds=round(duration, 1),
        run_id=resp.run_id,
        streaming_url=None,
    )
