from atlas.brain.kpi import KPIRegistry
from atlas.brain.kpi_intake import (
    record_manual_cost,
    record_manual_refund,
    record_manual_revenue,
    record_manual_settlement,
    record_revenue,
)
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Task


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def _ledger(tmp_path) -> Ledger:
    return Ledger(tmp_path / "ledger.json")


def _won_opportunity(goal_id, revenue, profit, opp_id="opp-1"):
    return {
        "id": opp_id,
        "stage": "won",
        "goal_id": goal_id,
        "recurring_monthly_revenue": revenue,
        "estimated_gross_profit": profit,
    }


def test_revenue_shape_accumulates_onto_running_total(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="promote")

    record_revenue(task, {"status": "done", "channel": "affiliate", "revenue_generated": 100.0}, kpis)
    record_revenue(task, {"status": "done", "channel": "affiliate", "revenue_generated": 50.0}, kpis)

    assert kpis.latest("revenue_goal-a") == 150.0


def test_recruitment_shape_attributes_via_opportunity_goal_id_not_task(tmp_path):
    kpis = _kpis(tmp_path)
    # The dispatching task belongs to goal-b, but the won opportunity is
    # tagged goal-a — attribution must follow the opportunity, not the task.
    triggering_task = Task(goal_id="goal-b", description="dispatch that happens to run the pipeline")
    result = {"status": "done", "opportunities": [_won_opportunity("goal-a", 1000.0, 400.0)]}

    record_revenue(triggering_task, result, kpis)

    assert kpis.latest("revenue_goal-a") == 1000.0
    assert kpis.latest("cost_goal-a") == 600.0
    assert kpis.latest("revenue_goal-b") is None
    assert kpis.latest("cost_goal-b") is None


