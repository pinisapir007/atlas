"""Stage 7 / Layer 2 — Pattern & Hypothesis Formation.

Layer 1 answers: "What did ATLAS actually observe?"
Layer 2 answers: "Do multiple durable observations suggest a recurring
relationship worth remembering and testing?"

Architectural boundary:
- Reads ONLY durable Finding records from KnowledgeBase.
- Never imports or depends on Browser/YouTube/PDF/Image/Audio/Video
  plugins or their transient observation types.
- A pattern hypothesis is knowledge state, never permission to act.
- Pattern formation may use repeated real observations even when source
  independence is still UNKNOWN. independent_source_count() is preserved
  as evidence-strength metadata, not fabricated into a hard proof gate.
- Every generated result is claim_type="hypothesis", never a validated
  conclusion merely because observations support forming the hypothesis.
- Existing Claim self-contamination rules remain unchanged: only Finding
  ids can be evidence; Claims may only be prior hypotheses/context.

This module is deliberately NOT wired into CEOBrain.tick() yet. It is a
bounded, directly-callable Layer 2 capability first; autonomous wiring
comes only after qualification.
"""

from dataclasses import dataclass
import re

from atlas.brain.evidence_provenance import independent_source_count
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Claim, Finding
from atlas.brain.reasoning_claims import (
    MAX_EVIDENCE_PER_REASON_CALL,
    MAX_PRIOR_CLAIMS_PER_REASON_CALL,
    reason,
)
from atlas.integrations.base import AIProvider

MIN_UNIQUE_OBSERVATIONS_FOR_PATTERN = 2
MAX_PATTERN_GROUPS_PER_RUN = 3

# Semantic candidate formation is deliberately bounded. The selector may
# inspect at most this many real Findings from one broad category group
# and may choose at most this many for one coherent candidate pattern.
MAX_FINDINGS_PER_CANDIDATE_SCAN = 12
MAX_FINDINGS_PER_PATTERN_CANDIDATE = 6


@dataclass(frozen=True)
class PatternEvidenceGroup:
    """One bounded set of real durable observations worth asking about.

    `independent_sources` is descriptive evidence-strength information.
    Zero does NOT mean "fake evidence"; it means provenance is not strong
    enough to prove real-world-source independence yet.
    """

    category: str
    finding_ids: tuple[str, ...]
    subject_ids: tuple[str, ...]
    independent_sources: int

    @property
    def scope_id(self) -> str:
        return f"pattern_scope::{self.category}"


def _observation_identity(finding: Finding) -> tuple[str, ...]:
    """Exact Layer-2 duplicate identity, never semantic guessing.

    Atomic Layer 1 already prevents exact re-persistence through its own
    seam. This additional read-time guard protects Layer 2 from legacy
    coarse writers that may have persisted the same unchanged observation
    more than once.

    Locator participates because two different timestamp/page observations
    from one real source can legitimately be different evidence units.
    Exact excerpt is preferred when present; otherwise description is the
    best durable text actually stored for this Finding.
    """
    return (
        finding.evidence.strip(),
        finding.content_hash.strip(),
        finding.evidence_locator.strip(),
        (finding.evidence_excerpt or finding.description).strip(),
        finding.category.strip(),
        finding.subject.strip(),
        finding.market.strip(),
    )


def _unique_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, ...]] = set()
    unique: list[Finding] = []

    for finding in findings:
        identity = _observation_identity(finding)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(finding)

    return unique


