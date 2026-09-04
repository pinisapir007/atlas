"""Sales Sync V1 (2026-08-06, M7 — Autonomous Revenue). The real
mechanism behind "a real sale is detected and recorded without a
human running a CLI command" — but honestly split in two, because
only one half can be written without guessing:

1. `record_real_sale()` — the real, idempotent recording primitive.
   Fully real, fully testable today: given an already-normalized real
   sale (goal_id, transaction_id, amount), records it exactly once,
   keyed by transaction_id, never double-counting a sale seen again
   on a later sync. Distinct from kpi_intake.record_manual_revenue():
   that function is for a founder-typed reading; this one is for a
   real, automatically-detected event, even though both share the
   same accumulate-onto-KPI mechanism underneath.

2. `sync_digistore24_sales()` — the real orchestration: calls the real
   Digistore24Provider.fetch_recent_sales(), and for each raw record,
   calls an injected `parse_sale` to normalize it. Deliberately NO
   default real `parse_sale` is provided here. Digistore24's actual
   per-purchase field shape has never been observed (Digistore24Provider.
   fetch_recent_sales's own docstring says so directly), and how one raw
   sale maps to a specific real Goal isn't defined anywhere in this
   codebase either. Writing a default parser now would mean guessing
   both — exactly the "guessing a live financial API's shape is a real
   risk, not a shortcut" rule this codebase has refused to break
   everywhere else (see Digistore24Provider's own module docstring).
   The real parser is the one, single, small piece of this module that
   a real, live Digistore24 account and one real observed response
   must inform — not fabricated here.
"""

from collections.abc import Callable

from atlas.brain.feature_flags import sales_sync_enabled
from atlas.brain.kpi import KPIRegistry
from atlas.brain.ledger import Ledger
from atlas.brain.models import LedgerEntry
from atlas.integrations.digistore24 import Digistore24Provider

# (goal_id, transaction_id, amount) or None to skip a raw record this
# account can't attribute to a real Goal.
SaleParser = Callable[[dict], tuple[str, str, float] | None]


def record_real_sale(
    goal_id: str,
    transaction_id: str,
    amount: float,
    kpis: KPIRegistry,
    ledger: Ledger,
    provider: str = "",
    cost: float | None = None,
) -> bool:
    """Records one real, automatically-detected sale exactly once.
    Returns True if newly recorded, False if `transaction_id` was
    already recorded on a prior call — real duplicate prevention, so
    the same sale seen again on a later sync (e.g. still within the
    provider's real "recent sales" window) is never double-counted.
    Raises ValueError for an empty transaction_id -- idempotency has
    nothing real to key on without one, and silently accepting "" would
    make every keyless call collide with every other, undercounting
    real, distinct sales instead."""
    if not transaction_id:
        raise ValueError("a real transaction_id is required -- idempotency depends on it")
    if ledger.entries_for_transaction(transaction_id):
        return False

    current_revenue = kpis.latest(f"revenue_{goal_id}") or 0.0
    kpis.record(f"revenue_{goal_id}", current_revenue + amount)
    ledger.record(
        LedgerEntry(goal_id=goal_id, kind="revenue_claimed", amount=amount, transaction_id=transaction_id, provider=provider)
    )

    if cost is not None:
        current_cost = kpis.latest(f"cost_{goal_id}") or 0.0
        kpis.record(f"cost_{goal_id}", current_cost + cost)
        ledger.record(
            LedgerEntry(goal_id=goal_id, kind="cost", amount=cost, transaction_id=transaction_id, provider=provider)
        )
    return True


def sync_digistore24_sales(
    provider: Digistore24Provider,
    parse_sale: SaleParser,
    kpis: KPIRegistry,
    ledger: Ledger,
) -> list[str]:
    """Calls the real fetch_recent_sales() and records each real,
    newly-seen sale exactly once via record_real_sale(). Returns the
    real transaction_ids newly recorded this call. Empty when
    fetch_recent_sales() returns None (no credential configured) --
    the same "not available right now" convention every provider in
    this codebase already uses -- or an empty list (a real, successful
    check that genuinely found nothing, a different, honest fact from
    "not configured")."""
    raw_sales = provider.fetch_recent_sales()
    if not raw_sales:
        return []

    recorded: list[str] = []
    for raw in raw_sales:
        parsed = parse_sale(raw)
        if parsed is None:
            continue
        goal_id, transaction_id, amount = parsed
        if record_real_sale(goal_id, transaction_id, amount, kpis, ledger, provider=provider.name):
            recorded.append(transaction_id)
    return recorded



_FINANCIAL_KINDS = {
    "revenue_claimed",
    "cash_settled",
    "cost",
    "fee",
    "refund",
}


def _assert_goal_currency_compatible(
    goal_id: str,
    currency: str,
    ledger: Ledger,
) -> None:
    """Never aggregate different or unknown monetary units into one KPI."""
    currency = currency.strip().upper()
    if not currency:
        raise ValueError("automated financial event requires currency")

    prior = [
        e for e in ledger.entries_for_goal(goal_id)
        if e.kind in _FINANCIAL_KINDS
    ]
    if not prior:
        return

    if any(not e.currency for e in prior):
        raise ValueError(
            f"goal {goal_id!r} has prior financial entries with unknown "
            f"currency; refusing automated {currency} aggregation"
        )

    known = {e.currency.upper() for e in prior}
    if known != {currency}:
        raise ValueError(
            f"goal {goal_id!r} already uses currency {sorted(known)!r}; "
            f"refusing to mix with {currency!r}"
        )


