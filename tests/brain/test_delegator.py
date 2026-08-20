from pathlib import Path
from unittest.mock import patch

from atlas.brain.delegator import Delegator
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.core.loader import discover_manifests
from atlas.core.models import AssetRecord
from atlas.core.registry import Registry
from atlas.core.store import JSONStore

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "assets"


def _registry(tmp_path, exclude=()):
    records = [r for r in discover_manifests([FIXTURES]) if r.id not in exclude]
    return Registry(records, store=JSONStore(tmp_path / "state.json"))


def test_delegates_to_capable_triggerable_asset(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="do work")

    Delegator(memory).delegate(task, registry)

    assert task.status == "delegated"
    assert task.assigned_asset_id == "sample-triggerable"


def test_blocks_when_no_capable_asset(tmp_path):
    registry = _registry(tmp_path, exclude=["sample-triggerable"])
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="do work")

    Delegator(memory).delegate(task, registry)

    assert task.status == "blocked"
    assert task.assigned_asset_id is None


def test_structural_category_always_produces_proposal(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="recruit a marketing agent", category="recruit_agent")

    Delegator(memory).delegate(task, registry)

    assert task.status == "pending_approval"
    proposals = memory.proposals()
    assert len(proposals) == 1
    assert proposals[0].kind == "recruit_agent"
    assert proposals[0].task_id == task.id


def test_redesign_category_produces_redesign_proposal_with_evidence(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="rework the marketing workflow", category="redesign_workflow")

    Delegator(memory).delegate(task, registry, evidence=["kpi flat for 3 periods"])

    proposal = memory.proposals()[0]
    assert proposal.kind == "redesign"
    assert proposal.evidence == ["kpi flat for 3 periods"]


def test_prefers_asset_with_matching_declared_category_over_first_alphabetical(tmp_path):
    records = [
        AssetRecord(
            id="alpha-generic",
            name="Alpha Generic",
            kind="agent",
            entrypoint="tests.fixtures.assets.triggerable_sample.agent:SampleTriggerable",
        ),
        AssetRecord(
            id="zeta-specific",
            name="Zeta Specific",
            kind="agent",
            entrypoint="tests.fixtures.assets.triggerable_sample.agent:SampleTriggerable",
            config={"categories": ["widget_task"]},
        ),
    ]
    registry = Registry(records, store=JSONStore(tmp_path / "state.json"))
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="do widget work", category="widget_task")

    Delegator(memory).delegate(task, registry)

    assert task.assigned_asset_id == "zeta-specific"


def test_blocks_when_no_registered_asset_matches_category(tmp_path):
    """Replaces the old test_falls_back_to_unmatched_asset_when_no_category_
    declared_matches (2026-08-15, Delegator Fail-Closed Fix, Foundation
    Design approved). That test documented and asserted the OLD, now-
    rejected intent -- "some dispatch is better than none": when zero
    registered assets declared the task's category, Delegator used to
    fall through to try every OTHER unrelated asset, in id-sorted order,
    dispatching to whichever one happened not to raise UnsupportedVerb.

    The new, approved architectural intent is the opposite: "fail closed;
    never guess a capability." Neither of these two assets declares the
    task's category ("general") -- the correct, honest behavior is now
    `blocked`, never a dispatch to zeta-specific or alpha-generic."""
    records = [
        AssetRecord(
            id="zeta-specific",
            name="Zeta Specific",
            kind="agent",
            entrypoint="tests.fixtures.assets.triggerable_sample.agent:SampleTriggerable",
            config={"categories": ["widget_task"]},
        ),
        AssetRecord(
            id="alpha-generic",
            name="Alpha Generic",
            kind="agent",
            entrypoint="tests.fixtures.assets.triggerable_sample.agent:SampleTriggerable",
        ),
    ]
    registry = Registry(records, store=JSONStore(tmp_path / "state.json"))
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="general work", category="general")

    with patch.object(Registry, "dispatch", wraps=registry.dispatch) as spy_dispatch:
        Delegator(memory).delegate(task, registry)

    assert task.status == "blocked"
    assert task.assigned_asset_id is None
    assert "general" in task.history[-1]["reason"]
    spy_dispatch.assert_not_called()  # neither unrelated asset was ever tried


def test_zero_match_never_attempts_dispatch_on_any_unrelated_asset(tmp_path):
    """Broader than the test above: three unrelated assets registered
    (none declaring the task's category), all real, all Triggerable-
    capable -- confirms the fix isn't just "the first fallback candidate
    was skipped" but that NO unrelated asset is ever tried, regardless of
    how many are registered."""
    records = [
        AssetRecord(
            id=f"unrelated-{i}",
            name=f"Unrelated {i}",
            kind="agent",
            entrypoint="tests.fixtures.assets.triggerable_sample.agent:SampleTriggerable",
            config={"categories": [f"other_category_{i}"]},
        )
        for i in range(3)
    ]
    registry = Registry(records, store=JSONStore(tmp_path / "state.json"))
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="general work", category="general")

    with patch.object(Registry, "dispatch", wraps=registry.dispatch) as spy_dispatch:
        Delegator(memory).delegate(task, registry)

    assert task.status == "blocked"
    spy_dispatch.assert_not_called()


def test_blocked_reason_is_explicit_and_auditable(tmp_path):
    registry = _registry(tmp_path, exclude=["sample-triggerable"])
    memory = BrainMemory(tmp_path / "brain.json")
    task = Task(goal_id="g1", description="do work", category="some_unregistered_category")

    Delegator(memory).delegate(task, registry)

    assert task.status == "blocked"
    reason = task.history[-1]["reason"]
    assert "some_unregistered_category" in reason
    assert "fail-closed" in reason
