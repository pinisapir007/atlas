"""Deterministic, template-based content package generation. No LLM, no
external API, no image/video generation, no publishing — planning only, as
required. `variant` shifts angle order and phrasing slightly so a
"request changes" regeneration produces genuinely different output, not a
byte-identical repeat dressed up as a revision.
"""

from atlas.assets.affiliate_department.models import AffiliateOpportunity

MARKETING_ANGLES = ["Problem/Solution", "Luxury", "Budget", "Before/After", "Lifestyle"]

_HOOK_TEMPLATES = {
    "Problem/Solution": [
        "Struggling with your {category} problem? Here's what actually worked.",
        "Nobody tells you this about {category} — until {name}.",
    ],
    "Luxury": [
        "This is how I upgraded my {category} setup without regret.",
        "{name} feels like a premium upgrade, not just a purchase.",
    ],
    "Budget": [
        "You don't need to spend a fortune to fix your {category} problem.",
        "{name}: the budget {category} pick I actually use.",
    ],
    "Before/After": [
        "Before {name}, my {category} routine was a mess. Here's the after.",
        "The {category} before-and-after nobody expected.",
    ],
    "Lifestyle": [
        "Here's what a day with {name} actually looks like.",
        "How {name} quietly fixed my {category} routine.",
    ],
}

_HEADLINE_TEMPLATES = {
    "Problem/Solution": [
        "The {category} fix nobody told you about: {name}",
        "Solving {category} problems with {name}",
    ],
    "Luxury": [
        "Why {name} feels like a premium upgrade",
        "The {category} upgrade worth the splurge: {name}",
    ],
    "Budget": [
        "{name}: the budget-friendly {category} pick",
        "Affordable {category}, done right, with {name}",
    ],
    "Before/After": [
        "My {category} before and after using {name}",
        "{name}: the {category} transformation",
    ],
    "Lifestyle": [
        "How {name} fits into my everyday {category} routine",
        "A day in the life with {name}",
    ],
}

_CTA_TEMPLATES = [
    "Try {name} — link in bio.",
    "See why I switched to {name} — link in bio.",
    "Get {name} before this offer changes — link in bio.",
    "Curious? Check out {name} — link in bio.",
    "Shop the {category} pick I recommend — link in bio.",
]

_PLATFORM_REASONS = {
    "TikTok": "Short-form, high-reach video suits a {category} product that benefits from a visual demo or before/after.",
    "Instagram Reels": "Same short-video format as TikTok, with strong overlap with MAYA's existing audience.",
    "Facebook": "Reaches an older, higher-purchasing-power demographic well-suited to a considered {category} purchase.",
    "Pinterest": "Strong for visually-driven, aspirational {category} content with a long content lifespan.",
    "YouTube Shorts": "Captures viewers actively searching for {category} solutions, with an easy link to a longer review.",
}

_VIDEO_IDEA_TEMPLATES = [
    "Unboxing {name} for the first time",
    "Day-in-the-life video featuring {name}",
    "Before/after using {name} for a week",
    "Answering the top 5 questions about {name}",
    "Why I almost didn't buy {name} (and why I'm glad I did)",
    "Quick {category} tip using {name}",
    "Rating {name} against 2 alternatives",
    "What I wish I knew before trying {name}",
    "3 ways to use {name} you haven't seen",
    "Is {name} worth it? Honest 60-second review",
]

_IMAGE_IDEA_TEMPLATES = [
    "Clean product shot of {name}",
    "{name} in a real, lived-in setting",
    "Side-by-side before/after image with {name}",
    "Close-up detail shot highlighting {name}'s main feature",
    "Flat-lay of {name} with complementary {category} items",
    "Quote-card testimonial graphic about {name}",
    "Infographic: 3 reasons to try {name}",
    "Behind-the-scenes shot of {name} in use",
    "Comparison graphic: {name} vs. doing without it",
    "Seasonal/contextual shot of {name} in daily life",
]

_CAROUSEL_IDEA_TEMPLATES = [
    "5-slide carousel: 'Why I recommend {name}'",
    "Carousel: the problem, the search, and finding {name}",
    "Carousel: 3 mistakes people make with {category} (and how {name} avoids them)",
    "Carousel: unboxing {name} step by step",
    "Carousel: FAQ about {name}, one question per slide",
]


def _rotate(items: list[str], variant: int) -> list[str]:
    if not items:
        return items
    shift = variant % len(items)
    return items[shift:] + items[:shift]


def _fill(template: str, name: str, category: str) -> str:
    return template.format(name=name, category=category)


def generate_content_package(opportunity: AffiliateOpportunity, variant: int = 0, include_disclosure: bool = False) -> dict:
    name = opportunity.product_name
    # marketing_niche (audience-facing, e.g. "Keto Diet / Weight Loss") takes
    # priority over category (the provider's product-type classification,
    # e.g. "software") for copy — falls back to category when unset so
    # placeholder opportunities are unaffected.
    category = opportunity.marketing_niche or opportunity.category

    angles = _rotate(MARKETING_ANGLES, variant)

    campaign_summary = {
        "product": name,
        "audience": f"MAYA's audience already interested in {category}",
        "main_problem_solved": f"A common {category} frustration MAYA's audience already has",
        "why_people_would_buy": opportunity.notes or f"Clear value for a {category} buyer at this price point",
    }

    hooks = []
    headlines = []
    for angle in angles:
        for hook_template, headline_template in zip(_HOOK_TEMPLATES[angle], _HEADLINE_TEMPLATES[angle]):
            hooks.append(f"[{angle}] {_fill(hook_template, name, category)}")
            headlines.append(f"[{angle}] {_fill(headline_template, name, category)}")

    ctas = [_fill(t, name, category) for t in _rotate(_CTA_TEMPLATES, variant)]
    if include_disclosure:
        ctas = [f"{cta} (affiliate link — I may earn a commission)" for cta in ctas]

    platform_suggestions = [
        {"platform": platform, "reason": _fill(reason, name, category)}
        for platform, reason in _PLATFORM_REASONS.items()
    ]

    video_ideas = [_fill(t, name, category) for t in _rotate(_VIDEO_IDEA_TEMPLATES, variant)]
    image_ideas = [_fill(t, name, category) for t in _rotate(_IMAGE_IDEA_TEMPLATES, variant)]
    carousel_ideas = [_fill(t, name, category) for t in _rotate(_CAROUSEL_IDEA_TEMPLATES, variant)]

    return {
        "variant": variant,
        "campaign_summary": campaign_summary,
        "marketing_angles": angles,
        "hooks": hooks,
        "headlines": headlines,
        "ctas": ctas,
        "platform_suggestions": platform_suggestions,
        "content_ideas": {
            "video": video_ideas,
            "image": image_ideas,
            "carousel": carousel_ideas,
        },
    }
