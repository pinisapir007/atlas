from atlas.brain.decision_apply import apply_decision, supersede_pending_capability_proposals
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


def test_invest_verdict_bootstraps_the_dead_end_pipeline_by_default(monkeypatch):
    # Opportunity Discovery V1 is off by default -- production behavior is
    # unchanged until the founder explicitly enables it.
    monkeypatch.delenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", raising=False)
    decision = _decision("invest", category="affiliate")

    _, task = apply_decision(decision)

    assert task.category == "affiliate_pipeline"


def test_invest_verdict_bootstraps_affiliate_intelligence_when_v1_enabled(monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    decision = _decision("invest", category="affiliate")

    _, task = apply_decision(decision)

    assert task.category == "affiliate_intelligence"


def test_v1_flag_does_not_affect_categories_without_an_override(monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    decision = _decision("invest", category="digital_product")

    _, task = apply_decision(decision)

    assert task.category == "revenue_digital_product"


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

def test_supersede_pending_capability_proposal_closes_triplet_atomically(tmp_path):
    from atlas.brain.memory import BrainMemory
    from atlas.brain.models import Goal, Proposal, Task

    memory = BrainMemory(tmp_path / "brain.json")

    goal = Goal(
        description="Capability gap: youtube",
        engine_id="intelligence_youtube",
    )
    task = Task(
        goal_id=goal.id,
        description="Evaluate building a real 'youtube' execution channel",
        category="create_asset",
    )
    task.transition("pending_approval", "structural proposal")
    proposal = Proposal(
        task_id=task.id,
        kind="create_asset",
        rationale=task.description,
    )

    memory.save_goal(goal)
    memory.save_task(task)
    memory.save_proposal(proposal)

    changed = supersede_pending_capability_proposals(
        "youtube",
        memory,
        "new evidence no longer supports the proposal",
    )

    assert changed == 1
    assert memory.get_goal(goal.id).status == "paused"
    assert memory.get_task(task.id).status == "superseded"
    assert memory.get_proposal(proposal.id).status == "superseded"
    assert memory.get_proposal(proposal.id).resolved_at is not None
    assert memory.completed_task_total() == 0

    # Idempotent: a repeated reconciliation has nothing left to change.
    assert (
        supersede_pending_capability_proposals(
            "youtube",
            memory,
            "new evidence no longer supports the proposal",
        )
        == 0
    )
