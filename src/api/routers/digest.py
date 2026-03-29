"""
/api/digest — AI-powered narrative briefings using TinyFish browser runs.

Briefing endpoints queue live TinyFish runs and return a run_id immediately so
the frontend can poll /api/runs/{run_id} until the structured result is ready.
If live research cannot be started, each endpoint falls back to a summary built
from local scan and finding data.

This keeps the UI responsive even when TinyFish runs take multiple minutes to
finish, which is common for Reuters/SEC research flows.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..store import scan_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/digest", tags=["digest"])

DIGEST_QUEUE_TIMEOUT_SECONDS = float(os.getenv("DIGEST_QUEUE_TIMEOUT_SECONDS", "15"))

# ------------------------------------------------------------------ helpers


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


def _severity_weight(level: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(str(level).lower(), 4)


def _top_findings(findings: list[Any], limit: int = 3) -> list[Any]:
    return sorted(
        findings,
        key=lambda finding: (
            _severity_weight(str(finding.severity)),
            -(finding.penalty_amount or 0.0),
        ),
    )[:limit]


def _verdict_for_score(score: Optional[float]) -> str:
    if score is None:
        return "LOW_RISK"
    if score >= 75:
        return "HIGH_RISK"
    if score >= 35:
        return "MEDIUM_RISK"
    return "LOW_RISK"


def _build_digest_response(
    *,
    digest_type: str,
    target: Optional[str],
    started_at: datetime,
    briefing: Optional[str],
    raw_result: Optional[dict[str, Any]],
    num_steps: int = 0,
    run_id: Optional[str] = None,
) -> DigestResponse:
    duration = (datetime.now(timezone.utc) - started_at).total_seconds()
    return DigestResponse(
        digest_type=digest_type,
        target=target,
        generated_at=started_at.isoformat(),
        briefing=briefing,
        raw_result=raw_result,
        num_steps=num_steps,
        duration_seconds=round(duration, 1),
        run_id=run_id,
        streaming_url=None,
    )


def _fallback_payload(reason: str, **payload: Any) -> dict[str, Any]:
    return {
        "mode": "fallback",
        "reason": reason,
        **payload,
    }


def _queued_payload(context: str) -> dict[str, Any]:
    return {
        "mode": "queued",
        "status": "RUNNING",
        "context": context,
        "message": "Live TinyFish research has started. Polling run status until completion.",
    }


async def _queue_agent_run(
    *,
    url: str,
    goal: str,
    browser_profile: Any,
    context: str,
    **kwargs: Any,
) -> tuple[Any | None, str | None]:
    """Queue a TinyFish run and return its run_id quickly for client-side polling."""
    try:
        from tinyfish import TinyFish
    except Exception as exc:
        reason = f"TinyFish import failed: {exc}"
        logger.warning("[Digest] %s", reason)
        return None, reason

    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key:
        reason = "TINYFISH_API_KEY not configured"
        logger.warning("[Digest] %s", reason)
        return None, reason

    try:
        client = TinyFish(api_key=api_key)
        queued = await asyncio.wait_for(
            asyncio.to_thread(
                client.agent.queue,
                url=url,
                goal=goal,
                browser_profile=browser_profile,
                **kwargs,
            ),
            timeout=DIGEST_QUEUE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        reason = f"TinyFish queue timed out after {DIGEST_QUEUE_TIMEOUT_SECONDS:.0f}s"
        logger.warning("[Digest] %s for %s", reason, context)
        return None, reason
    except Exception as exc:
        reason = f"TinyFish queue error: {exc}"
        logger.warning("[Digest] %s for %s", reason, context)
        return None, reason

    run_id = getattr(queued, "run_id", None)
    if not run_id:
        err = getattr(getattr(queued, "error", None), "message", str(queued))
        reason = f"agent.queue() returned no run_id: {err}"
        logger.warning("[Digest] %s for %s", reason, context)
        return None, reason

    logger.info("[Digest] Queued run %s for %s", run_id, context)
    return queued, None


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

    t0 = datetime.now(timezone.utc)

    queued, reason = await _queue_agent_run(
        url="https://www.reuters.com/business/legal/",
        goal=goal,
        browser_profile=BrowserProfile.LITE,
        context="portfolio_digest",
    )
    if queued is not None:
        return _build_digest_response(
            digest_type="portfolio",
            target=None,
            started_at=t0,
            briefing=None,
            raw_result=_queued_payload("portfolio_digest"),
            num_steps=0,
            run_id=queued.run_id,
        )

    portfolio_findings: list[Any] = []
    for scan in top5:
        portfolio_findings.extend(await scan_store.get_findings_async(scan.scan_id))

    ranked_findings = _top_findings(portfolio_findings, 4)
    key_risks = [
        f"{finding.entity_name}: {finding.violation_type} ({finding.severity})"
        for finding in ranked_findings
    ] or [
        f"{scan.target}: risk score {scan.risk_score or 0}/100 ({scan.risk_label or 'Unknown'})"
        for scan in top5[:3]
    ]
    recommended_actions = [
        f"Review the highest-risk entities first: {', '.join(scan.target for scan in top5[:3])}.",
        "Re-run AI briefings when TinyFish live research is available to enrich with external news.",
    ]
    if any((scan.risk_label or "").lower() == "critical" for scan in top5):
        recommended_actions.insert(1, "Escalate critical-risk entities for legal and compliance review.")

    briefing_text = (
        "Live external research is currently unavailable, so this briefing is generated from the latest completed "
        "AutoDiligence scans. "
        f"The highest current portfolio risk sits with {top5[0].target} at {top5[0].risk_score or 0}/100 "
        f"({top5[0].risk_label or 'Unknown'}), and the top five entities account for "
        f"{sum(scan.findings_count or 0 for scan in top5)} findings across the monitored portfolio. "
        f"The leading risk themes are {', '.join(key_risks[:3])}."
    )

    return _build_digest_response(
        digest_type="portfolio",
        target=None,
        started_at=t0,
        briefing=briefing_text,
        raw_result=_fallback_payload(
            reason or "Live research unavailable",
            key_risks=key_risks,
            recommended_actions=recommended_actions,
            top_entities=[
                {
                    "target": scan.target,
                    "risk_score": scan.risk_score,
                    "risk_label": scan.risk_label,
                    "findings_count": scan.findings_count,
                }
                for scan in top5
            ],
        ),
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

    t0 = datetime.now(timezone.utc)

    queued, reason = await _queue_agent_run(
        url=f"https://efts.sec.gov/LATEST/search-index?q=%22{target.replace(' ', '+')}%22",
        goal=goal,
        browser_profile=BrowserProfile.LITE,
        context=f"entity_digest:{target}",
    )
    if queued is not None:
        return _build_digest_response(
            digest_type="entity",
            target=target,
            started_at=t0,
            briefing=None,
            raw_result=_queued_payload(f"entity_digest:{target}"),
            num_steps=0,
            run_id=queued.run_id,
        )

    top_concerns = [
        f"{finding.violation_type} ({finding.source_id.upper()}, {finding.severity})"
        for finding in _top_findings(findings, 3)
    ] or ["No critical or high-severity findings in the latest completed scan"]
    exposure_total = sum(finding.penalty_amount or 0.0 for finding in findings)
    source_mix = Counter(finding.source_id.upper() for finding in findings).most_common(3)
    monitoring_recommendation = (
        "Escalate to compliance and legal review with a near-term re-scan."
        if (latest.risk_score or 0) >= 75
        else "Maintain periodic monitoring and re-run after any new enforcement activity."
    )
    briefing_text = (
        f"Live external research is currently unavailable, so this summary uses the latest completed AutoDiligence scan for {target}. "
        f"The entity is currently rated {latest.risk_label or 'Unknown'} at {latest.risk_score or 0}/100 with "
        f"{len(findings)} findings and approximately ${exposure_total:,.0f} of recorded exposure. "
        f"The top local concerns are {', '.join(top_concerns[:3])}."
    )

    return _build_digest_response(
        digest_type="entity",
        target=target,
        started_at=t0,
        briefing=briefing_text,
        raw_result=_fallback_payload(
            reason or "Live research unavailable",
            verdict=_verdict_for_score(latest.risk_score),
            top_concerns=top_concerns,
            monitoring_recommendation=monitoring_recommendation,
            dominant_sources=[{"source": source, "count": count} for source, count in source_mix],
        ),
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

    t0 = datetime.now(timezone.utc)

    queued, reason = await _queue_agent_run(
        url=f"https://www.reuters.com/search/news?blob={target.replace(' ', '+')}",
        goal=goal,
        browser_profile=BrowserProfile.LITE,
        context=f"risk_spike_digest:{target}",
    )
    if queued is not None:
        return _build_digest_response(
            digest_type="risk_spike",
            target=target,
            started_at=t0,
            briefing=None,
            raw_result=_queued_payload(f"risk_spike_digest:{target}"),
            num_steps=0,
            run_id=queued.run_id,
        )

    prev_findings = await scan_store.get_findings_async(prev.scan_id)
    latest_findings = await scan_store.get_findings_async(latest.scan_id)
    prev_critical = sum(1 for finding in prev_findings if finding.severity == "critical")
    latest_critical = sum(1 for finding in latest_findings if finding.severity == "critical")
    prev_high = sum(1 for finding in prev_findings if finding.severity == "high")
    latest_high = sum(1 for finding in latest_findings if finding.severity == "high")
    prev_exposure = sum(finding.penalty_amount or 0.0 for finding in prev_findings)
    latest_exposure = sum(finding.penalty_amount or 0.0 for finding in latest_findings)

    events_found: list[str] = []
    if latest_critical != prev_critical:
        events_found.append(f"Critical findings changed from {prev_critical} to {latest_critical}")
    if latest_high != prev_high:
        events_found.append(f"High-severity findings changed from {prev_high} to {latest_high}")
    if len(latest_findings) != len(prev_findings):
        events_found.append(f"Total findings changed from {len(prev_findings)} to {len(latest_findings)}")
    if round(latest_exposure - prev_exposure, 2) != 0:
        events_found.append(
            f"Recorded exposure changed by ${latest_exposure - prev_exposure:,.0f}"
        )
    if not events_found:
        events_found.append("Stored scan data shows no clear internal driver for the score change")

    justified = delta > 0 and (
        latest_critical > prev_critical
        or latest_high > prev_high
        or len(latest_findings) > len(prev_findings)
        or latest_exposure > prev_exposure
    )
    briefing_text = (
        f"Live external research is currently unavailable, so this explanation uses only the two most recent completed scans for {target}. "
        f"The score {direction} from {prev.risk_score or 0} to {latest.risk_score or 0} ({delta:+d}). "
        f"The clearest internal drivers are: {'; '.join(events_found[:3])}."
    )

    return _build_digest_response(
        digest_type="risk_spike",
        target=target,
        started_at=t0,
        briefing=briefing_text,
        raw_result=_fallback_payload(
            reason or "Live research unavailable",
            events_found=events_found,
            risk_delta=delta,
            assessment="The score change is JUSTIFIED" if justified else "UNEXPLAINED",
        ),
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

    queued_run_ids: list[str] = []
    targets_queued: list[str] = []

    try:
        from tinyfish import BrowserProfile, TinyFish
    except Exception as exc:
        return QueuedEnrichmentResponse(
            message=f"TinyFish queue unavailable: import failed ({exc})",
            queued_run_ids=[],
            targets_queued=[],
        )

    api_key = os.getenv("TINYFISH_API_KEY")
    if not api_key:
        return QueuedEnrichmentResponse(
            message="TinyFish queue unavailable: TINYFISH_API_KEY not configured",
            queued_run_ids=[],
            targets_queued=[],
        )

    client = TinyFish(api_key=api_key)

    for entity in entity_list:
        goal = f"""Search https://efts.sec.gov/LATEST/search-index?q=%22{entity.replace(' ', '+')}%22
