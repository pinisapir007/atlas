"""Integration tests for Decision Engine Integration V1 — deliberately
using the REAL Resource Discovery (ResourceAllowlist, ResourceIndex,
and the real LocalFolderProvider/scan_resources pipeline), REAL
Opportunity Discovery read path (opportunity_ranking.rank_opportunities
against a real KnowledgeBase), and REAL Time Awareness (TimeService)
components together — not the lightweight duck-typed fakes
test_decision_engine_integration.py's unit tests use. Every store is
still isolated (a real tmp_path for the filesystem scan, _FakeStore for
every JSON-backed registry) so nothing here ever touches this
project's real .atlas/ state.
"""

from datetime import datetime, timezone

from atlas.brain.decision_engine_integration import (
    EXECUTE,
    WAIT,
    TaskExecutionRequirements,
    evaluate_task_readiness,
)
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding, Task
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_discovery_engine import ResourceScanState, scan_resources
from atlas.brain.resource_index import ResourceIndex
from atlas.brain.time_service import TimeService


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_execute_after_a_real_scan_and_a_real_recorded_opportunity(tmp_path):
    # A full, real chain: approve a real folder -> real scan populates
    # the real ResourceIndex -> a real Finding is recorded -> the
    # decision engine reads both real stores and real-time-checks a
    # real deadline, and correctly says EXECUTE.
    real_file = tmp_path / "keto_report.csv"
    real_file.write_text("real data")

    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))

    resource_index = ResourceIndex(store=_FakeStore())
    scan_resources(allowlist=allowlist, scan_state=ResourceScanState(store=_FakeStore()), resource_index=resource_index)

    knowledge = KnowledgeBase(store=_FakeStore())
    knowledge.save_finding(Finding(source="founder", category="affiliate", description="real evidence", evidence="https://real.example.com", subject="KetoDNA"))

    task = Task(goal_id="g1", description="promote KetoDNA")
    requirements = TaskExecutionRequirements(
        required_resource_paths=[str(real_file)],
        opportunity_category="affiliate",
        deadline_iso="2026-12-31T00:00:00+00:00",
        minimum_remaining_seconds=60,
    )

    readiness = evaluate_task_readiness(task, requirements, resource_index=resource_index, resource_allowlist=allowlist, knowledge=knowledge)

    assert readiness.decision == EXECUTE
    assert readiness.reasons == []


def test_wait_when_the_real_scan_never_happened_for_a_required_resource(tmp_path):
    real_file = tmp_path / "report.csv"
    real_file.write_text("real data")

    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))
    # Deliberately no scan_resources() call -- the index stays empty,
    # even though the folder is genuinely approved.

    task = Task(goal_id="g1", description="promote KetoDNA")
    requirements = TaskExecutionRequirements(required_resource_paths=[str(real_file)])

    readiness = evaluate_task_readiness(task, requirements, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=allowlist, knowledge=KnowledgeBase(store=_FakeStore()))

    assert readiness.decision == WAIT
    assert "not found in the index" in readiness.reasons[0]


def test_wait_when_a_folder_was_scanned_but_never_approved(tmp_path):
    # Proves the allow-list is checked fresh at decision time, not just
    # trusted because a resource happens to be in the index -- an
    # approval could have been revoked after scanning.
    real_file = tmp_path / "report.csv"
    real_file.write_text("real data")

    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))
    resource_index = ResourceIndex(store=_FakeStore())
    scan_resources(allowlist=allowlist, scan_state=ResourceScanState(store=_FakeStore()), resource_index=resource_index)

    allowlist.revoke_folder(str(tmp_path))  # revoked AFTER scanning

    task = Task(goal_id="g1", description="promote KetoDNA")
    requirements = TaskExecutionRequirements(required_resource_paths=[str(real_file)])

    readiness = evaluate_task_readiness(task, requirements, resource_index=resource_index, resource_allowlist=allowlist, knowledge=KnowledgeBase(store=_FakeStore()))

    assert readiness.decision == WAIT
    assert "not approved" in readiness.reasons[0]


def test_wait_when_no_real_opportunity_has_been_discovered_yet():
    task = Task(goal_id="g1", description="promote something")
    requirements = TaskExecutionRequirements(opportunity_category="affiliate")

    readiness = evaluate_task_readiness(
        task, requirements, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()), knowledge=KnowledgeBase(store=_FakeStore())
    )

    assert readiness.decision == WAIT
    assert "no real opportunity recorded" in readiness.reasons[0]


def test_wait_when_a_real_deadline_has_already_passed():
    knowledge = KnowledgeBase(store=_FakeStore())
    knowledge.save_finding(Finding(source="founder", category="affiliate", description="real", evidence="https://real.example.com", subject="KetoDNA"))
    task = Task(goal_id="g1", description="promote KetoDNA")
    requirements = TaskExecutionRequirements(opportunity_category="affiliate", deadline_iso="2020-01-01T00:00:00+00:00")

    past_time_service = TimeService(clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    readiness = evaluate_task_readiness(
        task, requirements, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=ResourceAllowlist(store=_FakeStore()), knowledge=knowledge, time_service=past_time_service
    )

    assert readiness.decision == WAIT
    assert "deadline" in readiness.reasons[0]


def test_the_same_task_can_flip_from_wait_to_execute_once_the_missing_piece_is_supplied(tmp_path):
    # Demonstrates the decision is a real, live re-evaluation each call
    # -- not a cached verdict -- the same "recompute fresh, nothing is
    # permanently true" discipline the rest of this codebase's Decision
    # Engine already relies on, applied here at task-readiness scope.
    allowlist = ResourceAllowlist(store=_FakeStore())
    knowledge = KnowledgeBase(store=_FakeStore())
    task = Task(goal_id="g1", description="promote KetoDNA")
    requirements = TaskExecutionRequirements(opportunity_category="affiliate")

    first = evaluate_task_readiness(task, requirements, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=allowlist, knowledge=knowledge)
    assert first.decision == WAIT

    knowledge.save_finding(Finding(source="founder", category="affiliate", description="real", evidence="https://real.example.com", subject="KetoDNA"))

    second = evaluate_task_readiness(task, requirements, resource_index=ResourceIndex(store=_FakeStore()), resource_allowlist=allowlist, knowledge=knowledge)
    assert second.decision == EXECUTE
