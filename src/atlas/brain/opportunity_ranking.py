from collections import Counter

from atlas.brain.confidence import rank_by_confidence, recency_score, source_corroboration_score, weighted_average_of_available
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import SuccessLaw

# The same "evidence -> weighted_average_of_available() -> rank" pattern
# already applied at category level (confidence.confidence_score()) and
# provider level (provider_ranking.provider_confidence()), applied a third
# time, one level deeper than provider: to one specific candidate
# product/topic (Finding.subject) within a category. Only source
# corroboration and recency are honestly computable here — the same
# deliberately narrow model provider_ranking.py uses, for the same reason:
# ATLAS doesn't attribute real revenue/cost per-subject (only per-goal), so
# there's no real data yet for a third factor.
OPPORTUNITY_WEIGHTS = {
    "source_corroboration": 0.6,
    "recency": 0.4,
}


def opportunity_confidence(category: str, subject: str, knowledge: KnowledgeBase) -> dict:
    """Evidence-weighted confidence for one specific candidate opportunity
    (a product/topic named by `subject`) within a category — the
    opportunity-level analog of confidence.confidence_score() /
    provider_ranking.provider_confidence(). Same fail-closed combination: a
    missing factor is never treated as zero, and zero available factors
    returns None, not a fabricated score.

    `recommended_market` is the most common non-empty Finding.market among
    this subject's evidence — real, evidence-derived, "" when no finding
    ever stated one. Never a guess."""
    components = {
        "source_corroboration": source_corroboration_score(category, knowledge, subject=subject),
        "recency": recency_score(category, knowledge, subject=subject),
    }
    combined = weighted_average_of_available(components, OPPORTUNITY_WEIGHTS)

    findings = [f for f in knowledge.findings() if f.category == category and f.subject == subject]
    sourced = [f for f in findings if f.evidence]
    markets = Counter(f.market for f in findings if f.market)
    recommended_market = markets.most_common(1)[0][0] if markets else ""

    return {
        "subject": subject,
        "category": category,
        "score": combined,
        "factors": components,
        "factors_available": sum(1 for v in components.values() if v is not None),
        "factors_total": len(components),
        "independent_sources": len(sourced),
        "recommended_market": recommended_market,
    }


def explain_opportunity_subject(category: str, subject: str, knowledge: KnowledgeBase, rank: int | None = None) -> dict:
    """Every field the founder needs to see WHY a specific opportunity is
    promising — the opportunity-level analog of explain.explain_opportunity(),
    reusing opportunity_confidence() entirely rather than recomputing
    anything. Deliberately narrower than the category-level explanation: no
    expected_roi/probability_of_success here, because ATLAS doesn't
    attribute real revenue/cost per-subject (only per-goal) — naming those
    fields here would be a fabricated-precision claim this codebase's
    fail-closed rule exists to prevent. `risks` names that gap explicitly
    instead of silently omitting it.
    """
    result = opportunity_confidence(category, subject, knowledge)
    findings = [f for f in knowledge.findings() if f.category == category and f.subject == subject]

    evidence = [
        {"finding_id": f.id, "source": f.source, "description": f.description, "evidence": f.evidence, "market": f.market}
        for f in findings
    ]

    risks = _assess_opportunity_risks(result)

    rank_reason = (
        f"confidence {result['score']:.3f} built from {result['factors_available']}/{result['factors_total']} "
        f"evidence factors, {result['independent_sources']} independent source(s)"
        if result["score"] is not None
        else "no evidence recorded yet for this opportunity"
    )
    if rank is not None:
        rank_reason = f"ranked #{rank} — {rank_reason}"

    return {
        "subject": subject,
        "category": category,
        "evidence": evidence,
        "confidence": result,
        "recommended_market": result["recommended_market"],
        "risks": risks,
        "rank_reason": rank_reason,
        "success_laws": relevant_success_laws(category, knowledge),
    }


def relevant_success_laws(category: str, knowledge: KnowledgeBase) -> list[SuccessLaw]:
    """Decision Engine reasoning step 2+3 (2026-08-03, founder's "make
    ATLAS think" directive): "Retrieve relevant Success Laws. Rank the
    Success Laws by confidence and evidence quality." Retrieves every
    real SuccessLaw whose `applicable_business_models` names `category`,
    or that's category-general (an empty list — the same "" == general
    convention Finding.category/provider already use), ranked by real
    evidence volume (`len(evidence_finding_ids)`) — evidence-backed laws
    outrank unevidenced hypotheses, never a fabricated numeric confidence
    for a principle with no real citations behind it.

    Deliberately read-only and additive: surfaces relevant business
    intelligence in the same explanation trail the founder already
    reviews (`explain_opportunity_subject()`, `atlas brain opportunities
    --explain`) without changing what decide()/rank_opportunities()
    themselves compute — blending Success Laws into the numeric
    confidence score itself is a real, separate design decision (what
    weight should a principle carry versus measured evidence?), not
    something to fold in silently here.
    """
    relevant = [
        law
        for law in knowledge.success_laws()
        if category in law.applicable_business_models or not law.applicable_business_models
    ]
    return sorted(relevant, key=lambda law: (bool(law.evidence_finding_ids), len(law.evidence_finding_ids)), reverse=True)


def _assess_opportunity_risks(result: dict) -> list[str]:
    risks = []
    if result["independent_sources"] < 2:
        risks.append(f"only {result['independent_sources']} independent source(s) — below the standing 2-source policy bar for a real commitment")
    if not result["recommended_market"]:
        risks.append("no evidence names a specific market — recommendation is category-general, not market-targeted")
    risks.append("no real revenue/cost is attributed per-opportunity yet — this ranks discovery evidence only, not measured outcomes")
    return risks


def cited_evidence(category: str, subject: str, knowledge: KnowledgeBase) -> list[str]:
    """Real evidence URLs behind a specific subject within a category —
    shared extraction used by every Factory-style draft that needs to
    cite real evidence (influencer.factory.draft_influencer_proposal(),
    brand.factory.draft_brand_proposal(), ...), so this list comprehension
    lives in exactly one place rather than being reimplemented per
    Factory. Reuses explain_opportunity_subject() entirely."""
    explanation = explain_opportunity_subject(category, subject, knowledge)
    return [e["evidence"] for e in explanation["evidence"] if e["evidence"]]


def rank_opportunities(category: str, knowledge: KnowledgeBase) -> list[dict]:
    """Every distinct real subject named by a Finding in `category` (an
    empty/unset subject is a category-general finding, not a candidate
    opportunity, and is excluded), ranked by opportunity_confidence()
    descending. With no findings naming a subject yet (true everywhere
    today — no MarketSignalProvider is registered, see
    atlas.integrations.signal_registry), this honestly returns an empty
    list, never a fabricated candidate."""
    subjects = sorted({f.subject for f in knowledge.findings() if f.category == category and f.subject})
    unranked = [opportunity_confidence(category, subject, knowledge) for subject in subjects]
    return rank_by_confidence(unranked)
