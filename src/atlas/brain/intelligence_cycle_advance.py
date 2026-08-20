"""ATLAS Engine-Layer <-> CEOBrain Connection V1 (2026-08-05).

The minimum bridge required to run the new engine layer (Intelligence
Research Framework, Intelligence Engine, Resource Discovery,
Opportunity Discovery, Time Awareness, Business Execution Planning --
all built and tested, see docs/ATLAS_ARCHITECTURE_REFERENCE.md and
CLAUDE.md's "Architecture: End-to-End Intelligence Workflow") as part
of the real, automatic CEOBrain.tick() cycle, instead of being
reachable only by a human typing a CLI command.

Creates no new engine and no new evidence/scoring model. The one real
function this module exists for is intelligence_workflow.
run_intelligence_workflow(), completely unmodified, called once per
real, already-existing, active Goal the Decision Engine itself
created (Goal.engine_id == "intelligence_{category}" -- the exact
same correlation key campaign_advance.py already reads to find its
own goals). "Mission" in the founder's stated cycle (Mission ->
Intelligence -> Research -> Evidence -> Decision -> Execution Plan ->
Existing Execution Pipeline -> Measurement) is this real Goal --
never a fabricated/synthetic goal description invented by this
bridge.

Deliberately no new durable store: run_intelligence_workflow() is
pure and read-only (its Decision/Execution Plan stages never write
anything; its Intelligence/Resource stages write only into the
already-existing IntelligenceIndex/ResourceIndex). Per explicit
instruction for this pass, results are not persisted here -- CEOBrain
keeps the latest run in memory only (last_intelligence_workflow_results),
long enough to be inspected/reported, never written to disk.

The Decision -> Execution Plan stages inside the workflow are
read-only (see intelligence_workflow.py's own module docstring); the
real Decision -> Goal/Task -> Campaign -> Execution -> Measurement leg
that actually moves the business forward is CEOBrain's own,
pre-existing _decide_and_apply() / advance_decision_driven_campaigns()
/ advance_all_campaign_executions() -- unmodified by this bridge. This
module adds the missing automatic reasoning leg in parallel; it does
not duplicate or replace the existing action leg.

No new state, no deduplication, no caching: this reruns the full
workflow for every eligible Goal on every tick, exactly like decide_all()
already reruns fresh every tick. Optimizing repeated runs is explicitly
out of scope until the connection itself is proven to run end-to-end.
"""

from atlas.brain.intelligence_workflow import IntelligenceWorkflowResult, run_intelligence_workflow
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory

_ENGINE_ID_PREFIX = "intelligence_"


def _category_from_engine_id(engine_id: str | None) -> str | None:
    if engine_id and engine_id.startswith(_ENGINE_ID_PREFIX):
        return engine_id[len(_ENGINE_ID_PREFIX):]
    return None


def advance_intelligence_cycle(
    memory: BrainMemory,
    knowledge: KnowledgeBase,
    kpis: KPIRegistry,
) -> list[IntelligenceWorkflowResult]:
    """Runs the real, unmodified 8-stage intelligence workflow for
    every real, active Goal the Decision Engine has already created
    (one per evidenced category) -- the minimum bridge connecting the
    engine layer to CEOBrain.tick(). Returns every real result
    produced this call, in Goal iteration order; persists nothing new.
    """
    results = []
    for goal in memory.goals():
        if goal.status != "active":
            continue
        category = _category_from_engine_id(goal.engine_id)
        if category is None:
            continue
        results.append(
            run_intelligence_workflow(goal.description, category, knowledge=knowledge, memory=memory, kpis=kpis)
        )
    return results
