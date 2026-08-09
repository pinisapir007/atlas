"""ATLAS Headquarters (2026-08-09) — the real, unified operator interface
the founder asked for: "the best possible workspace for an AI CEO," not
a generic dashboard. Every real data point shown here is read straight
from functions that already exist and are already tested
(atlas.brain.console, CEOBrain, recall()) — this module owns
presentation and real-time surfacing only, never a second copy of any
state ATLAS already tracks. Build Once, Reuse Forever: Starlette,
uvicorn, and sse-starlette were already installed as transitive
dependencies (confirmed before writing a line of this file) — zero new
dependency was added to build a real local web server.

Honest about what "live" means here, the same discipline
browser_live_monitor.py already established: there is no real event bus
or persistent background process anywhere in ATLAS's execution model, so
the SSE stream is real, repeated polling of real state (every
POLL_INTERVAL_SECONDS) pushed to the browser — not true push-based
events. This is stated plainly in the frontend, never implied to be more
than it is.
"""

import asyncio
import json
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from sse_starlette.sse import EventSourceResponse

from atlas.brain.asset_value import rank_success_laws_by_track_record, success_law_lifetime_value
from atlas.brain.ceo import CEOBrain
from atlas.brain.console import (
    build_briefing,
    build_console_view,
    find_warnings,
    get_campaigns,
    get_opportunities,
    get_queue,
    get_system_health,
    recent_activity,
    summarize_department_report,
)
from atlas.brain.recall import recall
from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.base import AIProvider

POLL_INTERVAL_SECONDS = 5

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"

# First-person grounding prompt for real conversational presence
# (2026-08-09) -- the mechanism behind "ATLAS receives me, briefs me,
# answers my questions." Deliberately instructs the model to speak only
# from the real facts handed to it (the same build_briefing()/pending-
# approvals data already shown on the page, never a second,
# independently-guessed picture) and to say "I don't know" rather than
# invent -- the Prime Directive (ATLAS_CONSTITUTION.md Article III)
# applies to this conversational surface exactly as it does everywhere
# else in this codebase, not just to Findings/Decisions.
_ATLAS_PERSONA_PROMPT = (
    "You are ATLAS, the autonomous AI CEO of this real company. You are "
    "speaking directly with the founder, in his office. Reply in the same "
    "language he used. Speak in first person, as a real CEO would -- "
    "confident but honest, and never invent a fact, number, goal, or "
    "approval that isn't in your real state below. If something isn't "
    "there, say so plainly instead of guessing. Keep the reply "
    "conversational and concise -- a few real sentences, not a report "
    "dump.\n\n"
    "Your real current state:\n{context}\n\n"
    "The founder just said: \"{message}\"\n\n"
    "Reply as ATLAS, directly to him:"
)


def _conversation_context(brain: CEOBrain) -> str:
    """Compact, real grounding facts for a conversational turn -- reuses
    build_briefing() (the same real "since you were last here" narrative
    already on the page) plus the real pending-approval descriptions
    (build_console_view's own shape, not a re-derived one), so ATLAS's
    spoken answers are grounded in exactly the facts the page already
    shows."""
    lines = [build_briefing(brain)]
    pending = build_console_view(brain)["pending_approvals"]
    if pending:
        lines.append(
            "\nFull detail on the item(s) awaiting approval mentioned in the "
            "summary above (this is the same real list, not additional items):"
        )
        for task in pending[:10]:
            lines.append(f"- [{task['category']}] {task['description']}")
    return "\n".join(lines)


def _real_decisions(brain: CEOBrain, limit: int = 8) -> list[dict]:
    """Most-recent real Decisions, newest first — DecisionLog is already
    append-only and real; this only reads and sorts it, never a second
    decision-recording mechanism."""
    decisions = sorted(brain.decisions.decisions(), key=lambda d: d.created_at, reverse=True)[:limit]
    return [
        {"id": d.id, "category": d.category, "verdict": d.verdict, "confidence": d.confidence, "created_at": d.created_at}
        for d in decisions
    ]


