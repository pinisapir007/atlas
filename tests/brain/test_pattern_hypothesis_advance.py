from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding
from atlas.brain.pattern_hypothesis_advance import (
    BASELINE_EVENT,
    SCAN_COMPLETED_EVENT,
    SCAN_FAILED_EVENT,
    advance_pattern_hypotheses,
)


class _Provider:
    name = "fake"

    def __init__(
        self,
        *,
        cluster=True,
        hypothesis=True,
        raise_error=False,
    ):
        self.cluster = cluster
        self.hypothesis = hypothesis
        self.raise_error = raise_error
        self.calls = []

    def complete_structured(self, prompt, fields):
        self.calls.append((prompt, fields))

        if self.raise_error:
            raise RuntimeError("provider unavailable")

        if "pattern_candidate_possible" in fields:
            if not self.cluster:
                return {
                    "pattern_candidate_possible": "no",
                    "member_numbers": "",
                    "candidate_theme": "",
                    "reason": "no coherent subset",
                }

            return {
                "pattern_candidate_possible": "yes",
                "member_numbers": "1,2",
                "candidate_theme": "repeated customer friction",
                "reason": "both observations concern the same friction",
            }

        if not self.hypothesis:
            return {
                "coherent_claim_possible": "no",
                "predicate": "",
                "object": "",
                "supporting_points": "",
                "counter_considerations": "not enough to hypothesize",
            }

        return {
            "coherent_claim_possible": "yes",
            "predicate": "recurring_delivery_friction",
            "object": "delivery delay repeatedly appears in complaints",
            "supporting_points": "the supplied observations repeat it",
            "counter_considerations": "could be temporary",
        }


def _setup(tmp_path):
    memory = BrainMemory(tmp_path / "memory.json")
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    return memory, knowledge


def _finding(
    knowledge,
    *,
    description,
    evidence,
    category="company_research",
    subject="ExampleCo",
):
    finding = Finding(
        source="research",
        category=category,
        description=description,
        evidence=evidence,
        subject=subject,
        evidence_role="direct_assertion",
    )
    knowledge.save_finding(finding)
    return finding


def test_flag_off_is_completely_inert(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        raising=False,
    )

    memory, knowledge = _setup(tmp_path)
    first = _finding(
        knowledge,
        description="Delivery is slow.",
        evidence="https://a.example/report",
    )
    provider = _Provider()

    result = advance_pattern_hypotheses(
        memory,
        knowledge,
        baseline_finding_ids=set(),
        ai_provider=provider,
    )

    assert result == []
    assert provider.calls == []
    assert memory.log() == []
    assert knowledge.claims() == []
    assert knowledge.get_finding(first.id).id == first.id


def test_first_enabled_call_baselines_history_without_ai(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        "1",
    )

    memory, knowledge = _setup(tmp_path)
    historical = _finding(
        knowledge,
        description="Historical observation.",
        evidence="https://old.example/report",
    )
    provider = _Provider()

    result = advance_pattern_hypotheses(
        memory,
        knowledge,
        baseline_finding_ids={historical.id},
        ai_provider=provider,
    )

    assert result == []
    assert provider.calls == []
    assert knowledge.claims() == []

    baseline = [
        entry
        for entry in memory.log()
        if entry.get("event") == BASELINE_EVENT
    ]
    assert len(baseline) == 1
    assert baseline[0]["finding_ids"] == [historical.id]


def test_new_finding_can_use_historical_context_to_form_hypothesis(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        "1",
    )

    memory, knowledge = _setup(tmp_path)

    historical = _finding(
        knowledge,
        description="Customers repeatedly complain about delivery delays.",
        evidence="https://a.example/report",
        subject="CompanyA",
    )

    provider = _Provider()

    # Initialize historical baseline.
    assert advance_pattern_hypotheses(
        memory,
        knowledge,
        baseline_finding_ids={historical.id},
        ai_provider=provider,
    ) == []
    assert provider.calls == []

    new = _finding(
        knowledge,
        description="Late shipping is a recurring customer complaint.",
        evidence="https://b.example/report",
        subject="CompanyB",
    )

    hypotheses = advance_pattern_hypotheses(
        memory,
        knowledge,
        ai_provider=provider,
    )

    assert len(hypotheses) == 1
    hypothesis = hypotheses[0]
    assert hypothesis.claim_type == "hypothesis"
    assert new.id in hypothesis.evidence_finding_ids
    assert historical.id in hypothesis.evidence_finding_ids

    # Exactly one selector + one reasoning call.
    assert len(provider.calls) == 2

    completed = [
        entry
        for entry in memory.log()
        if entry.get("event") == SCAN_COMPLETED_EVENT
    ]
    assert len(completed) == 1
    assert completed[0]["finding_ids"] == [new.id]
    assert completed[0]["result"] == "hypothesis"
    assert completed[0]["hypothesis_id"] == hypothesis.id