def test_untagged_opportunity_contributes_to_no_goal(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")
    result = {"status": "done", "opportunities": [_won_opportunity(None, 1000.0, 400.0)]}

    record_revenue(task, result, kpis)

    assert kpis.latest("revenue_goal-a") is None
    assert kpis.names() == []


def test_non_won_opportunities_are_excluded_even_with_valid_goal_id(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")
    pipeline_stage_opp = {
        "id": "opp-1",
        "stage": "proposal_ready",
        "goal_id": "goal-a",
        "recurring_monthly_revenue": 5000.0,
        "estimated_gross_profit": 2000.0,
    }

    record_revenue(task, {"status": "done", "opportunities": [pipeline_stage_opp]}, kpis)

    assert kpis.latest("revenue_goal-a") is None


def test_repeated_identical_recruitment_dispatch_is_idempotent(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")
    result = {"status": "done", "opportunities": [_won_opportunity("goal-a", 1000.0, 400.0)]}

    record_revenue(task, result, kpis)
    record_revenue(task, result, kpis)
    record_revenue(task, result, kpis)

    assert kpis.latest("revenue_goal-a") == 1000.0
    assert kpis.latest("cost_goal-a") == 600.0
    assert len(kpis.history("revenue_goal-a")) == 3  # recorded each time, never inflated


def test_recruitment_totals_sum_multiple_won_opportunities_for_the_same_goal(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")
    result = {
        "status": "done",
        "opportunities": [
            _won_opportunity("goal-a", 1000.0, 400.0, opp_id="opp-1"),
            _won_opportunity("goal-a", 500.0, 300.0, opp_id="opp-2"),
        ],
    }

    record_revenue(task, result, kpis)

    assert kpis.latest("revenue_goal-a") == 1500.0
    assert kpis.latest("cost_goal-a") == (1000.0 - 400.0) + (500.0 - 300.0)


def test_record_manual_revenue_accumulates_revenue_and_cost(tmp_path):
    kpis = _kpis(tmp_path)

    record_manual_revenue("goal-a", 100.0, 30.0, kpis)
    record_manual_revenue("goal-a", 50.0, 10.0, kpis)

    assert kpis.latest("revenue_goal-a") == 150.0
    assert kpis.latest("cost_goal-a") == 40.0


def test_record_manual_revenue_without_cost_leaves_cost_untouched(tmp_path):
    kpis = _kpis(tmp_path)

    record_manual_revenue("goal-a", 100.0, None, kpis)

    assert kpis.latest("revenue_goal-a") == 100.0
    assert kpis.latest("cost_goal-a") is None


def test_record_manual_cost_accumulates_without_touching_revenue(tmp_path):
    kpis = _kpis(tmp_path)

    record_manual_cost("goal-a", 30.0, kpis)
    record_manual_cost("goal-a", 10.0, kpis)

    assert kpis.latest("cost_goal-a") == 40.0
    assert kpis.latest("revenue_goal-a") is None


def test_record_manual_settlement_accumulates_a_separate_series_from_revenue(tmp_path):
    kpis = _kpis(tmp_path)
    record_manual_revenue("goal-a", 100.0, None, kpis)

    record_manual_settlement("goal-a", 60.0, kpis)
    record_manual_settlement("goal-a", 20.0, kpis)

    assert kpis.latest("settled_goal-a") == 80.0
    assert kpis.latest("revenue_goal-a") == 100.0  # settlement never touches the claimed series


def test_record_manual_refund_decrements_claimed_revenue(tmp_path):
    kpis = _kpis(tmp_path)
    record_manual_revenue("goal-a", 150.0, None, kpis)

    record_manual_refund("goal-a", 50.0, kpis)

    assert kpis.latest("revenue_goal-a") == 100.0


def test_record_manual_cost_with_fee_kind_still_accumulates_onto_cost(tmp_path):
    kpis = _kpis(tmp_path)

    record_manual_cost("goal-a", 12.0, kpis, kind="fee", category="platform_fee")

    assert kpis.latest("cost_goal-a") == 12.0


def test_ledger_is_optional_and_existing_behavior_is_unchanged_without_one(tmp_path):
    kpis = _kpis(tmp_path)

    record_manual_revenue("goal-a", 100.0, 30.0, kpis)
    record_manual_cost("goal-a", 5.0, kpis)
    record_manual_settlement("goal-a", 90.0, kpis)
    record_manual_refund("goal-a", 10.0, kpis)

    assert kpis.latest("revenue_goal-a") == 90.0
    assert kpis.latest("cost_goal-a") == 35.0
    assert kpis.latest("settled_goal-a") == 90.0


def test_record_manual_revenue_writes_ledger_entries_for_revenue_and_cost(tmp_path):
    kpis, ledger = _kpis(tmp_path), _ledger(tmp_path)

    record_manual_revenue("goal-a", 150.0, 40.0, kpis, ledger, provider="digistore24", evidence="dashboard screenshot")

    entries = ledger.entries_for_goal("goal-a")
    assert {(e.kind, e.amount) for e in entries} == {("revenue_claimed", 150.0), ("cost", 40.0)}
    assert all(e.provider == "digistore24" for e in entries)


def test_record_manual_revenue_without_cost_writes_only_a_revenue_entry(tmp_path):
    kpis, ledger = _kpis(tmp_path), _ledger(tmp_path)

    record_manual_revenue("goal-a", 100.0, None, kpis, ledger)

    entries = ledger.entries_for_goal("goal-a")
    assert len(entries) == 1
    assert entries[0].kind == "revenue_claimed"


def test_record_manual_cost_writes_a_ledger_entry_with_category(tmp_path):
    kpis, ledger = _kpis(tmp_path), _ledger(tmp_path)

    record_manual_cost("goal-a", 25.0, kpis, ledger, category="ad_spend")

    entries = ledger.entries_for_goal("goal-a")
    assert len(entries) == 1
    assert entries[0].kind == "cost"
    assert entries[0].category == "ad_spend"


def test_record_manual_cost_as_fee_writes_a_fee_kind_ledger_entry(tmp_path):
    kpis, ledger = _kpis(tmp_path), _ledger(tmp_path)

    record_manual_cost("goal-a", 12.0, kpis, ledger, kind="fee", category="platform_fee")

    entries = ledger.entries_for_goal("goal-a")
    assert len(entries) == 1
    assert entries[0].kind == "fee"
    assert entries[0].category == "platform_fee"


def test_record_manual_settlement_writes_a_cash_settled_ledger_entry(tmp_path):
    kpis, ledger = _kpis(tmp_path), _ledger(tmp_path)

    record_manual_settlement("goal-a", 60.0, kpis, ledger, evidence="bank statement 2026-08")

    entries = ledger.entries_for_goal("goal-a")
    assert len(entries) == 1
    assert entries[0].kind == "cash_settled"
    assert entries[0].evidence == "bank statement 2026-08"


def test_record_manual_refund_writes_a_refund_ledger_entry(tmp_path):
    kpis, ledger = _kpis(tmp_path), _ledger(tmp_path)
    record_manual_revenue("goal-a", 150.0, None, kpis, ledger)

    record_manual_refund("goal-a", 50.0, kpis, ledger)

    refund_entries = [e for e in ledger.entries_for_goal("goal-a") if e.kind == "refund"]
    assert len(refund_entries) == 1
    assert refund_entries[0].amount == 50.0


def test_revenue_channel_result_writes_a_revenue_claimed_ledger_entry(tmp_path):
    kpis, ledger = _kpis(tmp_path), _ledger(tmp_path)
    task = Task(goal_id="goal-a", description="promote")

    record_revenue(task, {"status": "done", "revenue_generated": 100.0}, kpis, ledger)

    entries = ledger.entries_for_goal("goal-a")
    assert len(entries) == 1
    assert entries[0].kind == "revenue_claimed"
    assert entries[0].amount == 100.0


def test_recruitment_result_writes_ledger_entries_only_for_the_actual_delta(tmp_path):
    kpis, ledger = _kpis(tmp_path), _ledger(tmp_path)
    task = Task(goal_id="goal-b", description="dispatch")
    result = {"status": "done", "opportunities": [_won_opportunity("goal-a", 1000.0, 400.0)]}

    record_revenue(task, result, kpis, ledger)
    record_revenue(task, result, kpis, ledger)  # identical re-dispatch — same totals, no new delta

    entries = ledger.entries_for_goal("goal-a")
    assert len(entries) == 2  # one revenue_claimed + one cost, from the first call only
    assert {(e.kind, e.amount) for e in entries} == {("revenue_claimed", 1000.0), ("cost", 600.0)}


def test_unrecognized_shape_records_nothing(tmp_path):
    kpis = _kpis(tmp_path)
    task = Task(goal_id="goal-a", description="dispatch")

    record_revenue(task, {"status": "done", "opportunities": [{"description": "x", "suggested_category": "y"}]}, kpis)
    record_revenue(task, {"status": "done"}, kpis)
    record_revenue(task, None, kpis)
    record_revenue(task, "not a dict", kpis)

    assert kpis.names() == []
