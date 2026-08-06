"""Claude CLI Connection V1 (2026-08-05).

The first real, dependency-free connector between ATLAS and a real
executive (Claude), through the already-installed, already-
authenticated `claude` CLI on this machine, in headless/print mode
(`claude -p ... --output-format json`). Built only after a real, live
call was made and its actual JSON response shape observed directly —
not a guessed integration.

Real, verified facts this module is built against (checked on this
machine before writing any code, not assumed):
- `claude -p "<task>" --output-format json` runs one real, non-
  interactive turn and exits; stdout is a single real JSON object,
  stderr is separate and may carry an unrelated workspace-trust
  warning that must never be treated as part of the response.
- The real response envelope's relevant fields: `type` (=="result"
  on success), `is_error` (bool), `result` (the real text answer),
  `session_id`, `duration_ms`, `total_cost_usd`, `num_turns`.
- A real call is not free or instant: the first live test observed
  real cost around $0.33 and ~4-6 seconds, driven mostly by real
  cache-creation tokens (this project's own CLAUDE.md/context being
  loaded fresh into the child session) — a real, material operating
  cost, not hidden here.

Mirrors atlas.integrations.digistore24's exact discipline in two
ways: a loud, named exception on any real failure (ClaudeCLIError),
never a silent None/empty result; and staying genuinely dependency-
free — this module never imports atlas.brain (the standing layering
rule: atlas.integrations must stay dependency-free, atlas.brain
freely imports atlas.integrations, never the reverse). Returns the
CLI's real response payload exactly as received, unrenamed — the
same "don't invent a field-name mapping" discipline
Digistore24Provider.fetch_recent_sales() already established for an
unverified real API shape. Recording the interaction as a durable,
structured record is a brain-layer concern (see
atlas.brain.claude_executive), the same split provider_ranking.py
already draws over this exact connector's Digistore24 counterpart.
"""

import json
import subprocess

CLAUDE_CLI_COMMAND = "claude"


class ClaudeCLIError(Exception):
    """A real call to the `claude` CLI failed, timed out, or returned
    something this connector doesn't understand — never swallowed
    into a fabricated/partial result."""


def send_task(task: str, timeout_seconds: float = 120.0) -> dict:
    """Sends `task` to the real, already-installed `claude` CLI in
    headless mode and returns the real, parsed JSON response exactly
    as the CLI returned it. Raises ClaudeCLIError on any real
    failure — a missing CLI, a timeout, a non-zero exit, unparseable
    stdout, or the CLI's own reported error.
    """
    if not task or not task.strip():
        raise ValueError("a real, non-empty task is required")

    try:
        completed = subprocess.run(
            [CLAUDE_CLI_COMMAND, "-p", task, "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise ClaudeCLIError(f"claude CLI not found on PATH: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeCLIError(f"claude CLI did not respond within {timeout_seconds}s") from exc

    if completed.returncode != 0:
        raise ClaudeCLIError(f"claude CLI exited with code {completed.returncode}: {(completed.stderr or completed.stdout).strip()}")

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ClaudeCLIError(f"claude CLI returned non-JSON stdout: {completed.stdout[:500]!r} (stderr: {completed.stderr[:500]!r})") from exc

    if payload.get("type") != "result":
        raise ClaudeCLIError(f"unexpected response type from claude CLI: {payload.get('type')!r}")
    if payload.get("is_error"):
        raise ClaudeCLIError(f"claude CLI reported a real error: {payload.get('result')!r}")

    return payload


class ClaudeProvider:
    """Real AIProvider implementation over the real `claude` CLI
    connector above (2026-08-06, AI Orchestrator V1) — the second
    real AI backend, and exactly the trigger this module's own
    original docstring named ("no Protocol, no provider registry...
    generalizing before a second implementation exists would be
    premature"). `name` satisfies the AIProvider Protocol
    structurally (duck-typed, @runtime_checkable), the same pattern
    every other real provider in this codebase already uses.

    Deliberately calls the dependency-free `send_task` above directly
    -- never atlas.brain.claude_executive's logging wrapper. The
    durable, append-only "ATLAS <-> Claude executive interaction"
    record is a distinct, existing feature for a distinct purpose
    (see claude_executive.py); this provider is a lighter-weight path
    for ad-hoc, orchestrator-routed AI calls (e.g. structured
    extraction) and does not replace or reroute it.
    """

    name = "claude"

    def __init__(self, timeout_seconds: float = 120.0):
        self._timeout_seconds = timeout_seconds

    def complete(self, prompt: str) -> str:
        payload = send_task(prompt, timeout_seconds=self._timeout_seconds)
        return payload.get("result", "")

    def complete_structured(self, prompt: str, fields: dict[str, str]) -> dict[str, str]:
        field_list = "; ".join(f'"{key}": {description}' for key, description in fields.items())
        full_prompt = (
            f"{prompt}\n\nExtract these real fields: {field_list}\n\n"
            "If a field is not present, use an empty string for it -- never invent a value. "
            "Reply with ONLY a single real JSON object mapping each field name to its real string value -- "
            "no Markdown code fences, no explanation, no other text."
        )
        payload = send_task(full_prompt, timeout_seconds=self._timeout_seconds)
        raw_result = payload.get("result", "")
        return _parse_json_object(raw_result, fields)


def _parse_json_object(raw_result: str, fields: dict[str, str]) -> dict[str, str]:
    """Parses a real Claude text response into the requested fields.
    Claude CLI has no native structured-output parameter (unlike
    ChatGoogle's `output_format`), so this tolerates the one real,
    already-observed LLM quirk this codebase has hit before (a
    response wrapped in a Markdown code fence) by stripping fences
    before parsing -- never silently returning empty values for a
    response that was never valid JSON to begin with."""
    text = raw_result.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[: -len("```")]
        if text.startswith("json"):
            text = text[len("json"):]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ClaudeCLIError(f"claude CLI's real response was not valid JSON: {raw_result[:500]!r}") from exc

    if not isinstance(parsed, dict):
        raise ClaudeCLIError(f"claude CLI's real response was valid JSON but not an object: {raw_result[:500]!r}")

    return {key: str(parsed.get(key, "")) for key in fields}
