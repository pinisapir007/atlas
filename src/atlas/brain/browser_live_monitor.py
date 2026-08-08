"""Browser Live Monitoring (2026-08-09, Vision V1) — real, honest
scope: ATLAS has no persistent background process/daemon anywhere in
its real execution model (tick() runs on a schedule; every CLI/API
call is a fresh, short-lived process). "Live monitoring" here
honestly means what's actually buildable on that real foundation:
taking a real observation now, comparing it to a real previous
observation, and reporting what genuinely changed -- repeated,
on-demand snapshot diffing, not a continuously-running watcher
process. Calling this "continuous background monitoring" would be a
fabricated capability this codebase does not have; this module names
what it really is.

Reuses BrowserObserver unchanged -- this is a diffing utility over
real, already-produced PageObservations, not a new browser capability.
"""

from dataclasses import dataclass

from atlas.integrations.base import BrowserObserver, PageObservation


@dataclass
class BrowserChangeResult:
    """The real, detected difference between two real observations of
    the same real URL. `changed` is the honest, top-level verdict;
    the specific fields name exactly what changed, never a vague
    "something changed" with no detail."""

    changed: bool
    title_changed: bool
    text_changed: bool
    previous_title: str
    current_title: str
    previous_text_length: int
    current_text_length: int


def observe_and_compare(
    observer: BrowserObserver,
    url: str,
    previous: PageObservation | None,
) -> tuple[PageObservation, BrowserChangeResult]:
    """Takes one real, fresh observation of `url` and compares it to a
    real previous observation (from an earlier real call to this same
    function, or to observer.observe() directly) — `previous=None`
    (the first real check) always reports changed=True, honestly,
    since there is nothing real to compare against yet. Returns both
    the new real observation (for the caller to keep as `previous` on
    the next real check) and the real comparison result."""
    current = observer.observe(url)

    if previous is None:
        return current, BrowserChangeResult(
            changed=True,
            title_changed=True,
            text_changed=True,
            previous_title="",
            current_title=current.title,
            previous_text_length=0,
            current_text_length=len(current.text_content),
        )

    title_changed = previous.title != current.title
    text_changed = previous.text_content != current.text_content

    return current, BrowserChangeResult(
        changed=title_changed or text_changed,
        title_changed=title_changed,
        text_changed=text_changed,
        previous_title=previous.title,
        current_title=current.title,
        previous_text_length=len(previous.text_content),
        current_text_length=len(current.text_content),
    )
