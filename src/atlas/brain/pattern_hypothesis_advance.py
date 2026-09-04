"""Stage 7 / Layer 2 autonomous Pattern/Hypothesis advance bridge.

This is the ONLY production orchestration seam for autonomous Layer 2.

Contract:
- feature-flagged OFF by default;
- reads durable Finding records only;
- historical evidence present before activation is baselined, not
  reprocessed as if it had just arrived;
- processes at most one category per call;
- inspects a bounded evidence window;
- requires the semantic candidate to include at least one pending/new
  Finding, so old evidence alone cannot repeatedly trigger reasoning;
- persists only Claim knowledge plus durable BrainMemory audit markers;
- never creates or dispatches Task/Goal/Decision/action state;
- provider failures never crash CEOBrain.tick() and never mark the
  evidence completed, so a later healthy run may retry honestly.

Negative semantic/reasoning outcomes ARE completed scans. This prevents
ATLAS from spending another AI call every tick on the exact same evidence.
A genuinely new Finding later makes that category eligible again.
"""

from atlas.brain.evidence_provenance import independent_source_count
from atlas.brain.feature_flags import pattern_hypothesis_enabled
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Claim, Finding, now
from atlas.brain.pattern_hypothesis_engine import (
    MAX_FINDINGS_PER_CANDIDATE_SCAN,
    PatternEvidenceGroup,
    form_pattern_hypothesis,
    select_semantic_pattern_candidate,
)
from atlas.integrations.base import AIProvider


BASELINE_EVENT = "pattern_hypothesis_baseline"
SCAN_COMPLETED_EVENT = "pattern_hypothesis_scan_completed"
SCAN_FAILED_EVENT = "pattern_hypothesis_scan_failed"

# Explicit cost/rate bound: one category can cause at most one semantic
# selection call + one hypothesis reasoning call per tick.
MAX_CATEGORIES_PER_TICK = 1

# Pending evidence is consumed in small batches. Remaining pending evidence
# stays eligible for a later tick through the durable log watermark.
MAX_PENDING_FINDINGS_PER_SCAN = 6


def _baseline_entries(memory: BrainMemory) -> list[dict]:
    return [
        entry
        for entry in memory.log()
        if entry.get("event") == BASELINE_EVENT
    ]


def _accounted_finding_ids(memory: BrainMemory) -> set[str]:
    """Finding ids already baselined or fully scanned.

    Failure events deliberately do NOT count: a provider/network failure
    must never falsely convert unprocessed evidence into processed evidence.
    """
    accounted: set[str] = set()

    for entry in memory.log():
        if entry.get("event") not in {
            BASELINE_EVENT,
            SCAN_COMPLETED_EVENT,
        }:
            continue

        ids = entry.get("finding_ids", [])
        if isinstance(ids, list):
            accounted.update(
                fid
                for fid in ids
                if isinstance(fid, str) and fid
            )

    return accounted


def _initialize_baseline_if_needed(
    memory: BrainMemory,
    knowledge: KnowledgeBase,
    baseline_finding_ids: set[str] | None,
) -> None:
    """Create exactly one durable historical baseline.

    CEOBrain supplies the Finding ids that existed at the START of the
    first enabled tick. Therefore Findings genuinely created later in that
    same tick remain unaccounted and may be processed immediately.

    Direct callers that do not supply a baseline get the conservative
    behavior: everything currently in KnowledgeBase is historical baseline.
    """
    if _baseline_entries(memory):
        return

    if baseline_finding_ids is None:
        ids = {finding.id for finding in knowledge.findings()}
    else:
        ids = set(baseline_finding_ids)

    # Validate every supplied id against the real KnowledgeBase before
    # recording it as historical state.
    for finding_id in ids:
        knowledge.get_finding(finding_id)

    memory.append_log(
        {
            "at": now(),
            "event": BASELINE_EVENT,
            "finding_ids": sorted(ids),
        }
    )


def _pending_by_category(
    knowledge: KnowledgeBase,
    accounted_ids: set[str],
) -> dict[str, list[Finding]]:
    grouped: dict[str, list[Finding]] = {}

    for finding in knowledge.findings():
        if finding.id in accounted_ids:
            continue

        category = finding.category.strip()
        if not category:
            # Empty-category evidence cannot form a category pattern.
            # It is handled separately by the caller as a completed skip.
            grouped.setdefault("", []).append(finding)
            continue

        grouped.setdefault(category, []).append(finding)

    for findings in grouped.values():
        findings.sort(key=lambda f: (f.created_at, f.id))

    return grouped


def _complete_scan(
    memory: BrainMemory,
    *,
    category: str,
    finding_ids: list[str],
    result: str,
    hypothesis_id: str | None = None,
) -> None:
    entry = {
        "at": now(),
        "event": SCAN_COMPLETED_EVENT,
        "category": category,
        "finding_ids": sorted(set(finding_ids)),
        "result": result,
    }
    if hypothesis_id is not None:
        entry["hypothesis_id"] = hypothesis_id
    memory.append_log(entry)