def candidate_pattern_groups(
    knowledge: KnowledgeBase,
    category: str | None = None,
) -> list[PatternEvidenceGroup]:
    """Find bounded category-level evidence groups worth reasoning over.

    Category is only a retrieval/scope boundary, not the pattern itself.
    No predicate, business rule, relationship, trend, or success criterion
    is hardcoded here; the actual possible pattern is formed at runtime by
    reason() from the observations.

    At least two UNIQUE durable observations are required. We deliberately
    do not require two proven-independent sources here: hypothesis
    generation and hypothesis validation are different epistemic stages.
    Unknown provenance remains visible through `independent_sources`.
    """
    grouped: dict[str, list[Finding]] = {}

    for finding in knowledge.findings():
        finding_category = finding.category.strip()
        if not finding_category:
            continue
        if category is not None and finding_category != category:
            continue
        grouped.setdefault(finding_category, []).append(finding)

    candidates: list[PatternEvidenceGroup] = []

    for finding_category in sorted(grouped):
        unique = _unique_findings(grouped[finding_category])

        if len(unique) < MIN_UNIQUE_OBSERVATIONS_FOR_PATTERN:
            continue

        # reason() has its own hard evidence bound. Keep the newest bounded
        # window rather than silently exceeding it. KnowledgeBase preserves
        # insertion order, so the tail is the latest persisted evidence.
        selected = unique[-MAX_EVIDENCE_PER_REASON_CALL:]

        candidates.append(
            PatternEvidenceGroup(
                category=finding_category,
                finding_ids=tuple(f.id for f in selected),
                subject_ids=tuple(
                    sorted({f.subject for f in selected if f.subject})
                ),
                independent_sources=independent_source_count(selected),
            )
        )

    return candidates



def select_semantic_pattern_candidate(
    group: PatternEvidenceGroup,
    knowledge: KnowledgeBase,
    ai_provider: AIProvider | None = None,
) -> PatternEvidenceGroup | None:
    """Select one coherent semantic subset from a broad category group.

    This is a CURATION step only. It never creates a Finding, Claim,
    pattern, conclusion, or action. The provider may only choose among
    the real numbered Findings explicitly supplied here.

    Fail-closed rules:
    - fewer than two real observations -> None;
    - provider says no coherent candidate -> None;
    - malformed/out-of-range selection -> None;
    - fewer than two unique selected observations -> None.

    The selected subset remains ordinary Finding evidence. Semantic
    selection itself never becomes evidence and is never persisted.
    """
    findings = [
        knowledge.get_finding(fid)
        for fid in group.finding_ids
    ]
    findings = _unique_findings(findings)

    if len(findings) < MIN_UNIQUE_OBSERVATIONS_FOR_PATTERN:
        return None

    if any(f.category.strip() != group.category for f in findings):
        raise ValueError(
            "PatternEvidenceGroup contains Findings outside its category"
        )

    # Keep the candidate scan bounded and favor the most recently
    # persisted unique evidence, matching the existing bounded-window
    # discipline elsewhere in this module.
    findings = findings[-MAX_FINDINGS_PER_CANDIDATE_SCAN:]

    observation_lines = []
    for number, finding in enumerate(findings, 1):
        observation_lines.append(
            f"{number}. "
            f"subject={finding.subject or 'UNKNOWN'} | "
            f"market={finding.market or 'UNKNOWN'} | "
            f"source={finding.source or 'UNKNOWN'} | "
            f"provider={finding.provider or 'UNKNOWN'} | "
            f"claimant={finding.claimant or 'UNKNOWN'} | "
            f"role={finding.evidence_role or 'UNKNOWN'} | "
            f"observation={finding.description[:900]}"
        )

    prompt = (
        "You are curating REAL observations for later hypothesis "
        "formation. Select ONE subset whose observations are genuinely "
        "semantically related and together suggest a recurring pattern, "
        "relationship, common mechanism, repeated friction, repeated "
        "behavior, or reusable business signal worth reasoning about.\n\n"
        "Do NOT merely choose observations because they share the broad "
        "category. Do NOT invent missing facts. Do NOT claim causation. "
        "Do NOT treat the selection itself as proof. If no subset of at "
        "least two observations forms one coherent candidate pattern, "
        "answer no.\n\n"
        f"Category: {group.category}\n"
        "Real observations:\n"
        + "\n".join(observation_lines)
    )

    fields = {
        "pattern_candidate_possible": (
            "yes or no — is there one coherent semantic subset of at "
            "least two supplied observations worth testing as a pattern?"
        ),
        "member_numbers": (
            "comma-separated observation numbers from the supplied list "
            f"only; choose between 2 and "
            f"{MAX_FINDINGS_PER_PATTERN_CANDIDATE}; empty if no"
        ),
        "candidate_theme": (
            "short neutral phrase describing what makes the selected "
            "observations related; not a conclusion"
        ),
        "reason": (
            "one concise explanation of why these observations belong "
            "together and why unrelated observations were excluded"
        ),
    }

    provider = (
        ai_provider
        if ai_provider is not None
        else get_ai_provider()
    )

    result = provider.complete_structured(prompt, fields)

    possible = (
        result.get("pattern_candidate_possible", "")
        .strip()
        .lower()
        .startswith("y")
    )
    if not possible:
        return None

    raw_numbers = result.get("member_numbers", "")
    numbers = [
        int(value)
        for value in re.findall(r"\d+", raw_numbers)
    ]

    # Preserve provider order while removing repeated numbers.
    unique_numbers = list(dict.fromkeys(numbers))

    if not (
        MIN_UNIQUE_OBSERVATIONS_FOR_PATTERN
        <= len(unique_numbers)
        <= MAX_FINDINGS_PER_PATTERN_CANDIDATE
    ):
        return None

    if any(number < 1 or number > len(findings) for number in unique_numbers):
        return None

    selected = [
        findings[number - 1]
        for number in unique_numbers
    ]
    selected = _unique_findings(selected)

    if len(selected) < MIN_UNIQUE_OBSERVATIONS_FOR_PATTERN:
        return None

    return PatternEvidenceGroup(
        category=group.category,
        finding_ids=tuple(f.id for f in selected),
        subject_ids=tuple(
            sorted({f.subject for f in selected if f.subject})
        ),
        independent_sources=independent_source_count(selected),
    )

