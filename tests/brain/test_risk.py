from atlas.brain.models import Task
from atlas.brain.risk import RiskPolicy


def _task(**overrides) -> Task:
    defaults = dict(goal_id="g1", description="do something", reversible=True)
    defaults.update(overrides)
    return Task(**defaults)


def test_safe_task_does_not_require_approval():
    decision = RiskPolicy().evaluate(_task())
    assert decision.requires_approval is False


def test_not_reversible_requires_approval():
    decision = RiskPolicy().evaluate(_task(reversible=False))
    assert decision.requires_approval is True
    assert any("reversible" in r for r in decision.reasons)


def test_amount_over_threshold_requires_approval():
    decision = RiskPolicy(amount_threshold=100).evaluate(_task(estimated_amount=150))
    assert decision.requires_approval is True


def test_amount_within_threshold_is_fine():
    decision = RiskPolicy(amount_threshold=100).evaluate(_task(estimated_amount=50))
    assert decision.requires_approval is False


def test_privileged_access_requires_approval():
    decision = RiskPolicy().evaluate(_task(involves_privileged_access=True))
    assert decision.requires_approval is True


def test_legal_agreement_requires_approval():
    decision = RiskPolicy().evaluate(_task(involves_legal_agreement=True))
    assert decision.requires_approval is True


def test_create_asset_always_requires_approval():
    decision = RiskPolicy().evaluate(_task(category="create_asset"))
    assert decision.requires_approval is True


def test_recruit_agent_always_requires_approval():
    decision = RiskPolicy().evaluate(_task(category="recruit_agent"))
    assert decision.requires_approval is True


def test_redesign_prefix_always_requires_approval():
    decision = RiskPolicy().evaluate(_task(category="redesign_workflow"))
    assert decision.requires_approval is True
