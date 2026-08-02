from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.scoring import score_opportunity

# Reuses AffiliateOpportunity and score_opportunity from the Affiliate
# Department (Mission 003) rather than redefining an entity or a scoring
# formula — the one explicit exception to "assets are self-contained" is
# borrowing a plain data model/pure function from a sibling asset package,
# not a dependency on atlas.core/atlas.brain, which remains untouched.

# Fixed placeholder catalog, keyed by product name — the same three products
# used in Mission 003's demo, for continuity, not because they're real.
_RESEARCH_TABLE = {
    "FocusFlow (productivity SaaS)": {
        "category": "software",
        "commission_per_conversion": 15.0,
        "estimated_conversion": 0.01,
        "competition": 0.8,
        "content_difficulty": 0.7,
        "notes": "Well-established SaaS category; high competition makes organic reach difficult.",
    },
    "BudgetWise (personal finance app)": {
        "category": "software",
        "commission_per_conversion": 20.0,
        "estimated_conversion": 0.02,
        "competition": 0.5,
        "content_difficulty": 0.5,
        "notes": "Mid-tier commission with moderate competition; a reasonable middle option.",
    },
    "QuietDesk (ergonomic desk accessories)": {
        "category": "physical_good",
        "commission_per_conversion": 25.0,
        "estimated_conversion": 0.05,
        "competition": 0.2,
        "content_difficulty": 0.2,
        "notes": "Niche physical-good category; low competition and easy content angle.",
    },
}


class DiscoveryAgent:
    """Creates bare placeholder opportunities — name and description only,
    no evaluation data yet. No external source, no internet access."""

    def discover(self) -> list[AffiliateOpportunity]:
        return [
            AffiliateOpportunity(product_name=name, description=f"Placeholder candidate: {name}")
            for name in _RESEARCH_TABLE
        ]


class ResearchAgent:
    """Enriches a bare opportunity with category, estimated commission,
    competition, difficulty, and notes. Deterministic lookup against a fixed
    placeholder table — not fabricated per-call, and not a live external
    lookup of any kind."""

    def enrich(self, opportunity: AffiliateOpportunity) -> AffiliateOpportunity:
        data = _RESEARCH_TABLE.get(opportunity.product_name, {})
        opportunity.category = data.get("category", opportunity.category)
        opportunity.commission_per_conversion = data.get("commission_per_conversion", 0.0)
        opportunity.estimated_conversion = data.get("estimated_conversion", 0.0)
        opportunity.competition = data.get("competition", 0.0)
        opportunity.content_difficulty = data.get("content_difficulty", 0.0)
        opportunity.notes = data.get("notes", "")
        opportunity.transition("researched", "ResearchAgent: enriched with category/commission/competition/difficulty/notes")
        return opportunity


class RankingAgent:
    """Scores every researched opportunity (reusing score_opportunity — the
    exact same formula Mission 003's Affiliate Manager already uses, not a
    second one) and ranks them. Does not auto-select or auto-reject anything
    — every opportunity reaches "ranked"; the founder chooses which to
    pursue."""

    def rank(self, opportunities: list[AffiliateOpportunity]) -> list[AffiliateOpportunity]:
        ranked = sorted(opportunities, key=score_opportunity, reverse=True)
        for position, opportunity in enumerate(ranked, start=1):
            opportunity.score = score_opportunity(opportunity)
            opportunity.transition("ranked", f"RankingAgent: rank {position} of {len(ranked)}, score {opportunity.score:.4f}")
        return ranked