def sync_digistore24_commissions(
    provider: Digistore24Provider,
    valid_goal_ids: set[str],
    kpis: KPIRegistry,
    ledger: Ledger,
) -> list[str]:
    """Record attributable Digistore24 commission events exactly once.

    Official chain:
      listCommissions -> event/transaction/purchase/commission amount
      listTransactions -> payment/refund/chargeback semantics
      getPurchaseTracking -> campaign_key -> existing ATLAS goal_id

    refund_request is intentionally ignored because it is not yet a
    completed reversal.
    """
    commissions = provider.fetch_recent_commissions()
    if not commissions:
        return []

    transactions = provider.fetch_recent_transactions()
    if not transactions:
        return []

    tx_types = {}
    for tx in transactions:
        tx_id = tx.get("id")
        tx_type = tx.get("transaction_type")
        if tx_id is not None and isinstance(tx_type, str):
            tx_types[str(tx_id)] = tx_type.strip().lower()

    recorded = []

    for commission in commissions:
        event_raw = commission.get("id")
        tx_raw = commission.get("transaction_id")
        purchase_raw = commission.get("purchase_id")
        amount_raw = commission.get("amount")
        currency_raw = commission.get("currency")

        if event_raw is None or tx_raw is None:
            raise ValueError("Digistore24 commission lacks event/transaction id")
        if not isinstance(purchase_raw, str) or not purchase_raw.strip():
            raise ValueError("Digistore24 commission lacks purchase_id")
        if isinstance(amount_raw, bool) or not isinstance(amount_raw, (int, float)):
            raise ValueError("Digistore24 commission lacks numeric amount")
        if not isinstance(currency_raw, str) or not currency_raw.strip():
            raise ValueError("Digistore24 commission lacks currency")

        event_id = str(event_raw)
        transaction_id = str(tx_raw)
        purchase_id = purchase_raw.strip()
        amount = float(amount_raw)
        currency = currency_raw.strip().upper()

        # Provider-native event ID is the idempotency key.
        if ledger.entries_for_provider_event(provider.name, event_id):
            continue

        transaction_type = tx_types.get(transaction_id)

        # No semantics = no financial mutation.
        if transaction_type is None:
            continue

        if transaction_type == "refund_request":
            continue

        if transaction_type not in {"payment", "refund", "chargeback"}:
            continue

        tracking = provider.get_purchase_tracking(purchase_id)
        if not tracking:
            continue

        campaign_key = tracking.get("campaign_key")
        if not isinstance(campaign_key, str) or not campaign_key.strip():
            continue

        goal_id = campaign_key.strip()

        # Never fabricate a Goal from external tracking text.
        if goal_id not in valid_goal_ids:
            continue

        _assert_goal_currency_compatible(goal_id, currency, ledger)

        current = kpis.latest(f"revenue_{goal_id}") or 0.0
        reason = str(commission.get("reason") or "commission")

        if transaction_type == "payment":
            if amount < 0:
                raise ValueError("payment commission cannot be negative")

            kpis.record(f"revenue_{goal_id}", current + amount)

            ledger.record(
                LedgerEntry(
                    goal_id=goal_id,
                    kind="revenue_claimed",
                    amount=amount,
                    transaction_id=transaction_id,
                    provider=provider.name,
                    provider_event_id=event_id,
                    currency=currency,
                    category=reason,
                    evidence=(
                        f"digistore24 commission event={event_id}; "
                        f"purchase={purchase_id}; type=payment"
                    ),
                )
            )

        else:
            reversal = abs(amount)

            kpis.record(f"revenue_{goal_id}", current - reversal)

            ledger.record(
                LedgerEntry(
                    goal_id=goal_id,
                    kind="refund",
                    amount=reversal,
                    transaction_id=transaction_id,
                    provider=provider.name,
                    provider_event_id=event_id,
                    currency=currency,
                    category=reason,
                    evidence=(
                        f"digistore24 commission event={event_id}; "
                        f"purchase={purchase_id}; type={transaction_type}"
                    ),
                )
            )

        recorded.append(event_id)

    return recorded



def advance_sales_sync(
    goals,
    kpis: KPIRegistry,
    ledger: Ledger,
    provider: Digistore24Provider | None = None,
) -> list[str]:
    """Production bridge for autonomous revenue synchronization.

    Completely inert unless ATLAS_SALES_SYNC_ENABLED is set. The provider
    is not even constructed while disabled, so an off flag guarantees zero
    Digistore24 network calls from this bridge.
    """
    if not sales_sync_enabled():
        return []

    real_provider = provider if provider is not None else Digistore24Provider()
    valid_goal_ids = {goal.id for goal in goals}

    return sync_digistore24_commissions(
        real_provider,
        valid_goal_ids,
        kpis,
        ledger,
    )
