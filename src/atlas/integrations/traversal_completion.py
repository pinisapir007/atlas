"""Page Completion Contract + bounded Revisit (2026-08-15, Digital Body
Foundation) -- the real answer to the gap the M1 Page 2/3 detail-id work
surfaced: content-completeness (every record seen at least once) is not
the same fact as inspection-completeness (every record that needed a
closer look actually got one). "UNKNOWN because never re-inspected" was
being silently treated the same as an acceptable completion outcome; this
module makes that state explicit, bounded, and never silently dropped.

Traversal-local, in-memory, NEVER persisted -- this is process state
about what has/hasn't been inspected during ONE traversal session, not
durable knowledge (the same "currentness computed/tracked, not stored as
a permanent fact" discipline docs/BUSINESS_BRAIN_AGENTIC_OS_SPECIFICATION
.md's Cognitive Growth Foundation section already establishes elsewhere).
It must never be added to MarketplaceProductRecord or any
KnowledgeBase-persisted shape -- PageCompletionTracker holds no reference
to knowledge.py anywhere, structurally, not just by convention.

Deliberately generic: this module has zero knowledge of Marketplace,
dedupe_key(), or detail_id -- the caller supplies `key`/`data`/
`extract_fn`/`inspect_fn`, the same "caller supplies domain knowledge via
callback" discipline that already keeps DiscoveryScrollAdvancer reusable
for any virtualized-list discovery, not just the Marketplace.
"""

from dataclasses import dataclass, field
from typing import Callable

# The minimum semantic set: not_yet_inspected is the only non-terminal
# state; the other three are real, distinct outcomes an inspection can
# resolve to -- proven_missing is a legitimate, permanent finding (e.g.
# Prime Perform Supplement EN structurally has no detail link), not a
# failure to be confused with insufficient investigation.
INSPECTION_STATES = {"not_yet_inspected", "inspected", "proven_missing", "ambiguous_unresolved"}
_RESOLVED_STATES = INSPECTION_STATES - {"not_yet_inspected"}

MAX_REVISIT_PASSES = 5  # small, explicit, editable -- same class as MAX_DISCOVERY_CYCLES elsewhere in this codebase


@dataclass
class TrackedRecord:
    key: str
    data: object
    inspection_state: str = "not_yet_inspected"


