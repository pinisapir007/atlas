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
