"""identify_success_patterns() (2026-08-09, Learning V1) — the real,
named, still-open gap this codebase's own CLAUDE.md flagged repeatedly
("identify success patterns... nothing compares content style/format/
niche combinations") and confirmed absent from every existing Learning-
adjacent mechanism by direct audit (SuccessLaw track-record ranking,
Campaign.confidence_score/learning_history, SuccessPrinciplesReport are
all honestly-computed but currently inert bookkeeping — none of them
compares `content_formats`/`platform_strategy` across campaigns, and
none of them changes what ATLAS does next).

This module closes that gap at the one granularity CLAUDE.md itself
names: comparing real `Campaign.content_formats`/`platform_strategy`
combinations against real measured profit (never fabricated — via
cashflow.profit(), the same real revenue-cost function every other real
profit figure in this codebase already goes through). Fail-closed, the
same discipline confidence.py's MIN_INDEPENDENT_SOURCES already
established one layer up: a combination backed by fewer than
MIN_CAMPAIGNS_FOR_PATTERN real, profit-measured campaigns is never
reported as a pattern, no matter how good its one data point looks —
a single lucky campaign is not evidence of a repeatable pattern.

Deliberately read-only here, same as every other pure "compute a real
ranking from real state" module in this codebase (confidence.py,
opportunity_ranking.py, asset_value.py) — success_patterns.py never
writes anything. What makes this genuinely "Learning" and not a fourth
inert report is where its output gets consulted: campaign_advance.py's
create_campaign() call site (the real point where a new campaign's
content_formats/platform_strategy get decided) — see
best_pattern_for_category()'s docstring and campaign_advance.py's own
comment at that call site for the concrete behavior-change wiring.
"""

from dataclasses import dataclass, field

from atlas.brain.cashflow import profit
from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.campaign.registry import CampaignRegistry

MIN_CAMPAIGNS_FOR_PATTERN = 2


@dataclass
class SuccessPattern:
    category: str
    content_formats: list[str]
    platform_strategy: str
    campaign_count: int
    average_profit: float
    campaign_ids: list[str] = field(default_factory=list)


def identify_success_patterns(category: str, campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry) -> list[SuccessPattern]:
    """Real campaigns in `category` with a real, declared
    (content_formats, platform_strategy) combination AND real measured
    profit (via cashflow.profit(), resolving each campaign's real Goal
    through memory) are grouped by that exact combination. A campaign
    with no declared content_formats/platform_strategy, or no measured
    profit yet, contributes nothing — never guessed. Returns patterns
    ranked by real average profit descending; a combination with fewer
    than MIN_CAMPAIGNS_FOR_PATTERN real supporting campaigns is never
    included."""
    relevant = [c for c in campaigns.campaigns() if c.category == category]

    groups: dict[tuple[tuple[str, ...], str], list[tuple[str, float]]] = {}
    for c in relevant:
        if not c.content_formats or not c.platform_strategy:
            continue
        if not c.goal_id:
            continue
        try:
            goal = memory.get_goal(c.goal_id)
        except KeyError:
            continue
        measured_profit = profit(goal, kpis)
        if measured_profit is None:
            continue
        key = (tuple(sorted(c.content_formats)), c.platform_strategy)
        groups.setdefault(key, []).append((c.id, measured_profit))

    patterns = []
    for (formats, platform), entries in groups.items():
        if len(entries) < MIN_CAMPAIGNS_FOR_PATTERN:
            continue
        average = sum(p for _, p in entries) / len(entries)
        patterns.append(
            SuccessPattern(
                category=category,
                content_formats=list(formats),
                platform_strategy=platform,
                campaign_count=len(entries),
                average_profit=average,
                campaign_ids=[cid for cid, _ in entries],
            )
        )

    patterns.sort(key=lambda p: p.average_profit, reverse=True)
    return patterns


def best_pattern_for_category(category: str, campaigns: CampaignRegistry, memory: BrainMemory, kpis: KPIRegistry) -> SuccessPattern | None:
    """The one real function campaign_advance.py consults before
    creating a new campaign in `category`: the highest-real-profit
    pattern with enough real supporting evidence, or None when there
    isn't one yet (today's honest default — a brand-new category, or
    one where no campaign has both a declared content strategy and
    measured profit yet). This is the concrete mechanism that makes
    "identify success patterns" more than a report: its return value
    is used, not just displayed."""
    patterns = identify_success_patterns(category, campaigns, memory, kpis)
    return patterns[0] if patterns else None
