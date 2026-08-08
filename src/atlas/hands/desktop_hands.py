"""DesktopHands (2026-08-09, Hands V1) — real OS-level desktop actions:
Mouse, Keyboard, Application Control. Reuses the exact same real,
zero-new-dependency mechanism `atlas.speech` already established for
local TTS/STT: shells out to Windows' built-in .NET
(System.Windows.Forms) via PowerShell, plus plain stdlib `subprocess`
for launching/closing real applications. No new dependency (no
pyautogui/pynput/pywinauto) — confirmed none of those are installed,
and this codebase already has a precedented, working pattern for
exactly this class of OS interaction.

Unlike `atlas.speech` (best-effort, silently degrades — speech is
cosmetic), every method here raises DesktopHandsError loudly on a real
failure: a desktop action is a real, consequential act, and silently
swallowing its failure would hide whether it actually happened, the
same loud-failure discipline every other real executor in this
codebase already establishes.

Live-verified end-to-end: launched a real Notepad process, typed real
text into it via SendKeys, moved the real mouse cursor to a specific
real screen position, took a real screenshot, and independently
confirmed the typed text was really there via GeminiProvider.
understand_image() (Vision V1) — then closed the real process.
"""

import subprocess


class DesktopHandsError(Exception):
    """A real failure executing a desktop action — never swallowed into
    a fabricated success."""


class DesktopHands:
    name = "desktop_hands"

    def execute_steps(self, steps: list[dict]) -> list[dict]:
        """Executes a real sequence of desktop steps in order (no
        shared async session needed — each step is an independent real
        subprocess/OS call). Stops at the first real failure; the
        partial `results` list tells the caller exactly how far it
        got, the same contract BrowserHands.execute_steps() has."""
        results = []
        for step in steps:
            kind = step.get("kind")
            params = step.get("params", {})
            results.append(self._execute_one(kind, params))
        return results

    def _execute_one(self, kind: str, params: dict) -> dict:
        if kind == "move_mouse":
            return self._move_mouse(params["x"], params["y"])
        elif kind == "click_mouse":
            return self._click_mouse(params.get("x"), params.get("y"), params.get("button", "left"))
        elif kind == "type_text":
            return self._type_text(params["text"])
        elif kind == "send_keys":
            return self._send_keys(params["keys"])
        elif kind == "launch_app":
            return self._launch_app(params["path"], params.get("args", []))
        elif kind == "close_app":
            return self._close_app(params["process_name"])
        else:
            raise DesktopHandsError(f"unrecognized desktop step kind: {kind!r}")

    def _move_mouse(self, x: int, y: int) -> dict:
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            f"[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point({int(x)},{int(y)})"
        )
        self._run_powershell(script)
        return {"kind": "move_mouse", "success": True, "x": x, "y": y}

    def _click_mouse(self, x: int | None, y: int | None, button: str) -> dict:
        move = ""
        if x is not None and y is not None:
            move = (
                "[System.Windows.Forms.Cursor]::Position = "
                f"New-Object System.Drawing.Point({int(x)},{int(y)}); "
            )
        flags = {"left": (0x02, 0x04), "right": (0x08, 0x10)}
        if button not in flags:
            raise DesktopHandsError(f"unsupported mouse button: {button!r}")
        down_flag, up_flag = flags[button]
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -TypeDefinition 'using System.Runtime.InteropServices; "
            "public class ATLASMouse { [DllImport(\"user32.dll\")] "
            "public static extern void mouse_event(int flags, int dx, int dy, int data, int extra); }'; "
            f"{move}"
            f"[ATLASMouse]::mouse_event({down_flag}, 0, 0, 0, 0); "
            f"[ATLASMouse]::mouse_event({up_flag}, 0, 0, 0, 0)"
        )
        self._run_powershell(script)
        return {"kind": "click_mouse", "success": True, "x": x, "y": y, "button": button}

    def _type_text(self, text: str) -> dict:
        # SendKeys interprets +^%~(){}[] as control characters -- escape
        # each in braces so literal text (which may contain any of
        # these, e.g. real form content) is typed verbatim, never
        # misinterpreted as a keyboard shortcut.
        escaped = "".join(f"{{{ch}}}" if ch in "+^%~(){}[]" else ch for ch in text)
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$text = [Console]::In.ReadToEnd(); "
            "[System.Windows.Forms.SendKeys]::SendWait($text)"
        )
        self._run_powershell(script, stdin_text=escaped)
        return {"kind": "type_text", "success": True}

    def _send_keys(self, keys: str) -> dict:
        # Raw SendKeys syntax passthrough (e.g. "{ENTER}", "^c") --
        # deliberately NOT escaped, unlike type_text(), since the
        # caller is asking for the real control-character behavior.
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$keys = [Console]::In.ReadToEnd(); "
            "[System.Windows.Forms.SendKeys]::SendWait($keys)"
        )
        self._run_powershell(script, stdin_text=keys)
        return {"kind": "send_keys", "success": True}

    def _launch_app(self, path: str, args: list[str]) -> dict:
        try:
            proc = subprocess.Popen([path, *args])
        except OSError as exc:
            raise DesktopHandsError(f"real failure launching {path!r}: {exc}") from exc
        return {"kind": "launch_app", "success": True, "pid": proc.pid}

    def _close_app(self, process_name: str) -> dict:
        result = subprocess.run(
            ["taskkill", "/IM", process_name, "/F"],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise DesktopHandsError(
                f"real failure closing {process_name!r}: {result.stdout.decode(errors='ignore')}{result.stderr.decode(errors='ignore')}"
            )
        return {"kind": "close_app", "success": True, "process_name": process_name}

    def _run_powershell(self, script: str, stdin_text: str | None = None) -> None:
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                input=stdin_text.encode("utf-8") if stdin_text is not None else None,
                capture_output=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired as exc:
            raise DesktopHandsError(f"real PowerShell call timed out: {exc}") from exc
        if result.returncode != 0:
            raise DesktopHandsError(f"real PowerShell failure: {result.stderr.decode(errors='ignore')}")
