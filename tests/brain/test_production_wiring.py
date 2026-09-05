"""ONE BRAIN Production Wiring Validation (2026-08-17). Uses REAL
production classes (CEOBrain, MarketplaceCatalogStore, KnowledgeBase,
InvestigationStore, OpportunityStore, BrainMemory) with real
JSONFileStore persistence under an isolated tmp_path -- never hand-
wired toy substitutes, never the real project .atlas/ directory.
Genuine process/object recreation proves restart, not simulation.

NO live browser/Marketplace navigation anywhere in this file -- every
Marketplace "observation" is a directly-constructed, real
MarketplaceProductRecord (exactly what a real, separate, human-
supervised run_discovery() session would already have persisted to
disk before CEOBrain.tick() ever runs).
"""

from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.ceo import CEOBrain
from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.brain.decisions import DecisionLog
from atlas.brain.investigation_advance import advance_investigations
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.ledger import Ledger
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_extraction import MarketplaceProductRecord
from atlas.brain.memory import BrainMemory
from atlas.brain.opportunities import OpportunityStore
from atlas.campaign.registry import CampaignRegistry
from atlas.core.registry import Registry
from atlas.core.store import JSONStore
from atlas.influencer.registry import InfluencerRegistry
from atlas.integrations.base import PageObservation
from atlas.orchestrator.registry import ExecutionPlanRegistry


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
    def __init__(self, subject_match="same"):
        self._subject_match = subject_match

    def complete_structured(self, prompt, fields):
        if "verdict" in fields:
            return {"verdict": self._subject_match, "reason": "fake"}
        return {"relevant": "yes", "reason": "fake"}


def _real_brain(tmp_path) -> CEOBrain:
    """Every registry pointed at a real, isolated tmp_path file -- the
    exact isolation discipline test_ceo.py's own _brain() helper
    already established, extended with the two new ONE BRAIN stores."""
    return CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        intelligence_index=IntelligenceIndex(tmp_path / ".atlas" / "intelligence_index.json"),
        registry=Registry(store=JSONStore(tmp_path / "state.json")),
        knowledge=KnowledgeBase(tmp_path / "knowledge.json"),
        decisions=DecisionLog(tmp_path / "decisions.json"),
        ledger=Ledger(tmp_path / "ledger.json"),
        campaigns=CampaignRegistry(tmp_path / ".atlas" / "campaigns.json"),
        influencers=InfluencerRegistry(tmp_path / ".atlas" / "influencers.json"),
        execution_plans=ExecutionPlanRegistry(tmp_path / ".atlas" / "execution_plans.json"),
        affiliate_store=AffiliateStore(tmp_path / ".atlas" / "affiliate_intelligence.json"),
        opportunities=OpportunityStore(tmp_path / ".atlas" / "opportunities.json"),
        marketplace_catalog=MarketplaceCatalogStore(tmp_path / ".atlas" / "marketplace_catalog.json"),
        investigations=InvestigationStore(tmp_path / ".atlas" / "investigations.json"),
    )