def _real_success_laws(brain: CEOBrain, limit: int = 8) -> list[dict]:
    """Real Success Laws ranked by real, measured track record — the
    exact function 'atlas brain law list' already uses, not a new
    ranking mechanism built for this page."""
    laws = brain.knowledge.success_laws()
    ranked = rank_success_laws_by_track_record(laws, brain.campaigns, brain.memory, brain.kpis)[:limit]
    return [
        {
            "id": law.id,
            "principle": law.principle,
            "evidence_backed": bool(law.evidence_finding_ids),
            "track_record": success_law_lifetime_value(law.id, brain.campaigns, brain.memory, brain.kpis),
        }
        for law in ranked
    ]


def _real_active_asset_ids(brain: CEOBrain) -> list[str]:
    """Which real departments/assets have real work in flight right now
    -- Task.assigned_asset_id for every task whose real status is
    "delegated" or "in_progress" (the same IN_FLIGHT_STATUSES Monitor
    already uses to decide what to sync). This is the real, honest
    signal behind "a department lights up when it's active" -- never a
    decorative always-on animation, only ever true while a real Task is
    genuinely outstanding against that asset."""
    return sorted(
        {t.assigned_asset_id for t in brain.memory.tasks() if t.status in {"delegated", "in_progress"} and t.assigned_asset_id}
    )


def _real_last_active(activity: list[dict], decisions: list[dict]) -> str | None:
    """The real timestamp of ATLAS's own most recent recorded action —
    not the moment this page happened to render. Sourced only from
    timestamps ATLAS itself already wrote (the outcome/decision log),
    never the browser's clock, so the founder sees when ATLAS last
    actually did something, not when they last looked."""
    timestamps = [e.get("at") for e in activity if e.get("at")]
    timestamps += [d.get("created_at") for d in decisions if d.get("created_at")]
    return max(timestamps) if timestamps else None


def _real_state(brain: CEOBrain) -> dict:
    """One real, honest snapshot of everything ATLAS currently tracks —
    the exact same functions every CLI command already reads, never a
    second, parallel view of the same state."""
    view = build_console_view(brain)
    departments = {
        asset_id: {"raw": report, "summary": summarize_department_report(report)}
        for asset_id, report in view["departments"].items()
    }
    activity = recent_activity(brain, limit=12)
    decisions = _real_decisions(brain)
    return {
        "goals": view["goals"],
        "pending_approvals": view["pending_approvals"],
        "blocked": view["blocked"],
        "departments": departments,
        "active_asset_ids": _real_active_asset_ids(brain),
        "kpis": view["kpis"],
        "cash_flow": view["cash_flow"],
        "warnings": find_warnings(brain),
        "activity": activity,
        "system_health": get_system_health(brain),
        "queue": get_queue(brain),
        "campaigns": get_campaigns(brain),
        "opportunities": get_opportunities(brain),
        "decisions": decisions,
        "success_laws": _real_success_laws(brain),
        "briefing": build_briefing(brain),
        "atlas_last_active": _real_last_active(activity, decisions),
    }


