"""Investigation -> Research Bridge (2026-08-17, ONE BRAIN Root
Implementation) -- the resolution to the Investigation-vs-Task chicken-
and-egg problem the design audit found and then falsified its own
original answer to: Task.goal_id is a required field, so an
Investigation (which by definition exists BEFORE any Opportunity/Goal)
can never legitimately produce a Task. The proven, existing escape:
this codebase already has a real, legitimate command path for exactly
this kind of low-risk, read-only, epistemic evidence-collection that
requires neither Task nor Goal nor Delegator/Registry.dispatch() at
all -- the *_advance.py bridge shape itself (Bridge 1
opportunity_advance.advance_opportunities_from_findings(), Bridge 2/3,
revenue_strategy.commit_ready_opportunities()) is already a plain,
pure(ish) function called directly from CEOBrain.tick(), performing
real KnowledgeBase/store writes with no RiskPolicy gate -- because
RiskPolicy exists to gate real-world-risk (cost/privileged-access/
legal/irreversibility), and reading a web page to check a fact is none
of those. This module is the same shape, one more time, not a second
command bus.

Does NOT invent an autonomous source_ref (URL) selector -- a real,
named, still-open limitation (see docs). `source_refs`, when supplied,
maps investigation.id -> a real, already-approved source_ref the
caller (a human, a CLI, or a future, separate, deliberate source-
selection mechanism) has already decided is safe and relevant to check.
An Investigation with no supplied source_ref simply stays
"waiting_for_evidence", untouched -- never guessed at, never blocked
from being revisited on a later call once a real source_ref becomes
known.
"""

from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_research import (
    EvidenceQualityRejected,
    SubjectAttributionUnverified,
    collect_evidence_from_source,
)
from atlas.brain.models import Investigation, now
from atlas.integrations.base import AIProvider


def advance_investigations(
    investigations: InvestigationStore,
    knowledge: KnowledgeBase,
    source_refs: dict[str, str] | None = None,
    ai_provider: AIProvider | None = None,
) -> list[Investigation]:
    """For every real Investigation in "waiting_for_evidence" that has a
    real, caller-supplied source_ref: attempts real evidence collection
    (collect_evidence_from_source(), which already enforces both
    request-relevance and Return-Path Subject Verification --
    subject=investigation.subject_id, so a wrong-entity observation is
    rejected before it ever reaches this function at all). On real
    success, links the new Finding id into the Investigation and moves
    it to "ready_for_evaluation" -- Bridge 1 (opportunity_advance.py) is
    the only place that can ever turn that evidence into a real
    Opportunity, unchanged, not this bridge. On a real rejection
    (EvidenceQualityRejected/SubjectAttributionUnverified), the
    Investigation is left exactly as it was -- "waiting_for_evidence" is
    a legitimate, permanent-until-resolved state, never silently
    advanced on a failed attempt."""
    source_refs = source_refs or {}
    changed: list[Investigation] = []

    for investigation in investigations.by_status("waiting_for_evidence"):
        source_ref = source_refs.get(investigation.id)
        if not source_ref:
            continue  # no real, approved source known yet -- stays waiting, never invented

        try:
            finding = collect_evidence_from_source(
                source_ref,
                category=investigation.category,
                source="investigation_evidence_collection",
                task_description=investigation.missing_evidence or f"confirm evidence about {investigation.subject_id}",
                knowledge=knowledge,
                subject=investigation.subject_id,
                ai_provider=ai_provider,
            )
        except (EvidenceQualityRejected, SubjectAttributionUnverified):
            continue  # a real, honest rejection -- nothing false is ever recorded

        investigation.supporting_finding_ids = sorted(set(investigation.supporting_finding_ids) | {finding.id})
        investigation.status = "ready_for_evaluation"
        investigation.updated_at = now()
        investigations.save_investigation(investigation)
        changed.append(investigation)

    return changed
