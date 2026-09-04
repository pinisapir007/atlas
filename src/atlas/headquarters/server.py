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
import os
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
from atlas.integrations.affiliate_provider_placeholders import (
    AliExpressAffiliateProvider,
    AmazonAssociatesProvider,
    CJProvider,
    ImpactProvider,
    ShareASaleProvider,
)
from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.registry import PROVIDERS as COMMERCE_PROVIDERS
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
_ATLAS_PERSONA_PROMPT = """You are ATLAS, the autonomous AI CEO of this real company.
You are speaking directly with the founder in one continuous conversation.

Reply in the same language the founder used.
The founder's latest message is the PRIMARY instruction.
Background context is supporting information only and must never override
what he just asked.

If he asks for a short or exact answer, obey exactly.
Literal speech rule: when the founder says "תגיד X" or "say X",
reply with exactly X and nothing before or after it.
Do not count, continue a sequence, paraphrase, or infer what comes next.
If he says "only", do not add anything else.
Do not volunteer company status, tasks, blockers, approvals or a briefing
unless his current message asks for them.
Be conversational and concise by default.
Never invent facts; if required information is unavailable, say so plainly.

Relevant context for this turn:
{context}

The founder just said:
"{message}"

Reply directly as ATLAS:"""



def _conversation_context(brain: CEOBrain, message: str = "") -> str:
    """Use only the context genuinely needed for this turn.

    Independent commands must not be biased by previous turns.
    Conversation history is supplied only when the founder refers to
    prior conversation/continuity. Company state is supplied only when
    the current message asks for company state.
    """
    normalized = (message or "").strip().lower()

    state_terms = (
        "מצב", "חברה", "משימות", "משימה", "חסימות", "חסימה",
        "הכנסה", "הכנסות", "יעד", "יעדים", "אישורים", "אישור",
        "דוח", "מה קיים", "מה יש", "מה פתוח",
        "מה קרה", "מה חדש", "עדכון",
        "company", "status", "task", "tasks", "revenue",
        "income", "blocker", "blockers", "approval", "approvals",
        "goals", "report", "what happened", "what's new", "update",
    )

    continuity_terms = (
        "קודם", "מקודם", "לפני", "המשך", "תמשיך", "המשכנו",
        "עצרנו", "דיברנו", "אמרת", "אמרתי", "התכוונת",
        "מה שאמרת", "מה שאמרתי", "השיחה הקודמת",
        "זוכר", "תזכור",
        "previous", "earlier", "continue", "remember",
        "what you said", "what i said",
    )

    wants_company_state = any(term in normalized for term in state_terms)
    wants_history = any(term in normalized for term in continuity_terms)

    lines: list[str] = []

    # Do NOT inject old turns into an independent command such as
    # "תגיד שלוש". Old answers must never influence the new instruction.
    if wants_history:
        recent = brain.conversations.recent(limit=3)
        if recent:
            lines.append("Recent conversation continuity:")
            for turn in recent:
                founder = (turn.input_line or "").strip().replace("\n", " ")[:240]
                atlas = (turn.response_summary or "").strip().replace("\n", " ")[:320]
                lines.append(f"Founder: {founder}")
                lines.append(f"ATLAS: {atlas}")

    if wants_company_state:
        lines.append("\nRelevant live company state:")
        lines.append(build_briefing(brain))

        pending = build_console_view(brain)["pending_approvals"]
        if pending:
            lines.append("\nPending approvals relevant to company state:")
            for task in pending[:10]:
                lines.append(f"- [{task['category']}] {task['description']}")

    if not lines:
        return "No additional background is needed for this turn."

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


# Real, structural facts already written down elsewhere in this codebase
# (never invented for this panel): the 5 affiliate networks named as
# honest, zero-implementation placeholders in
# atlas.integrations.affiliate_provider_placeholders, and 5 more
# platforms named as real, documented future targets with genuinely no
# implementation anywhere -- YouTube/TikTok/Instagram/Facebook
# (atlas.integrations.base.ContentPublisher's own docstring) and Shopify
# (CLAUDE.md's own "Shopify Store — Credential-blocked" finding). The
# founder's explicit instruction (2026-08-09): show a not-yet-connected
# platform honestly rather than hiding it, never fake a green status.
_PLACEHOLDER_AFFILIATE_PROVIDERS = [
    AmazonAssociatesProvider(),
    AliExpressAffiliateProvider(),
    CJProvider(),
    ImpactProvider(),
    ShareASaleProvider(),
]
_PLACEHOLDER_AFFILIATE_LABELS = {
    "amazon_associates": "Amazon Associates",
    "aliexpress_affiliate": "AliExpress Affiliate",
    "cj": "CJ Affiliate",
    "impact": "Impact",
    "shareasale": "ShareASale",
}
_UNBUILT_NAMED_PLATFORMS = [
    {"id": "youtube", "label": "YouTube", "kind": "פרסום תוכן"},
    {"id": "tiktok", "label": "TikTok", "kind": "פרסום תוכן"},
    {"id": "instagram", "label": "Instagram", "kind": "פרסום תוכן"},
    {"id": "facebook", "label": "Facebook", "kind": "פרסום תוכן"},
    {"id": "shopify", "label": "Shopify", "kind": "חנות מכירות"},
]


