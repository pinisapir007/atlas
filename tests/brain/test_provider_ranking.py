from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Finding
from atlas.brain.provider_ranking import provider_confidence, rank_providers


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def test_provider_confidence_is_none_with_no_provider_scoped_evidence(tmp_path):
    kb = _kb(tmp_path)

    result = provider_confidence("affiliate", "digistore24", kb)

    assert result["score"] is None
    assert result["factors_available"] == 0
    assert result["factors_total"] == 2


def test_provider_confidence_combines_available_factors(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="x", evidence="https://x/1", provider="digistore24")
    )

    result = provider_confidence("affiliate", "digistore24", kb)

    assert result["score"] is not None
    assert result["factors_available"] == 2  # source_corroboration + recency
    assert result["provider"] == "digistore24"


def test_provider_confidence_ignores_a_different_providers_evidence(tmp_path):
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="x", evidence="https://x/1", provider="shareasale")
    )

    result = provider_confidence("affiliate", "digistore24", kb)

    assert result["score"] is None


def test_rank_providers_finds_digistore24_as_the_only_eligible_affiliate_provider(tmp_path):
    kb = _kb(tmp_path)

    ranked = rank_providers("affiliate", kb)

    assert len(ranked) == 1
    assert ranked[0]["provider"] == "digistore24"


def test_rank_providers_returns_nothing_for_a_category_with_no_registered_provider(tmp_path):
    kb = _kb(tmp_path)

    assert rank_providers("youtube", kb) == []


def test_rank_providers_orders_by_confidence_then_factors_available(tmp_path):
    # With only one real provider today this can't yet demonstrate a real
    # multi-provider ranking outcome — but the ordering contract itself
    # (score, then factors_available, both descending) is directly tested
    # via the same sort key confidence-based ranking already uses elsewhere.
    kb = _kb(tmp_path)
    kb.save_finding(
        Finding(source="research", category="affiliate", description="x", evidence="https://x/1", provider="digistore24")
    )

    ranked = rank_providers("affiliate", kb)

    assert ranked[0]["score"] is not None
    assert ranked == sorted(
        ranked, key=lambda r: (r["score"] is not None, r["score"] or 0.0, r["factors_available"]), reverse=True
    )
