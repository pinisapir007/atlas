"""ImagePlugin (2026-08-09, Vision V1) — the real KnowledgeSourcePlugin
implementation for local images. Image Understanding and OCR are
deliberately the SAME real capability, not two: a single real
multimodal call to Gemini (via GeminiProvider.understand_image) that
both describes an image AND transcribes any literal text in it,
live-verified (a real, generated PNG with real rendered text was read
back verbatim). Building two separate mechanisms for "what is this
image" and "what text is in this image" would be exactly the kind of
duplicated-capability mistake this codebase has avoided everywhere
else (see SUPPORTED_PROVIDERS's removal, or asset_lifetime_value's
shared core).

Reuses ResourceAllowlist, the same real local-file-access gate
DocumentPlugin already established -- a local image is exactly the
same real risk (autonomous local file access) that allowlist exists
to gate, and mirrors DocumentPlugin's structure closely by design.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.integrations.base import MediaEvidence, PageObservation
from atlas.integrations.gemini_provider import GeminiProvider, GeminiProviderError

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}

_UNDERSTAND_PROMPT = (
    "Describe what is shown in this real image in detail (objects, layout, context). "
    "Then, separately, transcribe any literal text visible in the image verbatim, exactly as written -- "
    "if there is no visible text, say so honestly rather than inventing any."
)


class ImagePluginError(Exception):
    """A real failure reading or understanding an image — never
    swallowed into a fabricated/partial observation, the same
    loud-failure discipline every other real plugin in this codebase
    already establishes."""


class PathNotApprovedError(ValueError):
    """Raised when `source_ref` is not within a real, founder-approved
    folder on the real ResourceAllowlist — the same fail-closed check
    DocumentPlugin already performs."""


class ImagePlugin:
    """Real KnowledgeSourcePlugin for local images — Image
    Understanding and OCR combined into one real capability. `name`
    satisfies the Protocol structurally (duck-typed,
    @runtime_checkable), the same pattern every other real provider
    in this codebase uses."""

    name = "image"

    def __init__(self, allowlist: ResourceAllowlist | None = None, gemini_provider: GeminiProvider | None = None):
        self._allowlist = allowlist if allowlist is not None else ResourceAllowlist()
        self._gemini = gemini_provider if gemini_provider is not None else GeminiProvider()

    def can_handle(self, source_ref: str) -> bool:
        return Path(source_ref).suffix.lower() in SUPPORTED_SUFFIXES

    def observe(self, source_ref: str, extract: dict[str, str] | None = None) -> PageObservation:
        image_bytes, path = self._read_approved_image(source_ref)
        media_type = _MEDIA_TYPES[path.suffix.lower()]

        try:
            description = self._gemini.understand_image(image_bytes, _UNDERSTAND_PROMPT, media_type=media_type)
            structured_data = {}
            if extract:
                structured_data = self._gemini.understand_image_structured(
                    image_bytes, "Look at this real image.", extract, media_type=media_type
                )
        except GeminiProviderError as exc:
            raise ImagePluginError(str(exc)) from exc

        return PageObservation(
            url=str(path.resolve()),
            title=path.name,
            text_content=description,
            structured_data=structured_data,
        )

    def observe_evidence(self, source_ref: str) -> list[MediaEvidence]:
        """Return evidence-honest observations from one real image.

        The image bytes are the real source identity. Gemini's visual/OCR
        interpretation is kept as sensor observation data and is never
        treated as a character-for-character grounded text excerpt.
        """
        image_bytes, path = self._read_approved_image(source_ref)
        media_type = _MEDIA_TYPES[path.suffix.lower()]

        fields = {
            "visual": (
                "Describe only objects, layout, people, products, charts, "
                "or other content directly visible in this real image."
            ),
            "transcribed_text": (
                "Transcribe literal text visible in the image as accurately "
                "as possible. Use an empty string if no text is visible."
            ),
            "confidence": (
                "HIGH, MEDIUM, or LOW confidence that the observation is "
                "directly supported by the image."
            ),
        }

        try:
            raw = self._gemini.understand_image_structured(
                image_bytes,
                "Inspect this real image as evidence. Do not infer facts that are not visibly supported.",
                fields,
                media_type=media_type,
            )
        except GeminiProviderError as exc:
            raise ImagePluginError(str(exc)) from exc

        visual = raw.get("visual", "").strip()
        transcribed = raw.get("transcribed_text", "").strip()
        confidence = raw.get("confidence", "").strip().upper()

        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            confidence = "UNKNOWN"

        if not visual and not transcribed:
            return []

        return [
            MediaEvidence(
                source_ref=str(path.resolve()),
                modality="image",
                locator="image:whole",
                visual=visual,
                transcribed_text=transcribed,
                confidence=confidence,
                observed_at=datetime.now(timezone.utc).isoformat(),
                content_hash=hashlib.sha256(image_bytes).hexdigest(),
            )
        ]

    def _read_approved_image(self, source_ref: str) -> tuple[bytes, Path]:
        if not self._allowlist.is_approved(source_ref):
            raise PathNotApprovedError(f"path not approved for autonomous reading: {source_ref!r}")

        path = Path(source_ref)
        if not path.is_file():
            raise ImagePluginError(f"real file not found: {source_ref!r}")

        try:
            return path.read_bytes(), path
        except OSError as exc:
            raise ImagePluginError(f"real failure reading {source_ref!r}: {exc}") from exc
