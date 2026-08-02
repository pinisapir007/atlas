from atlas.brain.intake import absorb_opportunities
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task
from atlas.core.models import AssetRecord
from atlas.core.registry import Registry
from atlas.core.store import JSONStore


def _registry(tmp_path):
    records = [
        AssetRecord(
            id="research",
            name="Research",
            kind="operational_agent",
            entrypoint="atlas.assets.research.agent:ResearchAgent",
            config={"categories": ["discover_opportunities"]},
        )
    ]
    return Registry(records, store=JSONStore(tmp_path / "state.json"))


def _done_research_task(goal_id="g1"):
    return Task(
        goal_id=goal_id,
        description="scan for opportunities",
        category="discover_opportunities",
        status="done",
        assigned_asset_id="research",
    )


def test_absorbs_opportunities_from_completed_research_task(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    registry.dispatch("research", "run")
    task = _done_research_task()
    memory.save_task(task)

    new_tasks = absorb_opportunities([task], registry, memory)

    assert len(new_tasks) == 2
    assert {t.category for t in new_tasks} == {"revenue_affiliate", "revenue_recruitment_leads"}
    assert all(t.goal_id == "g1" for t in new_tasks)
    assert all(t.reversible is True for t in new_tasks)


def test_does_not_absorb_the_same_task_twice(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    registry.dispatch("research", "run")
    task = _done_research_task()
    memory.save_task(task)

    first = absorb_opportunities([task], registry, memory)
    reloaded = memory.get_task(task.id)
    second = absorb_opportunities([reloaded], registry, memory)

    assert len(first) == 2
    assert len(second) == 0


def test_ignores_tasks_not_done_or_not_research_category(tmp_path):
    registry = _registry(tmp_path)
    memory = BrainMemory(tmp_path / "brain.json")
    proposed = Task(
        goal_id="g1", description="not finished yet", category="discover_opportunities", status="proposed"
    )
    other_category = Task(goal_id="g1", description="unrelated", category="general", status="done")

    new_tasks = absorb_opportunities([proposed, other_category], registry, memory)

    assert new_tasks == []
