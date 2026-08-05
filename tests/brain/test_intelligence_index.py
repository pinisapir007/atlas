from atlas.brain.intelligence_index import IntelligenceIndex
from atlas.integrations.base import Intelligence


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_all_intelligence_starts_empty():
    index = IntelligenceIndex(store=_FakeStore())
    assert index.all_intelligence() == []
    assert index.count() == 0


def test_replace_index_can_be_queried_without_a_new_collection():
    index = IntelligenceIndex(store=_FakeStore())
    items = [
        Intelligence(provider="findings_market_intelligence", domain="market", subject="KetoDNA", summary="real evidence"),
        Intelligence(provider="findings_market_intelligence", domain="market", subject="Widget", summary="other evidence"),
    ]

    index.replace_index(items)

    assert index.count() == 2
    assert {i.subject for i in index.all_intelligence()} == {"KetoDNA", "Widget"}


def test_get_returns_the_real_item_by_provider_and_subject():
    index = IntelligenceIndex(store=_FakeStore())
    index.replace_index([Intelligence(provider="findings_market_intelligence", domain="market", subject="KetoDNA", summary="real evidence")])

    item = index.get("findings_market_intelligence", "KetoDNA")

    assert item is not None
    assert item.summary == "real evidence"


def test_get_returns_none_for_an_unknown_provider_subject_pair():
    index = IntelligenceIndex(store=_FakeStore())
    assert index.get("no_such_provider", "no_such_subject") is None


def test_by_domain_filters_correctly():
    index = IntelligenceIndex(store=_FakeStore())
    index.replace_index(
        [
            Intelligence(provider="findings_market_intelligence", domain="market", subject="KetoDNA", summary="a"),
            Intelligence(provider="competitor_intelligence", domain="competitor", subject="RivalCo", summary="b"),
        ]
    )

    assert [i.subject for i in index.by_domain("market")] == ["KetoDNA"]
    assert [i.subject for i in index.by_domain("competitor")] == ["RivalCo"]
    assert index.by_domain("economic") == []


def test_by_subject_filters_correctly():
    index = IntelligenceIndex(store=_FakeStore())
    index.replace_index(
        [
            Intelligence(provider="findings_market_intelligence", domain="market", subject="KetoDNA", summary="a"),
            Intelligence(provider="competitor_intelligence", domain="competitor", subject="KetoDNA", summary="b"),
        ]
    )

    result = index.by_subject("KetoDNA")

    assert len(result) == 2
    assert {i.domain for i in result} == {"market", "competitor"}


def test_replace_index_is_a_full_replacement_not_an_incremental_merge():
    index = IntelligenceIndex(store=_FakeStore())
    index.replace_index([Intelligence(provider="p1", domain="market", subject="a", summary="x")])
    assert index.count() == 1

    index.replace_index([Intelligence(provider="p1", domain="market", subject="b", summary="y")])

    assert index.count() == 1
    assert index.get("p1", "a") is None
    assert index.get("p1", "b") is not None


def test_the_same_subject_from_two_different_providers_are_distinct_entries():
    index = IntelligenceIndex(store=_FakeStore())
    index.replace_index(
        [
            Intelligence(provider="provider_a", domain="market", subject="Widget", summary="from A"),
            Intelligence(provider="provider_b", domain="market", subject="Widget", summary="from B"),
        ]
    )

    assert index.count() == 2