def _real_platform_connections() -> list[dict]:
    """Every platform ATLAS has real code for, or has explicitly and
    honestly named as a future target somewhere real in this codebase —
    never a fabricated wishlist, and never a fabricated "connected"
    status. Three real, distinct states, not just a binary: "connected"
    (a real class AND a real credential is actually configured in this
    environment right now — checked live via os.environ, never assumed),
    "code_ready" (a real class exists but no credential is configured
    yet), and "not_built" (no real integration code exists at all)."""
    result: list[dict] = []
    for provider in COMMERCE_PROVIDERS.values():
        api_key_env = getattr(provider, "_API_KEY_ENV", None)
        connected = bool(api_key_env and os.environ.get(api_key_env))
        result.append(
            {
                "id": provider.name,
                "label": provider.name.capitalize(),
                "kind": "אפיליאייט / מסחר",
                "status": "connected" if connected else "code_ready",
            }
        )
    for provider in _PLACEHOLDER_AFFILIATE_PROVIDERS:
        result.append(
            {
                "id": provider.name,
                "label": _PLACEHOLDER_AFFILIATE_LABELS.get(provider.name, provider.name),
                "kind": "אפיליאייט",
                "status": "not_built",
            }
        )
    for platform in _UNBUILT_NAMED_PLATFORMS:
        result.append({**platform, "status": "not_built"})
    return result


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
    second, parallel view of the same state.

    Real bug, found live (2026-08-09) against real production-scale data
    (1771 tasks, a 10MB brain.json): this used to call find_warnings(),
    get_system_health(), and build_briefing() with no arguments, and each
    of those independently recomputed build_console_view() (and, for
    build_briefing, find_warnings() too) from scratch internally --
    5 total build_console_view() calls and 3 total find_warnings() calls
    per single _real_state() invocation. At real scale that was several
    seconds each, compounding into tens of seconds per request -- and
    since the SSE stream below re-ran this every 5 seconds on the same
    single-threaded event loop, a real connected browser tab left the
    entire server unable to answer even the plain index page. `view`/
    `warnings` are now computed exactly once and threaded through."""
    view = build_console_view(brain)
    warnings = find_warnings(brain, view)
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
        "platform_connections": _real_platform_connections(),
        "kpis": view["kpis"],
        "cash_flow": view["cash_flow"],
        "warnings": warnings,
        "activity": activity,
        "system_health": get_system_health(brain, warnings),
        "queue": get_queue(brain),
        "campaigns": get_campaigns(brain),
        "opportunities": get_opportunities(brain),
        "decisions": decisions,
        "success_laws": _real_success_laws(brain),
        "briefing": build_briefing(brain, view, warnings),
        "atlas_last_active": _real_last_active(activity, decisions),
    }



def _health_snapshot(brain: CEOBrain) -> tuple[dict, int]:
    """Minimal production liveness/state-readability check.

    Deliberately does not build the full Headquarters state, run a tick,
    call AI, browse the web, or touch any external provider. It verifies
    only that the two core durable financial/brain stores are readable.
    """
    checks = {}
    healthy = True

    try:
        goals = brain.memory.goals()
        checks["memory"] = {
            "status": "ok",
            "goals_readable": len(goals),
        }
    except Exception as exc:
        healthy = False
        checks["memory"] = {
            "status": "error",
            "error_type": type(exc).__name__,
        }

    try:
        entries = brain.ledger.entries()
        checks["ledger"] = {
            "status": "ok",
            "entries_readable": len(entries),
        }
    except Exception as exc:
        healthy = False
        checks["ledger"] = {
            "status": "error",
            "error_type": type(exc).__name__,
        }

    payload = {
        "status": "ok" if healthy else "unhealthy",
        "service": "atlas-headquarters",
        "checks": checks,
    }
    return payload, 200 if healthy else 503


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

    # Every handler below does real, synchronous, potentially
    # multi-second work (reading/parsing real store files, dispatching
    # to real assets) against a single asyncio event loop shared by
    # every concurrent connection -- including the SSE stream further
    # down, which re-runs _real_state() every 5 seconds for as long as
    # a real browser tab is open. Real bug, found live (2026-08-09): none
    # of this was ever offloaded to a thread, so one real request could
    # (and did, against real production-scale data) block every other
    # request, including the plain index page, for as long as it ran.
    # run_in_threadpool matches the discipline api_converse already
    # established for the AI provider call.
    async def api_health(request):
        payload, status_code = await run_in_threadpool(
            _health_snapshot, brain
        )
        return JSONResponse(payload, status_code=status_code)

    async def api_state(request):
        return JSONResponse(await run_in_threadpool(_real_state, brain))

    async def api_approve(request):
        task_id = request.path_params["task_id"]
        try:
            task = await run_in_threadpool(brain.approve, task_id)
        except KeyError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        return JSONResponse({"id": task.id, "status": task.status})

    async def api_reject(request):
        task_id = request.path_params["task_id"]
        try:
            task = await run_in_threadpool(brain.reject, task_id)
        except KeyError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        return JSONResponse({"id": task.id, "status": task.status})

    async def api_tick(request):
        """Runs the real operational cycle right now -- the exact same
        CEOBrain.tick() the real Windows Scheduled Task calls every 30
        minutes. A real CEO shouldn't have to wait for the clock."""
        await run_in_threadpool(brain.tick)
        return JSONResponse(await run_in_threadpool(_real_state, brain))

    async def api_review(request):
        """Runs the real strategic review cycle for a real period --
        CEOBrain.review(), unchanged. This has real side effects
        (reallocates goals, may create redesign tasks), so it is a
        deliberate POST action, never run silently in the background."""
        period = request.path_params["period"]
        try:
            report = await run_in_threadpool(brain.review, period)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse(report)

    async def api_recall(request):
        query = request.query_params.get("q", "")
        if not query:
            return JSONResponse({"hits": []})
        hits = await run_in_threadpool(
            recall,
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

        prompt = _ATLAS_PERSONA_PROMPT.format(context=_conversation_context(brain, message), message=message)
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
                state = await run_in_threadpool(_real_state, brain)
                yield {"event": "state", "data": json.dumps(state)}
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        return EventSourceResponse(stream())

    return Starlette(
        routes=[
            Route("/", index),
            Route("/health", api_health),
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

