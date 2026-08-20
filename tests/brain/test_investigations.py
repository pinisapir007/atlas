from atlas.brain.investigations import InvestigationStore
from atlas.brain.models import Investigation


def test_save_and_retrieve_an_investigation(tmp_path):
    store = InvestigationStore(tmp_path / "investigations.json")
    investigation = Investigation(subject_id="prostadine::vendorA", category="affiliate", reason_opened="high commission observed")
    store.save_investigation(investigation)

    reloaded = store.get_investigation(investigation.id)

    assert reloaded.subject_id == "prostadine::vendorA"
    assert reloaded.status == "open"
    assert reloaded.reason_opened == "high commission observed"


def test_by_status_filters_correctly(tmp_path):
    store = InvestigationStore(tmp_path / "investigations.json")
    open_one = Investigation(subject_id="a", category="affiliate", status="open")
    waiting_one = Investigation(subject_id="b", category="affiliate", status="waiting_for_evidence")
    store.save_investigation(open_one)
    store.save_investigation(waiting_one)

    assert [i.id for i in store.by_status("open")] == [open_one.id]
    assert [i.id for i in store.by_status("waiting_for_evidence")] == [waiting_one.id]


def test_by_subject_finds_the_real_investigation_for_that_category_and_subject(tmp_path):
    store = InvestigationStore(tmp_path / "investigations.json")
    investigation = Investigation(subject_id="prostadine::vendorA", category="affiliate")
    store.save_investigation(investigation)

    found = store.by_subject("affiliate", "prostadine::vendorA")
    assert found is not None
    assert found.id == investigation.id
    assert store.by_subject("affiliate", "unknown-subject") is None


def test_f_investigation_survives_process_and_store_recreation(tmp_path):
    """Test F."""
    path = tmp_path / "investigations.json"
    store1 = InvestigationStore(path)
    investigation = Investigation(
        subject_id="prostadine::vendorA", category="affiliate", status="waiting_for_evidence",
        reason_opened="high commission observed", missing_evidence="independent Sales Page confirmation",
    )
    store1.save_investigation(investigation)
    del store1

    store2 = InvestigationStore(path)
    reloaded = store2.get_investigation(investigation.id)
    assert reloaded.status == "waiting_for_evidence"
    assert reloaded.missing_evidence == "independent Sales Page confirmation"


def test_investigation_never_advances_stage_of_opportunity_no_such_capability_exists():
    """Structural sanity: Investigation has no relation to Opportunity.stage
    at all -- it is a genuinely separate entity, on purpose."""
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(Investigation)}
    assert "stage" not in field_names
    assert "goal_id" not in field_names  # Investigation predates Goal entirely
