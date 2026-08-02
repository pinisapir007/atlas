from atlas.assets.recruitment_workforce.models import CandidateRecord, EmployerDemand, Opportunity, WorkforceSupplier
from atlas.assets.recruitment_workforce.store import WorkforceStore


def test_round_trips_demand_supplier_candidate_and_opportunity(tmp_path):
    store = WorkforceStore(tmp_path / "recruitment_workforce.json")

    demand = EmployerDemand(
        industry="warehouse", employer_name="Acme", role="picker", headcount=2, rate_expectation_per_hour=25.0
    )
    store.save_demand(demand)

    supplier = WorkforceSupplier(name="Staffing Co", industry="warehouse")
    store.save_supplier(supplier)

    candidate = CandidateRecord(industry="warehouse", description="qualified worker", pay_rate_expectation_per_hour=18.0)
    store.save_candidate(candidate)

    opportunity = Opportunity(industry="warehouse", employer_demand_id=demand.id)
    store.save_opportunity(opportunity)

    assert store.get_demand(demand.id).employer_name == "Acme"
    assert store.suppliers()[0].name == "Staffing Co"
    assert store.candidates()[0].pay_rate_expectation_per_hour == 18.0
    assert store.get_opportunity(opportunity.id).employer_demand_id == demand.id


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "recruitment_workforce.json"
    store = WorkforceStore(path)
    store.save_supplier(WorkforceSupplier(name="Staffing Co", industry="warehouse"))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
