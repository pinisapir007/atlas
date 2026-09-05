from dataclasses import asdict

from atlas.assets.recruitment_workforce.matching import compute_revenue_model, select_candidates
from atlas.assets.recruitment_workforce.models import STAGES, CandidateRecord, EmployerDemand, Opportunity, WorkforceSupplier
from atlas.assets.recruitment_workforce.store import WorkforceStore

_SEED_SUPPLIER = {"name": "Midwest Staffing Pool", "industry": "warehouse_logistics"}
_SEED_CANDIDATES = [
    {"description": f"Warehouse-qualified worker #{i}", "pay_rate_expectation_per_hour": 18.0} for i in range(1, 4)
]
_SEED_DEMAND = {
    "industry": "warehouse_logistics",
    "employer_name": "Regional Distribution Center",
    "role": "Warehouse worker",
    "headcount": 3,
    "rate_expectation_per_hour": 28.0,
    "location": "Columbus, OH",
}


class RecruitmentAgent:
    """Recruitment / Workforce operational agent — V1 business workflow.

    Discovers employer demand and workforce supply, matches them, and
    tracks every opportunity through discovered -> qualified -> matched
    -> proposal_ready -> active -> won (or lost at any point before won).
    Reusable across industries: every demand/supplier/candidate/
    opportunity carries its own `industry` tag.

    Founder approval gates: proposal_ready -> active (external outreach)
    and active -> won (agreement/placement/commitment) never happen
    automatically — only approve_outreach()/approve_commitment() move an
    opportunity past those stages. No external integrations exist yet
    (deferred, pending separate approval); "outreach" and "placement"
    here are internal tracking only.

    Self-contained: no atlas.core/atlas.brain imports, matching every
    other asset in the registry.
    """

    def __init__(
        self,
        store: WorkforceStore | None = None,
        *,
        allow_demo_seed: bool = False,
    ) -> None:
        self._store = store if store is not None else WorkforceStore()
        self._allow_demo_seed = allow_demo_seed

    def run(self, task=None, **kwargs) -> dict:
        self._advance_all()
        if self._allow_demo_seed:
            self._ensure_seed_data()
        self._create_missing_opportunities(task)
        return {"status": "done", **self._summarize()}

    def report(self) -> dict:
        return {"status": "done", **self._summarize()}

    # --- intake -----------------------------------------------------

    def intake_demand(
        self,
        *,
        industry: str,
        employer_name: str,
        role: str,
        headcount: int,
        rate_expectation_per_hour: float,
        location: str = "",
    ):
        demand = EmployerDemand(
            industry=industry,
            employer_name=employer_name,
            role=role,
            headcount=headcount,
            rate_expectation_per_hour=rate_expectation_per_hour,
            location=location,
        )
        self._store.save_demand(demand)
        return demand

    def intake_supplier(self, *, name: str, industry: str):
        supplier = WorkforceSupplier(name=name, industry=industry)
        self._store.save_supplier(supplier)
        return supplier

    def intake_candidate(
        self,
        *,
        industry: str,
        description: str,
        pay_rate_expectation_per_hour: float,
        supplier_id: str | None = None,
        available: bool = True,
    ):
        candidate = CandidateRecord(
            industry=industry,
            description=description,
            pay_rate_expectation_per_hour=pay_rate_expectation_per_hour,
            supplier_id=supplier_id,
            available=available,
        )
        self._store.save_candidate(candidate)
        return candidate

    # --- founder approval gates --------------------------------------

    def approve_outreach(self, opportunity_id: str) -> Opportunity:
        opportunity = self._store.get_opportunity(opportunity_id)
        if opportunity.stage != "proposal_ready":
            raise ValueError(
                f"opportunity {opportunity_id} is not awaiting outreach approval (stage={opportunity.stage})"
            )
        opportunity.outreach_approved = True
        opportunity.transition("active", "founder approved outreach")
        self._store.save_opportunity(opportunity)
        return opportunity

    def approve_commitment(self, opportunity_id: str) -> Opportunity:
        opportunity = self._store.get_opportunity(opportunity_id)
        if opportunity.stage != "active":
            raise ValueError(
                f"opportunity {opportunity_id} is not awaiting commitment approval (stage={opportunity.stage})"
            )
        opportunity.commitment_approved = True
        opportunity.transition("won", "founder approved commitment")
        self._store.save_opportunity(opportunity)
        return opportunity

    def mark_lost(self, opportunity_id: str, reason: str = "") -> Opportunity:
        opportunity = self._store.get_opportunity(opportunity_id)
        if opportunity.stage in ("won", "lost"):
            raise ValueError(f"opportunity {opportunity_id} is already resolved (stage={opportunity.stage})")
        opportunity.transition("lost", reason)
        self._store.save_opportunity(opportunity)
        return opportunity

    # --- internal pipeline --------------------------------------------

    def _ensure_seed_data(self) -> None:
        if self._store.demands() or self._store.suppliers() or self._store.candidates():
            return  # real intake data already exists — never overwrite it
        supplier = self.intake_supplier(**_SEED_SUPPLIER)
        for candidate in _SEED_CANDIDATES:
            self.intake_candidate(supplier_id=supplier.id, industry=_SEED_SUPPLIER["industry"], **candidate)
        self.intake_demand(**_SEED_DEMAND)

    def _create_missing_opportunities(self, task=None) -> None:
        covered = {o.employer_demand_id for o in self._store.opportunities()}
        goal_id = getattr(task, "goal_id", None)
        task_id = getattr(task, "id", None)
        for demand in self._store.demands():
            if demand.id in covered:
                continue
            self._store.save_opportunity(
                Opportunity(
                    industry=demand.industry,
                    employer_demand_id=demand.id,
                    goal_id=goal_id,
                    task_id=task_id,
                )
            )

    def _advance_all(self) -> None:
        for opportunity in self._store.opportunities():
            self._advance_one(opportunity)

    def _advance_one(self, opportunity: Opportunity) -> None:
        if opportunity.stage == "discovered":
            opportunity.transition("qualified", "demand verified")
            self._store.save_opportunity(opportunity)
        elif opportunity.stage == "qualified":
            self._attempt_match(opportunity)
        elif opportunity.stage == "matched":
            opportunity.transition("proposal_ready", "revenue model prepared")
            self._store.save_opportunity(opportunity)
        # proposal_ready -> active and active -> won only happen through
        # approve_outreach()/approve_commitment(); "won"/"lost" are terminal.

    def _attempt_match(self, opportunity: Opportunity) -> None:
        demand = self._store.get_demand(opportunity.employer_demand_id)
        matched = select_candidates(self._store.candidates(), opportunity.industry, demand.headcount)
        if len(matched) < demand.headcount:
            return  # not enough available workforce yet — stays "qualified"

        for candidate in matched:
            candidate.available = False
            self._store.save_candidate(candidate)

        opportunity.candidate_ids = [c.id for c in matched]
        for field_name, value in compute_revenue_model(demand, matched).items():
            setattr(opportunity, field_name, value)
        opportunity.transition("matched", f"matched {len(matched)} candidate(s)")
        self._store.save_opportunity(opportunity)

    def _summarize(self) -> dict:
        opportunities = self._store.opportunities()
        by_stage = {stage: 0 for stage in STAGES}
        for o in opportunities:
            by_stage[o.stage] = by_stage.get(o.stage, 0) + 1
        won = [o for o in opportunities if o.stage == "won"]
        return {
            "opportunities": [asdict(o) for o in opportunities],
            "by_stage": by_stage,
            "awaiting_outreach_approval": by_stage["proposal_ready"],
            "awaiting_commitment_approval": by_stage["active"],
            "total_pipeline_recurring_monthly_revenue": sum(o.recurring_monthly_revenue for o in opportunities),
            "total_won_recurring_monthly_revenue": sum(o.recurring_monthly_revenue for o in won),
            "total_won_estimated_gross_profit": sum(o.estimated_gross_profit for o in won),
        }
