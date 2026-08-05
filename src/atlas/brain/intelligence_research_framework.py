"""ATLAS Intelligence Research Framework V1 (2026-08-05).

Before ATLAS gathers intelligence, it must first determine exactly WHAT
it needs to learn. This module transforms a free-text business goal
into a structured ResearchFramework — the mandatory first step before
any Intelligence Engine collection begins. It does NOT collect
intelligence (no KnowledgeBase/IntelligenceIndex read or write anywhere
in this module) and does NOT analyze intelligence (no scoring, no
evidence evaluation) — it only builds the framework that later,
separate steps would use to go find real answers.

The honest limit this module is built around: no LLM, no real natural-
language-understanding integration, and no real external research
capability exists anywhere in this codebase. A function that claimed to
"understand" a business goal and derive real facts from it (real
competitor names, real world leaders, a real success metric) would
either need a real, credentialed AI/research integration this codebase
doesn't have, or would have to fabricate plausible-sounding answers —
exactly the class of mistake this codebase has refused to make
everywhere else (Digistore24's API shape, Israel's DST dates, a
Persona's WHO fields). So this module does the other, honest half:
generate the right, structured QUESTIONS from the goal, deterministically
and transparently, and state plainly what is not yet known — never
invent the answers. This mirrors the exact "clearly-labeled,
deterministic, never-authoritative" discipline already established for
influencer.factory.suggest_persona()/brand.factory.suggest_brand(),
applied here to research questions instead of creative suggestions.

"Current World Leaders" is the sharpest example: naming real companies
or people without a real, verified source would assert unverified facts
about real entities — this module generates the research QUESTION
("who are they, relative to this goal") and honestly marks the answer
unknown, never a guessed name.

Intelligence Categories and Required Intelligence Sources are not
reinvented here — they reuse the real, already-built Intelligence
Engine V1 domain set (atlas.integrations.base.INTELLIGENCE_DOMAINS) and
provider classes (the real FindingsMarketIntelligenceProvider plus the
four real placeholder classes), read only for their static `name`/
`domain` attributes — never calling fetch_intelligence() on any of
them, so this stays real collection, never triggered.
"""

from dataclasses import dataclass, field

from atlas.brain.market_intelligence_provider import FindingsMarketIntelligenceProvider
from atlas.brain.time_service import TimeService
from atlas.integrations.base import INTELLIGENCE_DOMAINS
from atlas.integrations.intelligence_provider_placeholders import (
    CompetitorIntelligenceProvider,
    EconomicIntelligenceProvider,
    HumanBehaviorIntelligenceProvider,
    ProductIntelligenceProvider,
)

# One research-question template per real Intelligence Engine domain —
# generic, goal-agnostic structure, filled only with the real, verbatim
# goal text (never a parsed/interpreted "topic" — this module does no
# semantic extraction, since that would itself be an unverifiable claim
# of understanding). human_behavior's template restates this domain's
# own founding boundary directly, the same way the real
# HumanBehaviorIntelligenceProvider placeholder already does.
_DOMAIN_QUESTION_TEMPLATES = {
    "market": "What is the real demand, supply, pricing, and market-change data relevant to: '{goal}'?",
    "human_behavior": "What are the real motivations, pain points, desires, and buying behaviors of the people relevant to: '{goal}'? (Understanding only — never for manipulation or deception.)",
    "competitor": "Who are the real competitors already pursuing something like: '{goal}', and what are their real positioning, pricing, strengths, and weaknesses?",
    "product": "What real product quality, features, and differentiation would be required to achieve: '{goal}'?",
    "economic": "What real economic conditions (markets, countries, purchasing power, seasonal effects) affect: '{goal}'?",
}
assert set(_DOMAIN_QUESTION_TEMPLATES) == INTELLIGENCE_DOMAINS, "every real Intelligence Engine domain must have a real research-question template"

_SUCCESS_DEFINITION_TEMPLATES = [
    "What specific, measurable outcome would prove the goal '{goal}' has actually been achieved?",
    "By what real date should this goal be achieved?",
    "What real, trackable KPI(s) will be used to measure progress toward '{goal}'?",
    "What would make this goal definitively FAIL, not just underperform?",
]

_CURRENT_WORLD_LEADERS_TEMPLATE = (
    "Who are the real, current world leaders or benchmark businesses relative to: '{goal}'? "
    "Unknown as of framework creation — no automated real-world identification exists in this "
    "codebase; this requires real research (founder-supplied evidence, or a future real "
    "market-intelligence source)."
)

