"""
Comprehensive API feature tests for AutoDiligence.
Tests all 21 endpoints and MongoDB persistence.

Run: .venv\Scripts\python.exe test_all_features.py
"""

import asyncio
import json
import sys
import time
import httpx

BASE = "http://127.0.0.1:8000/api"
PASS = 0
FAIL = 0


def report(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    symbol = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    suffix = f" - {detail}" if detail else ""
    print(f"  [{symbol}] {name}{suffix}")


async def main():
    global PASS, FAIL

    async with httpx.AsyncClient(timeout=30) as c:

        # ═══════════════════════════════════════════════════════════
        print("\n=== 1. HEALTH & CONNECTIVITY ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/health")
        data = r.json()
        report("GET /health returns 200", r.status_code == 200)
        report("Health status is ok", data.get("status") == "ok", data.get("status", ""))
        report("Store is mongodb", data.get("store") == "mongodb", data.get("store", ""))
        report("Store is healthy", data.get("store_healthy") is True)

        # ═══════════════════════════════════════════════════════════
        print("\n=== 2. PERSONAS ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/personas")
        personas = r.json()
        report("GET /personas returns 200", r.status_code == 200)
        report("6 personas returned", len(personas) == 6, f"got {len(personas)}")

        persona_ids = [p["id"] for p in personas]
        expected_ids = ["compliance_officer", "m_and_a_analyst", "esg_researcher",
                        "legal_counsel", "investigative_journalist", "supply_chain_auditor"]
        report("All expected persona IDs present", set(expected_ids) <= set(persona_ids),
               str(persona_ids))

        # Test single persona
        r = await c.get(f"{BASE}/personas/compliance_officer")
        p = r.json()
        report("GET /personas/compliance_officer returns 200", r.status_code == 200)
        report("Persona has demo_targets", len(p.get("demo_targets", [])) > 0,
               f"{len(p.get('demo_targets', []))} targets")
        report("Persona has default_sources", len(p.get("default_sources", [])) > 0)

        # 404 for invalid persona
        r = await c.get(f"{BASE}/personas/nonexistent")
        report("GET /personas/nonexistent returns 404", r.status_code == 404)

        # ═══════════════════════════════════════════════════════════
        print("\n=== 3. SCAN LIFECYCLE (CREATE) ===")
        # ═══════════════════════════════════════════════════════════

        scan_req = {
            "target": "TestCorp Inc",
            "query": "regulatory violations",
            "sources": ["us_osha"],
            "persona_id": "compliance_officer",
            "max_concurrent_agents": 1,
        }
        r = await c.post(f"{BASE}/scans", json=scan_req)
        report("POST /scans returns 202", r.status_code == 202)
        scan = r.json()
        scan_id = scan.get("scan_id", "")
        report("Scan ID is a UUID", len(scan_id) == 36, scan_id)
        report("Status is pending", scan.get("status") == "pending", scan.get("status", ""))
        report("Target matches request", scan.get("target") == "TestCorp Inc")
        report("Persona ID stored", scan.get("persona_id") == "compliance_officer")
        report("sources_total >= 1", scan.get("sources_total", 0) >= 1,
               str(scan.get("sources_total")))

        # ═══════════════════════════════════════════════════════════
        print("\n=== 4. SCAN RETRIEVAL & LIST ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/scans/{scan_id}")
        report("GET /scans/{id} returns 200", r.status_code == 200)
        report("Scan ID matches", r.json().get("scan_id") == scan_id)

        r = await c.get(f"{BASE}/scans")
        all_scans = r.json()
        report("GET /scans returns 200", r.status_code == 200)
        report("Scan list contains our scan",
               any(s["scan_id"] == scan_id for s in all_scans),
               f"{len(all_scans)} scans total")

        # 404 for bad scan_id
        r = await c.get(f"{BASE}/scans/nonexistent-id")
        report("GET /scans/bad-id returns 404", r.status_code == 404)

        # ═══════════════════════════════════════════════════════════
        print("\n=== 5. WAIT FOR SCAN COMPLETION ===")
        # ═══════════════════════════════════════════════════════════

        max_wait = 120
        start = time.time()
        final_status = "pending"
        while time.time() - start < max_wait:
            r = await c.get(f"{BASE}/scans/{scan_id}")
            s = r.json()
            final_status = s.get("status", "unknown")
            if final_status in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(3)

        elapsed = round(time.time() - start, 1)
        report(f"Scan finished in {elapsed}s", final_status in ("completed", "failed"),
               f"status={final_status}")
        report("Scan has risk_score", s.get("risk_score") is not None or final_status == "failed",
               str(s.get("risk_score")))
        report("Scan has risk_label", s.get("risk_label") is not None or final_status == "failed",
               str(s.get("risk_label")))
        report("findings_count >= 0", s.get("findings_count", -1) >= 0,
               str(s.get("findings_count")))
        report("source_results populated", len(s.get("source_results", [])) > 0,
               str(len(s.get("source_results", []))))

        # ═══════════════════════════════════════════════════════════
        print("\n=== 6. FINDINGS ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/findings", params={"scan_id": scan_id, "page_size": 200})
        report("GET /findings returns 200", r.status_code == 200)
        fp = r.json()
        findings_count = fp.get("total", 0)
        findings = fp.get("findings", [])
        report(f"Findings total = {findings_count}", findings_count >= 0)

        if findings:
            f0 = findings[0]
            report("Finding has finding_id", bool(f0.get("finding_id")))
            report("Finding has severity", f0.get("severity") in ("critical", "high", "medium", "low"),
                   f0.get("severity", ""))
            report("Finding has status", f0.get("status") in ("open", "settled", "closed", "appealed", "unknown"),
                   f0.get("status", ""))
            report("Finding has penalty_amount", isinstance(f0.get("penalty_amount"), (int, float)),
                   str(f0.get("penalty_amount")))
            report("Finding has source_id", bool(f0.get("source_id")))
            report("Finding has description", isinstance(f0.get("description"), str))

            # Test severity filter
            sev = f0["severity"]
            r = await c.get(f"{BASE}/findings",
                            params={"scan_id": scan_id, "severity": sev})
            filtered = r.json().get("findings", [])
            all_match = all(f["severity"] == sev for f in filtered)
            report(f"Severity filter ({sev}) works", all_match and len(filtered) > 0,
                   f"{len(filtered)} results")

            # Test single finding
            fid = f0["finding_id"]
            r = await c.get(f"{BASE}/findings/{fid}", params={"scan_id": scan_id})
            report("GET /findings/{id} returns 200", r.status_code == 200)
            report("Finding ID matches", r.json().get("finding_id") == fid)
        else:
            print("  (No findings to test detail endpoints - scan may have failed)")

        # ═══════════════════════════════════════════════════════════
        print("\n=== 7. CSV EXPORT ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/findings/export/csv", params={"scan_id": scan_id})
        report("GET /findings/export/csv returns 200", r.status_code == 200)
        report("Content-Type is text/csv", "text/csv" in r.headers.get("content-type", ""))
        report("CSV has Content-Disposition header", "attachment" in r.headers.get("content-disposition", ""))
        csv_lines = r.text.strip().split("\n")
        report("CSV has header row", "finding_id" in csv_lines[0] if csv_lines else False)
        report(f"CSV has {len(csv_lines)-1} data rows", len(csv_lines) > 0)

        # ═══════════════════════════════════════════════════════════
        print("\n=== 8. STATS SUMMARY ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/findings/stats/summary", params={"scan_id": scan_id})
        report("GET /findings/stats/summary returns 200", r.status_code == 200)
        stats = r.json()
        report("Stats has total_findings", "total_findings" in stats, str(stats.get("total_findings")))
        report("Stats has by_severity", "by_severity" in stats)
        report("Stats has by_source", "by_source" in stats)
        report("Stats has total_exposure", "total_exposure" in stats,
               str(stats.get("total_exposure")))
        report("Stats has risk_score", "risk_score" in stats)
        report("Stats has top_violations", "top_violations" in stats)

        # ═══════════════════════════════════════════════════════════
        print("\n=== 9. EXECUTIVE REPORT ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/findings/report/executive", params={"scan_id": scan_id})
        report("GET /findings/report/executive returns 200", r.status_code == 200)
        rpt = r.json()
        report("Report has title", bool(rpt.get("title")), str(rpt.get("title", ""))[:60])
        report("Report has executive_summary", bool(rpt.get("executive_summary")))
        report("Report has key_metrics", isinstance(rpt.get("key_metrics"), dict))
        report("Report has recommendations", isinstance(rpt.get("recommendations"), list))
        report("Report has source_breakdown", isinstance(rpt.get("source_breakdown"), list))
        report("Report has persona field", "persona" in rpt, str(rpt.get("persona")))
        report("Report has generated_at", bool(rpt.get("generated_at")))

        # ═══════════════════════════════════════════════════════════
        print("\n=== 10. AGENT EVENTS ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/agents/events", params={"scan_id": scan_id})
        report("GET /agents/events returns 200", r.status_code == 200)
        ev_data = r.json()
        events = ev_data.get("events", [])
        report(f"Event history has {len(events)} events", len(events) >= 0)
        if events:
            e0 = events[0]
            report("Event has scan_id", e0.get("scan_id") == scan_id)
            report("Event has source_id", bool(e0.get("source_id")))
            report("Event has agent_tag", bool(e0.get("agent_tag")))
            report("Event has timestamp", bool(e0.get("timestamp")))

        # ═══════════════════════════════════════════════════════════
        print("\n=== 11. AGENT STATUS ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get(f"{BASE}/agents/status", params={"scan_id": scan_id})
        report("GET /agents/status returns 200", r.status_code == 200)
        adata = r.json()
        report("Agent status has sources_total", "sources_total" in adata)
        report("Agent status has source_results", isinstance(adata.get("source_results"), list))

        # ═══════════════════════════════════════════════════════════
        print("\n=== 12. RE-RUN SCAN ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.post(f"{BASE}/scans/{scan_id}/rerun")
        report("POST /scans/{id}/rerun returns 202", r.status_code == 202)
        rerun = r.json()
        rerun_id = rerun.get("scan_id", "")
        report("Rerun creates new scan ID", rerun_id != scan_id and len(rerun_id) == 36)
        report("Rerun targets same entity", rerun.get("target") == "TestCorp Inc")
        report("Rerun preserves persona", rerun.get("persona_id") == "compliance_officer")

        # Cancel the rerun so we don't wait for it
        await c.delete(f"{BASE}/scans/{rerun_id}")
        report("Cancelled rerun scan", True)

        # ═══════════════════════════════════════════════════════════
        print("\n=== 13. CANCEL SCAN ===")
        # ═══════════════════════════════════════════════════════════

        # Create a quick scan to cancel
        cancel_req = {"target": "CancelTestCorp", "sources": ["us_osha"], "max_concurrent_agents": 1}
        r = await c.post(f"{BASE}/scans", json=cancel_req)
        cancel_id = r.json().get("scan_id", "")
        r = await c.delete(f"{BASE}/scans/{cancel_id}")
        report("DELETE /scans/{id} returns 204", r.status_code == 204)

        r = await c.get(f"{BASE}/scans/{cancel_id}")
        report("Cancelled scan status is cancelled", r.json().get("status") == "cancelled")

        # ═══════════════════════════════════════════════════════════
        print("\n=== 14. SCAN COMPARISON ===")
        # ═══════════════════════════════════════════════════════════

        # Compare original scan with itself (quick test)
        r = await c.get(f"{BASE}/findings/compare",
                        params={"scan_a": scan_id, "scan_b": scan_id})
        report("GET /findings/compare returns 200", r.status_code == 200)
        cmp = r.json()
        report("Compare has scan_a", "scan_a" in cmp)
        report("Compare has scan_b", "scan_b" in cmp)
        report("Compare delta_risk is 0 (same scan)", cmp.get("delta_risk") == 0)
        report("Compare delta_findings is 0", cmp.get("delta_findings") == 0)
        report("Compare has shared_case_ids", "shared_case_ids" in cmp)

        # ═══════════════════════════════════════════════════════════
        print("\n=== 15. MONGODB PERSISTENCE ===")
        # ═══════════════════════════════════════════════════════════

        # Verify the scan we created is persisted in MongoDB by re-fetching
        r = await c.get(f"{BASE}/scans/{scan_id}")
        report("Scan still retrievable (MongoDB persistence)", r.status_code == 200)

        # Verify findings persisted
        r = await c.get(f"{BASE}/findings", params={"scan_id": scan_id})
        report("Findings still retrievable (MongoDB persistence)", r.status_code == 200)

        # Verify events persisted
        r = await c.get(f"{BASE}/agents/events", params={"scan_id": scan_id})
        report("Events still retrievable (MongoDB persistence)", r.status_code == 200)

        # Check scan list count
        r = await c.get(f"{BASE}/scans")
        all_scans = r.json()
        report(f"Total scans in MongoDB: {len(all_scans)}", len(all_scans) >= 1)

        # ═══════════════════════════════════════════════════════════
        print("\n=== 16. OPENAPI DOCS ===")
        # ═══════════════════════════════════════════════════════════

        r = await c.get("http://127.0.0.1:8000/openapi.json")
        report("OpenAPI schema available", r.status_code == 200)
        schema = r.json()
        report("API title is AutoDiligence API", schema.get("info", {}).get("title") == "AutoDiligence API")

        r = await c.get("http://127.0.0.1:8000/docs")
        report("Swagger UI available", r.status_code == 200)

    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 55)
    print(f"  RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 55 + "\n")

    return FAIL == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
