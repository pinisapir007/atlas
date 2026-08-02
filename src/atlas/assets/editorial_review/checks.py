"""Deterministic, rule-based content QA — no LLM, no external service. Each
check inspects the actual generated content_package for a real, checkable
defect; none of these are theater. Maps each of the 7 required dimensions to
exactly one content_package section, so a revision request can say precisely
what needs regenerating.
"""

MAX_HEADLINE_LENGTH = 150  # generous — current templates run well under this
_SPAM_WORDS = {"guaranteed", "miracle", "free money", "act now", "100% free"}
_ACTION_VERBS = ("try", "get", "see", "check", "shop", "grab")

DIMENSION_SECTIONS = {
    "quality": "hooks",
    "originality": "headlines",
    "brand_consistency": "campaign_summary",
    "spam_risk": "hooks",
    "compliance": "ctas",
    "marketing_clarity": "headlines",
    "cta_quality": "ctas",
}


def check_quality(package: dict, opportunity) -> tuple[bool, str]:
    hooks = package.get("hooks", [])
    if len(hooks) < 10:
        return False, f"Only {len(hooks)} hooks — at least 10 are required."
    for hook in hooks:
        if "{" in hook or "}" in hook:
            return False, "Found an unfilled template placeholder in a hook."
    return True, "Hooks are complete and well-formed."


def check_originality(package: dict, opportunity) -> tuple[bool, str]:
    headlines = package.get("headlines", [])
    if len(headlines) != len(set(headlines)):
        return False, "Duplicate headlines detected."
    return True, "All headlines are unique."


def check_brand_consistency(package: dict, opportunity) -> tuple[bool, str]:
    summary = package.get("campaign_summary", {})
    if opportunity.product_name not in summary.get("product", ""):
        return False, "Campaign summary does not name the product consistently."
    return True, "Campaign summary is consistent with the product."


def check_spam_risk(package: dict, opportunity) -> tuple[bool, str]:
    for hook in package.get("hooks", []):
        lowered = hook.lower()
        if any(word in lowered for word in _SPAM_WORDS):
            return False, "A hook contains spam-trigger language."
        if hook.count("!") >= 3:
            return False, "A hook uses excessive punctuation."
    return True, "No spam-trigger language detected."


def check_compliance(package: dict, opportunity) -> tuple[bool, str]:
    ctas = package.get("ctas", [])
    if not ctas:
        return False, "No CTAs present to check for affiliate disclosure."
    if not any("affiliate" in cta.lower() or "#ad" in cta.lower() for cta in ctas):
        return False, "No affiliate disclosure found in any CTA — required for platform compliance."
    return True, "Affiliate disclosure present in CTAs."


def check_marketing_clarity(package: dict, opportunity) -> tuple[bool, str]:
    headlines = package.get("headlines", [])
    if not headlines:
        return False, "No headlines to evaluate."
    for headline in headlines:
        if len(headline) > MAX_HEADLINE_LENGTH:
            return False, "A headline is too long to be clear at a glance."
    return True, "Headlines are clear and concise."


def check_cta_quality(package: dict, opportunity) -> tuple[bool, str]:
    ctas = package.get("ctas", [])
    if not ctas:
        return False, "No CTAs present."
    for cta in ctas:
        lowered = f" {cta.lower()} "
        if not any(lowered.startswith(f" {verb}") or f" {verb} " in lowered for verb in _ACTION_VERBS):
            return False, f"CTA lacks a clear action verb: '{cta}'"
    return True, "All CTAs contain a clear action verb."


CHECKS = {
    "quality": check_quality,
    "originality": check_originality,
    "brand_consistency": check_brand_consistency,
    "spam_risk": check_spam_risk,
    "compliance": check_compliance,
    "marketing_clarity": check_marketing_clarity,
    "cta_quality": check_cta_quality,
}


def evaluate(package: dict, opportunity) -> dict:
    """Runs all 7 checks, returns a structured verdict: PASS if everything
    passes, REVISION_REQUIRED if 1-2 dimensions fail (fixable), REJECT if 3+
    fail (too broken to patch incrementally)."""
    results = {}
    failed_sections = set()
    for dimension, check_fn in CHECKS.items():
        passed, note = check_fn(package, opportunity)
        results[dimension] = {"passed": passed, "note": note}
        if not passed:
            failed_sections.add(DIMENSION_SECTIONS[dimension])

    failed_count = sum(1 for r in results.values() if not r["passed"])
    if failed_count == 0:
        verdict = "pass"
    elif failed_count <= 2:
        verdict = "revision_required"
    else:
        verdict = "reject"

    return {"verdict": verdict, "checks": results, "failed_sections": sorted(failed_sections)}