def advance_pattern_hypotheses(
    memory: BrainMemory,
    knowledge: KnowledgeBase,
    *,
    baseline_finding_ids: set[str] | None = None,
    ai_provider: AIProvider | None = None,
) -> list[Claim]:
    """Autonomously process bounded newly-arrived Finding evidence.

    Returns hypotheses formed/reused during this call. The return value has
    no execution semantics and is not a command bus.

    Feature flag disabled -> immediate [] and no baseline/log/AI activity.
    """
    if not pattern_hypothesis_enabled():
        return []

    _initialize_baseline_if_needed(
        memory,
        knowledge,
        baseline_finding_ids,
    )

    accounted = _accounted_finding_ids(memory)
    pending_by_category = _pending_by_category(
        knowledge,
        accounted,
    )

    if not pending_by_category:
        return []

    # Empty-category evidence can never enter category-level semantic
    # pattern formation. Mark it honestly as examined/skipped so it cannot
    # create an infinite pending loop.
    empty_category = pending_by_category.pop("", [])
    if empty_category:
        _complete_scan(
            memory,
            category="",
            finding_ids=[f.id for f in empty_category],
            result="skipped_empty_category",
        )

    if not pending_by_category:
        return []

    # Oldest pending category first: deterministic and starvation-resistant.
    categories = sorted(
        pending_by_category,
        key=lambda category: (
            pending_by_category[category][0].created_at,
            category,
        ),
    )[:MAX_CATEGORIES_PER_TICK]

    hypotheses: list[Claim] = []

    for category in categories:
        pending = pending_by_category[category][
            :MAX_PENDING_FINDINGS_PER_SCAN
        ]
        pending_ids = {f.id for f in pending}

        # Give the selector historical context as well as the pending
        # evidence, but guarantee every pending Finding remains inside its
        # bounded scan window by placing context FIRST and pending LAST.
        category_findings = knowledge.findings(category=category)
        context = [
            finding
            for finding in category_findings
            if finding.id not in pending_ids
        ]

        context_slots = max(
            0,
            MAX_FINDINGS_PER_CANDIDATE_SCAN - len(pending),
        )
        context = context[-context_slots:] if context_slots else []

        scan_findings = [*context, *pending]

        # With only one observation and no historical context there is no
        # possible recurring pattern yet. Complete this scan; a future new
        # Finding will reopen the category and the old one will then be
        # available as historical context.
        if len(scan_findings) < 2:
            _complete_scan(
                memory,
                category=category,
                finding_ids=[f.id for f in pending],
                result="insufficient_context",
            )
            continue

        broad_group = PatternEvidenceGroup(
            category=category,
            finding_ids=tuple(f.id for f in scan_findings),
            subject_ids=tuple(
                sorted(
                    {
                        f.subject
                        for f in scan_findings
                        if f.subject
                    }
                )
            ),
            independent_sources=independent_source_count(
                scan_findings
            ),
        )

        try:
            semantic_group = select_semantic_pattern_candidate(
                broad_group,
                knowledge,
                ai_provider=ai_provider,
            )

            if semantic_group is None:
                _complete_scan(
                    memory,
                    category=category,
                    finding_ids=[f.id for f in pending],
                    result="no_semantic_cluster",
                )
                continue

            # Critical autonomy guard: a cluster made only from historical
            # context is not a response to the newly-arrived evidence.
            # Do not spend the second reasoning call on an old cluster.
            if not (
                set(semantic_group.finding_ids)
                & pending_ids
            ):
                _complete_scan(
                    memory,
                    category=category,
                    finding_ids=[f.id for f in pending],
                    result="no_new_evidence_cluster",
                )
                continue

            hypothesis = form_pattern_hypothesis(
                semantic_group,
                knowledge,
                ai_provider=ai_provider,
            )

            if hypothesis is None:
                _complete_scan(
                    memory,
                    category=category,
                    finding_ids=[f.id for f in pending],
                    result="no_hypothesis",
                )
                continue

            hypotheses.append(hypothesis)
            _complete_scan(
                memory,
                category=category,
                finding_ids=[f.id for f in pending],
                result="hypothesis",
                hypothesis_id=hypothesis.id,
            )

        except Exception as exc:
            # Autonomous cognition must never take down the operational CEO
            # tick because a remote AI provider is unavailable. Fail closed:
            # no Claim is fabricated and pending evidence remains uncompleted
            # for a future healthy retry.
            memory.append_log(
                {
                    "at": now(),
                    "event": SCAN_FAILED_EVENT,
                    "category": category,
                    "finding_ids": sorted(pending_ids),
                    "reason": (
                        f"{exc.__class__.__name__}: {str(exc)[:400]}"
                    ),
                }
            )

    return hypotheses
