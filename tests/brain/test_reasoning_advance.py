from atlas.brain.models import Opportunity
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.reasoning_advance import advance_opportunity_comparisons


def _opp(subject: str, category: str, stage: str = "ranked", competition: float | None = None, evidence_count: int = 0) -> Opportunity:
    return Opportunity(
        subject=subject,
        description="d",
        category=category,
        stage=stage,
        competition=competition,
        evidence_finding_ids=[f"finding-{i}" for i in range(evidence_count)],
    )


def _store(tmp_path) -> OpportunityStore:
    return OpportunityStore(tmp_path / "opportunities.json")


class TestDesignDocFalsificationTest:
    """docs/DESIGN_BRIDGE_2_OPPORTUNITY_TO_REASONING.md's own 4-part
    falsification test, kept as a permanent automated regression."""

    def test_part_1_two_real_opportunities_same_stage_produce_one_result(self, tmp_path):
        store = _store(tmp_path)
        a = _opp("Keto Diet Guide", "affiliate", competition=0.3, evidence_count=2)
        b = _opp("Project Management SaaS", "saas", competition=0.7, evidence_count=1)
        store.save_opportunity(a)
        store.save_opportunity(b)

        results = advance_opportunity_comparisons(store)

        assert len(results) == 1
        assert results[0]["preferred_id"] == a.id  # more evidence, less competition -- clearly stronger

    def test_part_2_three_real_opportunities_same_stage_produce_one_n_way_result(self, tmp_path):
        store = _store(tmp_path)
        for o in [_opp("a", "affiliate"), _opp("b", "saas"), _opp("c", "content")]:
            store.save_opportunity(o)

        results = advance_opportunity_comparisons(store)

        assert len(results) == 1  # one real N-way comparison, never 3 pairwise ones
        assert len(results[0]["compared"]) == 3

    def test_part_3_singles_at_different_stages_produce_zero_results(self, tmp_path):
        store = _store(tmp_path)
        store.save_opportunity(_opp("a", "affiliate", stage="discovered"))
        store.save_opportunity(_opp("b", "saas", stage="ranked"))

        results = advance_opportunity_comparisons(store)

        assert results == []

    def test_part_4_a_real_evidence_change_between_calls_changes_the_real_result(self, tmp_path):
        store = _store(tmp_path)
        a = _opp("a", "affiliate", competition=0.5, evidence_count=1)
        b = _opp("b", "saas", competition=0.5, evidence_count=1)
        store.save_opportunity(a)
        store.save_opportunity(b)

        first = advance_opportunity_comparisons(store)
        assert len(first) == 1

        # real evidence changes for b, saved for real -- the bridge must
        # never return a stale/cached prior answer
        b.evidence_finding_ids = ["finding-1", "finding-2", "finding-3"]
        store.save_opportunity(b)

        second = advance_opportunity_comparisons(store)
        assert second[0]["preferred_id"] == b.id


def test_a_lone_opportunity_at_a_stage_is_skipped_not_an_error(tmp_path):
    store = _store(tmp_path)
    store.save_opportunity(_opp("a", "affiliate"))

    assert advance_opportunity_comparisons(store) == []


def test_empty_store_produces_no_results(tmp_path):
    assert advance_opportunity_comparisons(_store(tmp_path)) == []


def test_calling_repeatedly_on_unchanged_data_is_stateless(tmp_path):
    store = _store(tmp_path)
    store.save_opportunity(_opp("a", "affiliate", competition=0.2, evidence_count=2))
    store.save_opportunity(_opp("b", "saas", competition=0.8, evidence_count=1))

    results = [advance_opportunity_comparisons(store) for _ in range(10)]

    assert all(r == results[0] for r in results)


def test_never_mutates_any_real_opportunity(tmp_path):
    store = _store(tmp_path)
    a = _opp("a", "affiliate", competition=0.2, evidence_count=2)
    b = _opp("b", "saas", competition=0.8, evidence_count=1)
    store.save_opportunity(a)
    store.save_opportunity(b)

    advance_opportunity_comparisons(store)

    reloaded_a = store.get_opportunity(a.id)
    reloaded_b = store.get_opportunity(b.id)
    assert reloaded_a.stage == "ranked"
    assert reloaded_b.stage == "ranked"
    assert reloaded_a.history == []
    assert reloaded_b.history == []
