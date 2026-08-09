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

POLL_INTERVAL_SECONDS = 5

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"


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


def create_app(brain: CEOBrain | None = None) -> Starlette:
    """Builds the real, real ASGI app. `brain` is injectable — the same
    dependency-injection discipline every other real component in this
    codebase already uses, so tests never touch real production state."""
    brain = brain if brain is not None else CEOBrain()

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
            Route("/api/events", api_events),
        ]
    )

