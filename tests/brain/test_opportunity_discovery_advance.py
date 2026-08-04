from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal
from atlas.brain.opportunity_discovery_advance import advance_opportunity_discovery


class _World:
    def __init__(self, tmp_path):
        self.memory = BrainMemory(tmp_path / "brain.json")
        self.knowledge = KnowledgeBase(tmp_path / "knowledge.json")
        self.affiliate_store = AffiliateStore(tmp_path / "affiliate_intelligence.json")

    def decision_engine_goal(self, category="affiliate", status="active") -> Goal:
        goal = Goal(description=f"Pursue {category} opportunities", engine_id=f"intelligence_{category}", status=status)
        self.memory.save_goal(goal)
        return goal

    def two_sourced_findings(self, category="affiliate", subject="KetoDNA", market="US"):
        self.knowledge.save_finding(
            Finding(source="research", category=category, description="a", evidence="https://x/1", subject=subject, market=market)
        )
        self.knowledge.save_finding(
            Finding(source="research", category=category, description="b", evidence="https://x/2", subject=subject, market=market)
        )

    def advance(self):
        advance_opportunity_discovery(self.memory, self.knowledge, self.affiliate_store)


def test_disabled_by_default_produces_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", raising=False)
    world = _World(tmp_path)
    world.decision_engine_goal()
    world.two_sourced_findings()

    world.advance()

    assert world.affiliate_store.opportunities() == []


def test_enabled_creates_a_real_ranked_opportunity_from_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    world = _World(tmp_path)
    goal = world.decision_engine_goal()
    world.two_sourced_findings(subject="KetoDNA", market="US")

    world.advance()

    opportunities = world.affiliate_store.opportunities()
    assert len(opportunities) == 1
    opportunity = opportunities[0]
    assert opportunity.product_name == "KetoDNA"
    assert opportunity.stage == "ranked"
    assert opportunity.goal_id == goal.id
    assert opportunity.category == "affiliate"
    # No commercial terms fabricated -- evidence picks the niche, not the deal.
    assert opportunity.real_affiliate_link == ""
    assert opportunity.commission_per_conversion == 0.0
    # Real, evidence-derived market recommendation carried onto the model
    # (not just embedded in a free-text note) so downstream consumers
    # (e.g. influencer selection) can read it structurally.
    assert opportunity.recommended_market == "US"


def test_enabled_leaves_recommended_market_empty_when_evidence_names_none(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    world = _World(tmp_path)
    world.decision_engine_goal()
    world.two_sourced_findings(subject="KetoDNA", market="")  # no market stated anywhere

    world.advance()

    opportunity = world.affiliate_store.opportunities()[0]
    assert opportunity.recommended_market == ""


def test_enabled_but_below_the_independent_source_bar_creates_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    world = _World(tmp_path)
    world.decision_engine_goal()
    world.knowledge.save_finding(
        Finding(source="research", category="affiliate", description="a", evidence="https://x/1", subject="KetoDNA")
    )  # only 1 independent source -- MIN_INDEPENDENT_SOURCES is 2

    world.advance()

    assert world.affiliate_store.opportunities() == []


def test_enabled_ignores_a_goal_not_created_by_the_decision_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    world = _World(tmp_path)
    goal = Goal(description="a manually-created goal, not Decision-Engine-driven")
    world.memory.save_goal(goal)
    world.two_sourced_findings()

    world.advance()

    assert world.affiliate_store.opportunities() == []


def test_enabled_ignores_an_unbridged_category(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    world = _World(tmp_path)
    world.decision_engine_goal(category="digital_product")
    world.two_sourced_findings(category="digital_product")

    world.advance()

    assert world.affiliate_store.opportunities() == []


def test_enabled_ignores_a_paused_goal(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    world = _World(tmp_path)
    world.decision_engine_goal(status="paused")
    world.two_sourced_findings()

    world.advance()

    assert world.affiliate_store.opportunities() == []


def test_advancing_twice_never_creates_a_duplicate_opportunity(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    world = _World(tmp_path)
    world.decision_engine_goal()
    world.two_sourced_findings()

    world.advance()
    world.advance()
    world.advance()

    assert len(world.affiliate_store.opportunities()) == 1
