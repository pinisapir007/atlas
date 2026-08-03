import pytest

from atlas.brain.ledger import Ledger
from atlas.brain.models import LedgerEntry


def test_round_trips_a_ledger_entry(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    entry = LedgerEntry(goal_id="goal-a", kind="revenue_claimed", amount=150.0, provider="digistore24")
    ledger.record(entry)

    reloaded = Ledger(tmp_path / "ledger.json").entries()
    assert len(reloaded) == 1
    assert reloaded[0].goal_id == "goal-a"
    assert reloaded[0].kind == "revenue_claimed"
    assert reloaded[0].amount == 150.0
    assert reloaded[0].provider == "digistore24"


def test_entries_are_never_mutated_a_correction_is_a_new_entry(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.record(LedgerEntry(goal_id="goal-a", kind="revenue_claimed", amount=150.0))
    ledger.record(LedgerEntry(goal_id="goal-a", kind="refund", amount=50.0))

    entries = ledger.entries()
    assert len(entries) == 2
    assert {e.kind for e in entries} == {"revenue_claimed", "refund"}


def test_entries_for_goal_filters_to_only_that_goal(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.record(LedgerEntry(goal_id="goal-a", kind="revenue_claimed", amount=100.0))
    ledger.record(LedgerEntry(goal_id="goal-b", kind="revenue_claimed", amount=200.0))

    assert [e.goal_id for e in ledger.entries_for_goal("goal-a")] == ["goal-a"]


def test_entries_for_transaction_filters_to_only_that_transaction(tmp_path):
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.record(LedgerEntry(goal_id="goal-a", kind="revenue_claimed", amount=100.0, transaction_id="txn-1"))
    ledger.record(LedgerEntry(goal_id="goal-a", kind="cash_settled", amount=90.0, transaction_id="txn-1"))
    ledger.record(LedgerEntry(goal_id="goal-a", kind="revenue_claimed", amount=50.0, transaction_id="txn-2"))

    matched = ledger.entries_for_transaction("txn-1")
    assert len(matched) == 2
    assert {e.kind for e in matched} == {"revenue_claimed", "cash_settled"}


def test_ledger_persists_across_instances(tmp_path):
    path = tmp_path / "ledger.json"
    Ledger(path).record(LedgerEntry(goal_id="goal-a", kind="cost", amount=40.0))

    assert len(Ledger(path).entries()) == 1


def test_missing_ledger_file_returns_no_entries(tmp_path):
    assert Ledger(tmp_path / "does_not_exist.json").entries() == []


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = Ledger(path)
    ledger.record(LedgerEntry(goal_id="goal-a", kind="fee", amount=5.0))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
