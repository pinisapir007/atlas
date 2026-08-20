"""ONE BRAIN Synthetic Continuity Test (2026-08-17, ONE BRAIN Root
Implementation) -- the real, end-to-end replacement for the lifecycle
test removed from test_cognitive_continuity.py, built entirely on the
approved architecture (no Marketplace-specific Opportunity writer
anywhere in this chain):

OBSERVE -> VERIFY SUBJECT -> FINDING -> INVESTIGATION -> RESEARCH ->
VERIFY RETURN -> BRIDGE 1 -> OPPORTUNITY -> TASK -> EXECUTE ->
VERIFY OUTCOME -> DONE -> RESTART -> STATE RECOVERED.

No live browser. No Campaign execution. Every store is real,
JSONFileStore-backed, on real disk under tmp_path -- process/object
recreation is genuine, not simulated.
"""

from atlas.brain.entity_resolution import resolve_canonical_subject
from atlas.brain.investigation_advance import advance_investigations
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_cognitive_bridge import claim_derived_economics, ground_marketplace_product
from atlas.brain.marketplace_extraction import MarketplaceProductRecord, dedupe_key
from atlas.brain.models import Claim, Investigation, Task
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.opportunity_advance import advance_opportunities_from_findings
from atlas.integrations.base import PageObservation

CATEGORY = "affiliate"


def _record(**overrides) -> MarketplaceProductRecord:
    defaults = dict(
        product_name="Prostadine", category="Supplements - health", price=209.18, commission_pct=65.0,
        vendor="VendorB", cart_conversion_pct=5.0, secondary_rate_pct=13.98, observed_date_raw="5/25/23",
        net_earnings_per_sale=142.73, earnings_per_cart_visitor=None,
        source_url="https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all",
        observed_at="2026-08-17T10:00:00+00:00", field_notes="",
    )
    defaults.update(overrides)
    return MarketplaceProductRecord(**defaults)


class _FakePlugin:
    name = "fake"

    def __init__(self, observation):
        self._observation = observation

    def can_handle(self, source_ref):
        return True

    def observe(self, source_ref, extract=None):
        return self._observation


class _FakeAIProvider:
    def __init__(self, subject_match="same", role="unknown"):
        self._subject_match = subject_match
        self._role = role

    def complete_structured(self, prompt, fields):
        if "verdict" in fields:
            return {"verdict": self._subject_match, "reason": "fake"}
        if "role" in fields:
            return {"role": self._role, "reason": "fake role judgment"}
        return {"relevant": "yes", "reason": "fake"}