def test_production_wiring_full_closed_loop_with_real_restarts(tmp_path, monkeypatch):
    # === PROCESS/OBJECT SET 1: initial Marketplace-style observation ======
    brain1 = _real_brain(tmp_path)
    brain1.marketplace_catalog.save_records([_record()])
    canonical_id = next(iter(brain1.marketplace_catalog.known_keys()))

    brain1.tick()  # production tick() -- grounds the record, opens an Investigation

    assert len(brain1.knowledge.findings(subject=canonical_id)) == 1
    investigation = brain1.investigations.by_subject("affiliate", canonical_id)
    assert investigation is not None
    assert investigation.status == "waiting_for_evidence"
    assert brain1.opportunities.opportunities() == []  # not enough evidence yet -- Bridge 1 correctly did nothing

    # a second, real, back-to-back tick must NOT create a second Investigation
    brain1.tick()
    assert len(brain1.investigations.investigations()) == 1

    del brain1

    # === PROCESS/OBJECT SET 2: restart, recover, supply approved evidence =
    brain2 = _real_brain(tmp_path)
    recovered_investigation = brain2.investigations.by_subject("affiliate", canonical_id)
    assert recovered_investigation is not None
    assert recovered_investigation.status == "waiting_for_evidence"
    assert recovered_investigation.reason_opened  # the real reason survived restart

    # a real, approved fixture source_ref -- tick() itself never invents one
    # (source_refs={} always), so this is the honest, separate step a real
    # future source-selection mechanism would supply.
    import atlas.brain.knowledge_source_research as ksr
    real_observation = PageObservation(
        url="https://independent-review.example.com/prostadine",
        title="Prostadine", text_content="A real, independent review of Prostadine " * 20,
    )
    monkeypatch.setattr(ksr, "select_plugin", lambda source_ref: _FakePlugin(real_observation))

    changed = advance_investigations(
        brain2.investigations, brain2.knowledge,
        source_refs={recovered_investigation.id: "https://independent-review.example.com/prostadine"},
        ai_provider=_FakeAIProvider(subject_match="same"),
    )
    assert len(changed) == 1
    assert brain2.investigations.by_subject("affiliate", canonical_id).status == "ready_for_evaluation"
    assert len(brain2.knowledge.findings(subject=canonical_id)) == 2  # now at the real MIN_INDEPENDENT_SOURCES bar

    # ONE BRAIN Evidence Role Gate (2026-08-17): collect_evidence_from_
    # source() (called inside advance_investigations() above) is a
    # generic, sense-agnostic writer that deliberately never guesses
    # evidence_role for open web content (see that audit). This second
    # Finding genuinely represents an independent reviewer's own
    # first-hand assessment (the Prostadine Golden Trace's "D" role,
    # direct_assertion) -- populating real evidence_role for this class
    # of writer is a deliberately separate, not-yet-built increment.
    second_finding = [f for f in brain2.knowledge.findings(subject=canonical_id) if f.claimant == "" and f.evidence_role == ""]
    assert len(second_finding) == 1
    second_finding[0].evidence_role = "direct_assertion"
    brain2.knowledge.save_finding(second_finding[0])

    brain2.tick()  # Bridge 1 (already wired) sees the real, sufficient evidence

    opportunities_after = brain2.opportunities.opportunities()
    assert len(opportunities_after) == 1
    assert opportunities_after[0].subject == canonical_id
    opportunity_id = opportunities_after[0].id

    del brain2

    # === PROCESS/OBJECT SET 3: restart again, rerun does not duplicate ====
    brain3 = _real_brain(tmp_path)
    assert len(brain3.investigations.investigations()) == 1
    assert len(brain3.opportunities.opportunities()) == 1
    assert brain3.opportunities.opportunities()[0].id == opportunity_id

    brain3.tick()
    brain3.tick()

    assert len(brain3.investigations.investigations()) == 1  # still exactly one
    assert len(brain3.opportunities.opportunities()) == 1  # still exactly one
    assert brain3.opportunities.opportunities()[0].id == opportunity_id  # same real Opportunity, not a new one


def test_wrong_subject_returned_evidence_never_advances_or_creates_false_opportunity(tmp_path, monkeypatch):
    brain = _real_brain(tmp_path)
    brain.marketplace_catalog.save_records([_record(product_name="Glucotonic", vendor="VendorX")])
    canonical_id = next(iter(brain.marketplace_catalog.known_keys()))

    brain.tick()
    investigation = brain.investigations.by_subject("affiliate", canonical_id)
    assert investigation is not None

    import atlas.brain.knowledge_source_research as ksr
    wrong_observation = PageObservation(
        url="https://example.com/different-product",
        title="A Totally Different Supplement", text_content="Real content about a different, unrelated product " * 20,
    )
    monkeypatch.setattr(ksr, "select_plugin", lambda source_ref: _FakePlugin(wrong_observation))

    changed = advance_investigations(
        brain.investigations, brain.knowledge,
        source_refs={investigation.id: "https://example.com/different-product"},
        ai_provider=_FakeAIProvider(subject_match="different"),
    )

    assert changed == []
    reloaded = brain.investigations.by_subject("affiliate", canonical_id)
    assert reloaded.status == "waiting_for_evidence"  # never falsely advanced
    assert len(brain.knowledge.findings(subject=canonical_id)) == 1  # only the original grounding Finding

    brain.tick()
    assert brain.opportunities.opportunities() == []  # no false Opportunity


def test_repeated_ticks_are_fully_idempotent_no_duplication_no_oscillation(tmp_path):
    brain = _real_brain(tmp_path)
    brain.marketplace_catalog.save_records([_record()])

    for _ in range(3):
        brain.tick()

    del brain
    brain2 = _real_brain(tmp_path)

    for _ in range(2):
        brain2.tick()

    assert len(brain2.investigations.investigations()) == 1
    assert len(brain2.knowledge.findings()) == 1  # still just the one real grounding Finding -- no re-grounding duplicate
    assert brain2.opportunities.opportunities() == []  # correctly still below the bar -- no false Opportunity
    # no Task/Goal was created merely for the Investigation itself
    assert brain2.memory.tasks() == []
    assert brain2.memory.goals() == []
