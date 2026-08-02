from datetime import datetime, timezone

from atlas.brain.cashflow import profit, roi
from atlas.brain.kpi import KPIRegistry
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Goal

# Named, stated methodology — an explicit weighting choice, not fabricated
# data, the same class of transparent assumption as ASSUMED_MONTHLY_LEADS in
# affiliate_pipeline_advance.py. Real measured money outweighs everything
# else; source corroboration and recency (real, but pre-revenue) count
# least. Editable, not sacred — revisit once real data volume justifies
# re-tuning it.
WEIGHTS = {
    "measured_outcomes": 0.30,
    "historical_success": 0.20,
    "internal_experiments": 0.15,
    "source_corroboration": 0.20,
    "recency": 0.10,
    "repeatability": 0.05,
}

SOURCE_SATURATION_SAMPLE = 3  # 3 independently-sourced findings = full corroboration credit, same saturating-sample shape as valuation.MATURITY_SAMPLE
RECENCY_WINDOW_DAYS = 90  # a finding older than this contributes ~0 recency credit

# Maps a Finding.category to the real, dispatchable Task categories
# (grepped from every manifest.toml's [config] categories, not guessed) that
# actually execute that channel today. "youtube"/"ugc" map to nothing —
# there is no dispatchable channel for either yet, so every score below
# honestly returns None for them rather than pretending one exists.
CATEGORY_TASK_CATEGORIES: dict[str, set[str]] = {
    "affiliate": {
        "affiliate_pipeline",
        "affiliate_intelligence",
        "content_factory",
        "content_factory_editorial_fix",
        "editorial_review",
        "creative_agent",
        "publishing_gateway",
        "revenue_affiliate",
    },
    "digital_product": {"revenue_digital_product"},
    "content": {"revenue_content_assets"},
    "recruitment": {"revenue_recruitment_leads"},
    "youtube": set(),
    "ugc": set(),
}

# Which real, dispatchable Task category actually bootstraps a fresh
# auto-promotion for each channel-ready category — one entry per category,
# the specific dispatch target Decision Engine investment uses (moved here
# from decision_apply.py so confidence.py stays the one place that owns
# "what a category's real execution capability actually is", rather than
# this knowledge existing in two files).
BOOTSTRAP_TASK_CATEGORY = {
    "affiliate": "affiliate_pipeline",
    "digital_product": "revenue_digital_product",
    "content": "revenue_content_assets",
    "recruitment": "revenue_recruitment_leads",
}

# Real, dispatchable Task categories whose executor is a hardcoded
# placeholder today — grepped from the actual channel source
# (revenue/channels/{affiliate,digital_products,content_assets}.py all
# literally always return revenue_generated: 0.0, "Execution is a
# placeholder pending a real ... integration"), not guessed.
# "channel_ready" (a real Task category exists, something will dispatch
# and mark itself done) is a different claim from "this channel can ever
# produce real revenue as currently built" — this is what keeps the two
# from being silently conflated into false confidence. Note
# BOOTSTRAP_TASK_CATEGORY never actually points "affiliate" at
# "revenue_affiliate" (it targets the real affiliate_department chain via
# "affiliate_pipeline" instead) — revenue_affiliate is listed here for
# completeness of what's real vs. placeholder, not because auto-promotion
# ever dispatches to it.
PLACEHOLDER_TASK_CATEGORIES = {"revenue_affiliate", "revenue_digital_product", "revenue_content_assets"}


def goals_touching_category(category: str, memory: BrainMemory) -> list[Goal]:
    task_categories = CATEGORY_TASK_CATEGORIES.get(category, set())
    if not task_categories:
        return []
    goal_ids = {t.goal_id for t in memory.tasks() if t.category in task_categories}
    return [g for g in memory.goals() if g.id in goal_ids]


def source_corroboration_score(category: str, knowledge: KnowledgeBase) -> float | None:
    """Factors 1+2 (number and quality of independent sources, source
    reliability) combined: v1 reliability is deliberately binary — a
    finding either carries a real evidence URL or it doesn't. A per-domain
    trust table would itself be an unverified judgment call dressed as
    evidence; not built here. Saturates at SOURCE_SATURATION_SAMPLE
    independently-sourced findings in this category."""
    sourced = [f for f in knowledge.findings() if f.category == category and f.evidence]
    if not sourced:
        return None
    return min(len(sourced) / SOURCE_SATURATION_SAMPLE, 1.0)