def test_full_one_brain_closed_loop(tmp_path, monkeypatch):
    catalog_path = tmp_path / "marketplace_catalog.json"
    knowledge_path = tmp_path / "knowledge.json"
    opportunities_path = tmp_path / "opportunities.json"
    investigations_path = tmp_path / "investigations.json"
    brain_path = tmp_path / "brain.json"

    # === OBSERVE ============================================================
    catalog = MarketplaceCatalogStore(path=catalog_path)
    record = _record()
    new_keys, canonical_by_raw = catalog.save_records_with_identity([record])
    canonical_id = canonical_by_raw[dedupe_key(record)]
    assert new_keys == [canonical_id]

    # === FINDING (OBSERVED + DERIVED, real subject-attribution already
    #     trusted since this is the raw catalog observation itself) =========
    knowledge = KnowledgeBase(path=knowledge_path)
    observed_claim = ground_marketplace_product(record, canonical_id, knowledge)
    assert observed_claim is not None
    derived_claim = claim_derived_economics(record, canonical_id, observed_claim.evidence_finding_ids, knowledge)
    assert derived_claim is not None
    # only ONE real Finding exists so far -- below Bridge 1's MIN_INDEPENDENT_SOURCES bar
    assert len(knowledge.findings(subject=canonical_id)) == 1

    # === INVESTIGATION opened (pre-Opportunity workflow state) =============
    investigations = InvestigationStore(path=investigations_path)
    investigation = Investigation(
        subject_id=canonical_id, category=CATEGORY, status="waiting_for_evidence",
        reason_opened="high net_earnings_per_sale relative to price -- worth independent confirmation",
        supporting_finding_ids=list(observed_claim.evidence_finding_ids),
        missing_evidence="an independent second source confirming this is a real, viable candidate",
    )
    investigations.save_investigation(investigation)

    # === RESEARCH (independent evidence collection) + VERIFY RETURN ========
    import atlas.brain.knowledge_source_research as ksr

    real_observation = PageObservation(
        url="https://independent-review.example.com/prostadine",
        title="Prostadine", text_content="A real, independent review of Prostadine " * 20,
    )
    monkeypatch.setattr(ksr, "select_plugin", lambda source_ref: _FakePlugin(real_observation))

    changed = advance_investigations(
        investigations, knowledge,
        source_refs={investigation.id: "https://independent-review.example.com/prostadine"},
        ai_provider=_FakeAIProvider(subject_match="same"),
    )
    assert len(changed) == 1
    investigation = investigations.get_investigation(investigation.id)
    assert investigation.status == "ready_for_evaluation"
    assert len(investigation.supporting_finding_ids) == 2  # the original + the newly-verified one
    assert len(knowledge.findings(subject=canonical_id)) == 2  # now at the real MIN_INDEPENDENT_SOURCES bar

    # === ONE BRAIN Evidence Role Gate (2026-08-17) =========================
    # collect_evidence_from_source() -- the real, generic, sense-agnostic
    # writer advance_investigations() just called -- honestly never
    # guesses evidence_role for open web content (no structural signal
    # distinguishes a direct source from a relay/quote; see the Evidence
    # Role Gate audit). This second Finding genuinely represents an
    # independent reviewer's own first-hand assessment (the Prostadine
    # Golden Trace's "D" role, direct_assertion) -- populating real
    # evidence_role for this class of writer is a deliberately separate,
    # not-yet-built increment (named in that audit's own Live Readiness
    # answer), so this test stands in for that known, still-open next
    # step explicitly rather than silently assuming it already exists.
    second_finding = [f for f in knowledge.findings(subject=canonical_id) if f.id != observed_claim.evidence_finding_ids[0]][0]
    second_finding.evidence_role = "direct_assertion"
    knowledge.save_finding(second_finding)

    # === BRIDGE 1 -> OPPORTUNITY (the ONLY creator) =========================
    opportunities = OpportunityStore(path=opportunities_path)
    created = advance_opportunities_from_findings(knowledge, opportunities)
    assert len(created) == 1
    opportunity = created[0]
    assert opportunity.subject == canonical_id
    assert opportunity.category == CATEGORY
    opportunity_id = opportunity.id

    # === ALIAS APPEARS LATER -> SAME OPPORTUNITY REUSED (pinned anchor) ====
    alias_subject = "prostadine::vendora"  # a different sense's own local identity for the SAME real product
    link_finding = knowledge.findings(subject=canonical_id)[0]
    knowledge.save_claim(Claim(
        subject_id=canonical_id, predicate="possibly_same_as", object_id=alias_subject,
        evidence_finding_ids=[link_finding.id],
    ))
    assert resolve_canonical_subject(alias_subject, CATEGORY, knowledge, opportunities) == canonical_id

    # a real Finding under the NEW alias must converge onto the SAME, already-pinned Opportunity
    from atlas.brain.models import Finding
    knowledge.save_finding(Finding(
        source="research", category=CATEGORY, description="a third, real corroborating source",
        evidence="https://another-independent-source.example.com/prostadine", subject=alias_subject,
    ))
    advance_opportunities_from_findings(knowledge, opportunities)
    assert len(opportunities.opportunities()) == 1  # still exactly one -- no duplicate
    assert opportunities.opportunities()[0].id == opportunity_id

    # === TASK with expected outcome -> EXECUTE -> VERIFY OUTCOME -> DONE ===
    task = Task(
        goal_id="goal-marketplace-1", description="Record real affiliate revenue for Prostadine",
        category="affiliate", reversible=True, expected_outcome="real revenue recorded in the Ledger",
    )
    # actuator technical success alone must NOT complete the task
    completed = task.try_complete("actuator reported dispatch success")
    assert completed is False
    assert task.status == "blocked"

    # independent verification arrives
    task.verification_status = "verified_success"
    task.verification_evidence_id = link_finding.id
    completed = task.try_complete("independently verified real outcome")
    assert completed is True
    assert task.status == "done"

    from atlas.brain.memory import BrainMemory
    memory = BrainMemory(path=brain_path)
    memory.save_task(task)

    # === RESTART: every object discarded, only real files remain ===========
    del catalog, knowledge, investigations, opportunities, memory, investigation, task

    catalog2 = MarketplaceCatalogStore(path=catalog_path)
    knowledge2 = KnowledgeBase(path=knowledge_path)
    investigations2 = InvestigationStore(path=investigations_path)
    opportunities2 = OpportunityStore(path=opportunities_path)
    memory2 = BrainMemory(path=brain_path)

    # === STATE RECOVERED ====================================================
    assert catalog2.resolve_canonical(_record()) == canonical_id
    reloaded_investigation = investigations2.by_subject(CATEGORY, canonical_id)
    assert reloaded_investigation.status == "ready_for_evaluation"
    reloaded_opportunities = opportunities2.opportunities()
    assert len(reloaded_opportunities) == 1
    assert reloaded_opportunities[0].id == opportunity_id
    reloaded_task = memory2.tasks()[0]
    assert reloaded_task.status == "done"
    assert reloaded_task.verification_status == "verified_success"
    assert reloaded_task.verification_evidence_id == link_finding.id


# --- Production-Continuity: Evidence Role Classification, real classifier ---
# (2026-08-17, ONE BRAIN Web Evidence Role Classification)
#
# Marketplace aggregated report -> Investigation -> browser returns a
# real relay article (subject verified, role=relay_or_quote classified
# by the real classify_evidence_role(), via a fake AIProvider -- no live
# browser) -> independence still below MIN_INDEPENDENT_SOURCES ->
# browser returns a real independent reviewer (role=direct_assertion) ->
# independence reaches the bar -> Bridge 1 creates exactly one
# Opportunity -> restart -> same Opportunity, same count, no duplicate
# Investigation.


