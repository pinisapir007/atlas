"""Business Opportunity Evaluation (Milestone 2, docs/
DESIGN_BUSINESS_OPPORTUNITY_EVALUATION.md, docs/
ARCHITECTURE_INTENT_BUSINESS_OPPORTUNITY_EVALUATION.md, docs/
CAPABILITY_DEFINITION_BUSINESS_OPPORTUNITY_EVALUATION.md -- all locked
before this was written) -- the real, missing link Root Cause A's own
closure made possible: ATLAS can now autonomously discover a specific
Subject (Milestone 1), but nothing evaluated it as a businessperson
would (real pros/cons, a ready/wait classification, a reasoned ranking)
until this.

Confirmed, not assumed, that no existing mechanism already does this
(Capability Definition doc's own input/output table): `explain_
opportunity_subject()` evaluates one Subject alone, no classification.
`rank_opportunities()` orders every Subject in a category, no per-
candidate detail, no classification. `reasoning.compare_opportunities()`
compares 2+ real Opportunities but only via 2 narrow factors
(competition + evidence count) and produces a single preference, never
a ready/wait split. None of the three produce what a real business
evaluation needs: an honest classification of whether a candidate is
even ready to be acted on yet.

Read-only, exactly like explain_opportunity_subject()/compare_
opportunities() -- never mutates an existing Opportunity (no stage
advance, no field write). This is a locked architectural choice, not
an oversight: Root Cause B's own RCA (docs/ROOT_CAUSE_ANALYSIS_RUN4.md)
found a real bug the same day this was designed, caused by exactly the
opposite pattern -- two uncoordinated writers to one shared field
(SimplePrioritizer vs. Bridge 3 on Task.priority_score). Staying pure
here avoids that whole class of bug by construction, not luck.

Deliberately does NOT call reasoning.compare_opportunities() -- decided
explicitly in Architecture Intent, not by default: Reasoning's real
factors (competition + evidence count) are narrower than the richer
factors this module already computes for the ready/wait classification;
routing through Reasoning would discard richness already computed, not
add any. The real, honest cost of this choice: Reasoning still has no
live consumer anywhere in the codebase after this module exists --
named directly in Architecture Intent, not hidden, and logged as a
real Backlog item (docs/BUSINESSMAN_V1_SOURCE_OF_TRUTH.md) for a future
richer Reasoning capability that could characterize real relationships
between opportunities (complementary vs. competing) rather than just a
single winner.

Never fabricates a factor with no real source (market demand, real
affiliate-program verification, audience reach, dollar revenue
potential) -- these are named explicitly as unknown, never guessed.
"""

from atlas.brain.confidence import CATEGORY_TASK_CATEGORIES, recency_score, source_corroboration_score, weighted_average_of_available
from atlas.brain.decision_engine import MIN_INDEPENDENT_SOURCES
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Opportunity
from atlas.brain.opportunities import OpportunityStore

# Stated, editable assumption -- same class as reasoning.REASONING_WEIGHTS/
# confidence.WEIGHTS, not a fabricated precision claim. Evidence weighted
# highest (the most directly verifiable signal); execution-readiness next
# (a real structural fact, not a judgment call); recency and competition
# (when known) round it out.
EVALUATION_WEIGHTS = {"evidence": 0.4, "recency": 0.3, "execution_readiness": 0.2, "competition": 0.1}

# Real factors with no real data source anywhere in this codebase today
# (verified directly, Capability Definition step) -- always reported as
# unknown, never guessed at.
ALWAYS_UNKNOWN_FACTORS = ["market_demand", "affiliate_program_exists", "audience_reach", "revenue_potential_dollars"]


def _execution_ready(category: str) -> bool:
    """A real, structural fact (does a real dispatchable execution
    channel already exist for this category) -- not a judgment call.
    Doubles honestly as the only real, non-fabricated proxy available
    today for both time-to-revenue and capability-fit."""
    return bool(CATEGORY_TASK_CATEGORIES.get(category))


