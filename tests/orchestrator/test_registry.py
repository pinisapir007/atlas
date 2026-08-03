import pytest

from atlas.orchestrator.models import ExecutionPlan, ExecutionStep
from atlas.orchestrator.registry import ExecutionPlanRegistry


def test_round_trips_a_plan_with_nested_steps(tmp_path):
    registry = ExecutionPlanRegistry(tmp_path / "execution_plans.json")
    step = ExecutionStep(campaign_id="campaign-a", kind="verify_readiness")
    plan = ExecutionPlan(campaign_id="campaign-a", steps=[step])
    registry.save_plan(plan)

    reloaded = ExecutionPlanRegistry(tmp_path / "execution_plans.json").get_plan(plan.id)
    assert reloaded.campaign_id == "campaign-a"
    assert len(reloaded.steps) == 1
    assert reloaded.steps[0].kind == "verify_readiness"
    assert reloaded.status == "in_progress"


def test_missing_plan_raises_keyerror(tmp_path):
    registry = ExecutionPlanRegistry(tmp_path / "execution_plans.json")
    with pytest.raises(KeyError):
        registry.get_plan("does-not-exist")


def test_plans_for_campaign_filters_correctly(tmp_path):
    registry = ExecutionPlanRegistry(tmp_path / "execution_plans.json")
    registry.save_plan(ExecutionPlan(campaign_id="campaign-a"))
    registry.save_plan(ExecutionPlan(campaign_id="campaign-b"))

    assert [p.campaign_id for p in registry.plans_for_campaign("campaign-a")] == ["campaign-a"]


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "execution_plans.json"
    registry = ExecutionPlanRegistry(path)
    registry.save_plan(ExecutionPlan(campaign_id="campaign-a"))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
