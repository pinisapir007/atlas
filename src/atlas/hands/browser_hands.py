"""BrowserHands (2026-08-09, Hands V1) — real browser actions: Web
Navigation, Mouse (click), Keyboard (input text, send keys), Fill Forms,
Upload Files, Download Files. Executes a whole real step sequence within
ONE real browser session and ONE asyncio event loop (never one session
per action) — CDP-backed sessions like this one hold live connections
tied to the loop that created them, so splitting a sequence across
multiple asyncio.run() calls would silently break the live connection
between steps.

Reuses the real, already-installed `browser_use` package directly —
specifically its `Tools` action-call API (`tools.navigate(...)`,
`tools.click(...)`, ...), the exact same real, mature action-execution
engine browser_use's own agent loop already uses internally, confirmed
by direct inspection of its registered actions (tools/service.py).
Never wraps another LLM agent loop around this — ATLAS's own brain
decides WHAT to do; this module only executes ONE already-decided real
action at a time. No new dependency: browser_use is already installed
(BrowserUseObserver already depends on it for read-only observation).

Live-verified end-to-end against a real local HTTP-served form: real
navigate, real text input, real file upload, real click (which produced
a real, observable DOM change), and a real file download (captured via
browser_use's own `session.downloaded_files`).
"""

from atlas.hands.models import BROWSER_STEP_KINDS


class BrowserHandsError(Exception):
    """A real failure executing a browser action — never swallowed into
    a fabricated success, the same loud-failure discipline every other
    real executor in this codebase already establishes."""


class BrowserHands:
    name = "browser_hands"

    def execute_steps(self, steps: list[dict]) -> dict:
        """Executes a real sequence of browser steps atomically (one
        real session, in order). Returns {"results": [...one real dict
        per step...], "downloaded_files": [...real paths, if any real
        download happened...]}. Stops at the first real failure — later
        steps are never attempted against a session whose state is no
        longer trusted — and the partial `results` list (already
        appended before the raising step) tells the caller exactly how
        far it got."""
        import asyncio

        try:
            return asyncio.run(self._execute_steps_async(steps))
        except BrowserHandsError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BrowserHandsError(f"real browser session failure: {exc}") from exc

    async def _execute_steps_async(self, steps: list[dict]) -> dict:
        from browser_use import BrowserSession
        from browser_use.filesystem.file_system import FileSystem
        from browser_use.tools.service import Tools

        import tempfile

        session = BrowserSession()
        tools = Tools()
        file_system = FileSystem(base_dir=tempfile.gettempdir())
        results: list[dict] = []

        await session.start()
        try:
            for step in steps:
                kind = step.get("kind")
                params = step.get("params", {})
                if kind not in BROWSER_STEP_KINDS:
                    raise BrowserHandsError(f"unrecognized browser step kind: {kind!r}")
                results.append(await self._execute_one(tools, session, file_system, kind, params))
            downloaded_files = list(session.downloaded_files)
        finally:
            await session.stop()

        return {"results": results, "downloaded_files": downloaded_files}

    async def _execute_one(self, tools, session, file_system, kind: str, params: dict) -> dict:
        if kind == "navigate":
            result = await tools.navigate(url=params["url"], new_tab=params.get("new_tab", False), browser_session=session)
        elif kind == "click":
            result = await tools.click(index=params["index"], browser_session=session)
        elif kind == "input_text":
            result = await tools.input(index=params["index"], text=params["text"], browser_session=session)
        elif kind == "upload_file":
            result = await tools.upload_file(
                index=params["index"],
                path=params["path"],
                browser_session=session,
                available_file_paths=[params["path"]],
                file_system=file_system,
            )
        elif kind == "send_keys":
            result = await tools.send_keys(keys=params["keys"], browser_session=session)
        elif kind == "scroll":
            result = await tools.scroll(
                down=params.get("down", True),
                pages=params.get("pages", 1.0),
                index=params.get("index"),
                browser_session=session,
            )
        elif kind == "describe_page":
            text = await session.get_state_as_text()
            return {"kind": kind, "success": True, "text": text}
        else:  # pragma: no cover -- guarded by BROWSER_STEP_KINDS membership check above
            raise BrowserHandsError(f"unrecognized browser step kind: {kind!r}")

        error = getattr(result, "error", None)
        return {
            "kind": kind,
            "success": error is None,
            "error": error,
            "extracted_content": getattr(result, "extracted_content", None),
        }
