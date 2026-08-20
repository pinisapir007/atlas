"""reason() — the Cognitive Foundation's LLM-backed reasoning call
(2026-08-15, Design Lock approved). This is the one place a genuinely
novel relation/attribute/hypothesis (a "criterion" no programmer wrote
code for) can be formed at runtime: `question` is a caller/runtime-
composed string, never a hardcoded prompt template — the same generic
`AIProvider.complete_structured(prompt, fields)` seam every other real
call site in this codebase already uses (evidence_validation.py,
research_discovery/agent.py), just reached generically here instead of
through a fixed, single-purpose call site.

Deliberately kept in its own module, separate from reasoning.py — that
module's own docstring states "no new AI/network call" as its scope;
mixing a real LLM call into it would silently widen a scope that was
explicitly locked narrow.

Structural firewall (2026-08-15): this module never imports Delegator,
Registry, or RiskPolicy, and never will — a Claim this function produces
is knowledge/reasoning state, never permission to act. Verified by a
structural test (tests/brain/test_reasoning_claims.py), the same
inspect.getsource() technique already proven for
browser_scroll_advancer.py's own click/input/navigate exclusion.

No orchestration wiring exists here or anywhere yet (no CEOBrain/tick()
caller) — reason() is a real, tested, directly-callable capability today,
the same "real but not yet autonomous" precedent claude_executive.py
already established. Wiring it into an autonomous cycle is a separate,
later, deliberate step once a concrete consumer exists.
"""

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Claim
from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.base import AIProvider

# Bounds (2026-08-15 Design Lock, §11/G): a caller must curate what goes
# into a reasoning call, never dump the whole KnowledgeBase — both real,
# small, editable constants, the same class as MAX_DISCOVERY_CYCLES/
# MAX_REVISIT_PASSES elsewhere in this codebase, not a fabricated-precise
# number.
MAX_EVIDENCE_PER_REASON_CALL = 20
MAX_PRIOR_CLAIMS_PER_REASON_CALL = 5


class ReasonBoundsExceeded(ValueError):
    """Raised when a caller passes more evidence/prior-claim context than
    the stated bound — forces curation at the call site rather than
    silently truncating (which would hide which evidence was dropped)."""


