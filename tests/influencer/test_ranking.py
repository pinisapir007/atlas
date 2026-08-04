from atlas.brain.kpi import KPIRegistry
from atlas.brain.memory import BrainMemory
from atlas.influencer.models import DigitalInfluencer, IdentityProfile
from atlas.influencer.performance import record_metric
from atlas.influencer.ranking import prefer_market_match, rank_influencers
from atlas.influencer.registry import InfluencerRegistry


def _kpis(tmp_path) -> KPIRegistry:
    return KPIRegistry(BrainMemory(tmp_path / "brain.json"))


def _registry(tmp_path) -> InfluencerRegistry:
    return InfluencerRegistry(tmp_path / "influencers.json")


def _influencer(name, categories, status="active") -> DigitalInfluencer:
    return DigitalInfluencer(identity=IdentityProfile(name=name), categories=categories, status=status)


def test_rank_influencers_is_empty_when_none_are_tagged_for_the_category(tmp_path):
    registry, kpis = _registry(tmp_path), _kpis(tmp_path)
    registry.save_influencer(_influencer("Mira", categories=["digital_product"]))

    assert rank_influencers("affiliate", registry, kpis) == []


def test_rank_influencers_excludes_retired_influencers(tmp_path):
    registry, kpis = _registry(tmp_path), _kpis(tmp_path)
    registry.save_influencer(_influencer("Mira", categories=["affiliate"], status="retired"))

    assert rank_influencers("affiliate", registry, kpis) == []


def test_rank_influencers_ranks_more_real_evidence_first(tmp_path):
    registry, kpis = _registry(tmp_path), _kpis(tmp_path)
    thin = _influencer("Thin", categories=["affiliate"])
    rich = _influencer("Rich", categories=["affiliate"])
    registry.save_influencer(thin)
    registry.save_influencer(rich)
    record_metric(rich.id, "followers", 10000.0, kpis)
    record_metric(rich.id, "views", 50000.0, kpis)

    ranked = rank_influencers("affiliate", registry, kpis)

    assert [r["influencer_id"] for r in ranked] == [rich.id, thin.id]
    assert ranked[0]["factors_available"] == 2
    assert ranked[1]["factors_available"] == 0


def test_rank_influencers_never_fabricates_a_score_with_no_real_data(tmp_path):
    registry, kpis = _registry(tmp_path), _kpis(tmp_path)
    registry.save_influencer(_influencer("Mira", categories=["affiliate"]))

    ranked = rank_influencers("affiliate", registry, kpis)

    assert ranked[0]["metrics"] == {"followers": None, "views": None, "engagement_rate": None}
    assert "score" not in ranked[0]  # deliberately no blended numeric score yet — see ranking.py docstring


def test_rank_influencers_only_includes_influencers_tagged_for_that_specific_category(tmp_path):
    registry, kpis = _registry(tmp_path), _kpis(tmp_path)
    affiliate_only = _influencer("Mira", categories=["affiliate"])
    both = _influencer("Kai", categories=["affiliate", "digital_product"])
    registry.save_influencer(affiliate_only)
    registry.save_influencer(both)

    affiliate_ranked = {r["influencer_id"] for r in rank_influencers("affiliate", registry, kpis)}
    digital_product_ranked = {r["influencer_id"] for r in rank_influencers("digital_product", registry, kpis)}

    assert affiliate_ranked == {affiliate_only.id, both.id}
    assert digital_product_ranked == {both.id}


# --- prefer_market_match ---------------------------------------------------


def test_prefer_market_match_falls_back_to_top_ranked_when_market_is_unset(tmp_path):
    registry, kpis = _registry(tmp_path), _kpis(tmp_path)
    top = DigitalInfluencer(identity=IdentityProfile(name="Top", market="US"), categories=["affiliate"])
    registry.save_influencer(top)
    ranked = rank_influencers("affiliate", registry, kpis)

    chosen = prefer_market_match(ranked, "", registry)

    assert chosen == ranked[0]


def test_prefer_market_match_falls_back_to_top_ranked_when_no_candidate_matches(tmp_path):
    registry, kpis = _registry(tmp_path), _kpis(tmp_path)
    registry.save_influencer(DigitalInfluencer(identity=IdentityProfile(name="Mira", market="DE"), categories=["affiliate"]))
    ranked = rank_influencers("affiliate", registry, kpis)

    chosen = prefer_market_match(ranked, "US", registry)

    # No candidate is built for "US" -- never blocks on it, falls back to top-ranked.
    assert chosen == ranked[0]


def test_prefer_market_match_prefers_a_real_market_match_over_a_higher_ranked_non_match(tmp_path):
    registry, kpis = _registry(tmp_path), _kpis(tmp_path)
    rich_wrong_market = DigitalInfluencer(identity=IdentityProfile(name="Rich", market="DE"), categories=["affiliate"])
    thin_right_market = DigitalInfluencer(identity=IdentityProfile(name="Thin", market="US"), categories=["affiliate"])
    registry.save_influencer(rich_wrong_market)
    registry.save_influencer(thin_right_market)
    record_metric(rich_wrong_market.id, "followers", 10000.0, kpis)
    ranked = rank_influencers("affiliate", registry, kpis)
    assert ranked[0]["influencer_id"] == rich_wrong_market.id  # confirms it really is ranked higher

    chosen = prefer_market_match(ranked, "US", registry)

    assert chosen["influencer_id"] == thin_right_market.id


def test_prefer_market_match_returns_none_when_nothing_is_ranked(tmp_path):
    registry = _registry(tmp_path)

    assert prefer_market_match([], "US", registry) is None
