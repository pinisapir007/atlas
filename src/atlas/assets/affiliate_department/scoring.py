from atlas.assets.affiliate_department.models import AffiliateOpportunity


def score_opportunity(opportunity: AffiliateOpportunity) -> float:
    """Deterministic, fully transparent placeholder scoring — rewards higher
    estimated conversion and commission, penalizes higher competition and
    content difficulty. Not a black box: every input is a field already on
    the opportunity, every output is traceable back to those inputs, so the
    Strategist's business report can explain a selection/rejection by simply
    citing this formula's inputs, not by inventing a post-hoc justification.
    """
    return (
        opportunity.estimated_conversion
        * opportunity.commission_per_conversion
        * (1 - opportunity.competition)
        * (1 - opportunity.content_difficulty)
    )
