"""Future Capability Recall + Gates, Phase 1 (2026-08-15): the trigger
registry and lifecycle logic for FutureItem (atlas.brain.models).

Founder's core requirement, structurally enforced here, not just
documented: a deferred idea must never become a one-time notification
someone can miss. due_future_items() is a pure, read-only function that
recomputes due-ness fresh every call from real, current state -- the
same "nothing is permanently true, recompute fresh" discipline
decision_engine.decide() already established. There is no "seen"/
"acknowledged"/"notified" field anywhere on FutureItem to silence it
with -- the only way a due item stops being surfaced is a real,
explicit resolution via resolve_future_item().

TRIGGER_CHECKS (2026-08-15, real, honest state): starts EMPTY. Every
real trigger a FutureItem could reference must be a deterministic,
testable predicate over real system state (a registered Campaign
reaching a real milestone, a real ContentPublisher being registered,
...) -- never free text like "when we reach M6", which is exactly the
un-enforceable "someone will remember" pattern this mechanism replaces.
Mirrors the same "reserved, zero implementations until a real one is
justified" precedent atlas.integrations.signal_registry.SIGNAL_PROVIDERS
and atlas.integrations.base.ContentPublisher already established --
this file's job is the mechanism, not inventing predicates that don't
exist yet.

UNWIRED_TRIGGER_CHECK is the one other valid trigger_check value: an
explicit, honest "no real predicate exists yet for this item" --
deliberately preferred, per standing instruction (2026-08-15), over
fabricating a fake-but-plausible-looking predicate just to make a
FutureItem look fully wired up. An unwired item is never reported as
"trigger fired" (there is no real check to fire) -- see
due_future_items()'s separate `unwired` bucket, kept distinct from
`trigger_fired` so a caller can never confuse "we don't know yet" with
"the real condition is true".
"""

from typing import Callable

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import FUTURE_ITEM_RESOLUTIONS, FutureItem, now

UNWIRED_TRIGGER_CHECK = "not_yet_wired"

# Real, named, testable predicates over real system state. Starts empty
# -- see module docstring. Adding a real trigger is one new entry here,
# never a change to FutureItem/KnowledgeBase/due_future_items().
TRIGGER_CHECKS: dict[str, Callable[[], bool]] = {}


def is_valid_trigger_check(trigger_check: str) -> bool:
    return trigger_check == UNWIRED_TRIGGER_CHECK or trigger_check in TRIGGER_CHECKS


def due_future_items(knowledge: KnowledgeBase) -> dict[str, list[FutureItem]]:
    """Every non-resolved FutureItem, split into two real, honestly
    distinct categories -- never merged into one ambiguous list:

    - `trigger_fired`: a real, registered TRIGGER_CHECKS predicate for
      this item evaluated True right now. This is the "must stay
      visibly due until an explicit resolution is recorded" set.
    - `unwired`: trigger_check == UNWIRED_TRIGGER_CHECK -- whether it's
      genuinely due cannot be determined yet (no real predicate exists),
      but the item must not be silently invisible either.

    Pure and read-only: never mutates status/triggered_at. Deciding what
    to do with a due item (surface it in a briefing, create a Task, ...)
    is deliberately not this function's job -- see the module docstring
    and Phase 2 notes in the design doc."""
    trigger_fired: list[FutureItem] = []
    unwired: list[FutureItem] = []

    for item in knowledge.future_items():
        if item.status == "resolved":
            continue
        if item.trigger_check == UNWIRED_TRIGGER_CHECK:
            unwired.append(item)
            continue
        check = TRIGGER_CHECKS.get(item.trigger_check)
        if check is not None and check():
            trigger_fired.append(item)

    return {"trigger_fired": trigger_fired, "unwired": unwired}


def resolve_future_item(
    item_id: str,
    resolution: str,
    resolution_notes: str,
    knowledge: KnowledgeBase,
    next_trigger_check: str | None = None,
) -> tuple[FutureItem, FutureItem | None]:
    """Records a real, explicit resolution for one FutureItem -- the
    only way a due item stops being surfaced (see module docstring).
    Fail-closed: `resolution` must be one of FUTURE_ITEM_RESOLUTIONS;
    "deferred_again" requires a real `next_trigger_check` (a registered
    TRIGGER_CHECKS key or UNWIRED_TRIGGER_CHECK), never silently reused
    from the original item -- a re-deferral names what it's now waiting
    on, explicitly, every time.

    The original item is marked resolved (status="resolved",
    resolved_at=now()) -- never deleted, never mutated beyond this,
    the same append-only-in-spirit discipline Decision/DecisionLog
    already establish (a changed verdict is a new record, not an edit
    to the old one). For "deferred_again", a new FutureItem is created
    carrying `next_trigger_check` as its own trigger_check, chained back
    via superseded_by_id -- the same superseded_id chain Decision
    already uses. Returns (resolved_original, new_item_or_None)."""
    if resolution not in FUTURE_ITEM_RESOLUTIONS:
        raise ValueError(f"unknown FutureItem resolution: {resolution!r} (must be one of {sorted(FUTURE_ITEM_RESOLUTIONS)})")

    item = knowledge.get_future_item(item_id)

    new_item: FutureItem | None = None
    if resolution == "deferred_again":
        if not next_trigger_check:
            raise ValueError("deferred_again requires a real next_trigger_check (a registered key or UNWIRED_TRIGGER_CHECK)")
        if not is_valid_trigger_check(next_trigger_check):
            raise ValueError(f"unknown trigger_check: {next_trigger_check!r} (not in TRIGGER_CHECKS and not UNWIRED_TRIGGER_CHECK)")
        new_item = FutureItem(
            type=item.type,
            title=item.title,
            rationale=item.rationale,
            trigger_description=f"Deferred again from {item.id}: {resolution_notes}",
            trigger_check=next_trigger_check,
            source_description=item.source_description,
            evidence_finding_ids=list(item.evidence_finding_ids),
            applicable_capabilities=list(item.applicable_capabilities),
        )
        knowledge.save_future_item(new_item)

    item.status = "resolved"
    item.resolution = resolution
    item.resolution_notes = resolution_notes
    item.resolved_at = now()
    if new_item is not None:
        item.superseded_by_id = new_item.id
    knowledge.save_future_item(item)

    return item, new_item
