"""One true end-to-end test for Business Execution Planning V1 —
a real filesystem scan (via the real LocalFolderProvider/
scan_resources(), not pre-populated index data) through to a real,
fully executable BusinessExecutionPlan. Mirrors the same "real
components, isolated storage" pattern test_decision_engine_integration_
end_to_end.py already established one module over.
"""

from atlas.brain.business_execution_planning import build_execution_plan
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding
from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.brain.resource_discovery_engine import ResourceScanState, scan_resources
from atlas.brain.resource_index import ResourceIndex


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_full_real_pipeline_scan_to_evidence_to_executable_plan(tmp_path):
    # Resource Discovery: approve a real folder, run a real scan.
    research_file = tmp_path / "market_research.csv"
    research_file.write_text("real research data")
    allowlist = ResourceAllowlist(store=_FakeStore())
    allowlist.approve_folder(str(tmp_path))
    resource_index = ResourceIndex(store=_FakeStore())
    scan_resources(allowlist=allowlist, scan_state=ResourceScanState(store=_FakeStore()), resource_index=resource_index)

    # Opportunity Discovery / Decision Engine: real, sourced evidence
    # for a real subject, enough to clear MIN_INDEPENDENT_SOURCES.
    knowledge = KnowledgeBase(tmp_path / "knowledge.json")
    knowledge.save_finding(Finding(source="research", category="digital_product", description="signal 1", evidence="https://example.com/1", subject="Widget"))
    knowledge.save_finding(Finding(source="research", category="digital_product", description="signal 2", evidence="https://example.com/2", subject="Widget"))
    memory = BrainMemory(tmp_path / "brain.json")
    kpis = KPIRegistry(memory)

    plan = build_execution_plan(
        "digital_product", knowledge, memory, kpis,
        resource_index=resource_index, resource_allowlist=allowlist,
        required_resource_paths=[str(research_file)],
        estimated_duration_seconds=7200,
    )

    assert plan.verdict == "invest"
    assert plan.selected_opportunity["subject"] == "Widget"
    assert plan.required_resources["available"] is True
    assert plan.estimated_execution_time["duration_seconds"] == 7200
    assert plan.can_execute is True
    assert plan.blocking_reasons == []
    assert plan.task_dependency_order == ["verify_readiness", "produce_content", "request_founder_review", "check_measurement"]
    # Planning only -- nothing executed, no Task/Campaign/real action
    # exists anywhere as a side effect of building this plan.
    assert memory.tasks() == []
    assert memory.goals() == []
