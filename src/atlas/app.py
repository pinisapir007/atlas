"""ATLAS — the full-screen application. Every command still goes through
atlas.repl.dispatch() (which calls straight into CEOBrain.approve()/
reject()/Registry.dispatch()) and every dashboard section reads from
atlas.brain.console's existing data functions. This module adds a
full-screen frame, a natural-language alias layer, and voice input/output
around all of it — no business logic lives here.
"""

import os

from atlas.brain.ceo import CEOBrain
from atlas.brain.console import (
    build_briefing,
    build_console_view,
    get_campaigns,
    get_opportunities,
    get_queue,
    get_system_health,
    recent_activity,
    summarize_department_report,
)
from atlas.repl import HELP_TEXT, dispatch
from atlas.speech import listen, speak

_LOGO_WIDTH = 50

# Natural-language phrasing mapped onto the exact same commands
# atlas.repl.dispatch already understands — a translation layer, not a
# second command interpreter. Anything not recognized here falls straight
# through to dispatch() unchanged, so every original command still works.
_ALIASES = {
    "how are we doing": "status",
    "how are things": "status",
    "what needs my attention": "approvals",
    "what needs attention": "approvals",
    "anything urgent": "warnings",
    "any warnings": "warnings",
    "is everything ok": "warnings",
    "show me the pipeline": "campaigns",
    "show the pipeline": "campaigns",
    "what's in the queue": "queue",
    "whats in the queue": "queue",
    "show opportunities": "opportunities",
    "show me opportunities": "opportunities",
    "how's revenue": "kpi",
    "hows revenue": "kpi",
    "how are we doing financially": "kpi",
    "what have you been doing": "activity",
    "what have you done": "activity",
    "goodbye": "exit",
    "bye": "exit",
    "quit": "exit",
}


def _normalize(line: str) -> str:
    stripped = line.strip().rstrip("?.!").lower()
    return _ALIASES.get(stripped, line)


def _build_logo() -> str:
    top = "╔" + "═" * _LOGO_WIDTH + "╗"
    bottom = "╚" + "═" * _LOGO_WIDTH + "╝"

    def _row(text: str) -> str:
        return "║" + text.center(_LOGO_WIDTH) + "║"

    return "\n".join([top, _row(""), _row("A T L A S"), _row("CEO Operating System"), _row(""), bottom])


def _clear(clear_fn=None) -> None:
    if clear_fn is not None:
        clear_fn()
        return
    os.system("cls" if os.name == "nt" else "clear")


def _render(brain: CEOBrain, transcript: list[str]) -> str:
    view = build_console_view(brain)
    health = get_system_health(brain)
    queue = get_queue(brain)
    campaigns = get_campaigns(brain)
    opportunities = get_opportunities(brain)

    lines = [_build_logo(), ""]
    lines.append(
        f"Goals: {len(view['goals'])}  |  Approvals waiting: {len(view['pending_approvals'])}  |  "
        f"Opportunities: {len(opportunities)}  |  Campaigns: {len(campaigns)}  |  Queue: {len(queue)}"
    )
    lines.append("")

    if health["warnings"]:
        lines.append("System health:")
        for w in health["warnings"]:
            lines.append(f"  ! {w}")
        lines.append("")

    lines.append("Departments:")
    for asset_id, report in view["departments"].items():
        lines.append(f"  {asset_id}: {summarize_department_report(report)}")
    lines.append("")

    lines.append("Business KPIs:")
    if view["kpis"]:
        for name, value in sorted(view["kpis"].items()):
            lines.append(f"  {name} = {value}")
    else:
        lines.append("  (none recorded yet)")
    lines.append("")

    lines.append("Pending Approvals:")
    if view["pending_approvals"]:
        for a in view["pending_approvals"]:
            lines.append(f"  [{a['category']}] {a['description']} ({a['id']})")
    else:
        lines.append("  (none)")
    lines.append("")

    activity = recent_activity(brain, limit=5)
    lines.append("Live activity:")
    if activity:
        for entry in activity:
            reason = entry.get("reason") or entry.get("status") or ""
            label = entry.get("description") or entry.get("goal_id") or entry.get("task_id", "")
            lines.append(f"  - {label}: {reason}".strip(": "))
    else:
        lines.append("  (nothing yet)")

    if transcript:
        lines.append("")
        lines.append("─" * (_LOGO_WIDTH + 2))
        lines.extend(transcript[-16:])
        lines.append("─" * (_LOGO_WIDTH + 2))

    return "\n".join(lines)


def _redraw(brain: CEOBrain, transcript: list[str], print_fn, clear_fn, footer: str | None = None) -> None:
    _clear(clear_fn)
    print_fn(_render(brain, transcript))
    if footer:
        print_fn(footer)


def run_app(
    brain: CEOBrain | None = None,
    input_lines=None,
    speak_enabled: bool | None = None,
    listen_enabled: bool = False,
    print_fn=print,
    clear_fn=None,
) -> None:
    brain = brain if brain is not None else CEOBrain()
    if speak_enabled is None:
        speak_enabled = os.environ.get("ATLAS_CONSOLE_SPEAK") == "1"

    briefing = build_briefing(brain)
    if speak_enabled:
        speak(briefing)

    transcript = [f"atlas: {briefing}"]
    footer = HELP_TEXT + ("\n(voice input enabled — type 'voice' to speak a command instead)" if listen_enabled else "")
    _redraw(brain, transcript, print_fn, clear_fn, footer=footer)

    source = iter(input_lines) if input_lines is not None else None
    while True:
        try:
            line = next(source) if source is not None else input("\natlas> ")
        except (StopIteration, EOFError, KeyboardInterrupt):
            print_fn("")
            return

        line = line.replace(chr(0xFEFF), "").strip()
        if not line:
            continue

        if listen_enabled and line.lower() in ("voice", "listen"):
            heard = listen()
            if heard is None:
                transcript.append("atlas: (voice input unavailable, or nothing was understood in time)")
                _redraw(brain, transcript, print_fn, clear_fn)
                continue
            line = heard

        transcript.append(f"you: {line}")
        buffer: list[str] = []
        result = dispatch(brain, _normalize(line), print_fn=buffer.append)
        transcript.extend(buffer)
        _redraw(brain, transcript, print_fn, clear_fn)

        if result is False:
            return
