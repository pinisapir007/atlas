"""ATLAS Success Principles Engine V1 (2026-08-05).

ATLAS must not stop at collecting intelligence — its purpose is to
transform intelligence into actionable Success Principles. This
engine does NOT collect new intelligence and does NOT invent a new
evidence model: it analyzes real, already-recorded SuccessLaw records
(atlas.brain.models.SuccessLaw, the founder's own "extract the
principle, never copy the blueprint" mechanism, built 2026-08-03)
against real, already-measured Campaign outcomes (Campaign.
success_law_ids + cashflow.profit(), the exact association the "first
complete, measurable, closed-loop business cycle" milestone already
wired up) — turning two already-real, already-tested mechanisms into
one structured, verified Success Principle per law.

The founder's 8 analysis questions, and where each is honestly
answered (never a fabricated summary — see the output shape below):

  1. Why did successful cases succeed?     -> supporting_evidence,
                                               conditions_for_success
  2. Why did unsuccessful cases fail?      -> conditions_for_failure
  3. Which principles consistently recur   -> successful_case_count +
     across successful cases?                 the categories named in
                                               conditions_for_success
  4. Which mistakes recur across failed    -> the real, named failed
     cases?                                   campaigns in
                                               conditions_for_failure
                                               (this codebase has no
                                               structured root-cause/
                                               post-mortem field on
                                               Campaign, so the honest
                                               "mistake" recorded is
                                               the real fact itself:
                                               this campaign, under
                                               this principle, measured
                                               non-positive profit —
                                               never a fabricated root
                                               cause)
  5. Under what conditions does a          -> conditions_for_success
     principle work?
  6. Under what conditions does it fail?   -> conditions_for_failure
  7. Highest probability of success?       -> confidence_level (a
                                               real, measured success
                                               rate — never a
                                               fabricated score) and
                                               the report's own sort
                                               order (highest first)
  8. How can principles improve beyond     -> possible_improvements —
     current best practices?                  always the mandatory
                                               closing question,
                                               grounded in this
                                               principle's own real
                                               track record, never a
                                               fabricated answer

The output is NOT a summary: analyze_success_principles() returns a
structured list of SuccessPrinciple records, each carrying exactly
the 8 fields the founder specified (Principle, Supporting evidence,
Confidence level, Known limitations, Conditions for success,
Conditions for failure, Recommended implementation, Possible
improvements). The report always closes with CLOSING_QUESTION,
verbatim, regardless of how many principles exist.

ATLAS never copies a successful system: recommended_implementation is
always the real, founder-authored, transferable SuccessLaw.principle
text itself (structurally separate from source_description on
SuccessLaw — the same discipline that already keeps a Success Law
from being a blueprint), never a description of what a specific
external source did. possible_improvements always asks, never
answers, "what could outperform this principle's own track record" —
no LLM or real content-generation/analysis integration exists
anywhere in this codebase to honestly answer that, the same
never-fabricate-the-answer boundary intelligence_research_framework.py
already established for "Current World Leaders".

"Success" and "failure" are both derived from the one real, existing
signal this codebase has for it: cashflow.profit() on the real Goal a
Campaign executes under, for a Campaign whose success_law_ids names
this law. Real, positive profit is a success case; real, non-positive
profit is a failure case; unmeasured profit is neither — an untested
case is honestly unknown, not silently assumed either way. This is an
ASSOCIATION between a law and a real outcome, never a causal claim
that the law *caused* the profit — the exact same discipline
asset_value.success_law_lifetime_value() already applies one level
up (a single aggregate number); this engine is the same real signal,
broken out per real case so each of the founder's 8 questions can be
answered from real data instead of one aggregate.
"""

from dataclasses import dataclass, field

from atlas.brain.cashflow import profit as compute_profit
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.brain.models import SuccessLaw
from atlas.brain.time_service import TimeService
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry

CLOSING_QUESTION = "What can ATLAS do better than the current best?"


@dataclass
class SuccessPrinciple:
    """One verified Success Principle — exactly the 8 fields the
    founder specified, plus the minimum correlation/count fields
    every other structured record in this codebase already carries
    (e.g. Decision.id, ResearchFramework.created_at) so a principle
    can be traced back to its real source SuccessLaw and re-verified,
    never counted against the founder's named 8."""

    principle: str
    supporting_evidence: list[str]
    confidence_level: float | None
    known_limitations: list[str]
    conditions_for_success: list[str]
    conditions_for_failure: list[str]
    recommended_implementation: str
    possible_improvements: str
    source_success_law_id: str
    applicable_business_models: list[str] = field(default_factory=list)
    successful_case_count: int = 0
    failed_case_count: int = 0


@dataclass
class SuccessPrinciplesReport:
    """The engine's complete real output — a structured set of
    verified Success Principles, sorted by real probability of
    success (question 7), never a prose summary. Always closes with
    the mandatory question, verbatim, regardless of how many
    principles exist."""

    principles: list[SuccessPrinciple]
    generated_at: str
    closing_question: str = CLOSING_QUESTION


def _cited_evidence(law: SuccessLaw, knowledge: KnowledgeBase) -> list[str]:
    """Real evidence URLs this law was already grounded in — a direct
    read of Finding.evidence for each real, already-cited finding id,
    never re-derived or fabricated. A finding id that no longer
    resolves is silently skipped, not treated as an error — the same
    tolerance rank_success_laws_by_track_record() already extends to
    a law with no measured campaigns yet."""
    cited = []
    for finding_id in law.evidence_finding_ids:
        try:
            finding = knowledge.get_finding(finding_id)
        except KeyError:
            continue
        if finding.evidence:
            cited.append(finding.evidence)
    return cited


