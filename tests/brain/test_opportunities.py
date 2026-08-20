import pytest

from atlas.brain.models import Finding, Opportunity, OPPORTUNITY_STAGES
from atlas.brain.opportunities import OpportunityStore


def test_round_trips_an_opportunity(tmp_path):
    store = OpportunityStore(tmp_path / "opportunities.json")
    opp = Opportunity(subject="Keto Diet Guide", description="a real candidate niche", category="affiliate")
    store.save_opportunity(opp)

    reloaded = OpportunityStore(tmp_path / "opportunities.json").get_opportunity(opp.id)
    assert reloaded.subject == "Keto Diet Guide"
    assert reloaded.category == "affiliate"
    assert reloaded.stage == "discovered"


def test_opportunities_persist_across_instances(tmp_path):
    path = tmp_path / "opportunities.json"
    OpportunityStore(path).save_opportunity(Opportunity(subject="x", description="d", category="saas"))

    assert len(OpportunityStore(path).opportunities()) == 1


def test_missing_opportunity_raises_keyerror(tmp_path):
    store = OpportunityStore(tmp_path / "opportunities.json")
    with pytest.raises(KeyError):
        store.get_opportunity("does-not-exist")


def test_by_category_filters_correctly(tmp_path):
    store = OpportunityStore(tmp_path / "opportunities.json")
    store.save_opportunity(Opportunity(subject="a", description="d", category="affiliate"))
    store.save_opportunity(Opportunity(subject="b", description="d", category="saas"))

    assert len(store.by_category("affiliate")) == 1
    assert len(store.by_category("saas")) == 1


def test_by_stage_filters_correctly(tmp_path):
    store = OpportunityStore(tmp_path / "opportunities.json")
    selected = Opportunity(subject="a", description="d", category="affiliate", stage="selected")
    lost = Opportunity(subject="b", description="d", category="affiliate", stage="lost")
    store.save_opportunity(selected)
    store.save_opportunity(lost)

    assert [o.id for o in store.by_stage("selected")] == [selected.id]


def test_transition_updates_stage_and_appends_history(tmp_path):
    store = OpportunityStore(tmp_path / "opportunities.json")
    opp = Opportunity(subject="a", description="d", category="affiliate")
    opp.transition("researched", "real evidence gathered")
    opp.transition("selected", "cleared the evidence bar")
    store.save_opportunity(opp)

    reloaded = store.get_opportunity(opp.id)
    assert reloaded.stage == "selected"
    assert len(reloaded.history) == 2
    assert reloaded.history[0]["stage"] == "researched"
    assert reloaded.history[1]["reason"] == "cleared the evidence bar"


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "opportunities.json"
    store = OpportunityStore(path)
    store.save_opportunity(Opportunity(subject="a", description="d", category="affiliate"))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()


def test_every_opportunity_stage_is_a_real_recognized_value():
    assert set(OPPORTUNITY_STAGES) == {"discovered", "researched", "ranked", "selected", "lost"}
    # deliberately excludes atlas.assets.affiliate_department.models.STAGES'
    # own downstream content-production values -- those belong to a
    # channel-specific extension, never to the universal core
    # (docs/DESIGN_OPPORTUNITY_UNIVERSAL_CORE.md)
    excluded = {"content_planned", "selected_for_marketing", "content_packaged", "editorial_passed", "approved_for_marketing"}
    assert not excluded & set(OPPORTUNITY_STAGES)


class TestUniversalCoreFalsificationAcrossTwoGenuinelyDifferentChannels:
    """docs/DESIGN_OPPORTUNITY_UNIVERSAL_CORE.md's own falsification test:
    two Opportunities from genuinely different channels (affiliate, saas),
    using ONLY core fields, must move through the exact same lifecycle and
    accumulate real evidence with zero channel-specific code. If either
    needed a Part-B (affiliate-only) field to function, the core would not
    actually be general -- that would be a real finding, not a failure to
    hide."""

    def test_an_affiliate_flavored_opportunity_moves_through_the_shared_lifecycle(self, tmp_path):
        store = OpportunityStore(tmp_path / "opportunities.json")
        finding = Finding(
            source="research", category="affiliate", description="real Keto affiliate program data",
            evidence="https://example.com/keto", subject="Keto Diet Guide", market="US",
        )
        opp = Opportunity(
            subject="Keto Diet Guide",
            description="a real affiliate candidate",
            category="affiliate",
            marketing_niche="Keto Diet / Weight Loss",
            recommended_market="US",
            competition=0.4,
            score=0.82,
            provider="digistore24",
            evidence_finding_ids=[finding.id],
        )
        opp.transition("researched")
        opp.transition("ranked")
        opp.transition("selected", "cleared the evidence bar")
        store.save_opportunity(opp)

        reloaded = store.get_opportunity(opp.id)
        assert reloaded.stage == "selected"
        assert reloaded.evidence_finding_ids == [finding.id]

    def test_a_saas_flavored_opportunity_moves_through_the_identical_lifecycle(self, tmp_path):
        # Same fields, same code path, a genuinely different real business
        # model -- no affiliate-only field (commission_per_conversion,
        # real_affiliate_link, content_brief, etc.) is used or needed.
        store = OpportunityStore(tmp_path / "opportunities.json")
        finding = Finding(
            source="research", category="saas", description="real B2B SaaS market sizing data",
            evidence="https://example.com/saas-market", subject="Project Management SaaS", market="US",
        )
        opp = Opportunity(
            subject="Project Management SaaS",
            description="a real saas candidate",
            category="saas",
            marketing_niche="Small Business Project Management",
            recommended_market="US",
            competition=0.7,
            score=0.65,
            provider="",  # no real external network for a direct SaaS build -- honestly empty, never guessed
            evidence_finding_ids=[finding.id],
        )
        opp.transition("researched")
        opp.transition("ranked")
        opp.transition("selected", "cleared the evidence bar")
        store.save_opportunity(opp)

        reloaded = store.get_opportunity(opp.id)
        assert reloaded.stage == "selected"
        assert reloaded.evidence_finding_ids == [finding.id]

    def test_both_channels_are_comparable_side_by_side_with_zero_channel_specific_code(self, tmp_path):
        store = OpportunityStore(tmp_path / "opportunities.json")
        affiliate_opp = Opportunity(subject="Keto Diet Guide", description="d", category="affiliate", score=0.82)
        saas_opp = Opportunity(subject="Project Management SaaS", description="d", category="saas", score=0.65)
        store.save_opportunity(affiliate_opp)
        store.save_opportunity(saas_opp)

        all_opportunities = store.opportunities()
        # the same, single, generic comparison a real Executive Reasoning
        # step would perform -- ranking by `score` needs no knowledge of
        # which category is affiliate vs. saas
        ranked = sorted(all_opportunities, key=lambda o: o.score or 0.0, reverse=True)
        assert [o.category for o in ranked] == ["affiliate", "saas"]