def _real_risks(opportunity: Opportunity, execution_ready: bool) -> list[str]:
    """Real, concrete risk statements -- never a fabricated numeric risk
    score. Mirrors the honest-gap discipline opportunity_ranking.
    _assess_opportunity_risks() already established one level up."""
    risks = []
    if len(opportunity.evidence_finding_ids) < MIN_INDEPENDENT_SOURCES:
        risks.append(
            f"only {len(opportunity.evidence_finding_ids)} independent source(s) -- below the standing "
            f"{MIN_INDEPENDENT_SOURCES}-source policy bar for a real commitment"
        )
    if opportunity.competition is None:
        risks.append("no real competitive-intensity assessment exists yet for this candidate")
    if not execution_ready:
        risks.append(f"no real execution channel exists yet for category '{opportunity.category}' -- time-to-revenue unknown")
    risks.append("no real market demand data exists for this candidate -- evidence reflects attention found, not verified demand")
    return risks


def evaluate_opportunity(opportunity: Opportunity, knowledge: KnowledgeBase) -> dict:
    """The real per-candidate evaluation -- real factors (or None,
    honestly, when no real source exists), a real ready/wait
    classification (reuses decision_engine.MIN_INDEPENDENT_SOURCES,
    the same standing evidence bar already reused three times elsewhere
    in this codebase -- not a new, invented threshold), and a
    deterministic reasoning string citing the real numbers behind it.
    Never mutates `opportunity` -- read-only, recomputed fresh every
    call, exactly like explain_opportunity_subject()/
    compare_opportunities()."""
    evidence_component = source_corroboration_score(opportunity.category, knowledge, subject=opportunity.subject)
    recency_component = recency_score(opportunity.category, knowledge, subject=opportunity.subject)
    competition_component = (1.0 - opportunity.competition) if opportunity.competition is not None else None
    execution_ready = _execution_ready(opportunity.category)
    execution_component = 1.0 if execution_ready else 0.0

    combined = weighted_average_of_available(
        {
            "evidence": evidence_component,
            "recency": recency_component,
            "competition": competition_component,
            "execution_readiness": execution_component,
        },
        EVALUATION_WEIGHTS,
    )

    classification = "ready" if len(opportunity.evidence_finding_ids) >= MIN_INDEPENDENT_SOURCES else "wait"

    unknown = (["competition"] if opportunity.competition is None else []) + list(ALWAYS_UNKNOWN_FACTORS)

    reasoning = (
        f"'{opportunity.subject}' ({opportunity.category}): {classification} -- "
        f"{len(opportunity.evidence_finding_ids)} independent source(s) "
        f"(bar: {MIN_INDEPENDENT_SOURCES}), execution channel {'exists' if execution_ready else 'does not exist yet'}, "
        f"combined score {'unscored' if combined is None else f'{combined:.2f}'}. "
        f"Unknown: {', '.join(unknown)}."
    )

    return {
        "opportunity_id": opportunity.id,
        "subject": opportunity.subject,
        "category": opportunity.category,
        "classification": classification,
        "factors": {
            "evidence": evidence_component,
            "recency": recency_component,
            "competition": competition_component,
            "execution_readiness": execution_component,
            "combined_score": combined,
        },
        "unknown": unknown,
        "risks": _real_risks(opportunity, execution_ready),
        "reasoning": reasoning,
    }


def evaluate_opportunities(category: str, opportunities: OpportunityStore, knowledge: KnowledgeBase) -> dict:
    """The real Milestone 2 entry point -- every real Opportunity in
    `category`, each evaluated honestly. Returns real "ready" candidates
    (sorted by combined_score descending, None-safe) separately from
    real "wait" candidates -- never a single forced ranking across both,
    since a "wait" candidate isn't yet comparable to a "ready" one.
    Empty category -> empty lists, honestly, never a fabricated
    candidate (mirrors rank_opportunities()'s own empty-data honesty)."""
    candidates = [evaluate_opportunity(o, knowledge) for o in opportunities.by_category(category)]
    ready = sorted(
        (c for c in candidates if c["classification"] == "ready"),
        key=lambda c: (c["factors"]["combined_score"] is not None, c["factors"]["combined_score"] or 0.0),
        reverse=True,
    )
    wait = [c for c in candidates if c["classification"] == "wait"]
    return {"ready": ready, "wait": wait}
