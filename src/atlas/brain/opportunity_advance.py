"""Bridge 1: Finding -> Opportunity (2026-08-11, docs/
DESIGN_BRIDGE_1_FINDING_TO_OPPORTUNITY.md). A Connectivity Bridge, not a
Capability -- adds zero new judgment. It only recognizes a real, already-
computable structural fact (a real (category, subject) pair has crossed
decision_engine.MIN_INDEPENDENT_SOURCES -- the exact same evidence bar
decide()/exploration_gate.py already reuse, a third reuse here, not a new
threshold) and performs a mechanical find-or-create-and-accumulate on
Opportunity. Deleting this module would leave Finding-accumulation and
Opportunity Universal Core each fully intact and working independently --
proof it holds no capability of its own (feedback_bridge_design_principles:
"every Bridge must disappear").

Preserves meaning, never adds interpretation (the same memo's second
rule): the real Opportunity created here cites real Finding ids and a
description built directly from real Finding text -- never a fabricated
summary, never an inferred judgment about the candidate's quality.

Explicit non-goals, per the locked Design doc: never sets `score` or
`competition` (each channel's own concern); never advances `stage` past
"discovered" (who does that, and when, is a real, still-open question --
not answered here); never calls Reasoning or decide(); never touches
Research Discovery's own Finding-creation mechanism.
"""

from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES
from atlas.brain.entity_resolution import resolve_canonical_subject
from atlas.brain.evidence_provenance import independent_source_count
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding, Opportunity, now
from atlas.brain.opportunities import OpportunityStore


def _sourced_findings_by_subject(knowledge: KnowledgeBase, opportunities: OpportunityStore) -> dict[tuple[str, str], list[Finding]]:
    """Real, evidenced Findings grouped by (category, canonical subject)
    -- a Finding with no real subject can't identify a specific candidate
    (Opportunity's own core definition), so subject="" Findings are
    deliberately excluded here, not silently folded into a category-wide
    bucket.

    Entity Convergence (2026-08-17, ONE BRAIN Root Implementation,
    additive to this Bridge's original grouping): each Finding's own
    raw, local `subject` is resolved through entity_resolution.
    resolve_canonical_subject() before grouping -- so Findings from
    different senses/local-identity-schemes that are genuinely the same
    real-world entity (linked by a real, supported possibly_same_as
    Claim) converge onto one grouping key, while an already-pinned
    Opportunity.subject is never silently moved (see
    resolve_canonical_subject()'s own contract for the full rule,
    including the two-conflicting-pinned-anchors fail-closed case).
    Finding.subject itself is never rewritten on disk -- only this
    grouping key is computed, fresh, every call. With zero
    possibly_same_as Claims anywhere (today's real, default state),
    resolve_canonical_subject() returns each subject unchanged, so this
    grouping is byte-for-byte identical to the original, pre-Entity-
    Convergence behavior -- a real, verified backward-compatibility
    property, not just an assumption."""
    grouped: dict[tuple[str, str], list[Finding]] = {}
    for finding in knowledge.findings():
        if not finding.evidence or not finding.subject:
            continue
        canonical_subject = resolve_canonical_subject(finding.subject, finding.category, knowledge, opportunities)
        grouped.setdefault((finding.category, canonical_subject), []).append(finding)
    return grouped


def _real_description(category: str, subject: str, findings: list[Finding]) -> str:
    # Reuses the first real Finding's own real text rather than
    # fabricating a summary -- preserves meaning, adds no interpretation
    # of its own (feedback_bridge_design_principles).
    return f"Real candidate '{subject}' in category '{category}', based on {len(findings)} real Finding(s): {findings[0].description}"


def advance_opportunities_from_findings(knowledge: KnowledgeBase, opportunities: OpportunityStore) -> list[Opportunity]:
    """The real bridge entry point -- for every (category, subject) pair
    whose real, evidenced Finding count has crossed MIN_INDEPENDENT_SOURCES,
    finds the existing real Opportunity or creates one, and keeps its
    evidence_finding_ids in sync with every real Finding actually
    contributing to it. Idempotent and side-effect-free when nothing real
    has changed: only returns Opportunities that were genuinely newly
    created or whose real evidence just grew this call, the same
    "don't touch what didn't change" discipline every other *_advance.py
    bridge in this codebase already follows."""
    changed: list[Opportunity] = []
    existing_by_key = {(o.category, o.subject): o for o in opportunities.opportunities()}

    for (category, subject), findings in _sourced_findings_by_subject(knowledge, opportunities).items():
        # Independent-source counting (2026-08-17, ONE BRAIN Evidence
        # Provenance): the same real evidence_provenance.
        # independent_source_count() decision_engine.decide() itself
        # now uses -- real Findings sharing a known claimant or a known
        # real-world origin (the same underlying source, observed twice
        # through different senses, or syndicated content) count once,
        # never once-per-Finding. UNKNOWN provenance never inflates the
        # count either. MIN_INDEPENDENT_SOURCES itself is unchanged.
        if independent_source_count(findings) < MIN_INDEPENDENT_SOURCES:
            continue

        real_finding_ids = sorted(f.id for f in findings)
        opportunity = existing_by_key.get((category, subject))

        if opportunity is None:
            opportunity = Opportunity(
                subject=subject,
                description=_real_description(category, subject, findings),
                category=category,
                evidence_finding_ids=real_finding_ids,
            )
            opportunities.save_opportunity(opportunity)
            changed.append(opportunity)
        elif sorted(opportunity.evidence_finding_ids) != real_finding_ids:
            # Real evidence changed -- record it and refresh updated_at,
            # but never call transition(): stage/history are explicitly
            # not this bridge's responsibility (locked Design doc).
            opportunity.evidence_finding_ids = real_finding_ids
            opportunity.updated_at = now()
            opportunities.save_opportunity(opportunity)
            changed.append(opportunity)

    return changed
