from atlas.brain.cashflow import roi
from atlas.brain.confidence import (
    BOOTSTRAP_TASK_CATEGORY,
    CATEGORY_TASK_CATEGORIES,
    PLACEHOLDER_TASK_CATEGORIES,
    confidence_score,
    goals_touching_category,
)
from atlas.brain.kpi import KPIRegistry
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory

_FACTOR_LABELS = {
    "source_corroboration": "number/quality of independent sources",
    "recency": "recency",
    "repeatability": "repeatability across markets",
    "historical_success": "historical success of similar opportunities",
    "internal_experiments": "internal experiments",
    "measured_outcomes": "measured outcomes",
}


def explain_opportunity(
    category: str, knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry, rank: int | None = None
) -> dict:
    """Every field a decision about `category` must show: the evidence
    behind it, the confidence score and what it does/doesn't rest on,
    expected ROI (never fabricated — absent, not guessed, until real
    revenue/cost exist), concrete risks, and why it ranked where it did.
    Reuses confidence_score() entirely rather than recomputing anything.
    """
    result = confidence_score(category, knowledge, memory, kpis)
    findings = knowledge.findings(category=category)

    evidence = [
        {"finding_id": f.id, "source": f.source, "description": f.description, "evidence": f.evidence}
        for f in findings
    ]

    rois = [r for g in goals_touching_category(category, memory) if (r := roi(g, kpis)) is not None]
    expected_roi = sum(rois) / len(rois) if rois else None

    # historical_success_score() already IS a real win-rate — the fraction
    # of this category's past goals that resolved profitable. Surfaced
    # directly under its requested name rather than invented separately;
    # None (not a guessed percentage) until a real track record exists —
    # inventing a number here would be exactly the "intuition dressed as
    # evidence" this whole model exists to rule out.
    probability_of_success = result["factors"]["historical_success"]

    risks = _assess_risks(category, result, expected_roi)

    missing = [_FACTOR_LABELS[k] for k, v in result["factors"].items() if v is None]
    rank_reason = (
        f"confidence {result['score']:.3f} built from {result['factors_available']}/{result['factors_total']} "
        f"evidence factors ({', '.join(_FACTOR_LABELS[k] for k, v in result['factors'].items() if v is not None)})"
        if result["score"] is not None
        else "no evidence recorded yet for this category"
    )
    if rank is not None:
        rank_reason = f"ranked #{rank} — {rank_reason}"

    return {
        "category": category,
        "evidence": evidence,
        "confidence": result,
        "expected_roi": expected_roi,
        "probability_of_success": probability_of_success,
        "risks": risks,
        "missing_evidence": missing,
        "rank_reason": rank_reason,
    }


def _assess_risks(category: str, confidence_result: dict, expected_roi: float | None) -> list[str]:
    risks = []
    if not CATEGORY_TASK_CATEGORIES.get(category):
        risks.append(f"no dispatchable execution channel exists for '{category}' yet — cannot actually execute this today")
    elif BOOTSTRAP_TASK_CATEGORY.get(category) in PLACEHOLDER_TASK_CATEGORIES:
        risks.append(
            f"the real execution channel for '{category}' is a hardcoded placeholder that always returns zero "
            "revenue — a dispatched task will show status=done, but cannot produce real revenue until a real "
            "integration is built, regardless of confidence score"
        )
    if confidence_result["factors"]["measured_outcomes"] is None:
        risks.append("no real measured revenue/cost exists for this category — confidence rests on research, not results")
    if confidence_result["factors"]["historical_success"] is None:
        risks.append("no track record of similar opportunities succeeding or failing")
    if expected_roi is not None and expected_roi < 0:
        risks.append(f"measured ROI is currently negative ({expected_roi:.2f})")
    if confidence_result["factors_available"] < 3:
        risks.append(
            f"only {confidence_result['factors_available']}/{confidence_result['factors_total']} evidence factors "
            "available — this confidence score is built on a narrow evidence base"
        )
    return risks
