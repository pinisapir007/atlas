from atlas.brain.decision_apply import apply_decision
from atlas.brain.models import Decision


def _decision(verdict: str, category: str = "digital_product", sources: int = 2) -> Decision:
    return Decision(
        category=category,
        verdict=verdict,
        confidence=0.7,
        factors={},
        context={"independent_sources": sources},
    )


def test_invest_verdict_creates_a_real_channel_task():
    decision = _decision("invest")

    goal, task = apply_decision(decision)

    assert goal.engine_id == "intelligence_digital_product"
    assert goal.founder_estimate == {}  # no fabricated founder judgment
    assert task.goal_id == goal.id
    assert task.category == "revenue_digital_product"
    assert task.reversible is True
    assert decision.goal_id == goal.id  # the passed-in Decision is updated with what it produced


def test_propose_capability_verdict_creates_a_gated_create_asset_task():
    decision = _decision("propose_capability", category="youtube")

    goal, task = apply_decision(decision)

    assert "Capability gap" in goal.description
    assert task.category == "create_asset"
    assert task.reversible is False  # default — always requires approval regardless
    assert decision.goal_id == goal.id


def test_insufficient_evidence_produces_nothing():
    decision = _decision("insufficient_evidence")

    goal, task = apply_decision(decision)

    assert goal is None
    assert task is None
    assert decision.goal_id is None


def test_already_invested_produces_nothing():
    decision = _decision("already_invested")

    goal, task = apply_decision(decision)

    assert goal is None
    assert task is None


def test_already_proposed_produces_nothing():
    decision = _decision("already_proposed")

    goal, task = apply_decision(decision)

    assert goal is None
    assert task is None
