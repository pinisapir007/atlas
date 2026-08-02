"""Deterministic, template-based creative brief generation. No LLM, no
external API, no real image/video rendering — produces a structured
shot-list/composition brief from an opportunity's existing Content Factory
package, for a human (or a future real generation provider, a separate
decision) to actually execute.
"""

DEFAULT_ASSET_TYPE = "short_video"


def generate_creative_brief(opportunity) -> dict:
    package = opportunity.content_package
    platform_suggestions = package.get("platform_suggestions", [])
    platform = platform_suggestions[0]["platform"] if platform_suggestions else "unspecified"

    hooks = package.get("hooks", [])
    headlines = package.get("headlines", [])
    ctas = package.get("ctas", [])
    video_ideas = package.get("content_ideas", {}).get("video", [])

    hook = hooks[0] if hooks else ""
    headline = headlines[0] if headlines else opportunity.product_name
    cta = ctas[0] if ctas else ""
    lead_shot = video_ideas[0] if video_ideas else f"Show {opportunity.product_name} in use"

    shots = [
        {"shot": 1, "duration_seconds": 3, "direction": f'Open on-camera with the hook: "{hook}"'},
        {"shot": 2, "duration_seconds": 15, "direction": lead_shot},
        {"shot": 3, "duration_seconds": 5, "direction": f'On-screen text: "{headline}"'},
        {"shot": 4, "duration_seconds": 4, "direction": f'Close with the CTA, spoken and on-screen: "{cta}"'},
    ]

    return {
        "platform": platform,
        "on_screen_text": headline,
        "voiceover_or_caption": hook,
        "cta_text": cta,
        "shots": shots,
        "estimated_total_seconds": sum(s["duration_seconds"] for s in shots),
    }