def reason(
    question: str,
    subject_id: str,
    evidence_finding_ids: list[str],
    knowledge: KnowledgeBase,
    object_id: str | None = None,
    prior_claim_ids: list[str] | None = None,
    ai_provider: AIProvider | None = None,
    claim_type: str = "",
) -> Claim | None:
    """Composes context EXCLUSIVELY from the Findings/Claims explicitly
    passed in (never "the whole brain" — Design Lock §6), asks a real LLM
    a genuinely runtime-composed `question` via the existing
    `complete_structured()` seam, and returns a new Claim — or `None`.

    Returns `None` only when no coherent claim can be formed at all (the
    LLM's own `coherent_claim_possible` answer is "no", or it names no
    real predicate) — never when evidence is merely thin. A coherent
    hypothesis with insufficient evidence to conclude is still saved as a
    real Claim (predicate/object set, evidence_finding_ids exactly as
    passed, possibly empty) — claim_status() honestly derives
    "insufficient_evidence" for it later; the hypothesis itself is never
    discarded just because reason() was asked for an answer (Design Lock
    §1, "UNKNOWN IS KNOWLEDGE ABOUT WHAT WE DO NOT YET KNOW").

    Every prior Claim fed in via `prior_claim_ids` is labeled in the
    prompt, verbatim, as a prior hypothesis requiring re-validation — never
    presented as settled fact (Design Lock §F/§9, the learned-criteria
    reuse test).

    `evidence_finding_ids` on the returned Claim is EXACTLY what was
    passed in — never expanded by anything the LLM's own answer mentions.
    This, together with `contradicted_by_finding_ids` staying untouched
    here (a caller/future investigation adds those explicitly, later), is
    the self-contamination firewall in practice: this function can never
    let an LLM's own assertion count as evidence for itself.

    `object_id`, when the caller supplies it, always wins over whatever
    the LLM's own "object" answer says — the caller already knows which
    specific entity this question relates `subject_id` to; the LLM's
    "object" field is only ever used to fill in an attribute/value claim
    when the caller left `object_id` as None.

    Raises (never silently swallows) on: too much context passed
    (`ReasonBoundsExceeded`), or a real provider failure — a wrong Claim
    is worse than a loud failure, the same fail-closed discipline
    GeminiProviderError already establishes.

    `claim_type` (2026-08-16, optional, `""` default -- purely additive,
    every existing caller keeps the exact original behavior): passed
    straight through to the resulting Claim, unchanged. Never inferred
    from the LLM's own answer -- only the caller composing `question`
    actually knows whether it's asking for an inference, a hypothesis, or
    something else; guessing it from the response would be exactly the
    kind of after-the-fact classification `Claim.claim_type`'s own
    docstring forbids."""
    prior_claim_ids = prior_claim_ids or []
    if len(evidence_finding_ids) > MAX_EVIDENCE_PER_REASON_CALL:
        raise ReasonBoundsExceeded(
            f"{len(evidence_finding_ids)} evidence_finding_ids exceeds the "
            f"{MAX_EVIDENCE_PER_REASON_CALL} bound — curate the evidence passed in, don't dump the KnowledgeBase"
        )
    if len(prior_claim_ids) > MAX_PRIOR_CLAIMS_PER_REASON_CALL:
        raise ReasonBoundsExceeded(
            f"{len(prior_claim_ids)} prior_claim_ids exceeds the {MAX_PRIOR_CLAIMS_PER_REASON_CALL} bound"
        )

    findings = [knowledge.get_finding(fid) for fid in evidence_finding_ids]
    prior_claims = [knowledge.get_claim(cid) for cid in prior_claim_ids]

    evidence_text = (
        "\n".join(f"- {f.description} (evidence: {f.evidence or 'none cited'})" for f in findings)
        or "(no evidence supplied)"
    )
    prior_text = (
        "\n".join(
            f"- Prior hypothesis, NOT yet re-validated, treat as a lead to check, never as fact: "
            f"{c.predicate} {c.object_id or c.object_value or ''}".strip()
            for c in prior_claims
        )
        or "(no prior hypotheses supplied)"
    )

    prompt = (
        f"Question: {question}\n\n"
        f"Real evidence:\n{evidence_text}\n\n"
        f"Prior hypotheses (not facts, still require re-validation):\n{prior_text}\n"
    )
    fields = {
        "coherent_claim_possible": (
            "yes or no — can a specific, auditable claim (a predicate, and optionally what it relates to) "
            "be formed from this, even a tentative one that still lacks enough evidence to conclude?"
        ),
        "predicate": (
            "a few words naming the relationship or attribute this suggests — empty string if "
            "coherent_claim_possible is no"
        ),
        "object": (
            "the entity or value this predicate relates the subject to, or empty string if this is a claim "
            "about the subject alone"
        ),
        "supporting_points": "what in the evidence supports this",
        "counter_considerations": "what would make this false, or an alternative explanation that fits the same observations",
    }

    provider = ai_provider if ai_provider is not None else get_ai_provider()
    result = provider.complete_structured(prompt, fields)

    coherent = result.get("coherent_claim_possible", "").strip().lower().startswith("y")
    predicate = result.get("predicate", "").strip()
    if not coherent or not predicate:
        return None

    if object_id is not None:
        claim_object_id, claim_object_value = object_id, None
    else:
        object_value = result.get("object", "").strip()
        claim_object_id, claim_object_value = None, (object_value or None)

    claim = Claim(
        subject_id=subject_id,
        predicate=predicate,
        object_id=claim_object_id,
        object_value=claim_object_value,
        evidence_finding_ids=list(evidence_finding_ids),
        prior_claim_ids=list(prior_claim_ids),
        question=question,
        source="reason_llm",
        claim_type=claim_type,
    )
    knowledge.save_claim(claim)
    return claim