for recent SEC filings, enforcement actions, or regulatory disclosures involving {entity}.
Return JSON: {{"entity": "{entity}", "findings": [...], "risk_indicators": [...]}}"""

        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    client.agent.queue,
                    url=f"https://efts.sec.gov/LATEST/search-index?q=%22{entity.replace(' ', '+')}%22",
                    goal=goal,
                    browser_profile=BrowserProfile.LITE,
                ),
                timeout=max(5.0, DIGEST_TIMEOUT_SECONDS / 2),
            )
            if resp.run_id:
                queued_run_ids.append(resp.run_id)
                targets_queued.append(entity)
                logger.info(f"[Digest] Queued enrichment run {resp.run_id} for '{entity}'")
            elif resp.error:
                logger.warning(f"[Digest] Queue failed for '{entity}': {resp.error.message}")
        except asyncio.TimeoutError:
            logger.warning(f"[Digest] Queue timed out for '{entity}'")
        except Exception as exc:
            logger.error(f"[Digest] Queue error for '{entity}': {exc}")

    return QueuedEnrichmentResponse(
        message=(
            f"Queued {len(queued_run_ids)} enrichment run(s) via TinyFish agent.queue()"
            if queued_run_ids
            else "No enrichment runs were queued. TinyFish may be unavailable or timing out."
        ),
        queued_run_ids=queued_run_ids,
        targets_queued=targets_queued,
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

    t0 = datetime.now(timezone.utc)

    proxy_config = ProxyConfig(
        enabled=True,
        country_code=ProxyCountryCode(country_code.upper()),
    )

    queued, reason = await _queue_agent_run(
        url=url,
        goal=goal,
        browser_profile=BrowserProfile.STEALTH,
        proxy_config=proxy_config,
        context=f"geo_targeted_scan:{target}:{country_code.upper()}",
    )
    if queued is not None:
        return _build_digest_response(
            digest_type=f"geo_scan_{country_code.lower()}",
            target=target,
            started_at=t0,
            briefing=None,
            raw_result=_queued_payload(f"geo_targeted_scan:{target}:{country_code.upper()}"),
            num_steps=0,
            run_id=queued.run_id,
        )

    entity_scans = [
        scan for scan in await scan_store.list_all()
        if scan.target.lower() == target.lower() and scan.status == "completed"
    ]
    if not entity_scans:
        raise HTTPException(status_code=404, detail=f"No completed scans for '{target}'")

    latest = max(entity_scans, key=lambda scan: scan.created_at)
    findings = await scan_store.get_findings_async(latest.scan_id)
    actions_found = [
        {
            "case_id": finding.case_id,
            "type": finding.violation_type,
            "date": finding.decision_date,
            "penalty": f"${finding.penalty_amount:,.0f}",
            "status": finding.status,
        }
        for finding in _top_findings(findings, 3)
    ]
    briefing_text = (
        f"Live geo-targeted research for {country_names.get(country_code.upper(), country_code)} is currently unavailable, "
        f"so this result uses the latest completed AutoDiligence scan for {target}. "
        f"The current local posture is {latest.risk_label or 'Unknown'} risk at {latest.risk_score or 0}/100 with "
        f"{len(findings)} findings on record."
    )

    return _build_digest_response(
        digest_type=f"geo_scan_{country_code.lower()}",
        target=target,
        started_at=t0,
        briefing=briefing_text,
        raw_result=_fallback_payload(
            reason or "Live research unavailable",
            entity=target,
            jurisdiction=country_names.get(country_code.upper(), country_code),
            actions_found=actions_found,
            risk_level=latest.risk_label or "NONE",
        ),
    )