class PageCompletionTracker:
    """Pure bookkeeping, no browser interaction anywhere in this class --
    every method here is synchronous and side-effect-free beyond its own
    in-memory dict."""

    def __init__(self) -> None:
        self._records: dict[str, TrackedRecord] = {}

    def observe(self, key: str, data: object) -> bool:
        """Adds a newly-seen key (starts "not_yet_inspected"), or
        refreshes an already-known key's `data` WITHOUT resetting its
        inspection_state -- the same preserve-on-update discipline
        MarketplaceCatalogStore.save_records() already established for
        detail_id, generalized here to the whole record. This is what
        makes the union virtualization-safe: a card that scrolls out of
        view and back never loses its accumulated inspection progress.
        Returns True if `key` was genuinely new to this tracker."""
        is_new = key not in self._records
        if is_new:
            self._records[key] = TrackedRecord(key=key, data=data)
        else:
            self._records[key].data = data
        return is_new

    def resolve(self, key: str, state: str) -> None:
        """Fail-closed: `state` must be a real resolved state (never
        "not_yet_inspected" -- that's the default, not something to
        explicitly resolve back to), and `key` must already be observed
        -- resolving something never seen would silently invent a
        record."""
        if state not in _RESOLVED_STATES:
            raise ValueError(f"resolve() requires a resolved state, one of {sorted(_RESOLVED_STATES)}, got {state!r}")
        if key not in self._records:
            raise KeyError(f"cannot resolve an unobserved key: {key!r}")
        self._records[key].inspection_state = state

    def pending_keys(self) -> list[str]:
        return [k for k, r in self._records.items() if r.inspection_state == "not_yet_inspected"]

    def is_inspection_complete(self) -> bool:
        return not self.pending_keys()

    def is_page_complete(self, content_complete: bool) -> bool:
        """Page Complete = CONTENT COMPLETE + INSPECTION COMPLETE, both
        required. `content_complete` is the caller's own signal (e.g. the
        existing pages_below==0 + stable-reads criteria already proven
        for M1) -- this class has no opinion on how content-completeness
        itself is decided, the same reusability boundary as everywhere
        else in this module."""
        return content_complete and self.is_inspection_complete()

    def records(self) -> list[TrackedRecord]:
        return list(self._records.values())

    def unresolved_report(self) -> list[str]:
        """Keys still not_yet_inspected -- for honest reporting. Never
        silently dropped; a caller declaring completion must consult this
        explicitly (is_page_complete()/is_inspection_complete() already
        do), so a genuinely unresolved record can never vanish quietly."""
        return self.pending_keys()

    def to_dict(self) -> dict:
        """Pure serialization -- no I/O, no new imports, this module
        stays exactly as dependency-free as before (2026-08-17, Cognitive
        State Wiring: PageCompletionTracker was found to be in-memory-
        only, forgotten every process exit -- real, durable persistence
        is atlas.brain.inspection_memory's job, using this codebase's own
        BrainStore/JSONFileStore pattern; this class itself never learns
        about storage, only how to describe its own state as plain data
        and rebuild itself from that description)."""
        return {
            key: {"data": record.data, "inspection_state": record.inspection_state}
            for key, record in self._records.items()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PageCompletionTracker":
        tracker = cls()
        for key, entry in data.items():
            tracker._records[key] = TrackedRecord(key=key, data=entry["data"], inspection_state=entry["inspection_state"])
        return tracker


@dataclass
class RevisitOutcome:
    passes_used: int
    resolved_this_run: int
    stopped_reason: str  # "all_resolved" | "max_passes" | "no_progress"
    remaining_pending: list[str] = field(default_factory=list)


def revisit_until_resolved(
    url: str,
    tracker: PageCompletionTracker,
    advancer,  # a DiscoveryScrollAdvancer, or anything with the same .advance(...) shape (duck-typed for testability)
    extract_fn: Callable[[str], list[tuple[str, object]]],
    inspect_fn: Callable[[str, str, object], str | None],
    verify_target: Callable[[str], bool] | None = None,
    max_passes: int = MAX_REVISIT_PASSES,
    content_change_timeout: float = 15.0,
) -> RevisitOutcome:
    """One bounded revisit loop: scroll UP (`advancer.advance(..., direction="up",
    include_dom=True)`), re-extract via `extract_fn` (keeps the union
    current -- new/refreshed records observed even during a reverse
    pass), then attempt `inspect_fn(key, text, selector_map)` for every
    currently-pending key using THIS SAME advance() call's text and
    selector_map (never a separate, later read -- the "48317 lesson",
    structurally enforced since both come from one ScrollAdvanceResult).

    `inspect_fn` returns a real resolved state (a value from
    INSPECTION_STATES minus "not_yet_inspected") if it could determine
    one from the current text/selector_map, or `None` if the key still
    isn't resolvable this pass (not currently in view, or genuinely
    inconclusive) -- resolution never happens on a stale/absent read.

    Re-identification is by `key` alone (e.g. a dedupe_key the caller
    computes) -- never scroll position or coordinates; a key that
    reappears in ANY revisit pass is recognized correctly regardless of
    where it lands on screen.

    Stops on: nothing left pending ("all_resolved"), `max_passes`
    exhausted ("max_passes"), or a pass that resolves zero keys
    ("no_progress" -- never loops forever chasing something unresolvable).
    Never fabricates success -- `remaining_pending` on the returned
    RevisitOutcome names exactly what's still unresolved, explicitly, for
    honest reporting."""
    passes_used = 0
    resolved_total = 0

    while True:
        if not tracker.pending_keys():
            stopped_reason = "all_resolved"
            break
        if passes_used >= max_passes:
            stopped_reason = "max_passes"
            break

        result = advancer.advance(
            url,
            verify_target=verify_target,
            direction="up",
            content_change_timeout=content_change_timeout,
            include_dom=True,
        )
        passes_used += 1

        for key, data in extract_fn(result.text_content):
            tracker.observe(key, data)

        resolved_this_pass = 0
        for key in tracker.pending_keys():
            outcome = inspect_fn(key, result.text_content, result.selector_map)
            if outcome is not None:
                tracker.resolve(key, outcome)
                resolved_this_pass += 1

        resolved_total += resolved_this_pass
        if resolved_this_pass == 0:
            stopped_reason = "no_progress"
            break

    return RevisitOutcome(
        passes_used=passes_used,
        resolved_this_run=resolved_total,
        stopped_reason=stopped_reason,
        remaining_pending=tracker.pending_keys(),
    )
