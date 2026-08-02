"""The interactive ATLAS console — a persistent REPL. Every founder action
here calls straight into the existing CEOBrain.approve()/reject() and
Registry.dispatch(...) — no business logic is duplicated, this module is
presentation and dispatch only.
"""

import os

from atlas.brain.ceo import CEOBrain
from atlas.brain.console import (
    build_briefing,
    build_console_view,
    find_warnings,
    format_console_view,
    get_campaigns,
    get_opportunities,
    get_queue,
    recent_activity,
    summarize_department_report,
)
from atlas.speech import speak

HELP_TEXT = """Commands:
  status         consolidated view: goals, approvals, departments, KPIs
  briefing       narrative briefing of current state
  departments    each department's status
  approvals      list of tasks awaiting your approval
  approve <id>   approve a task (calls the existing CEOBrain.approve())
  reject <id>    reject a task (calls the existing CEOBrain.reject())
  queue          the publishing queue
  campaigns      opportunities currently in the content/marketing pipeline
  opportunities  the full affiliate opportunity list, with stage and score
  kpi            all recorded KPIs
  warnings       MAYA/Revenue/redesign/stale-KPI warnings
  activity       recent log activity
  exit           quit the console"""


def run_repl(brain: CEOBrain | None = None, input_lines=None, speak_enabled: bool | None = None, print_fn=print) -> None:
    brain = brain if brain is not None else CEOBrain()
    if speak_enabled is None:
        speak_enabled = os.environ.get("ATLAS_CONSOLE_SPEAK") == "1"

    briefing = build_briefing(brain)
    print_fn(briefing)
    if speak_enabled:
        speak(briefing)
    print_fn(f"\n{HELP_TEXT}")

    source = iter(input_lines) if input_lines is not None else None
    while True:
        try:
            line = next(source) if source is not None else input("atlas> ")
        except (StopIteration, EOFError, KeyboardInterrupt):
            print_fn("")
            return
        line = line.strip()
        if not line:
            continue
        if dispatch(brain, line, print_fn=print_fn) is False:
            return


def dispatch(brain: CEOBrain, line: str, print_fn=print) -> bool | None:
    """Returns False to signal the REPL should stop; otherwise None."""
    # A leading BOM shows up here in practice (e.g. PowerShell piping stdin
    # as UTF-8-with-BOM) — strip it defensively so the first command in a
    # scripted/piped session isn't silently misread as unknown.
    line = line.replace(chr(0xFEFF), "")
    parts = line.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else None

    if cmd in ("exit", "quit"):
        return False
    if cmd == "status":
        print_fn(format_console_view(build_console_view(brain)))
    elif cmd == "briefing":
        print_fn(build_briefing(brain))
    elif cmd == "departments":
        _print_departments(brain, print_fn)
    elif cmd == "approvals":
        _print_approvals(brain, print_fn)
    elif cmd == "approve":
        _do_approve(brain, arg, print_fn)
    elif cmd == "reject":
        _do_reject(brain, arg, print_fn)
    elif cmd == "queue":
        _print_queue(brain, print_fn)
    elif cmd == "campaigns":
        _print_campaigns(brain, print_fn)
    elif cmd == "opportunities":
        _print_opportunities(brain, print_fn)
    elif cmd == "kpi":
        _print_kpis(brain, print_fn)
    elif cmd == "warnings":
        _print_warnings(brain, print_fn)
    elif cmd == "activity":
        _print_activity(brain, print_fn)
    else:
        print_fn(f"unknown command: {cmd!r} — type 'status' to see everything, or see the command list below.")
        print_fn(HELP_TEXT)
    return None


def _print_departments(brain: CEOBrain, print_fn) -> None:
    view = build_console_view(brain)
    for asset_id, report in view["departments"].items():
        print_fn(f"  {asset_id}: {summarize_department_report(report)}")


def _print_approvals(brain: CEOBrain, print_fn) -> None:
    view = build_console_view(brain)
    if not view["pending_approvals"]:
        print_fn("No pending approvals.")
        return
    for a in view["pending_approvals"]:
        print_fn(f"  [{a['category']}] {a['description']} ({a['id']})")


def _do_approve(brain: CEOBrain, task_id: str | None, print_fn) -> None:
    if not task_id:
        print_fn("usage: approve <task_id>")
        return
    try:
        task = brain.approve(task_id)  # the existing, unmodified brain logic
    except KeyError as exc:
        print_fn(f"error: {exc}")
        return
    print_fn(f"{task.id} -> {task.status}")


def _do_reject(brain: CEOBrain, task_id: str | None, print_fn) -> None:
    if not task_id:
        print_fn("usage: reject <task_id>")
        return
    try:
        task = brain.reject(task_id)  # the existing, unmodified brain logic
    except KeyError as exc:
        print_fn(f"error: {exc}")
        return
    print_fn(f"{task.id} -> {task.status}")


def _print_queue(brain: CEOBrain, print_fn) -> None:
    packages = get_queue(brain)
    if not packages:
        print_fn("Queue is empty.")
        return
    for p in packages:
        print_fn(f"  {p['id']}\t{p['status']}\t{p['platform']}\t{p['title']}")


def _print_campaigns(brain: CEOBrain, print_fn) -> None:
    campaigns = get_campaigns(brain)
    if not campaigns:
        print_fn("No opportunities currently in the content/marketing pipeline.")
        return
    for o in campaigns:
        print_fn(f"  {o['id']}\t{o['stage']}\t{o['product_name']}")


def _print_opportunities(brain: CEOBrain, print_fn) -> None:
    opportunities = get_opportunities(brain)
    if not opportunities:
        print_fn("No opportunities yet.")
        return
    for o in opportunities:
        print_fn(f"  {o['id']}\t{o['stage']}\tscore={o.get('score', 0.0):.4f}\t{o['product_name']}")


def _print_kpis(brain: CEOBrain, print_fn) -> None:
    view = build_console_view(brain)
    if not view["kpis"]:
        print_fn("No KPIs recorded yet.")
        return
    for name, value in sorted(view["kpis"].items()):
        print_fn(f"  {name} = {value}")


def _print_warnings(brain: CEOBrain, print_fn) -> None:
    warnings = find_warnings(brain)
    if not warnings:
        print_fn("No warnings.")
        return
    for w in warnings:
        print_fn(f"  ! {w}")


def _print_activity(brain: CEOBrain, print_fn) -> None:
    activity = recent_activity(brain)
    if not activity:
        print_fn("No activity recorded yet.")
        return
    for entry in activity:
        print_fn(f"  {entry}")
