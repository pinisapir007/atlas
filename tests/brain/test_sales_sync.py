import pytest

from atlas.brain.kpi import KPIRegistry
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.brain.sales_sync import record_real_sale, sync_digistore24_sales, sync_digistore24_commissions, advance_sales_sync


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



class _FakeCommissionProvider:
    name = "digistore24"

    def __init__(self, commissions, transactions, tracking):
        self._commissions = commissions
        self._transactions = transactions
        self._tracking = tracking

    def fetch_recent_commissions(self):
        return self._commissions

    def fetch_recent_transactions(self):
        return self._transactions

    def get_purchase_tracking(self, purchase_id):
        return self._tracking.get(purchase_id)


def test_commission_sync_records_payment_and_refund(tmp_path):
    kpis, ledger = _world(tmp_path)

    provider = _FakeCommissionProvider(
        commissions=[
            {
                "id": 101,
                "amount": 12.34,
                "currency": "EUR",
                "transaction_id": 1001,
                "purchase_id": "PUR-1",
            },
            {
                "id": 102,
                "amount": -3.0,
                "currency": "EUR",
                "transaction_id": 1002,
                "purchase_id": "PUR-1",
            },
        ],
        transactions=[
            {"id": 1001, "transaction_type": "payment"},
            {"id": 1002, "transaction_type": "refund"},
        ],
        tracking={"PUR-1": {"campaign_key": "goal-1"}},
    )

    result = sync_digistore24_commissions(
        provider, {"goal-1"}, kpis, ledger
    )

    assert result == ["101", "102"]
    assert kpis.latest("revenue_goal-1") == pytest.approx(9.34)

    entries = ledger.entries_for_goal("goal-1")
    assert [(e.kind, e.amount) for e in entries] == [
        ("revenue_claimed", 12.34),
        ("refund", 3.0),
    ]
    assert {e.currency for e in entries} == {"EUR"}
    assert {e.provider_event_id for e in entries} == {"101", "102"}


def test_commission_sync_is_idempotent_by_provider_event(tmp_path):
    kpis, ledger = _world(tmp_path)

    provider = _FakeCommissionProvider(
        commissions=[{
            "id": 201,
            "amount": 10.0,
            "currency": "EUR",
            "transaction_id": 2001,
            "purchase_id": "PUR-2",
        }],
        transactions=[{"id": 2001, "transaction_type": "payment"}],
        tracking={"PUR-2": {"campaign_key": "goal-1"}},
    )

    first = sync_digistore24_commissions(
        provider, {"goal-1"}, kpis, ledger
    )
    second = sync_digistore24_commissions(
        provider, {"goal-1"}, kpis, ledger
    )

    assert first == ["201"]
    assert second == []
    assert kpis.latest("revenue_goal-1") == 10.0
    assert len(ledger.entries_for_goal("goal-1")) == 1


def test_refund_request_does_not_change_revenue(tmp_path):
    kpis, ledger = _world(tmp_path)

    provider = _FakeCommissionProvider(
        commissions=[{
            "id": 301,
            "amount": -5.0,
            "currency": "EUR",
            "transaction_id": 3001,
            "purchase_id": "PUR-3",
        }],
        transactions=[
            {"id": 3001, "transaction_type": "refund_request"}
        ],
        tracking={"PUR-3": {"campaign_key": "goal-1"}},
    )

    result = sync_digistore24_commissions(
        provider, {"goal-1"}, kpis, ledger
    )

    assert result == []
    assert kpis.latest("revenue_goal-1") is None
    assert ledger.entries() == []


def test_unknown_campaign_key_is_not_recorded(tmp_path):
    kpis, ledger = _world(tmp_path)

    provider = _FakeCommissionProvider(
        commissions=[{
            "id": 401,
            "amount": 8.0,
            "currency": "EUR",
            "transaction_id": 4001,
            "purchase_id": "PUR-X",
        }],
        transactions=[{"id": 4001, "transaction_type": "payment"}],
        tracking={"PUR-X": {"campaign_key": "unknown-goal"}},
    )

    result = sync_digistore24_commissions(
        provider, {"goal-1"}, kpis, ledger
    )

    assert result == []
    assert ledger.entries() == []



def test_advance_sales_sync_is_inert_when_flag_is_off(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_SALES_SYNC_ENABLED", raising=False)
    kpis, ledger = _world(tmp_path)

    provider = _FakeCommissionProvider(
        commissions=[{
            "id": 501,
            "amount": 20.0,
            "currency": "EUR",
            "transaction_id": 5001,
            "purchase_id": "PUR-5",
        }],
        transactions=[{"id": 5001, "transaction_type": "payment"}],
        tracking={"PUR-5": {"campaign_key": "goal-1"}},
    )

    class Goal:
        id = "goal-1"

    result = advance_sales_sync([Goal()], kpis, ledger, provider)

    assert result == []
    assert kpis.latest("revenue_goal-1") is None
    assert ledger.entries() == []


def test_advance_sales_sync_runs_when_flag_is_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("ATLAS_SALES_SYNC_ENABLED", "1")
    kpis, ledger = _world(tmp_path)

    provider = _FakeCommissionProvider(
        commissions=[{
            "id": 601,
            "amount": 20.0,
            "currency": "EUR",
            "transaction_id": 6001,
            "purchase_id": "PUR-6",
        }],
        transactions=[{"id": 6001, "transaction_type": "payment"}],
        tracking={"PUR-6": {"campaign_key": "goal-1"}},
    )

    class Goal:
        id = "goal-1"

    result = advance_sales_sync([Goal()], kpis, ledger, provider)

    assert result == ["601"]
    assert kpis.latest("revenue_goal-1") == 20.0
    assert len(ledger.entries_for_goal("goal-1")) == 1
