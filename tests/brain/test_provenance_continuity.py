"""ONE BRAIN Evidence Provenance -- synthetic continuity test
(2026-08-17). Real production classes (KnowledgeBase, OpportunityStore,
Bridge 1), real JSONFileStore persistence under tmp_path, genuine
process/object recreation. No live browser/Marketplace navigation.

OBSERVATION → SUBJECT VERIFIED → FINAL URL CAPTURED →
CLAIMANT/ORIGIN RECORDED → FINDING → RESTART →
DUPLICATE ORIGIN OBSERVED → COUNT STILL 1 →
INDEPENDENT ORIGIN OBSERVED → COUNT 2 → BRIDGE 1 → ONE OPPORTUNITY
"""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.opportunity_advance import advance_opportunities_from_findings


def test_provenance_continuity_full_synthetic_trace(tmp_path):
    knowledge_path = tmp_path / "knowledge.json"
    opportunities_path = tmp_path / "opportunities.json"

    # === Finding A: sensor=marketplace, known claimant+origin ==============
    knowledge1 = KnowledgeBase(knowledge_path)
    opportunities1 = OpportunityStore(opportunities_path)

    finding_a = Finding(
        source="marketplace_catalog", category="affiliate", description="Prostadine, real vendor listing",
        evidence="https://vendor-x.example.com/prostadine", claimant="vendorX", subject="Prostadine",
    )
    knowledge1.save_finding(finding_a)

    created = advance_opportunities_from_findings(knowledge1, opportunities1)
    assert created == []  # only 1 independent source -- below the real bar

    # === Finding B: sensor=browser, SAME real-world origin as A =============
    finding_b = Finding(
        source="browser", category="affiliate", description="Prostadine, same vendor statement relayed",
        evidence="https://vendor-x.example.com/prostadine?utm_source=affiliate", claimant="vendorX", subject="Prostadine",
    )
    knowledge1.save_finding(finding_b)

    created = advance_opportunities_from_findings(knowledge1, opportunities1)
    assert created == []  # A and B share claimant+normalized-origin -- still counts as 1
    assert opportunities1.opportunities() == []  # no false Opportunity

    del knowledge1, opportunities1

    # === RESTART: real process/object recreation ============================
    knowledge2 = KnowledgeBase(knowledge_path)
    opportunities2 = OpportunityStore(opportunities_path)

    assert len(knowledge2.findings(subject="Prostadine")) == 2  # both real Findings survived
    assert opportunities2.opportunities() == []  # still correctly no Opportunity

    # === Finding C: sensor=browser, genuinely DIFFERENT claimant+origin =====
    finding_c = Finding(
        source="browser", category="affiliate", description="Prostadine, independent reviewer's own real assessment",
        evidence="https://independent-review.example.com/prostadine", claimant="independent-reviewer", subject="Prostadine",
    )
    knowledge2.save_finding(finding_c)

    created = advance_opportunities_from_findings(knowledge2, opportunities2)

    assert len(created) == 1  # {A,B} (1 source) + C (1 source) = 2 real independent sources
    assert created[0].subject == "Prostadine"
    opportunity_id = created[0].id

    del knowledge2, opportunities2

    # === RESTART again: count and Opportunity both stable ====================
    knowledge3 = KnowledgeBase(knowledge_path)
    opportunities3 = OpportunityStore(opportunities_path)

    assert len(opportunities3.opportunities()) == 1
    assert opportunities3.opportunities()[0].id == opportunity_id

    # a repeated call must not create a duplicate or a second Opportunity
    advance_opportunities_from_findings(knowledge3, opportunities3)
    assert len(opportunities3.opportunities()) == 1
    assert opportunities3.opportunities()[0].id == opportunity_id


# --- Prostadine Golden Trace (2026-08-17, ONE BRAIN Evidence Role Gate) -----
#
# A. Marketplace mixed record (aggregated_report, claimant="")
# B. Vendor official page (direct_assertion, claimant="" -- origin is the
#    vendor's own domain, safe via role even though claimant is unpopulated)
# C. Affiliate article quoting vendor (relay_or_quote, claimant="") --
#    MUST NOT count
# D. Independent reviewer (direct_assertion, claimant="")
# F. ATLAS-derived economics -- a Claim, never a Finding; never enters
#    this count at all (not constructed here -- there is nothing to
#    construct, that is the point).
#
# Expected: independent_source_count == 3 (A, B, D; not C).
# Bridge 1: MIN_INDEPENDENT_SOURCES(=2) is crossed -> exactly one
# Opportunity, never more, regardless of how many relay artifacts exist.


def test_prostadine_golden_trace_role_gate_produces_exactly_one_opportunity(tmp_path):
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    opportunities = OpportunityStore(tmp_path / "opportunities.json")

    finding_a = Finding(
        source="marketplace_catalog", category="affiliate",
        description="Digistore24 Marketplace listing: Prostadine", subject="Prostadine",
        evidence="https://www.digistore24-app.com/marketplace/detail/prostadine",
        claimant="", evidence_role="aggregated_report",
    )
    finding_b = Finding(
        source="browser_research", category="affiliate",
        description="Prostadine official vendor page", subject="Prostadine",
        evidence="https://prostadine-official.example.com/", claimant="", evidence_role="direct_assertion",
    )
    finding_c = Finding(
        source="browser_research", category="affiliate",
        description="Affiliate article: 'According to Prostadine's team, results in 2 weeks'", subject="Prostadine",
        evidence="https://health-review-blog.example.com/prostadine-review",
        claimant="", evidence_role="relay_or_quote",
    )
    finding_d = Finding(
        source="browser_research", category="affiliate",
        description="Independent reviewer's own 30-day assessment of Prostadine", subject="Prostadine",
        evidence="https://independent-review.example.com/prostadine", claimant="", evidence_role="direct_assertion",
    )
    for finding in (finding_a, finding_b, finding_c, finding_d):
        knowledge.save_finding(finding)

    from atlas.brain.evidence_provenance import independent_source_count

    assert independent_source_count(knowledge.findings(subject="Prostadine")) == 3

    created = advance_opportunities_from_findings(knowledge, opportunities)

    assert len(created) == 1
    assert opportunities.opportunities()[0].subject == "Prostadine"
    assert sorted(opportunities.opportunities()[0].evidence_finding_ids) == sorted(
        f.id for f in (finding_a, finding_b, finding_c, finding_d)
    )  # evidence_finding_ids still cites the FULL real evidence trail, including C -- independence is a separate question from citation

    # a relay-only re-run adding more relay noise must never create a
    # second Opportunity or change the independent count.
    finding_e_more_relay = Finding(
        source="knowledge_source_research", category="affiliate",
        description="A second affiliate site syndicating the same vendor claim", subject="Prostadine",
        evidence="https://another-relay.example.com/prostadine", claimant="", evidence_role="relay_or_quote",
    )
    knowledge.save_finding(finding_e_more_relay)
    assert independent_source_count(knowledge.findings(subject="Prostadine")) == 3
    advance_opportunities_from_findings(knowledge, opportunities)
    assert len(opportunities.opportunities()) == 1