def form_pattern_hypothesis(
    group: PatternEvidenceGroup,
    knowledge: KnowledgeBase,
    ai_provider: AIProvider | None = None,
) -> Claim | None:
    """Ask the existing Cognitive Foundation to form one pattern hypothesis.

    Re-validates the supplied group from real KnowledgeBase state rather
    than trusting a caller-created PatternEvidenceGroup blindly.

    Exact-evidence idempotency: if an active hypothesis for this pattern
    scope already used exactly this evidence set, return that Claim without
    spending another LLM call or creating a duplicate hypothesis.

    If new evidence has arrived, up to the existing prior-claim bound is
    supplied to reason() explicitly as prior hypotheses, never as evidence.
    """
    findings = [knowledge.get_finding(fid) for fid in group.finding_ids]
    findings = _unique_findings(findings)

    if len(findings) < MIN_UNIQUE_OBSERVATIONS_FOR_PATTERN:
        return None

    if any(f.category.strip() != group.category for f in findings):
        raise ValueError(
            "PatternEvidenceGroup contains Findings outside its category"
        )

    if len(findings) > MAX_EVIDENCE_PER_REASON_CALL:
        raise ValueError(
            "PatternEvidenceGroup exceeds the reasoning evidence bound"
        )

    evidence_ids = [f.id for f in findings]
    evidence_id_set = set(evidence_ids)

    prior_hypotheses = [
        claim
        for claim in knowledge.claims(subject_id=group.scope_id)
        if claim.claim_type == "hypothesis"
        and claim.superseded_by_id is None
    ]

    # Same real evidence set -> same already-formed hypothesis context.
    # Do not repeatedly ask an LLM to rediscover it.
    for existing in prior_hypotheses:
        if set(existing.evidence_finding_ids) == evidence_id_set:
            return existing

    prior_ids = [
        claim.id
        for claim in prior_hypotheses[-MAX_PRIOR_CLAIMS_PER_REASON_CALL:]
    ]

    independent_sources = independent_source_count(findings)

    metadata_lines = []
    for finding in findings:
        metadata_lines.append(
            " | ".join(
                [
                    f"finding_id={finding.id}",
                    f"subject={finding.subject or 'UNKNOWN'}",
                    f"market={finding.market or 'UNKNOWN'}",
                    f"provider={finding.provider or 'UNKNOWN'}",
                    f"claimant={finding.claimant or 'UNKNOWN'}",
                    f"evidence_role={finding.evidence_role or 'UNKNOWN'}",
                    f"observed_at={finding.observed_at or 'UNKNOWN'}",
                    f"locator={finding.evidence_locator or 'SOURCE_LEVEL'}",
                ]
            )
        )

    question = (
        "Determine whether these real observations suggest ONE recurring, "
        "reusable pattern or common relationship worth testing further. "
        "Do not merely summarize the observations. Do not invent a pattern "
        "when the observations are unrelated. Do not infer causation from "
        "correlation. A pattern hypothesis may be formed even when source "
        "independence is not yet proven, but UNKNOWN provenance must never "
        "be described as independent validation. If no specific recurring "
        "relationship is coherently suggested, answer that no coherent "
        "claim is possible.\n\n"
        f"Pattern scope category: {group.category}\n"
        f"Unique durable observations: {len(findings)}\n"
        f"Independent real-world source count currently proven: "
        f"{independent_sources}\n"
        "Observation metadata:\n"
        + "\n".join(f"- {line}" for line in metadata_lines)
    )

    return reason(
        question=question,
        subject_id=group.scope_id,
        evidence_finding_ids=evidence_ids,
        knowledge=knowledge,
        prior_claim_ids=prior_ids,
        ai_provider=ai_provider,
        claim_type="hypothesis",
    )


