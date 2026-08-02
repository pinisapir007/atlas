import pytest

from atlas.brain.decisions import DecisionLog
from atlas.brain.models import Decision


def test_round_trips_a_decision(tmp_path):
    log = DecisionLog(tmp_path / "decisions.json")
    decision = Decision(category="affiliate", verdict="invest", confidence=0.778, factors={"recency": 1.0})
    log.save_decision(decision)

    reloaded = DecisionLog(tmp_path / "decisions.json").get_decision(decision.id)
    assert reloaded.verdict == "invest"
    assert reloaded.confidence == 0.778
    assert reloaded.factors == {"recency": 1.0}


def test_decisions_persist_across_instances(tmp_path):
    path = tmp_path / "decisions.json"
    DecisionLog(path).save_decision(Decision(category="youtube", verdict="propose_capability", confidence=0.5, factors={}))

    assert len(DecisionLog(path).decisions()) == 1


def test_missing_decision_raises_keyerror(tmp_path):
    log = DecisionLog(tmp_path / "decisions.json")
    with pytest.raises(KeyError):
        log.get_decision("does-not-exist")


def test_latest_for_category_returns_none_when_never_decided(tmp_path):
    log = DecisionLog(tmp_path / "decisions.json")
    assert log.latest_for_category("affiliate") is None


def test_latest_for_category_returns_the_most_recent(tmp_path):
    log = DecisionLog(tmp_path / "decisions.json")
    first = Decision(category="affiliate", verdict="insufficient_evidence", confidence=None, factors={})
    first.created_at = "2026-08-01T00:00:00+00:00"
    log.save_decision(first)
    second = Decision(category="affiliate", verdict="invest", confidence=0.7, factors={}, superseded_id=first.id)
    second.created_at = "2026-08-02T00:00:00+00:00"
    log.save_decision(second)

    latest = log.latest_for_category("affiliate")
    assert latest.id == second.id
    assert latest.superseded_id == first.id


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "decisions.json"
    log = DecisionLog(path)
    log.save_decision(Decision(category="affiliate", verdict="invest", confidence=0.7, factors={}))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
