"""AudioPlugin (2026-08-09, Hearing V1) — the real KnowledgeSourcePlugin
implementation for local audio files. Audio Understanding, Speech
Transcription, Speaker Recognition, Audio Summarization, MP3, and
"Zoom Audio" (as an exported audio file) are deliberately the SAME
real capability, not five: a single real multimodal call to Gemini
(via GeminiProvider.understand_audio) whose prompt determines which of
these the caller wants -- mirrors ImagePlugin's exact "one call, many
prompts" discipline for Image Understanding + OCR.

Reuses ResourceAllowlist, the same real local-file-access gate
ImagePlugin/DocumentPlugin already established -- a local audio file
is exactly the same real risk (autonomous local file access) that
allowlist exists to gate.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.integrations.base import MediaEvidence, PageObservation
from atlas.integrations.gemini_provider import GeminiProvider, GeminiProviderError

SUPPORTED_SUFFIXES = {".wav", ".mp3", ".aiff", ".aac", ".ogg", ".flac"}

_MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".aiff": "audio/aiff",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}

_UNDERSTAND_PROMPT = (
    "Transcribe this real audio verbatim. Then, separately, identify any distinct speakers present "
    "(e.g. 'Speaker 1', 'Speaker 2') if more than one is audible, and give a one-sentence summary. "
    "If there is no speech, describe honestly what is audible rather than inventing any transcript."
)


class AudioPluginError(Exception):
    """A real failure reading or understanding an audio file — never
    swallowed into a fabricated/partial observation, the same
    loud-failure discipline every other real plugin in this codebase
    already establishes."""


class PathNotApprovedError(ValueError):
    """Raised when `source_ref` is not within a real, founder-approved
    folder on the real ResourceAllowlist — the same fail-closed check
    ImagePlugin/DocumentPlugin already perform."""


class AudioPlugin:
    """Real KnowledgeSourcePlugin for local audio — Audio Understanding,
    Transcription, Speaker Recognition, and Summarization combined into
    one real capability. `name` satisfies the Protocol structurally
    (duck-typed, @runtime_checkable), the same pattern every other real
    provider in this codebase uses."""

    name = "audio"

    def __init__(self, allowlist: ResourceAllowlist | None = None, gemini_provider: GeminiProvider | None = None):
        self._allowlist = allowlist if allowlist is not None else ResourceAllowlist()
        self._gemini = gemini_provider if gemini_provider is not None else GeminiProvider()

    def can_handle(self, source_ref: str) -> bool:
        return Path(source_ref).suffix.lower() in SUPPORTED_SUFFIXES

    def observe(self, source_ref: str, extract: dict[str, str] | None = None) -> PageObservation:
        audio_bytes, path = self._read_approved_audio(source_ref)
        mime_type = _MIME_TYPES[path.suffix.lower()]

        try:
            description = self._gemini.understand_audio(audio_bytes, _UNDERSTAND_PROMPT, mime_type=mime_type)
            structured_data = {}
            if extract:
                structured_data = self._gemini.understand_audio_structured(
                    audio_bytes, "Listen to this real audio.", extract, mime_type=mime_type
                )
        except GeminiProviderError as exc:
            raise AudioPluginError(str(exc)) from exc

        return PageObservation(
            url=str(path.resolve()),
            title=path.name,
            text_content=description,
            structured_data=structured_data,
        )

    def observe_evidence(self, source_ref: str) -> list[MediaEvidence]:
        """Return evidence-honest observations from one real audio file.

        Gemini's transcription/audio interpretation remains a sensor
        observation and is never treated as character-for-character
        grounded source text.
        """
        audio_bytes, path = self._read_approved_audio(source_ref)
        mime_type = _MIME_TYPES[path.suffix.lower()]

        fields = {
            "audible": (
                "Describe only what is directly audible in this real audio, "
                "including speech, speakers, music, or other sounds."
            ),
            "transcribed_text": (
                "Transcribe the spoken words as accurately as possible. "
                "Use an empty string if there is no speech."
            ),
            "confidence": (
                "HIGH, MEDIUM, or LOW confidence that the observation is "
                "directly supported by the audio."
            ),
        }

        try:
            raw = self._gemini.understand_audio_structured(
                audio_bytes,
                "Listen to this real audio as evidence. Do not infer facts that are not audibly supported.",
                fields,
                mime_type=mime_type,
            )
        except GeminiProviderError as exc:
            raise AudioPluginError(str(exc)) from exc

        audible = raw.get("audible", "").strip()
        transcribed = raw.get("transcribed_text", "").strip()
        confidence = raw.get("confidence", "").strip().upper()

        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            confidence = "UNKNOWN"

        if not audible and not transcribed:
            return []

        return [
            MediaEvidence(
                source_ref=str(path.resolve()),
                modality="audio",
                locator="audio:whole",
                audible=audible,
                transcribed_text=transcribed,
                confidence=confidence,
                observed_at=datetime.now(timezone.utc).isoformat(),
                content_hash=hashlib.sha256(audio_bytes).hexdigest(),
            )
        ]

    def _read_approved_audio(self, source_ref: str) -> tuple[bytes, Path]:
        if not self._allowlist.is_approved(source_ref):
            raise PathNotApprovedError(f"path not approved for autonomous reading: {source_ref!r}")

        path = Path(source_ref)
        if not path.is_file():
            raise AudioPluginError(f"real file not found: {source_ref!r}")

        try:
            return path.read_bytes(), path
        except OSError as exc:
            raise AudioPluginError(f"real failure reading {source_ref!r}: {exc}") from exc