def create_app(brain: CEOBrain | None = None, ai_provider: AIProvider | None = None) -> Starlette:
    """Builds the real, real ASGI app. `brain` is injectable — the same
    dependency-injection discipline every other real component in this
    codebase already uses, so tests never touch real production state.
    `ai_provider` is injectable for the same reason: a real Claude CLI
    call costs real money and real seconds (see claude_provider.py's own
    docstring) — tests inject a fake, never make a real call."""
    brain = brain if brain is not None else CEOBrain()
    ai_provider = ai_provider if ai_provider is not None else get_ai_provider("claude")

    async def index(request):
        return HTMLResponse(_TEMPLATE_PATH.read_text(encoding="utf-8"))

    async def api_state(request):
        return JSONResponse(_real_state(brain))

    async def api_approve(request):
        task_id = request.path_params["task_id"]
        try:
            task = brain.approve(task_id)
        except KeyError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        return JSONResponse({"id": task.id, "status": task.status})

    async def api_reject(request):
        task_id = request.path_params["task_id"]
        try:
            task = brain.reject(task_id)
        except KeyError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        return JSONResponse({"id": task.id, "status": task.status})

    async def api_tick(request):
        """Runs the real operational cycle right now -- the exact same
        CEOBrain.tick() the real Windows Scheduled Task calls every 30
        minutes. A real CEO shouldn't have to wait for the clock."""
        brain.tick()
        return JSONResponse(_real_state(brain))

    async def api_review(request):
        """Runs the real strategic review cycle for a real period --
        CEOBrain.review(), unchanged. This has real side effects
        (reallocates goals, may create redesign tasks), so it is a
        deliberate POST action, never run silently in the background."""
        period = request.path_params["period"]
        try:
            report = brain.review(period)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(report)

    async def api_recall(request):
        query = request.query_params.get("q", "")
        if not query:
            return JSONResponse({"hits": []})
        hits = recall(
            query,
            memory=brain.memory,
            knowledge=brain.knowledge,
            decisions=brain.decisions,
            campaigns=brain.campaigns,
            influencers=brain.influencers,
            brands=brain.brands,
            ledger=brain.ledger,
            execution_plans=brain.execution_plans,
            conversations=brain.conversations,
            limit=20,
        )
        return JSONResponse({"hits": [{"store": h.store, "id": h.id, "summary": h.summary, "created_at": h.created_at} for h in hits]})

    async def api_converse(request):
        """The real conversational core: a genuine, grounded reply from
        a real AI backend speaking as ATLAS -- not a scripted response.
        Deliberately a distinct, on-demand POST the founder must
        actively trigger (typing/speaking a message), never something
        the 5-second SSE poll or any background loop calls, since a
        real call here has a real cost (see claude_provider.py) every
        single time. Every real turn is recorded via ConversationMemory
        -- the same durable record the REPL/app already keep."""
        body = await request.json()
        message = (body.get("message") or "").strip()
        if not message:
            return JSONResponse({"error": "a real, non-empty message is required"}, status_code=400)

        prompt = _ATLAS_PERSONA_PROMPT.format(context=_conversation_context(brain), message=message)
        try:
            reply = await run_in_threadpool(ai_provider.complete, prompt)
        except Exception as exc:
            return JSONResponse({"error": f"ATLAS is not reachable right now: {exc}"}, status_code=502)

        brain.conversations.record_turn(message, reply)
        return JSONResponse({"reply": reply})

    async def api_conversations(request):
        """Real recent conversation history -- so opening Headquarters
        never starts from a cold, empty chat panel; the founder sees
        real continuity with what he and ATLAS already discussed."""
        entries = brain.conversations.recent(limit=20)
        return JSONResponse(
            {
                "entries": [
                    {"id": e.id, "input_line": e.input_line, "response_summary": e.response_summary, "created_at": e.created_at}
                    for e in entries
                ]
            }
        )

    async def api_events(request):
        async def stream():
            while True:
                if await request.is_disconnected():
                    break
                yield {"event": "state", "data": json.dumps(_real_state(brain))}
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        return EventSourceResponse(stream())

    return Starlette(
        routes=[
            Route("/", index),
            Route("/api/state", api_state),
            Route("/api/approve/{task_id}", api_approve, methods=["POST"]),
            Route("/api/reject/{task_id}", api_reject, methods=["POST"]),
            Route("/api/tick", api_tick, methods=["POST"]),
            Route("/api/review/{period}", api_review, methods=["POST"]),
            Route("/api/recall", api_recall),
            Route("/api/converse", api_converse, methods=["POST"]),
            Route("/api/conversations", api_conversations),
            Route("/api/events", api_events),
        ]
    )

