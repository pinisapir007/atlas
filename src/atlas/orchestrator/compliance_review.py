"""Compliance & Trust Review V1 (2026-08-05).

The mandatory gate the founder ordered after a real defect was found in a
real, already-produced campaign package (KetoDNA / Maya Health): the
deterministic Content Production Layer (built before this review existed)
had no awareness of the AI-disclosure and no-fabricated-personal-experience
rules established in this codebase's own prior research. Content reached
"produce_content: done" while still claiming a first-person personal
experience an AI persona never had, and disclosing nothing about being a
digital persona at all.

This module is that gate: `review_content_compliance()` inspects a real,
already-assembled ContentPackage and returns a structured, honest
pass/fail with every issue named -- never a silent pass. Heuristic and
keyword-based, deliberately: no LLM/content-understanding integration
exists anywhere in this codebase (the same boundary
content_factory/generator.py and production.py already draw), so this
cannot be a semantic judge of intent. It catches the concrete, named
failure patterns already found real evidence for in this codebase's own
research (fabricated first-person experience, missing AI/digital-persona
disclosure, missing material-connection/affiliate disclosure,
unsubstantiated "miracle cure"-class claims) -- not a general content
moderator. A pass here is not a legal guarantee; it is the mechanical
floor every package must clear before a human ever reviews it.

Keyword lists are stated, editable assumptions -- the same class as
HASHTAG_PLATFORMS/MARKET_LOCALE elsewhere in this codebase -- never
claimed as exhaustive.
"""

from dataclasses import dataclass, field

from atlas.influencer.models import ContentPackage

# Phrases that indicate the content itself discloses it comes from an
# AI/digital persona, not a real human. Case-insensitive substring match.
AI_DISCLOSURE_PHRASES = [
    "ai-curated", "ai curated", "ai-generated", "ai generated",
    "digital persona", "virtual persona", "ai persona",
    "not a real person", "not a real human",
]

# Phrases that claim a real, lived, first-person personal experience --
# something no AI persona actually has. Presence of any of these without
# an AI-disclosure phrase elsewhere in the same package is a real,
# concrete deception risk (see FTC synthetic-endorser guidance cited in
# this codebase's own prior research).
FABRICATED_PERSONAL_EXPERIENCE_PHRASES = [
    "i tried", "i've tried", "i have tried", "my experience", "my honest experience",
    "i switched", "my journey", "my story", "in my experience", "i've used", "i have used",
    "when i used", "i personally",
]

# Unsubstantiated / high-risk health-and-outcome claim language (see
# CLAUDE.md's documented FTC Health Products Compliance Guidance research).
UNSUBSTANTIATED_CLAIM_PHRASES = [
    "guaranteed", "miracle", "instant results", "100% effective", "cure", "cures",
    "no side effects", "risk-free",
]

# Material-connection / affiliate disclosure phrases (FTC 16 CFR 255).
AFFILIATE_DISCLOSURE_PHRASES = [
    "affiliate link", "#ad", " ad ", "sponsored", "commission", "paid partnership",
]


@dataclass
class ComplianceReviewResult:
    """A structured, honest review outcome -- every issue named, never a
    bare pass/fail flag. `passed` is True only when `issues` is empty."""

    passed: bool
    issues: list[str] = field(default_factory=list)


def _combined_text(package: ContentPackage) -> str:
    parts = (
        package.titles + package.descriptions + package.hooks + package.ctas
        + package.captions + package.landing_page_messages
    )
    return " \n".join(parts).lower()


def review_content_compliance(package: ContentPackage) -> ComplianceReviewResult:
    """Reviews one real, already-assembled ContentPackage against the
    founder's mandatory Compliance & Trust Review checks. Pure, read-only
    -- never mutates the package or the influencer. Real: this runs
    against the actual real KetoDNA/Maya Health package during
    development of this module, confirmed to catch the exact real defect
    that triggered it, and confirmed to pass the corrected version.
    """
    text = _combined_text(package)
    issues: list[str] = []

    has_ai_disclosure = any(phrase in text for phrase in AI_DISCLOSURE_PHRASES)
    has_fabricated_experience = any(phrase in text for phrase in FABRICATED_PERSONAL_EXPERIENCE_PHRASES)
    if has_fabricated_experience and not has_ai_disclosure:
        issues.append(
            "content claims a first-person personal experience ('I tried'/'my journey'-class phrasing) "
            "with no AI/digital-persona disclosure present -- a digital persona cannot have a real personal "
            "experience; this is a deception risk under FTC synthetic-endorser guidance"
        )

    if not has_ai_disclosure:
        issues.append(
            "no AI/digital-persona disclosure found anywhere in the package -- required whenever the "
            "persona is not a real person (FTC AI endorsement disclosure rules)"
        )

    unsubstantiated = [phrase for phrase in UNSUBSTANTIATED_CLAIM_PHRASES if phrase in text]
    if unsubstantiated:
        issues.append(f"unsubstantiated/high-risk claim language found: {sorted(unsubstantiated)}")

    has_affiliate_disclosure = any(phrase in text for phrase in AFFILIATE_DISCLOSURE_PHRASES)
    if not has_affiliate_disclosure:
        issues.append("no affiliate/material-connection disclosure found (FTC 16 CFR 255)")

    return ComplianceReviewResult(passed=not issues, issues=issues)