def _classify_linked_campaigns(
    law: SuccessLaw, campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry
) -> tuple[list[tuple[Campaign, float]], list[tuple[Campaign, float]], list[Campaign]]:
    """Every real Campaign this law was relevant/considered for
    (Campaign.success_law_ids), split into three real, honest groups:
    successful (real, positive measured profit), failed (real,
    non-positive measured profit), and unmeasured (no real profit
    reading exists yet — neither counted as success nor failure)."""
    linked = [c for c in campaigns.campaigns() if law.id in c.success_law_ids]

    successful: list[tuple[Campaign, float]] = []
    failed: list[tuple[Campaign, float]] = []
    unmeasured: list[Campaign] = []

    for campaign in linked:
        goal = None
        if campaign.goal_id:
            try:
                goal = memory.get_goal(campaign.goal_id)
            except KeyError:
                goal = None
        p = compute_profit(goal, kpis) if goal is not None else None
        if p is None:
            unmeasured.append(campaign)
        elif p > 0:
            successful.append((campaign, p))
        else:
            failed.append((campaign, p))

    return successful, failed, unmeasured


def _build_principle(law: SuccessLaw, campaigns: CampaignRegistry, knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry) -> SuccessPrinciple:
    successful, failed, unmeasured = _classify_linked_campaigns(law, campaigns, memory, kpis)

    success_categories = sorted({c.category for c, _ in successful if c.category})
    failure_categories = sorted({c.category for c, _ in failed if c.category})

    conditions_for_success = [f"category '{cat}'" for cat in success_categories] + [
        f"real campaign {c.id} ('{c.business_objective}') measured positive profit (${p:.2f})" for c, p in successful
    ]
    conditions_for_failure = [f"category '{cat}'" for cat in failure_categories] + [
        f"real campaign {c.id} ('{c.business_objective}') measured non-positive profit (${p:.2f})" for c, p in failed
    ]

    total_measured = len(successful) + len(failed)
    confidence_level = (len(successful) / total_measured) if total_measured else None

    known_limitations = []
    if not law.evidence_finding_ids:
        known_limitations.append("unevidenced hypothesis — no real Finding citation exists yet for this principle")
    if total_measured == 0:
        known_limitations.append("no real ATLAS campaign has measured a profit outcome for this principle yet — untested in real execution")
    if unmeasured:
        known_limitations.append(f"{len(unmeasured)} real campaign(s) linked to this principle have no measured profit yet")
    if failed and not successful:
        known_limitations.append("every real measured case for this principle failed so far — do not treat as validated")

    track_record_note = (
        f"{len(successful)} successful / {len(failed)} failed real case(s)"
        + (f" ({confidence_level:.0%} measured success rate)" if confidence_level is not None else " (no real case measured yet)")
    )
    possible_improvements = (
        f"{CLOSING_QUESTION} Current real track record for this principle: {track_record_note}. No automated "
        "answer exists — this requires real founder/analyst research, the same honest-question-never-"
        "fabricated-answer boundary intelligence_research_framework.py already established for its own "
        "'Current World Leaders' question."
    )

    return SuccessPrinciple(
        principle=law.principle,
        supporting_evidence=_cited_evidence(law, knowledge),
        confidence_level=confidence_level,
        known_limitations=known_limitations,
        conditions_for_success=conditions_for_success,
        conditions_for_failure=conditions_for_failure,
        recommended_implementation=law.principle,
        possible_improvements=possible_improvements,
        source_success_law_id=law.id,
        applicable_business_models=list(law.applicable_business_models),
        successful_case_count=len(successful),
        failed_case_count=len(failed),
    )


def analyze_success_principles(
    knowledge: KnowledgeBase,
    campaigns: CampaignRegistry,
    memory: BrainMemory,
    kpis: KPIRegistry,
    time_service: TimeService | None = None,
) -> SuccessPrinciplesReport:
    """The one real transformation this engine exists for: every real
    SuccessLaw on record, in to one verified SuccessPrinciple, out —
    analyzed against real, measured Campaign outcomes. Pure, read-
    only: never writes a SuccessLaw, a Campaign, a Finding, or
    anything else. Recomputed fresh every call from current real
    state (the same "nothing is permanently true" discipline decide()
    itself already relies on) — a principle's confidence_level and
    case counts change automatically as more real campaigns measure
    real outcomes, with no caching to go stale.

    Sorted by real probability of success (question 7): highest real
    measured success rate first (ties broken by real successful-case
    volume), every principle with zero real measured cases last. Among
    those, more real cited evidence outranks less — the same "the
    input's own evidence-quality ranking is the honest fallback until
    real outcomes exist to say more" precedent
    rank_success_laws_by_track_record() already established, applied
    here as the deterministic tiebreak rather than left to input
    order.
    """
    ts = time_service if time_service is not None else TimeService()
    laws = knowledge.success_laws()
    principles = [_build_principle(law, campaigns, knowledge, memory, kpis) for law in laws]
    principles.sort(
        key=lambda p: (p.confidence_level is not None, p.confidence_level or 0.0, p.successful_case_count, len(p.supporting_evidence)),
        reverse=True,
    )
    return SuccessPrinciplesReport(principles=principles, generated_at=ts.iso_timestamp())