def test_production_continuity_evidence_role_classification_real_classifier(tmp_path, monkeypatch):
    from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES
    from atlas.brain.evidence_provenance import independent_source_count

    catalog_path = tmp_path / "marketplace_catalog.json"
    knowledge_path = tmp_path / "knowledge.json"
    opportunities_path = tmp_path / "opportunities.json"
    investigations_path = tmp_path / "investigations.json"

    # === Marketplace aggregated report ======================================
    catalog = MarketplaceCatalogStore(path=catalog_path)
    record = _record()
    new_keys, canonical_by_raw = catalog.save_records_with_identity([record])
    canonical_id = canonical_by_raw[dedupe_key(record)]

    knowledge = KnowledgeBase(path=knowledge_path)
    observed_claim = ground_marketplace_product(record, canonical_id, knowledge)
    assert knowledge.findings(subject=canonical_id)[0].evidence_role == "aggregated_report"

    # === Investigation opened ================================================
    investigations = InvestigationStore(path=investigations_path)
    investigation = Investigation(
        subject_id=canonical_id, category=CATEGORY, status="waiting_for_evidence",
        reason_opened="high net_earnings_per_sale relative to price -- worth independent confirmation",
        supporting_finding_ids=list(observed_claim.evidence_finding_ids),
        missing_evidence="an independent second source confirming this is a real, viable candidate",
    )
    investigations.save_investigation(investigation)

    opportunities = OpportunityStore(path=opportunities_path)
    import atlas.brain.knowledge_source_research as ksr

    # === Browser returns a real relay article (role=relay_or_quote) =========
    relay_observation = PageObservation(
        url="https://health-review-blog.example.com/prostadine-review",
        title="Prostadine Review", text_content="According to Prostadine's team, users see results in 2 weeks. " * 5,
    )
    monkeypatch.setattr(ksr, "select_plugin", lambda source_ref: _FakePlugin(relay_observation))

    changed = advance_investigations(
        investigations, knowledge,
        source_refs={investigation.id: "https://health-review-blog.example.com/prostadine-review"},
        ai_provider=_FakeAIProvider(subject_match="same", role="relay_or_quote"),
    )
    assert len(changed) == 1
    investigation = investigations.get_investigation(investigation.id)
    assert investigation.status == "ready_for_evaluation"
    relay_finding = [f for f in knowledge.findings(subject=canonical_id) if f.evidence_role == "relay_or_quote"][0]
    assert relay_finding.claimant == ""

    # independence still below the real bar -- the relay contributes zero
    assert independent_source_count(knowledge.findings(subject=canonical_id)) == 1
    created = advance_opportunities_from_findings(knowledge, opportunities)
    assert created == []
    assert opportunities.opportunities() == []

    # === A second, real, approved source_ref becomes available (the same
    #     real, named, still-open limitation investigation_advance.py's
    #     own docstring already states: this bridge never invents a
    #     source_ref selector -- a real future mechanism, or a human,
    #     supplies this one, the same as it supplied the first) ==========
    investigation.status = "waiting_for_evidence"
    investigations.save_investigation(investigation)

    # === Browser returns a real independent reviewer (role=direct_assertion) ===
    reviewer_observation = PageObservation(
        url="https://independent-review.example.com/prostadine",
        title="My Prostadine Review", text_content="I personally tested Prostadine for 30 days myself. " * 5,
    )
    monkeypatch.setattr(ksr, "select_plugin", lambda source_ref: _FakePlugin(reviewer_observation))

    changed = advance_investigations(
        investigations, knowledge,
        source_refs={investigation.id: "https://independent-review.example.com/prostadine"},
        ai_provider=_FakeAIProvider(subject_match="same", role="direct_assertion"),
    )
    assert len(changed) == 1

    # === Independence now reaches the real bar -> Bridge 1 fires ===========
    assert independent_source_count(knowledge.findings(subject=canonical_id)) == MIN_INDEPENDENT_SOURCES == 2
    created = advance_opportunities_from_findings(knowledge, opportunities)
    assert len(created) == 1
    opportunity_id = created[0].id
    assert created[0].subject == canonical_id

    # exactly ONE Investigation exists throughout -- never duplicated
    assert len(investigations.investigations()) == 1

    # === RESTART: every object discarded, only real files remain ===========
    del catalog, knowledge, investigations, opportunities, investigation

    knowledge2 = KnowledgeBase(path=knowledge_path)
    opportunities2 = OpportunityStore(path=opportunities_path)
    investigations2 = InvestigationStore(path=investigations_path)

    assert independent_source_count(knowledge2.findings(subject=canonical_id)) == 2
    assert len(opportunities2.opportunities()) == 1
    assert opportunities2.opportunities()[0].id == opportunity_id
    assert len(investigations2.investigations()) == 1  # still no duplicate

    # a repeated call must not create a duplicate Opportunity
    advance_opportunities_from_findings(knowledge2, opportunities2)
    assert len(opportunities2.opportunities()) == 1
    assert opportunities2.opportunities()[0].id == opportunity_id
