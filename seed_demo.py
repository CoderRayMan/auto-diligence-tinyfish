"""
AutoDiligence Demo Seed Script
================================
Populates MongoDB with rich, realistic demo data for a full-featured video walkthrough.

Covers all 6 personas, 12 companies, 80+ findings, multi-scan history for trend charts.

Run:
    .venv\Scripts\python.exe seed_demo.py
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

# ── Seed data ────────────────────────────────────────────────────────────────

SOURCES = ["us_osha", "us_fda", "us_sec", "us_dol", "us_epa"]

SOURCE_URLS = {
    "us_osha": "https://www.osha.gov/pls/imis/establishment.inspection_detail",
    "us_fda":  "https://www.fda.gov/inspections-compliance-enforcement",
    "us_sec":  "https://www.sec.gov/litigation/litreleases",
    "us_dol":  "https://enforcedata.dol.gov",
    "us_epa":  "https://echo.epa.gov/enforcement-and-compliance",
}

COMPANIES = [
    # (target, persona_id, risk_score, risk_label, sources_used, scan_history_count)
    ("Tesla Inc",           "compliance_officer",      62, "High",     ["us_osha","us_sec","us_epa"],    3),
    ("Johnson & Johnson",   "compliance_officer",      78, "Critical",  ["us_osha","us_fda","us_sec"],    2),
    ("Amazon.com Inc",      "m_and_a_analyst",         55, "High",     ["us_osha","us_dol","us_sec"],    2),
    ("Boeing Company",      "m_and_a_analyst",         85, "Critical", ["us_sec","us_osha","us_epa"],    3),
    ("ExxonMobil",          "esg_researcher",          91, "Critical", ["us_epa","us_osha","us_dol"],    2),
    ("Tyson Foods",         "esg_researcher",          44, "Medium",   ["us_osha","us_dol","us_epa"],    2),
    ("Wells Fargo",         "legal_counsel",           73, "High",     ["us_sec","us_dol"],             3),
    ("3M Company",          "investigative_journalist",88, "Critical", ["us_epa","us_osha","us_sec","us_dol"], 2),
    ("Uber Technologies",   "investigative_journalist",49, "Medium",   ["us_dol","us_osha","us_sec"],   2),
    ("Foxconn",             "supply_chain_auditor",    67, "High",     ["us_osha","us_dol","us_epa"],   2),
    ("Smithfield Foods",    "supply_chain_auditor",    58, "High",     ["us_osha","us_epa","us_dol"],   2),
    ("Apple Inc",           "compliance_officer",       8, "Clean",    ["us_osha","us_sec","us_epa"],   2),
]

# Per-company finding templates
FINDINGS_TEMPLATES = {
    "Tesla Inc": [
        ("us_osha", "high",     "open",     220000,  "Ergonomic hazards and repetitive motion injuries at Fremont assembly plant; 47 recordable incidents in Q3", "OSHA-2024-TES-0441", "Workplace Safety", "California"),
        ("us_osha", "medium",   "settled",   85000,  "Inadequate machine guarding on stamping presses; 3 employee injuries reported", "OSHA-2024-TES-0389", "Machine Guarding", "California"),
        ("us_sec",  "high",     "open",          0,  "SEC investigation into Elon Musk Twitter acquisition disclosures and Tesla board independence", "SEC-2024-TES-0112", "Securities Disclosure", "Federal"),
        ("us_epa",  "medium",   "settled",   45000,  "Air quality permit violations at Nevada Gigafactory; unauthorized particulate emissions", "EPA-2024-TES-0078", "Air Quality", "Nevada"),
        ("us_osha", "low",      "closed",    12000,  "Forklift safety training documentation gaps; corrective action completed", "OSHA-2023-TES-0271", "Forklift Safety", "Texas"),
        ("us_sec",  "medium",   "settled",  1200000, "SEC settlement over undisclosed compensation arrangements with executives", "SEC-2023-TES-0088", "Executive Compensation", "Federal"),
    ],
    "Johnson & Johnson": [
        ("us_fda",  "critical", "open",    2000000,  "Warning letter: inadequate sterility controls at McPherson, KS facility; production shutdown ordered", "FDA-2024-JNJ-0221", "Manufacturing Sterility", "Federal"),
        ("us_fda",  "critical", "open",    5500000,  "Class I recall of talc-based products due to asbestos contamination; 38,000 units affected", "FDA-2024-JNJ-0198", "Product Contamination", "Federal"),
        ("us_sec",  "high",     "open",          0,  "SEC subpoena re: adequacy of talc-cancer risk disclosures to investors 2016-2023", "SEC-2024-JNJ-0067", "Material Disclosure", "Federal"),
        ("us_fda",  "high",     "settled", 8900000,  "Misbranding of DePuy hip implant marketing materials; consent decree entered", "FDA-2023-JNJ-0154", "Medical Device Misbranding", "Federal"),
        ("us_osha", "medium",   "closed",    95000,  "Chemical exposure incidents at pharmaceutical manufacturing site; HAZMAT protocol gaps", "OSHA-2023-JNJ-0312", "Chemical Exposure", "New Jersey"),
        ("us_fda",  "high",     "appealed", 3400000,  "483 observations: 12 critical deviations at Puerto Rico manufacturing facility", "FDA-2024-JNJ-0177", "GMP Violations", "Puerto Rico"),
        ("us_dol",  "low",      "settled",    25000,  "FMLA violations — improper denial of leave to 14 employees", "DOL-2023-JNJ-0088", "Labor Compliance", "New Jersey"),
    ],
    "Amazon.com Inc": [
        ("us_osha", "critical", "open",    7800000,  "Citation: systemic ergonomic hazards at 6 fulfillment centers; injury rates 2.4x industry average", "OSHA-2024-AMZ-0512", "Ergonomic Hazards", "Federal"),
        ("us_osha", "high",     "open",     680000,  "Fatal forklift accident at DFW fulfillment center; inadequate pedestrian separation", "OSHA-2024-AMZ-0498", "Fatal Accident", "Texas"),
        ("us_dol",  "high",     "settled",  450000,  "DOL Wage & Hour: off-the-clock security screening time constitutes compensable work", "DOL-2024-AMZ-0156", "Wage Theft", "Federal"),
        ("us_osha", "medium",   "open",     180000,  "Heat illness prevention violations at Central California warehouse; no cooling areas", "OSHA-2024-AMZ-0443", "Heat Safety", "California"),
        ("us_sec",  "medium",   "settled",  1900000,  "SEC enforcement: insider trading by logistics executive using warehouse data", "SEC-2023-AMZ-0091", "Insider Trading", "Federal"),
        ("us_dol",  "medium",   "closed",    88000,  "FMLA interference — retaliation against employees for taking medical leave", "DOL-2023-AMZ-0201", "FMLA Retaliation", "Washington"),
    ],
    "Boeing Company": [
        ("us_sec",  "critical", "open",   22000000, "SEC fraud charges: misleading investors about 737 MAX safety fixes post-fatal crashes", "SEC-2024-BA-0044", "Securities Fraud", "Federal"),
        ("us_osha", "critical", "open",    4100000, "Willful citations: systemic quality control failures; falsified inspection records at Renton facility", "OSHA-2024-BA-0387", "Quality Falsification", "Washington"),
        ("us_osha", "high",     "open",     990000, "Door plug assembly process violations; inadequate torque verification procedures", "OSHA-2024-BA-0412", "Manufacturing Safety", "Washington"),
        ("us_epa",  "medium",   "settled",  125000, "Hazardous waste storage violations at Spirit AeroSystems supplier site", "EPA-2023-BA-0066", "Hazardous Waste", "Kansas"),
        ("us_sec",  "high",     "settled", 2500000, "Deferred prosecution agreement: misleading FAA and investors on MAX certification timeline", "SEC-2021-BA-0011", "DPA Violation", "Federal"),
        ("us_osha", "high",     "open",     560000, "Inadequate whistleblower protection; 6 employees retaliated against for safety concerns", "OSHA-2024-BA-0399", "Retaliation", "Washington"),
        ("us_osha", "medium",   "closed",   240000, "Lockout/tagout violations during 787 fuselage assembly; 2 near-miss incidents", "OSHA-2023-BA-0291", "LOTO Violations", "South Carolina"),
    ],
    "ExxonMobil": [
        ("us_epa",  "critical", "open",  14500000, "Clean Water Act violations: Baytown TX refinery discharged 2.1M gallons of polluted water into Houston Ship Channel", "EPA-2024-XOM-0234", "Water Pollution", "Texas"),
        ("us_epa",  "critical", "settled",9800000, "Clean Air Act: methane emissions 400% above permit limits at Permian Basin operations 2019-2023", "EPA-2023-XOM-0187", "Methane Emissions", "Texas/New Mexico"),
        ("us_osha", "high",     "open",    750000, "Process safety management deficiencies at Baton Rouge chemical plant; near-explosion event", "OSHA-2024-XOM-0341", "Process Safety", "Louisiana"),
        ("us_epa",  "high",     "open",   3200000, "RCRA violations: improper disposal of hazardous drilling fluids at 14 sites", "EPA-2024-XOM-0219", "Hazardous Waste", "Federal"),
        ("us_sec",  "high",     "settled", 4100000, "SEC settlement: misleading reserve estimates and climate risk disclosures to shareholders", "SEC-2024-XOM-0078", "Climate Disclosure Fraud", "Federal"),
        ("us_dol",  "medium",   "settled",  320000, "MSHA violations at Wyoming shale operations; inadequate emergency evacuation procedures", "DOL-2023-XOM-0112", "Mine Safety", "Wyoming"),
        ("us_epa",  "medium",   "open",   1800000, "Superfund liability: ExxonMobil listed as PRP at 3 contaminated groundwater sites", "EPA-2024-XOM-0201", "Superfund", "New Jersey"),
    ],
    "Tyson Foods": [
        ("us_osha", "high",     "open",     890000, "Repeat ergonomic violations at Dakota City NE beef plant; 62 musculoskeletal injuries in 12 months", "OSHA-2024-TSN-0289", "Repetitive Motion", "Nebraska"),
        ("us_dol",  "high",     "settled",  540000, "DOL: child labor violations — 16 minors employed in hazardous poultry processing roles", "DOL-2024-TSN-0044", "Child Labor", "Federal"),
        ("us_epa",  "medium",   "settled",  280000, "Clean Water Act: ammonia discharge into Arkansas River; fish kill event reported", "EPA-2023-TSN-0156", "Water Discharge", "Arkansas"),
        ("us_osha", "medium",   "closed",   145000, "COVID-era workplace safety failures; inadequate PPE and distancing at Waterloo IA facility", "OSHA-2021-TSN-0198", "COVID Safety", "Iowa"),
        ("us_dol",  "low",      "settled",   45000, "Wage & Hour: missed break time compensation for 3,200 line workers", "DOL-2023-TSN-0178", "Wage Compliance", "Arkansas"),
    ],
    "Wells Fargo": [
        ("us_sec",  "critical", "open",   3000000000, "SEC investigation: ongoing review of sales practice fraud aftermath; 3.7M unauthorized accounts", "SEC-2024-WFC-0019", "Consumer Fraud", "Federal"),
        ("us_sec",  "critical", "settled",3700000000, "SEC consent order: unauthorized account creation scheme; largest bank fraud settlement in history", "SEC-2020-WFC-0003", "Banking Fraud", "Federal"),
        ("us_dol",  "high",     "settled",  220000000, "DOL: systematic 401k fee overcharges affecting 2.1M employee retirement accounts", "DOL-2022-WFC-0067", "Retirement Fraud", "Federal"),
        ("us_sec",  "high",     "open",      1800000, "SEC inquiry: auto-loan insurance force-placement practices and related disclosures", "SEC-2024-WFC-0031", "Consumer Protection", "Federal"),
        ("us_osha", "low",      "settled",     18000, "Back-office ergonomic violations; seating and monitor height compliance", "OSHA-2023-WFC-0441", "Ergonomics", "California"),
        ("us_sec",  "high",     "settled",  500000000, "Foreign correspondent banking violations; AML program deficiencies", "SEC-2023-WFC-0022", "AML Compliance", "Federal"),
    ],
    "3M Company": [
        ("us_epa",  "critical", "open",  10300000000, "PFAS contamination: EPA enforcement for PFAS releases affecting 19 public water systems across 6 states", "EPA-2024-MMM-0098", "PFAS Contamination", "Federal"),
        ("us_epa",  "critical", "settled",  450000000, "Superfund: 3M designated PRP for PFAS groundwater contamination at Decatur AL site", "EPA-2022-MMM-0056", "Superfund Liability", "Alabama"),
        ("us_osha", "high",     "open",      1200000, "PFAS worker exposure violations; inadequate respiratory protection and medical monitoring", "OSHA-2024-MMM-0211", "Chemical Exposure", "Minnesota"),
        ("us_sec",  "high",     "open",            0, "SEC investigation: adequacy of PFAS liability disclosures to investors over 10-year period", "SEC-2024-MMM-0044", "Material Disclosure", "Federal"),
        ("us_dol",  "medium",   "settled",    340000, "DOL retaliation case: 4 environmental health employees fired after raising PFAS concerns", "DOL-2023-MMM-0089", "Whistleblower", "Federal"),
        ("us_epa",  "high",     "open",     8900000, "TSCA violations: failure to report PFAS health risk studies as required under Section 8(e)", "EPA-2024-MMM-0112", "Chemical Reporting", "Federal"),
    ],
    "Uber Technologies": [
        ("us_dol",  "high",     "appealed",  1900000, "DOL ruling: 765 Massachusetts drivers misclassified as contractors; unemployment insurance owed", "DOL-2024-UBR-0078", "Worker Misclassification", "Massachusetts"),
        ("us_osha", "medium",   "settled",    280000, "Failure to record driver assault incidents in OSHA 300 log; 47 unreported incidents", "OSHA-2023-UBR-0156", "Recordkeeping", "California"),
        ("us_sec",  "medium",   "settled",   4400000, "SEC settlement: material misstatements about driver safety data in IPO prospectus", "SEC-2022-UBR-0034", "IPO Disclosure", "Federal"),
        ("us_dol",  "medium",   "open",       540000, "DOL investigation: tip-credit violations and minimum wage shortfalls for Uber Eats couriers", "DOL-2024-UBR-0091", "Minimum Wage", "Federal"),
        ("us_osha", "low",      "closed",      35000, "Vehicle safety training documentation violations; incomplete driver onboarding records", "OSHA-2023-UBR-0201", "Training Records", "California"),
    ],
    "Foxconn": [
        ("us_osha", "high",     "open",      780000, "OSHA inspection at Wisconsin facility: 34 recordable injuries, inadequate machine guarding", "OSHA-2024-FOX-0167", "Machine Safety", "Wisconsin"),
        ("us_dol",  "high",     "open",     1200000, "DOL: recruitment fee repayment scheme — migrant workers charged up to $6,500 each", "DOL-2024-FOX-0034", "Forced Labor", "Wisconsin"),
        ("us_epa",  "medium",   "settled",    190000, "EPA: wastewater discharge limits exceeded at Mount Pleasant WI plant; 8 violations", "EPA-2023-FOX-0089", "Water Discharge", "Wisconsin"),
        ("us_osha", "medium",   "open",       340000, "Heat illness violations: no cooling stations in 1.2M sq ft factory; 3 heat-related hospitalizations", "OSHA-2024-FOX-0189", "Heat Safety", "Wisconsin"),
        ("us_dol",  "medium",   "settled",    280000, "Wage & Hour: overtime miscalculation for 1,800 manufacturing workers", "DOL-2023-FOX-0112", "Wage Theft", "Wisconsin"),
    ],
    "Smithfield Foods": [
        ("us_osha", "critical", "open",    2200000, "Willful citation: systemic failure to protect workers from ammonia leaks at Sioux Falls SD plant", "OSHA-2024-SFD-0234", "Ammonia Safety", "South Dakota"),
        ("us_epa",  "high",     "settled",  880000, "Clean Air Act: hog waste lagoon hydrogen sulfide emissions exceeding NAAQS standards", "EPA-2024-SFD-0145", "Air Emissions", "North Carolina"),
        ("us_dol",  "high",     "open",     660000, "DOL H-2A visa program violations: foreign workers paid $3.80/hour below required wage floor", "DOL-2024-SFD-0056", "Guest Worker Violations", "Federal"),
        ("us_osha", "high",     "settled",  490000, "COVID: failure to implement adequate protective measures; 4 worker deaths attributed to cluster", "OSHA-2021-SFD-0198", "COVID Safety", "South Dakota"),
        ("us_epa",  "medium",   "open",     340000, "Clean Water Act: nutrient runoff from land application sites contaminating local waterways", "EPA-2024-SFD-0167", "Nutrient Pollution", "Virginia"),
        ("us_dol",  "medium",   "settled",  145000, "Child labor: minors under 16 operating prohibited slaughter equipment on overnight shifts", "DOL-2023-SFD-0089", "Child Labor", "Mississippi"),
    ],
    "Apple Inc": [
        ("us_osha", "low",      "closed",     8500, "Retail store ergonomic self-audit findings; proactively remediated before citation", "OSHA-2023-APL-0445", "Ergonomics", "California"),
        ("us_sec",  "low",      "settled",   25000, "Minor 10-K amendment: immaterial reclassification of warranty reserve accounting", "SEC-2023-APL-0201", "Accounting Restatement", "Federal"),
    ],
}

# ── MongoDB helpers ───────────────────────────────────────────────────────────

def get_db():
    from pymongo import MongoClient
    from pymongo.server_api import ServerApi
    uri = os.getenv("MONGODB_URI", "")
    client = MongoClient(uri, server_api=ServerApi("1"), serverSelectionTimeoutMS=15000)
    client.admin.command("ping")
    return client, client[os.getenv("MONGODB_DB", "autodiligence")]


def make_scan(target, persona_id, risk_score, risk_label, sources_used,
              created_offset_days=0, scan_id=None):
    now = datetime.now(timezone.utc)
    created = now - timedelta(days=created_offset_days)
    completed = created + timedelta(seconds=45 + (risk_score % 30))
    sid = scan_id or str(uuid.uuid4())
    findings_count = len(FINDINGS_TEMPLATES.get(target, []))
    return {
        "_id": sid,
        "scan_id": sid,
        "status": "completed",
        "target": target,
        "query": "regulatory violations and enforcement actions",
        "persona_id": persona_id,
        "created_at": created.isoformat(),
        "completed_at": completed.isoformat(),
        "sources_total": len(sources_used),
        "sources_completed": len(sources_used),
        "sources_failed": 0,
        "risk_score": risk_score,
        "risk_label": risk_label,
        "findings_count": findings_count,
        "source_results": [
            {
                "source_id": s,
                "status": "completed",
                "records_found": sum(1 for f in FINDINGS_TEMPLATES.get(target, []) if f[0] == s),
                "execution_time_s": round(8.5 + (hash(target + s) % 15), 1),
                "error": None,
            }
            for s in sources_used
        ],
    }


def make_finding(target, scan_id, source_id, severity, status, penalty,
                 description, case_id, violation_type, jurisdiction, decision_date):
    return {
        "_id": str(uuid.uuid4()),
        "finding_id": str(uuid.uuid4()),
        "scan_id": scan_id,
        "source_id": source_id,
        "case_id": case_id,
        "case_type": "enforcement_action",
        "entity_name": target,
        "violation_type": violation_type,
        "decision_date": decision_date,
        "penalty_amount": float(penalty),
        "severity": severity,
        "status": status,
        "description": description,
        "source_url": SOURCE_URLS.get(source_id, ""),
        "jurisdiction": jurisdiction,
    }


async def seed():
    print("[INIT] AutoDiligence Demo Seed")
    print("=" * 52)

    client, db = get_db()
    print("[OK] Connected to MongoDB")

    # Clear existing data
    db.scans.drop()
    db.findings.drop()
    db.agent_events.drop()
    print("[OK] Cleared existing collections")

    # Create indexes
    db.scans.create_index("created_at")
    db.findings.create_index("scan_id")
    db.findings.create_index("severity")
    db.agent_events.create_index("scan_id")
    print("[OK] Indexes created")

    total_scans = 0
    total_findings = 0
    scan_id_map = {}  # target -> latest scan_id (for trend tracking)

    for (target, persona_id, risk_score, risk_label, sources_used, history_count) in COMPANIES:
        print(f"\n  [TARGET] {target} ({persona_id})")
        templates = FINDINGS_TEMPLATES.get(target, [])

        # Create historical scans first (older ones with slightly different scores)
        historical_ids = []
        for h in range(history_count - 1, 0, -1):
            offset_days = h * 14  # 2-week intervals
            hist_score = max(0, min(100, risk_score + (h * 7) - 3))
            hist_risk_label = (
                "Critical" if hist_score >= 80 else
                "High"     if hist_score >= 50 else
                "Medium"   if hist_score >= 25 else
                "Low"      if hist_score >= 10 else "Clean"
            )
            hist_scan = make_scan(
                target, persona_id, hist_score, hist_risk_label, sources_used,
                created_offset_days=offset_days
            )
            db.scans.insert_one(hist_scan)
            historical_ids.append(hist_scan["_id"])
            total_scans += 1

            # Add a subset of findings to historical scans
            hist_findings = []
            for i, (src, sev, st, pen, desc, cid, vtype, jur) in enumerate(templates):
                if i >= max(1, len(templates) // 2):
                    break
                date_offset = offset_days + 30
                decision_date = (datetime.now(timezone.utc) - timedelta(days=date_offset)).strftime("%Y-%m-%d")
                hist_findings.append(make_finding(
                    target, hist_scan["_id"], src, sev, st, pen, desc, cid + f"-H{h}", vtype, jur, decision_date
                ))
            if hist_findings:
                db.findings.insert_many(hist_findings)
                total_findings += len(hist_findings)
            print(f"    + History scan {h}: score={hist_score} ({hist_risk_label}), {len(hist_findings)} findings")

        # Create the LATEST (current) scan
        latest_scan = make_scan(
            target, persona_id, risk_score, risk_label, sources_used,
            created_offset_days=0
        )
        db.scans.insert_one(latest_scan)
        scan_id_map[target] = latest_scan["_id"]
        total_scans += 1

        # Add full findings to latest scan
        latest_findings = []
        for (src, sev, st, pen, desc, cid, vtype, jur) in templates:
            days_ago = abs(hash(cid)) % 730  # random date within 2 years
            decision_date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            latest_findings.append(make_finding(
                target, latest_scan["_id"], src, sev, st, pen, desc, cid, vtype, jur, decision_date
            ))
        if latest_findings:
            db.findings.insert_many(latest_findings)
            total_findings += len(latest_findings)

        # Add agent events
        events = []
        for src in sources_used:
            src_findings = [f for f in latest_findings if f["source_id"] == src]
            base_time = datetime.fromisoformat(latest_scan["created_at"])
            events.append({
                "_id": str(uuid.uuid4()),
                "scan_id": latest_scan["_id"],
                "source_id": src,
                "agent_tag": "RUNNING",
                "message": f"Agent starting for source: {src}",
                "timestamp": base_time.isoformat(),
                "streaming_url": None,
            })
            events.append({
                "_id": str(uuid.uuid4()),
                "scan_id": latest_scan["_id"],
                "source_id": src,
                "agent_tag": "COMPLETED",
                "message": f"Found {len(src_findings)} records",
                "timestamp": (base_time + timedelta(seconds=10 + (hash(src) % 20))).isoformat(),
                "streaming_url": None,
            })
        if events:
            db.agent_events.insert_many(events)

        print(f"    [OK] Latest scan: score={risk_score} ({risk_label}), {len(latest_findings)} findings")

    print(f"\n{'='*52}")
    print(f"[DONE] Seed complete!")
    print(f"   {total_scans:>3} scans   (across {len(COMPANIES)} companies)")
    print(f"   {total_findings:>3} findings (with realistic penalties & dates)")
    print(f"\n[HIGHLIGHTS]")
    print(f"   • Wells Fargo: ${3_000_000_000 + 3_700_000_000:,.0f} total exposure (banking fraud)")
    print(f"   • 3M Company: $10.3B PFAS contamination enforcement")
    print(f"   • Boeing: Critical SEC fraud + OSHA willful citations")
    print(f"   • Apple: Clean record — risk score 8/100")
    print(f"\n[NEXT] Start the server and open http://localhost:5174")
    print(f"    .venv\\Scripts\\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
