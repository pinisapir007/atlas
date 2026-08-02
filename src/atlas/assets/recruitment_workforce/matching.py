from atlas.assets.recruitment_workforce.models import CandidateRecord, EmployerDemand

MONTHLY_HOURS_PER_WORKER = 160.0


def select_candidates(
    candidates: list[CandidateRecord], industry: str, headcount: int
) -> list[CandidateRecord]:
    """First-available matching heuristic: earliest-added, available
    candidates in the requested industry. A placeholder for real matching
    (skills scoring, availability windows, geography) — same spirit as
    SimplePlanner's keyword-based category inference, swappable later
    without changing how RecruitmentAgent calls it."""
    pool = [c for c in candidates if c.industry == industry and c.available]
    return pool[:headcount]


def compute_revenue_model(demand: EmployerDemand, matched_candidates: list[CandidateRecord]) -> dict:
    """Placeholder staffing-industry pricing model pending real business
    rules from the founder: bill rate is the employer's stated rate
    expectation, pay rate is the average of matched candidates' stated
    pay expectations, and the placement fee is one month's margin."""
    headcount = len(matched_candidates)
    fee_per_hour = demand.rate_expectation_per_hour
    avg_pay_rate = sum(c.pay_rate_expectation_per_hour for c in matched_candidates) / headcount
    recurring_monthly_revenue = fee_per_hour * MONTHLY_HOURS_PER_WORKER * headcount
    monthly_cost = avg_pay_rate * MONTHLY_HOURS_PER_WORKER * headcount
    estimated_gross_profit = recurring_monthly_revenue - monthly_cost
    return {
        "fee_per_hour": fee_per_hour,
        "placement_fee": estimated_gross_profit,  # one month's margin, placeholder convention
        "recurring_monthly_revenue": recurring_monthly_revenue,
        "estimated_gross_profit": estimated_gross_profit,
    }
