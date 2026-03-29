"""
Persona definitions — pre-built role-based scan configurations for instant demos.

Each persona represents a real-world user role with pre-configured:
 • Regulatory sources to query
 • Research focus / query template
 • Risk weight preferences
 • Demo-ready sample targets
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class DemoTarget(BaseModel):
    """A pre-built target that shows off the persona's capabilities."""
    name: str
    description: str
    query_override: Optional[str] = None


class Persona(BaseModel):
    """A role-based scan configuration persona."""
    id: str
    label: str
    icon: str
    description: str
    color: str                                  # CSS colour for UI cards
    default_sources: List[str]
    default_query: str
    focus_areas: List[str]
    demo_targets: List[DemoTarget] = Field(default_factory=list)


# ── Persona registry ──────────────────────────────────────────────

PERSONAS: List[Persona] = [
    Persona(
        id="compliance_officer",
        label="Compliance Officer",
        icon="shield-check",
        description="Full regulatory sweep across all federal agencies. Surfaces enforcement actions, consent orders, and penalty history for board-level risk reports.",
        color="#3b82f6",
        default_sources=["us_osha", "us_fda", "us_sec", "us_dol", "us_epa"],
        default_query="Find all enforcement actions, violations, penalties, consent orders, and regulatory warnings",
        focus_areas=["Enforcement Actions", "Consent Orders", "Penalty History", "Regulatory Warnings"],
        demo_targets=[
            DemoTarget(name="Tesla Inc", description="Electric vehicle manufacturer — OSHA, SEC, and EPA exposure"),
            DemoTarget(name="Johnson & Johnson", description="Pharma/consumer goods — FDA warnings & product liability"),
            DemoTarget(name="Amazon.com Inc", description="E-commerce giant — OSHA warehouse safety & DOL wage violations"),
        ],
    ),
    Persona(
        id="m_and_a_analyst",
        label="M&A Analyst",
        icon="bar-chart-2",
        description="Pre-acquisition target screening. Focuses on material liabilities, pending litigation, and financial exposure that could affect deal valuation.",
        color="#8b5cf6",
        default_sources=["us_sec", "us_osha", "us_epa"],
        default_query="Find material enforcement actions, pending litigation, financial penalties, and unresolved regulatory matters that represent acquisition risk",
        focus_areas=["Material Liabilities", "Pending Litigation", "Financial Exposure", "Deal Breakers"],
        demo_targets=[
            DemoTarget(name="Boeing Company", description="Aerospace — SEC disclosures & OSHA safety after 737 MAX"),
            DemoTarget(name="Wells Fargo", description="Banking — SEC enforcement & ongoing regulatory scrutiny"),
            DemoTarget(name="Meta Platforms", description="Tech — SEC securities matters & regulatory actions"),
        ],
    ),
    Persona(
        id="esg_researcher",
        label="ESG Researcher",
        icon="leaf",
        description="Environmental, Social & Governance screening. Highlights EPA violations, workplace safety records, and governance failures for ESG scoring.",
        color="#10b981",
        default_sources=["us_epa", "us_osha", "us_dol"],
        default_query="Find environmental violations, workplace safety incidents, labor violations, and governance failures relevant to ESG assessment",
        focus_areas=["Environmental Violations", "Workplace Safety", "Labor Practices", "Governance Failures"],
        demo_targets=[
            DemoTarget(name="ExxonMobil", description="Oil & gas — EPA environmental enforcement history"),
            DemoTarget(name="Tyson Foods", description="Food processing — OSHA safety & DOL labor practices"),
            DemoTarget(name="Dow Chemical", description="Chemical manufacturing — EPA and OSHA exposure"),
        ],
    ),
    Persona(
        id="legal_counsel",
        label="Legal Counsel",
        icon="scale",
        description="Litigation risk assessment for pending or potential legal matters. Focuses on case status, appeal history, and precedent-setting actions.",
        color="#f59e0b",
        default_sources=["us_sec", "us_fda", "us_osha"],
        default_query="Find all enforcement actions with case status details, appeal history, settlement amounts, and ongoing litigation matters",
        focus_areas=["Active Litigation", "Settlement History", "Appeal Status", "Precedent Cases"],
        demo_targets=[
            DemoTarget(name="Purdue Pharma", description="Opioid litigation — FDA enforcement & SEC matters"),
            DemoTarget(name="Volkswagen", description="Emissions scandal — EPA enforcement & SEC securities fraud"),
            DemoTarget(name="Theranos", description="Healthcare fraud — SEC enforcement & FDA regulatory actions"),
        ],
    ),
    Persona(
        id="investigative_journalist",
        label="Investigative Journalist",
        icon="search",
        description="Deep-dive research mode. Maximizes source coverage and focuses on patterns of repeat violations, escalating penalties, and cover-ups.",
        color="#ef4444",
        default_sources=["us_osha", "us_fda", "us_sec", "us_dol", "us_epa"],
        default_query="Find all violations, enforcement actions, repeat offenses, escalating penalties, whistleblower complaints, and patterns of non-compliance",
        focus_areas=["Repeat Violations", "Escalating Penalties", "Whistleblower Cases", "Cover-up Patterns"],
        demo_targets=[
            DemoTarget(name="3M Company", description="PFAS contamination — EPA, OSHA, and multi-agency exposure"),
            DemoTarget(name="Uber Technologies", description="Gig economy — DOL, OSHA, and SEC regulatory history"),
            DemoTarget(name="Facebook", description="Social media — SEC enforcement & whistleblower revelations"),
        ],
    ),
    Persona(
        id="supply_chain_auditor",
        label="Supply Chain Auditor",
        icon="factory",
        description="Vendor and supplier risk assessment. Screens for OSHA safety violations, EPA compliance issues, and DOL labor practice violations in manufacturing.",
        color="#06b6d4",
        default_sources=["us_osha", "us_epa", "us_dol"],
        default_query="Find workplace safety violations, environmental compliance issues, and labor practice violations related to manufacturing and supply chain operations",
        focus_areas=["Factory Safety", "Environmental Compliance", "Labor Standards", "Supplier Risk"],
        demo_targets=[
            DemoTarget(name="Foxconn", description="Electronics manufacturing — OSHA & DOL labor conditions"),
            DemoTarget(name="Smithfield Foods", description="Meat processing — OSHA safety & EPA environmental"),
            DemoTarget(name="Dollar Tree", description="Retail distribution — OSHA warehouse safety violations"),
        ],
    ),
]

PERSONA_MAP = {p.id: p for p in PERSONAS}


def get_persona(persona_id: str) -> Optional[Persona]:
    """Look up a persona by ID."""
    return PERSONA_MAP.get(persona_id)


def list_personas() -> List[Persona]:
    """Return all available personas."""
    return PERSONAS
