"""Evidence Role Classification (2026-08-17, ONE BRAIN Web Evidence Role
Classification) -- the one, general, brain-level function that decides
WHAT KIND of relationship a real observed web/document artifact has to
its real-world source, before that observation is ever allowed to
increase independent-source confidence.

Sense-agnostic by construction, the same discipline subject_verification.
verify_subject_match() already established: operates only on
PageObservation (the same generic result every KnowledgeSourcePlugin --
Browser/Document/Image/Audio/Video/YouTube, and any future plugin --
already returns), never on anything sensor-specific. The Brain (this
module, called from browser_research.py/knowledge_source_research.py,
never from inside any plugin/sensor) owns the classification decision --
sensors only ever extract raw observations. No BrowserPlugin, no
individual KnowledgeSourcePlugin, ever decides its own role.

Deliberately reuses the exact AIProvider.complete_structured seam
subject_verification.py/evidence_validation.py already established --
a third distinct question on the same real observation (quality,
subject-attribution, and now role), never a duplicated mechanism.

Fail-closed (locked, do not weaken): returns "unknown" whenever the
real, available signal isn't confidently one of the three known,
provable roles -- never guessed from a domain name, an "official"-
sounding URL, a page title, the subject name appearing in the text, or
a provider name. UNKNOWN is the preferred, correct answer whenever this
function is not genuinely certain -- the same "unknown is preferred to
false certainty" principle verify_subject_match() already established.

This module classifies ROLE only. It never extracts/infers claimant --
that remains a deliberately separate, not-yet-built concern (Finding.
claimant stays whatever the caller already knows, unrelated to this
function's return value).
"""

from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.base import AIProvider, PageObservation

DIRECT_ASSERTION = "direct_assertion"
RELAY_OR_QUOTE = "relay_or_quote"
AGGREGATED_REPORT = "aggregated_report"
UNKNOWN = "unknown"

_VALID_ROLES = frozenset({DIRECT_ASSERTION, RELAY_OR_QUOTE, AGGREGATED_REPORT, UNKNOWN})

# A real, structural, non-AI signal for AGGREGATED_REPORT: the caller
# asked to extract multiple independently-indexed items (e.g.
# research_discovery's `result_1_title`/`result_2_title`/...,
# `candidate_1`/`candidate_2`/...) and more than one came back non-empty.
# Deterministic, checked BEFORE any AI call -- an artifact that
# structurally bundles multiple distinct extracted records is aggregated
# by construction, not by semantic judgment.
_MIN_POPULATED_ITEMS_FOR_AGGREGATED = 2


def _aggregated_report_signal(structured_data: dict) -> bool:
    """True only when the real, already-extracted structured_data proves
    at least two distinct, independently-indexed items are genuinely
    present (non-empty) -- never guessed from the mere existence of a
    structured_data dict (a single-item extract, e.g. one title/price
    pair, is not an aggregation)."""
    if not structured_data:
        return False
    populated = [v for v in structured_data.values() if isinstance(v, str) and v.strip()]
    # Distinct-item proof: at least two populated values under keys that
    # look like an indexed series (result_1_*, result_2_*, candidate_1,
    # candidate_2, ...) -- a real, mechanical structural fact, not a guess.
    indexed_keys = [k for k in structured_data if any(ch.isdigit() for ch in k)]
    populated_indexed = [k for k in indexed_keys if isinstance(structured_data.get(k), str) and structured_data[k].strip()]
    distinct_indices = {"".join(ch for ch in k if ch.isdigit()) for k in populated_indexed}
    return len(distinct_indices) >= _MIN_POPULATED_ITEMS_FOR_AGGREGATED and len(populated) >= _MIN_POPULATED_ITEMS_FOR_AGGREGATED


def classify_evidence_role(
    observation: PageObservation,
    requested_subject: str = "",
    ai_provider: AIProvider | None = None,
) -> str:
    """The one, general, brain-level classifier. Returns exactly one of
    DIRECT_ASSERTION/RELAY_OR_QUOTE/AGGREGATED_REPORT/UNKNOWN -- never
    anything else, never PRIMARY_OBSERVATION (that role is reserved for
    a genuinely claimant-free observation -- e.g. screen_observation's
    own local screen capture -- never for a generic web page, which by
    definition IS content some real-world actor published).

    Order of checks, cheapest/most-certain first:
    1. Real, structural AGGREGATED_REPORT signal (multiple distinct
       extracted items) -- no AI call needed, since this is a mechanical
       fact about what was actually extracted, not a semantic judgment.
    2. AI-judged DIRECT_ASSERTION vs RELAY_OR_QUOTE vs UNKNOWN --
       reached only when step 1 didn't already prove aggregation.
       Never reached for empty/near-empty text (nothing to judge)."""
    if _aggregated_report_signal(observation.structured_data):
        return AGGREGATED_REPORT

    text = (observation.text_content or "").strip()
    title = (observation.title or "").strip()
    if not text:
        return UNKNOWN

    combined = f"Title: {title}\n\n{text[:4000]}" if title else text[:4000]
    subject_line = f" about {requested_subject!r}" if requested_subject else ""

    provider = ai_provider if ai_provider is not None else get_ai_provider()
    prompt = (
        f"Here is real text actually observed from a real web page/document{subject_line}:\n\n{combined}\n\n"
        "We need to know WHO is making the claims/statements in this text -- not what the page is about, "
        "but who is asserting it.\n\n"
        "Answer 'direct_assertion' ONLY if the page itself, in its own voice, is the original, first-party "
        "source of the claims (e.g. a vendor's own product page describing its own product, an official "
        "registry/platform reporting its own data, an author giving their own first-hand, independently-"
        "formed analysis/review/testimony that they conducted themselves).\n\n"
        "Answer 'relay_or_quote' if the page is reporting, quoting, citing, or repeating a claim that "
        "actually originates from someone else (e.g. 'according to X...', 'X says...', 'reported by...', "
        "a press release distributed through a wire service, an article summarizing or copying another "
        "article's content) -- even if the page adds its own commentary around the quoted/relayed material.\n\n"
        "Answer 'unknown' if you cannot confidently tell which of the above applies -- for example the text "
        "is too short, too generic, mixes original analysis with unattributed claims in a way you can't "
        "cleanly separate, or gives no real signal of who is actually speaking. 'unknown' is the correct, "
        "preferred answer whenever you are not genuinely certain -- never guess from the domain name, "
        "whether the word 'official' appears anywhere, the page title alone, or whether the subject name "
        "is merely mentioned."
    )
    fields = {
        "role": "exactly one word: direct_assertion, relay_or_quote, or unknown",
        "reason": "one honest sentence explaining the judgment",
    }
    result = provider.complete_structured(prompt, fields)
    role = (result.get("role", "") or "").strip().lower()

    if role in (DIRECT_ASSERTION, RELAY_OR_QUOTE):
        return role
    return UNKNOWN