# A stated, editable default ordering (the same class of transparent
# assumption as confidence.HASHTAG_PLATFORMS) — not a computed,
# evidence-based priority, since no real evidence exists yet to compute
# one from. Market and competitor context typically ground every other
# domain, so they're proposed first; reorder freely per goal.
DEFAULT_RESEARCH_PRIORITY = ["market", "competitor", "product", "human_behavior", "economic"]
assert set(DEFAULT_RESEARCH_PRIORITY) == INTELLIGENCE_DOMAINS, "DEFAULT_RESEARCH_PRIORITY must name exactly the real Intelligence Engine domains"


@dataclass
class ResearchQuestion:
    domain: str
    question: str


@dataclass
class RequiredIntelligenceSource:
    domain: str
    provider_name: str


@dataclass
class ResearchFramework:
    """The structured output of one goal -> research-framework
    transformation. Every field is either the real, verbatim input, a
    deterministic template filled with that input, or a real read of
    the already-built Intelligence Engine's domain/provider registry —
    nothing here is collected, scored, or fabricated. Produced fresh on
    every call, never persisted — the same read-only-view discipline
    BusinessExecutionPlan already established one engine over."""

    objective: str
    success_definition: list[str]
    current_world_leaders_question: str
    knowledge_gaps: list[str]
    research_questions: list[ResearchQuestion]
    intelligence_categories: list[str]
    required_intelligence_sources: list[RequiredIntelligenceSource]
    missing_knowledge: list[str]
    research_priority: list[str] = field(default_factory=lambda: list(DEFAULT_RESEARCH_PRIORITY))
    completion_criteria: str = ""
    created_at: str = ""


def _real_intelligence_providers() -> list:
    """The real provider instances this codebase already registers for
    each Intelligence Engine domain — imported directly by class (not
    intelligence_engine.py's own default-provider list), so this module
    never touches or depends on that module's internals. Constructing
    these does no I/O; only calling fetch_intelligence() would, and
    nothing here ever does."""
    return [
        FindingsMarketIntelligenceProvider(),
        HumanBehaviorIntelligenceProvider(),
        CompetitorIntelligenceProvider(),
        ProductIntelligenceProvider(),
        EconomicIntelligenceProvider(),
    ]


def build_research_framework(goal: str, time_service: TimeService | None = None) -> ResearchFramework:
    """The one real transformation this module exists for: a free-text
    business goal in, a complete ResearchFramework out. Pure — no
    KnowledgeBase/IntelligenceIndex read or write, no network call, no
    filesystem write. Deterministic: the same real goal text always
    produces the same real framework (aside from `created_at`).

    Raises ValueError for an empty/blank goal — there is no honest
    framework to build from nothing.
    """
    if not goal or not goal.strip():
        raise ValueError("a real, non-empty business goal is required to build a research framework")

    ts = time_service if time_service is not None else TimeService()
    domains = sorted(INTELLIGENCE_DOMAINS)
    providers = _real_intelligence_providers()

    research_questions = [ResearchQuestion(domain=d, question=_DOMAIN_QUESTION_TEMPLATES[d].format(goal=goal)) for d in domains]
    required_sources = [RequiredIntelligenceSource(domain=p.domain, provider_name=p.name) for p in providers]
    success_definition = [t.format(goal=goal) for t in _SUCCESS_DEFINITION_TEMPLATES]

    knowledge_gaps = [f"no real {d.replace('_', ' ')} intelligence has been collected yet for this goal" for d in domains]
    knowledge_gaps.append("no real-world benchmark/leader has been identified yet for this goal")

    missing_knowledge = [
        "success_definition: not yet confirmed by the founder",
        "current_world_leaders: unknown — no automated real-world identification exists in this codebase",
    ] + [f"{d}: no real intelligence collected yet" for d in domains]

    return ResearchFramework(
        objective=goal,
        success_definition=success_definition,
        current_world_leaders_question=_CURRENT_WORLD_LEADERS_TEMPLATE.format(goal=goal),
        knowledge_gaps=knowledge_gaps,
        research_questions=research_questions,
        intelligence_categories=domains,
        required_intelligence_sources=required_sources,
        missing_knowledge=missing_knowledge,
        research_priority=list(DEFAULT_RESEARCH_PRIORITY),
        completion_criteria=(
            f"Complete when every one of the {len(research_questions)} research questions above has a "
            f"real, cited answer recorded (0 of {len(research_questions)} answered as of framework creation)."
        ),
        created_at=ts.iso_timestamp(),
    )
