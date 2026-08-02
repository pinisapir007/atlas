"""Optional, best-effort local text-to-speech for the console briefing.

No external API, no new dependency: shells out to Windows' built-in
System.Speech via PowerShell. Text is passed over stdin, never interpolated
into the command string, so briefing content (which can contain goal/task
descriptions with arbitrary characters) can never break out of the command
or inject anything. Silently does nothing on any failure — speech is a
nice-to-have, it must never block or crash the console.
"""

import subprocess

_SPEAK_SCRIPT = (
    "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
    "Add-Type -AssemblyName System.Speech; "
    "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$text = [Console]::In.ReadToEnd(); "
    "if ($text) { $synth.Speak($text) }"
)

# Best-effort dictation via the same local, built-in Windows capability, no
# grammar/vocabulary defined ahead of time — "optional if available" by
# design: any failure (no mic, no recognizer, nothing said in time) must
# degrade to "no input captured," never crash the console.
    # A PowerShell script is nearly all braces — using str.format() here
    # would require doubling every literal "{"/"}" (easy to get wrong, and
    # it was: an earlier version of this file did). Plain .replace() on a
    # unique token sidesteps that whole class of mistake entirely.
_LISTEN_SCRIPT_TEMPLATE = (
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    "Add-Type -AssemblyName System.Speech; "
    "try { "
    "$rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
    "$rec.SetInputToDefaultAudioDevice(); "
    "$rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
    "$result = $rec.Recognize([TimeSpan]::FromSeconds(__TIMEOUT__)); "
    "if ($result) { [Console]::Out.Write($result.Text) } "
    "} catch { }"
)


def speak(text: str) -> bool:
    """Attempts to speak `text` locally. Returns True if it appears to have
    run, False if speech isn't available here — never raises."""
    if not text:
        return False
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SPEAK_SCRIPT],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def listen(timeout_seconds: int = 8) -> str | None:
    """Attempts one best-effort local dictation capture. Returns the
    recognized text, or None if voice input isn't available here (no mic,
    no recognizer, nothing understood in time) — never raises. "Optional if
    available" is enforced by this always-safe-to-call contract, not by the
    caller having to check anything first."""
    try:
        script = _LISTEN_SCRIPT_TEMPLATE.replace("__TIMEOUT__", str(int(timeout_seconds)))
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=timeout_seconds + 10,
        )
        text = result.stdout.decode("utf-8", errors="ignore").strip()
        return text or None
    except Exception:
        return None
