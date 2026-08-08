"""HandsRequest (2026-08-09, Hands V1) — the durable record of one real
Hands dispatch: a founder-approved-or-auto-safe SEQUENCE of one or more
concrete real actions (browser or desktop), executed atomically within
one real session. Deliberately a sequence, not a single action: this is
the one, honest mechanism behind "Multi-Step Task Execution" — a
multi-step Hands dispatch is not a second orchestration engine bolted
on top, it is a structural property every HandsRequest already has.

Mirrors Campaign/ExecutionPlan's exact "durable record correlated to a
real, risk-gated Task" shape: `HandsRequest.id` is what
`Task.source_opportunity_id` points back to (reusing that field's own
documented, generalized role — "a correlation key... reused across
several bridges to mean 'what this dispatch is about', not always
literally an opportunity" — exactly this case).

Every risk axis here is an honest, caller-declared fact about the
SPECIFIC real sequence being requested, mirroring how every other real
Task creator in this codebase already declares its own risk axes
explicitly rather than having them inferred. Defaults are fail-closed
(`reversible=False`), the same default `Task` itself already uses —
unless a caller affirmatively says a sequence is safe, RiskPolicy
requires founder approval before it ever runs.
"""

from dataclasses import dataclass, field

from atlas.brain.models import new_id, now

# Real, executable step kinds -- an explicit, documented, bounded set
# (the same "open-but-bounded" discipline TEMPLATE_KINDS/ExecutionStep.kind
# already established), split by which real executor (BrowserHands vs
# DesktopHands) owns it. A single HandsRequest's steps must be
# homogeneous (all BROWSER_STEP_KINDS or all DESKTOP_STEP_KINDS) --
# interleaving the two within one atomic dispatch is deliberately out of
# scope for V1, not silently broken.
BROWSER_STEP_KINDS = {
    "navigate",  # params: url, new_tab(optional)
    "click",  # params: index
    "input_text",  # params: index, text
    "upload_file",  # params: index, path
    "send_keys",  # params: keys (e.g. "Enter", "Control+a")
    "scroll",  # params: down(optional), pages(optional), index(optional)
    "describe_page",  # params: {} -- real DOM text, for discovering indices ahead of a later request
}

DESKTOP_STEP_KINDS = {
    "move_mouse",  # params: x, y
    "click_mouse",  # params: x(optional), y(optional), button(optional, default "left")
    "type_text",  # params: text
    "send_keys",  # params: keys (raw SendKeys syntax, e.g. "{ENTER}")
    "launch_app",  # params: path, args(optional list[str])
    "close_app",  # params: process_name
}


class InvalidHandsRequestError(ValueError):
    """Raised when a HandsRequest's steps are empty, unrecognized, or mix
    browser and desktop step kinds in one atomic dispatch — the same
    fail-closed validation discipline `create_campaign()` already applies
    to its own inputs."""


@dataclass
class HandsRequest:
    goal_id: str
    steps: list[dict] = field(default_factory=list)  # [{"kind": str, "params": dict}, ...]
    reversible: bool = False
    estimated_amount: float = 0.0
    involves_privileged_access: bool = False
    involves_legal_agreement: bool = False
    description: str = ""
    status: str = "pending"  # pending -> done | failed
    results: list[dict] = field(default_factory=list)  # one real per-step result, honest partial record on failure
    task_id: str | None = None
    id: str = field(default_factory=lambda: new_id("hands"))
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)

    def executor(self) -> str:
        """Which real executor this request's steps belong to
        ("browser" or "desktop") — validated fail-closed by
        validate_steps() before this is ever trusted."""
        first_kind = self.steps[0]["kind"]
        return "browser" if first_kind in BROWSER_STEP_KINDS else "desktop"


def validate_steps(steps: list[dict]) -> None:
    """Fail-closed validation shared by every real caller before a
    HandsRequest is ever stored or dispatched — never trust an empty,
    unrecognized, or mixed-executor step list."""
    if not steps:
        raise InvalidHandsRequestError("a real HandsRequest needs at least one step")

    kinds = [step.get("kind") for step in steps]
    unknown = [k for k in kinds if k not in BROWSER_STEP_KINDS and k not in DESKTOP_STEP_KINDS]
    if unknown:
        raise InvalidHandsRequestError(f"unrecognized step kind(s): {unknown!r}")

    is_browser = [k in BROWSER_STEP_KINDS for k in kinds]
    if any(is_browser) and not all(is_browser):
        raise InvalidHandsRequestError("a single HandsRequest cannot mix browser and desktop steps")