def recency_score(category: str, knowledge: KnowledgeBase) -> float | None:
    """Factor 3. Average freshness of this category's findings — a category
    with only stale findings scores low (real signal), a category with no
    findings at all scores None (no signal, not a false zero)."""
    findings = [f for f in knowledge.findings() if f.category == category]
    if not findings:
        return None
    now = datetime.now(timezone.utc)
    ages = [(now - datetime.fromisoformat(f.created_at)).total_seconds() / 86400 for f in findings]
    freshness = [max(0.0, 1 - age / RECENCY_WINDOW_DAYS) for age in ages]
    return sum(freshness) / len(freshness)


def repeatability_score(category: str, knowledge: KnowledgeBase) -> float | None:
    """Factor 4: repeatability across different markets. Always None today
    — ATLAS has no real data anywhere about the same opportunity type
    succeeding across distinct markets/niches. Kept as a real function (not
    silently omitted) so the breakdown always names this dimension and
    wiring in real data later is additive, not a redesign."""
    return None


def historical_success_score(category: str, memory: BrainMemory, kpis: KPIRegistry) -> float | None:
    """Factor 5: historical success of similar opportunities — the fraction
    of this category's goals with a real, positive measured profit. None
    when no goal in this category has both revenue and cost measured yet."""
    resolved = [p for g in goals_touching_category(category, memory) if (p := profit(g, kpis)) is not None]
    if not resolved:
        return None
    return sum(1 for p in resolved if p > 0) / len(resolved)


def internal_experiments_score(category: str, memory: BrainMemory, kpis: KPIRegistry) -> float | None:
    """Factor 6: internal experiments — real ROI from goals in this
    category that are explicitly tagged as a deliberate internal test via
    Goal.engine_id (the mechanism that field exists for, unused until now).
    Distinct from historical_success_score: this is ATLAS's own controlled
    tests, not general category history. None until goals are actually
    tagged with engine_id and have measured cost."""
    rois = [
        r
        for g in goals_touching_category(category, memory)
        if g.engine_id is not None and (r := roi(g, kpis)) is not None
    ]
    if not rois:
        return None
    avg = sum(rois) / len(rois)
    return max(0.0, min(1.0, 0.5 + avg / 2))  # roi 0.0 -> 0.5, roi >= 1.0 -> 1.0, roi <= -1.0 -> 0.0


def measured_outcomes_score(category: str, memory: BrainMemory, kpis: KPIRegistry) -> float | None:
    """Factor 7: measured outcomes — real average ROI magnitude across this
    category's goals with measured cost (not just win/loss like factor 5,
    the actual size of the return). The single strongest factor: real
    money, not a proxy for it."""
    rois = [r for g in goals_touching_category(category, memory) if (r := roi(g, kpis)) is not None]
    if not rois:
        return None
    avg = sum(rois) / len(rois)
    return max(0.0, min(1.0, 0.5 + avg / 2))


def confidence_score(category: str, knowledge: KnowledgeBase, memory: BrainMemory, kpis: KPIRegistry) -> dict:
    """Combines every factor above into one score: a weighted average of
    only the factors that have real data — matching valuation.blended()'s
    fail-closed shape, generalized to more than two inputs. A missing
    factor is never treated as zero; if every factor is missing, the
    combined score is None, not a fabricated number. Returns the full
    per-factor breakdown alongside the combined score so it's always
    visible which dimensions the score actually rests on.
    """
    components = {
        "source_corroboration": source_corroboration_score(category, knowledge),
        "recency": recency_score(category, knowledge),
        "repeatability": repeatability_score(category, knowledge),
        "historical_success": historical_success_score(category, memory, kpis),
        "internal_experiments": internal_experiments_score(category, memory, kpis),
        "measured_outcomes": measured_outcomes_score(category, memory, kpis),
    }
    available = {k: v for k, v in components.items() if v is not None}
    if not available:
        combined = None
    else:
        weight_sum = sum(WEIGHTS[k] for k in available)
        combined = sum(WEIGHTS[k] * v for k, v in available.items()) / weight_sum

    return {
        "category": category,
        "score": combined,
        "factors": components,
        "factors_available": len(available),
        "factors_total": len(components),
    }