def test_negative_cluster_is_completed_and_not_charged_again(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        "1",
    )

    memory, knowledge = _setup(tmp_path)

    historical = _finding(
        knowledge,
        description="A product costs $29.",
        evidence="https://a.example/x",
    )

    provider = _Provider(cluster=False)

    advance_pattern_hypotheses(
        memory,
        knowledge,
        baseline_finding_ids={historical.id},
        ai_provider=provider,
    )

    new = _finding(
        knowledge,
        description="A company changed its logo.",
        evidence="https://b.example/y",
    )

    first = advance_pattern_hypotheses(
        memory,
        knowledge,
        ai_provider=provider,
    )
    calls_after_first = len(provider.calls)

    second = advance_pattern_hypotheses(
        memory,
        knowledge,
        ai_provider=provider,
    )

    assert first == []
    assert second == []
    assert calls_after_first == 1
    assert len(provider.calls) == 1

    completed = [
        entry
        for entry in memory.log()
        if entry.get("event") == SCAN_COMPLETED_EVENT
    ]
    assert any(
        entry["finding_ids"] == [new.id]
        and entry["result"] == "no_semantic_cluster"
        for entry in completed
    )


def test_provider_failure_never_crashes_and_never_marks_completed(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        "1",
    )

    memory, knowledge = _setup(tmp_path)

    historical = _finding(
        knowledge,
        description="Repeated friction A.",
        evidence="https://a.example/x",
    )

    advance_pattern_hypotheses(
        memory,
        knowledge,
        baseline_finding_ids={historical.id},
        ai_provider=_Provider(),
    )

    new = _finding(
        knowledge,
        description="Repeated friction B.",
        evidence="https://b.example/y",
    )

    failing = _Provider(raise_error=True)

    result = advance_pattern_hypotheses(
        memory,
        knowledge,
        ai_provider=failing,
    )

    assert result == []
    assert knowledge.claims() == []

    failed = [
        entry
        for entry in memory.log()
        if entry.get("event") == SCAN_FAILED_EVENT
    ]
    assert len(failed) == 1
    assert failed[0]["finding_ids"] == [new.id]

    completed = [
        entry
        for entry in memory.log()
        if entry.get("event") == SCAN_COMPLETED_EVENT
        and new.id in entry.get("finding_ids", [])
    ]
    assert completed == []

    # Because failure did NOT falsely mark completion, a healthy provider
    # on the next call is allowed to retry the same evidence.
    healthy = _Provider()
    retried = advance_pattern_hypotheses(
        memory,
        knowledge,
        ai_provider=healthy,
    )

    assert len(retried) == 1
    assert len(healthy.calls) == 2


def test_only_one_pending_category_is_processed_per_tick(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        "1",
    )

    memory, knowledge = _setup(tmp_path)

    a_old = _finding(
        knowledge,
        category="a_category",
        description="old a",
        evidence="https://a.example/old",
    )
    b_old = _finding(
        knowledge,
        category="b_category",
        description="old b",
        evidence="https://b.example/old",
    )

    provider = _Provider(cluster=False)

    advance_pattern_hypotheses(
        memory,
        knowledge,
        baseline_finding_ids={a_old.id, b_old.id},
        ai_provider=provider,
    )

    a_new = _finding(
        knowledge,
        category="a_category",
        description="new a",
        evidence="https://a.example/new",
    )
    b_new = _finding(
        knowledge,
        category="b_category",
        description="new b",
        evidence="https://b.example/new",
    )

    advance_pattern_hypotheses(
        memory,
        knowledge,
        ai_provider=provider,
    )

    completed_ids = {
        fid
        for entry in memory.log()
        if entry.get("event") == SCAN_COMPLETED_EVENT
        for fid in entry.get("finding_ids", [])
    }

    # Cost bound: only one category consumed this tick.
    assert len({a_new.id, b_new.id} & completed_ids) == 1

    # The second category remains pending and is consumed next call.
    advance_pattern_hypotheses(
        memory,
        knowledge,
        ai_provider=provider,
    )

    completed_ids = {
        fid
        for entry in memory.log()
        if entry.get("event") == SCAN_COMPLETED_EVENT
        for fid in entry.get("finding_ids", [])
    }
    assert a_new.id in completed_ids
    assert b_new.id in completed_ids