def discover_pattern_hypotheses(
    knowledge: KnowledgeBase,
    ai_provider: AIProvider | None = None,
    category: str | None = None,
    max_groups: int = MAX_PATTERN_GROUPS_PER_RUN,
) -> list[Claim]:
    """Bounded Layer-2 pass over candidate evidence groups.

    Directly callable only for now — deliberately no CEO/tick wiring.
    Returns existing idempotent hypotheses as well as newly formed ones;
    callers can therefore reason about current Layer-2 state without
    interpreting "no new write" as "no hypothesis exists".
    """
    if max_groups < 0:
        raise ValueError("max_groups must be >= 0")

    hypotheses: list[Claim] = []

    for broad_group in candidate_pattern_groups(
        knowledge,
        category=category,
    )[:max_groups]:
        # If an active Layer-2 hypothesis already exists for this scope
        # and NO Finding in the current bounded broad group is newer than
        # that hypothesis, the evidence environment has not changed since
        # the last successful semantic-selection/reasoning pass.
        #
        # Reuse the durable hypothesis directly: no second semantic LLM
        # selection call and no second reasoning call. As soon as genuinely
        # new Finding evidence arrives later, created_at becomes newer and
        # the normal semantic-selection path runs again.
        existing = [
            claim
            for claim in knowledge.claims(
                subject_id=broad_group.scope_id
            )
            if claim.claim_type == "hypothesis"
            and claim.source == "reason_llm"
            and claim.superseded_by_id is None
        ]

        if existing:
            latest = max(
                existing,
                key=lambda claim: claim.created_at,
            )
            broad_findings = [
                knowledge.get_finding(fid)
                for fid in broad_group.finding_ids
            ]

            if all(
                finding.created_at <= latest.created_at
                for finding in broad_findings
            ):
                hypotheses.append(latest)
                continue

        semantic_group = select_semantic_pattern_candidate(
            broad_group,
            knowledge,
            ai_provider=ai_provider,
        )
        if semantic_group is None:
            continue

        hypothesis = form_pattern_hypothesis(
            semantic_group,
            knowledge,
            ai_provider=ai_provider,
        )
        if hypothesis is not None:
            hypotheses.append(hypothesis)

    return hypotheses
