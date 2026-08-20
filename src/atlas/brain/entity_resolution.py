"""Entity Resolution (2026-08-17, ONE BRAIN Root Implementation) --
canonical reasoning identity, COMPUTED fresh on every call, never
persisted -- the same "nothing is permanently true, recompute"
discipline decide()/confidence_score()/Strategist already establish
throughout this codebase.

Root finding this replaces (proven, not assumed): a purely-computed
"lexicographically smallest representative" is NOT a stable identity --
it can drift as new aliases join an equivalence class, and Bridge 1's
own persisted `Opportunity.subject` lookup depends on stability, so a
drifting representative would silently create a second, duplicate
Opportunity for the same real-world entity. The fix: once a real
`Opportunity` exists for a member of an equivalence class, that
Opportunity's own persisted `subject` becomes a PINNED anchor --
permanent, never rewritten -- and future resolution always prefers it
over a freshly-recomputed representative.

Uses `Claim(predicate="possibly_same_as")` as pure identity-relation
EVIDENCE (only `claim_status() == "supported"` participates -- ambiguous/
contradicted/insufficient_evidence relations are excluded, never
guessed into inclusion) -- never as workflow state. No autonomous
matcher exists here or is proposed here: producing a real
`possibly_same_as` Claim from real corroborating evidence is a
separate, later, deliberate decision: this module only ever CONSUMES
already-supported relations, read-only.

Two-pinned-anchors fail-closed rule (the other proven-necessary case):
when an equivalence class already contains MORE THAN ONE distinct
pinned `Opportunity.subject`, this is a real identity conflict between
two already-real business entities (each possibly already carrying its
own goal_id/Campaign/Ledger consequences) -- merging, deleting, or
silently choosing one would be a destructive, irreversible-feeling
business decision this module has no authority to make. The safe,
read-time, non-destructive answer: refuse to improve the grouping for
that specific class (return the input unchanged, i.e. fall back to
today's pre-canonicalization behavior for exactly that ambiguous
class) -- see console.find_warnings() for how this is surfaced to the
founder, non-destructively, without Task/Goal/Proposal.
"""

from atlas.brain.claims import claim_status
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.opportunities import OpportunityStore

POSSIBLY_SAME_AS = "possibly_same_as"


def _equivalence_class(subject_id: str, knowledge: KnowledgeBase) -> set[str]:
    """Transitive closure over supported possibly_same_as claims, walked
    in both directions (subject_id->object_id and the reverse) since a
    relation between two subjects may have been recorded from either
    side. Always includes subject_id itself, even with zero real
    claims -- the trivial, single-member class, which is exactly
    today's behavior when no aliasing has ever been recorded."""
    seen = {subject_id}
    frontier = [subject_id]
    while frontier:
        current = frontier.pop()
        for claim in knowledge.claims(subject_id=current, predicate=POSSIBLY_SAME_AS):
            if claim.object_id and claim_status(claim) == "supported" and claim.object_id not in seen:
                seen.add(claim.object_id)
                frontier.append(claim.object_id)
        for claim in knowledge.claims(predicate=POSSIBLY_SAME_AS):
            if claim.object_id == current and claim_status(claim) == "supported" and claim.subject_id not in seen:
                seen.add(claim.subject_id)
                frontier.append(claim.subject_id)
    return seen


def resolve_canonical_subject(subject_id: str, category: str, knowledge: KnowledgeBase, opportunities: OpportunityStore) -> str:
    """The one, general grouping-key resolver: given a real, local
    subject_id, returns the subject string Bridge 1 should group
    Findings under for this call.

    - Zero existing pinned Opportunity in the equivalence class: no
      anchor to respect yet -- returns a deterministic (lexicographically
      smallest), purely-computed representative. Safe: nothing persisted
      depends on this choice being stable yet.
    - Exactly one existing pinned Opportunity.subject in the class:
      returns it, unconditionally -- the anchor always wins over a
      fresher/different computed representative.
    - Two or more DISTINCT existing pinned Opportunity.subjects in the
      class: a real, unresolved identity conflict -- returns subject_id
      UNCHANGED (refuses to improve/merge the grouping for this specific
      class), so Bridge 1's existing_by_key lookup keeps finding each
      real Opportunity under its own real, already-persisted subject,
      and no third, duplicate Opportunity can ever be created from the
      ambiguous class."""
    equivalence_class = _equivalence_class(subject_id, knowledge)
    pinned = sorted(
        {
            o.subject
            for o in opportunities.opportunities()
            if o.category == category and o.subject in equivalence_class
        }
    )
    if len(pinned) == 1:
        return pinned[0]
    if len(pinned) >= 2:
        return subject_id
    return min(equivalence_class)


def detect_pinned_identity_conflicts(knowledge: KnowledgeBase, opportunities: OpportunityStore) -> list[tuple[str, str, str]]:
    """Real, read-only detection of every pair of existing, persisted
    Opportunities (same category, different subject) that fall inside
    one supported possibly_same_as equivalence class -- the exact
    condition resolve_canonical_subject() above refuses to auto-resolve.
    Returns (category, subject_a, subject_b) tuples, deduplicated. Never
    mutates anything -- the sole consumer is console.find_warnings()."""
    conflicts: list[tuple[str, str, str]] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    opportunities_list = opportunities.opportunities()
    for i, opportunity_a in enumerate(opportunities_list):
        for opportunity_b in opportunities_list[i + 1 :]:
            if opportunity_a.category != opportunity_b.category or opportunity_a.subject == opportunity_b.subject:
                continue
            if opportunity_b.subject in _equivalence_class(opportunity_a.subject, knowledge):
                key = (opportunity_a.category,) + tuple(sorted([opportunity_a.subject, opportunity_b.subject]))
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    conflicts.append(key)
    return conflicts
