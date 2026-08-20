"""Executive Reasoning MVP (2026-08-11, docs/DESIGN_EXECUTIVE_REASONING_MVP.md)
-- the first real implementation of the Specification's own long-named,
never-built Reasoning layer: compares 2+ real Opportunity Universal Core
candidates and produces one explained, evidence-grounded preference.
Never commits to anything (no Goal/Task/Proposal), never calls decide(),
never mutates an Opportunity -- pure, read-only, on-demand, the same
shape explain_opportunity() already has.

Deliberately does NOT use Opportunity.score: its own docstring states the
formula behind it is each channel's own concern, so a saas-channel score
and an affiliate-channel score are not guaranteed to be on the same
comparable scale -- using it directly here would be exactly the
fabricated-precision mistake this codebase avoids everywhere else. Uses
only two fields guaranteed comparable by construction, regardless of
channel: `competition` (a real, stated 0.0-1.0 scale) and the real count
of `evidence_finding_ids` (mirrors confidence.source_corroboration_score()'s
existing "more independent sources = stronger" logic exactly, at a
saturating sample size rather than an unbounded raw count).

MVP scope, deliberately narrow (docs/DESIGN_EXECUTIVE_REASONING_MVP.md):
only compares Opportunities that share the same real `stage` -- comparing
across stages (e.g. "selected" vs. "discovered") is a real, separate
question, left as Backlog, not silently answered here.
"""

from atlas.brain.confidence import weighted_average_of_available
from atlas.brain.models import Opportunity

# Same "stated, editable assumption" class as confidence.WEIGHTS -- not
# sacred, revisit once real comparisons accumulate to justify re-tuning.
# Weighted toward evidence over competition: how much real support a
# candidate already has is a stronger, more verifiable signal today than
# a competition estimate, which (per Opportunity's own docstring) is
# still a judgment call, not measured data.
REASONING_WEIGHTS = {"evidence": 0.6, "competition": 0.4}

# Same saturating-sample shape as confidence.SOURCE_SATURATION_SAMPLE --
# 3 real, accumulated Findings earns full evidence credit for this
# comparison; more than that doesn't further strengthen the case.
EVIDENCE_SATURATION_COUNT = 3


class IncomparableOpportunitiesError(ValueError):
    """Raised when asked to compare Opportunities that aren't real peers
    -- fewer than 2 given, or not all sharing the same real stage. Never
    silently compares mismatched candidates."""


def _opportunity_scores(opportunity: Opportunity) -> dict:
    """The real, per-factor breakdown for one Opportunity -- never a
    single fabricated number standing in for two different questions,
    the same discipline confidence_score()/EvidenceQualityResult already
    establish elsewhere in this codebase."""
    evidence_component = min(len(opportunity.evidence_finding_ids) / EVIDENCE_SATURATION_COUNT, 1.0)
    # Lower real competition is preferred -- inverted onto the same
    # 0.0-1.0 "higher is better" scale evidence_component already uses,
    # so weighted_average_of_available() can combine them meaningfully.
    competition_component = (1.0 - opportunity.competition) if opportunity.competition is not None else None
    combined = weighted_average_of_available(
        {"evidence": evidence_component, "competition": competition_component}, REASONING_WEIGHTS
    )
    return {
        "evidence_component": evidence_component,
        "competition_component": competition_component,
        "combined_score": combined,
    }


def compare_opportunities(opportunities: list[Opportunity]) -> dict:
    """The real Executive Reasoning MVP entry point -- on-demand, read-only,
    never called from tick(). Given 2+ real Opportunities sharing the same
    real stage, returns which one is preferred and a deterministic,
    evidence-cited reasoning string -- never freeform generated text, the
    same discipline Decision.reasoning already establishes.

    Raises IncomparableOpportunitiesError for fewer than 2 opportunities,
    or a mix of real stages -- comparing "selected" against "discovered"
    is a real, different question this MVP deliberately doesn't answer.
    """
    if len(opportunities) < 2:
        raise IncomparableOpportunitiesError("need at least 2 real Opportunities to compare")
    stages = {o.stage for o in opportunities}
    if len(stages) > 1:
        raise IncomparableOpportunitiesError(
            f"cannot compare Opportunities across different real stages: {sorted(stages)} "
            "-- same-stage comparison only in this MVP"
        )

    scored = [(opportunity, _opportunity_scores(opportunity)) for opportunity in opportunities]
    ranked = sorted(
        scored,
        key=lambda pair: (pair[1]["combined_score"] is not None, pair[1]["combined_score"] or 0.0),
        reverse=True,
    )
    preferred, preferred_scores = ranked[0]

    def _describe(opportunity: Opportunity, scores: dict) -> str:
        competition_text = "n/a" if scores["competition_component"] is None else f"{scores['competition_component']:.2f}"
        combined_text = "unscored" if scores["combined_score"] is None else f"{scores['combined_score']:.2f}"
        return (
            f"{opportunity.id} ({opportunity.subject!r}): evidence={scores['evidence_component']:.2f} "
            f"({len(opportunity.evidence_finding_ids)} real finding(s)), competition={competition_text}, "
            f"combined={combined_text}"
        )

    others_summary = "; ".join(_describe(o, s) for o, s in ranked[1:])
    reasoning = (
        f"Preferred '{preferred.subject}' ({preferred.id}) over {len(ranked) - 1} real alternative(s) at stage "
        f"'{preferred.stage}': {_describe(preferred, preferred_scores)}. Compared against: {others_summary}"
    )

    return {
        "preferred_id": preferred.id,
        "stage": preferred.stage,
        "compared": [o.id for o in opportunities],
        "scores": {o.id: s for o, s in scored},
        "reasoning": reasoning,
    }
