"""Evidence Validation V1 (2026-08-06, Knowledge Sources V1) — the
real "Understand" step this codebase was missing: not every real,
successfully-read observation is actually usable evidence. Before
this existed, any real text a plugin returned was trusted as-is; now
a real observation must clear two genuinely different checks, always
combined by explicit AND, never AI alone deciding on its own:

1. Objective, deterministic checks (no LLM call, always run first):
   did the plugin report a real error, and is there enough real text
   to possibly answer anything at all.
2. AI-judged task relevance (only reached if #1 passes -- no point
   spending a real AI call judging text that's already disqualified):
   does this real text actually address the specific real task, not
   merely contain related words. Routed through the real AI
   Orchestrator (M1) rather than a hardcoded model call.

Never treats a low-quality or off-task observation as evidence "found
nothing" -- collect_evidence_from_source (knowledge_source_research.py)
raises loudly on a failed check, the same fail-closed discipline every
other real gate in this codebase already establishes, so a caller (or
a future "decide next observation" planner) always knows explicitly
that this particular source didn't pan out, rather than silently
getting an empty/misleading Finding.
"""

from dataclasses import dataclass

from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.base import AIProvider, PageObservation

MIN_TEXT_LENGTH = 50  # a real, editable minimum -- an empty/near-empty read can never be usable evidence, regardless of task


@dataclass
class EvidenceQualityResult:
    """The real, combined verdict — never a single number standing in
    for two genuinely different questions. `ai_relevant`/`ai_reasoning`
    stay None/"" when the objective checks already failed, since the
    AI call is never reached in that case (never spent, never
    fabricated)."""

    passed: bool
    reason: str
    text_length: int
    ai_relevant: bool | None = None
    ai_reasoning: str = ""


def assess_observation_quality(
    observation: PageObservation,
    task_description: str,
    ai_provider: AIProvider | None = None,
) -> EvidenceQualityResult:
    """The real combined check. `task_description` is required — a
    default would mean inventing what the caller was actually trying
    to learn, the same "never guess a value the caller must supply"
    discipline Finding.subject/market already establish."""
    if observation.error:
        return EvidenceQualityResult(
            passed=False,
            reason=f"observation reported a real error: {observation.error}",
            text_length=0,
        )

    text = (observation.text_content or "").strip()
    if len(text) < MIN_TEXT_LENGTH:
        return EvidenceQualityResult(
            passed=False,
            reason=f"real text content is only {len(text)} chars, below the {MIN_TEXT_LENGTH}-char minimum",
            text_length=len(text),
        )

    provider = ai_provider if ai_provider is not None else get_ai_provider()
    prompt = (
        f"A real research task needs to be answered: {task_description}\n\n"
        f"Here is real text actually read from a real source:\n{text[:4000]}\n\n"
        "Does this text genuinely address the task -- not merely contain related words, but actually "
        "answer it or provide real evidence toward it?"
    )
    fields = {"relevant": "the single word yes or no", "reason": "one honest sentence explaining the judgment"}
    result = provider.complete_structured(prompt, fields)
    ai_relevant = result.get("relevant", "").strip().lower().startswith("y")
    ai_reasoning = result.get("reason", "")

    if not ai_relevant:
        return EvidenceQualityResult(
            passed=False,
            reason=f"AI judged this not task-relevant: {ai_reasoning}",
            text_length=len(text),
            ai_relevant=False,
            ai_reasoning=ai_reasoning,
        )

    return EvidenceQualityResult(
        passed=True,
        reason="passed both the objective checks and AI task-relevance judgment",
        text_length=len(text),
        ai_relevant=True,
        ai_reasoning=ai_reasoning,
    )
