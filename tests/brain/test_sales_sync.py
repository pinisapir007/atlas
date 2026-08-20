import pytest

from atlas.brain.kpi import KPIRegistry
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.brain.sales_sync import record_real_sale, sync_digistore24_sales


def _world(tmp_path):
    kpis = KPIRegistry(BrainMemory(tmp_path / "brain.json"))
    ledger = Ledger(tmp_path / "ledger.json")
    return kpis, ledger


def test_records_a_real_new_sale(tmp_path):
    kpis, ledger = _world(tmp_path)

    recorded = record_real_sale("goal-1", "txn-abc", 47.0, kpis, ledger, provider="digistore24")

    assert recorded is True
    assert kpis.latest("revenue_goal-1") == 47.0
    entries = ledger.entries_for_transaction("txn-abc")
    assert len(entries) == 1
    assert entries[0].amount == 47.0
    assert entries[0].provider == "digistore24"
    assert entries[0].kind == "revenue_claimed"


def test_the_same_transaction_id_is_never_recorded_twice(tmp_path):
    kpis, ledger = _world(tmp_path)

    first = record_real_sale("goal-1", "txn-abc", 47.0, kpis, ledger)
    second = record_real_sale("goal-1", "txn-abc", 47.0, kpis, ledger)

    assert first is True
    assert second is False
    assert kpis.latest("revenue_goal-1") == 47.0  # not 94.0 -- never double-counted
    assert len(ledger.entries_for_transaction("txn-abc")) == 1


def test_two_real_distinct_sales_both_accumulate(tmp_path):
    kpis, ledger = _world(tmp_path)

    record_real_sale("goal-1", "txn-a", 47.0, kpis, ledger)
    record_real_sale("goal-1", "txn-b", 33.0, kpis, ledger)

    assert kpis.latest("revenue_goal-1") == 80.0


def test_raises_on_an_empty_transaction_id(tmp_path):
    kpis, ledger = _world(tmp_path)

    with pytest.raises(ValueError, match="transaction_id"):
        record_real_sale("goal-1", "", 47.0, kpis, ledger)


def test_a_real_cost_is_recorded_alongside_revenue(tmp_path):
    kpis, ledger = _world(tmp_path)

    record_real_sale("goal-1", "txn-a", 47.0, kpis, ledger, cost=10.0)

    assert kpis.latest("revenue_goal-1") == 47.0
    assert kpis.latest("cost_goal-1") == 10.0
    kinds = {e.kind for e in ledger.entries_for_transaction("txn-a")}
    assert kinds == {"revenue_claimed", "cost"}


class _FakeDigistore24Provider:
    name = "digistore24"

    def __init__(self, sales):
        self._sales = sales

    def fetch_recent_sales(self):
        return self._sales


def test_sync_returns_empty_when_no_credential_is_configured(tmp_path):
    kpis, ledger = _world(tmp_path)
    provider = _FakeDigistore24Provider(None)  # real convention: None means "no credential configured"

    recorded = sync_digistore24_sales(provider, parse_sale=lambda raw: None, kpis=kpis, ledger=ledger)

    assert recorded == []


def test_sync_records_every_real_sale_the_parser_can_attribute(tmp_path):
    kpis, ledger = _world(tmp_path)
    raw_sales = [{"order_id": "1001", "total": 47.0}, {"order_id": "1002", "total": 33.0}]
    provider = _FakeDigistore24Provider(raw_sales)

    def parse_sale(raw):
        return ("goal-1", raw["order_id"], raw["total"])

    recorded = sync_digistore24_sales(provider, parse_sale, kpis, ledger)

    assert recorded == ["1001", "1002"]
    assert kpis.latest("revenue_goal-1") == 80.0


def test_sync_skips_a_raw_sale_the_parser_cannot_attribute_to_a_goal(tmp_path):
    kpis, ledger = _world(tmp_path)
    raw_sales = [{"order_id": "1001", "total": 47.0}, {"order_id": "unknown-product"}]
    provider = _FakeDigistore24Provider(raw_sales)

    def parse_sale(raw):
        if raw["order_id"] == "1001":
            return ("goal-1", "1001", 47.0)
        return None  # real, honest "can't attribute this one" case

    recorded = sync_digistore24_sales(provider, parse_sale, kpis, ledger)

    assert recorded == ["1001"]


def test_sync_never_double_records_a_sale_seen_again_on_a_later_sync(tmp_path):
    kpis, ledger = _world(tmp_path)
    provider = _FakeDigistore24Provider([{"order_id": "1001", "total": 47.0}])
    parse_sale = lambda raw: ("goal-1", raw["order_id"], raw["total"])

    first = sync_digistore24_sales(provider, parse_sale, kpis, ledger)
    second = sync_digistore24_sales(provider, parse_sale, kpis, ledger)  # same real sale still in the API's "recent" window

    assert first == ["1001"]
    assert second == []  # already recorded -- not recorded again
    assert kpis.latest("revenue_goal-1") == 47.0
