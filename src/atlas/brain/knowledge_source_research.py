"""Knowledge Source Research V1 (2026-08-06) — the generalized
successor to atlas.brain.browser_research.collect_evidence_from_url:
the same real "observe a real source, produce exactly one real,
durable Finding" mechanism, now dispatching by real plugin
(knowledge_source_registry.select_plugin) instead of taking a single
BrowserObserver directly, and now gated by real Evidence Validation
before a Finding is ever saved.

browser_research.py is untouched and stays real/valid for the
narrower "browser only, no quality gate" case; this module is the
preferred entry point going forward, for any real registered source —
web today, and a future document/video/social source with zero change
to this function.

Never infers category/subject/market from content -- same discipline
browser_research.py already established. Never touches the Decision
Engine, Finding, or KnowledgeBase's own shape -- a Finding produced
here is picked up automatically on the next tick, same as any other.
"""

from atlas.brain.browser_research import _real_description
from atlas.brain.evidence_validation import assess_observation_quality
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_registry import select_plugin
from atlas.brain.models import Finding
from atlas.integrations.base import AIProvider


class EvidenceQualityRejected(ValueError):
    """Raised when a real observation was successfully read but
    failed evidence-quality validation (a real error, too little real
    text, or a real AI judgment that it doesn't address the task) —
    never silently turned into a low-quality Finding."""


def collect_evidence_from_source(
    source_ref: str,
    category: str,
    source: str,
    task_description: str,
    knowledge: KnowledgeBase,
    subject: str = "",
    market: str = "",
    extract: dict[str, str] | None = None,
    ai_provider: AIProvider | None = None,
) -> Finding:
    """Dispatches to the real registered plugin for `source_ref`
    (raises ValueError if none can handle it), observes it for real,
    validates the real result against `task_description` (raises
    EvidenceQualityRejected if it doesn't pass), and records exactly
    one real, durable Finding. Whatever real error the selected
    plugin raises (not approved, not found, a real backend failure)
    propagates unchanged -- never caught here to fabricate a fallback
    result."""
    plugin = select_plugin(source_ref)
    observation = plugin.observe(source_ref, extract=extract)

    quality = assess_observation_quality(observation, task_description, ai_provider=ai_provider)
    if not quality.passed:
        raise EvidenceQualityRejected(
            f"real observation of {source_ref!r} (via {plugin.name!r}) failed evidence quality: {quality.reason}"
        )

    finding = Finding(
        source=source,
        category=category,
        description=_real_description(observation),
        evidence=source_ref,
        subject=subject,
        market=market,
    )
    knowledge.save_finding(finding)
    return finding
