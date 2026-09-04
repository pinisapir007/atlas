"""Real PDF KnowledgeSourcePlugin for Stage 7.

Uses pypdf for genuine PDF text extraction. Each real PDF page becomes
a GroundedTextSegment with a real 1-based page locator.

Image-only/scanned PDFs are NOT silently treated as readable text:
if no extractable text exists, this plugin fails loudly. OCR is a
separate future capability.

Local access reuses ATLAS's existing ResourceAllowlist.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any

from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.base import (
    AIProvider,
    GroundedTextSegment,
    PageObservation,
)


class PDFPluginError(Exception):
    """A real PDF could not be safely/readably observed."""


class PDFPathNotApprovedError(ValueError):
    """The requested PDF is outside founder-approved local resources."""


class PDFPlugin:
    name = "pdf"
    raw_text_grounded = True

    def __init__(
        self,
        allowlist: ResourceAllowlist | None = None,
        ai_provider: AIProvider | None = None,
        reader_factory: Callable[[str], Any] | None = None,
    ):
        self._allowlist = (
            allowlist if allowlist is not None else ResourceAllowlist()
        )
        self._ai_provider = ai_provider
        self._reader_factory = reader_factory

    def can_handle(self, source_ref: str) -> bool:
        return Path(source_ref).suffix.lower() == ".pdf"

    def _reader(self, path: Path):
        if self._reader_factory is not None:
            return self._reader_factory(str(path))

        from pypdf import PdfReader

        return PdfReader(str(path))

    def observe(
        self,
        source_ref: str,
        extract: dict[str, str] | None = None,
    ) -> PageObservation:
        if not self._allowlist.is_approved(source_ref):
            raise PDFPathNotApprovedError(
                f"path not approved for autonomous PDF reading: {source_ref!r}"
            )

        path = Path(source_ref)
        if not path.is_file():
            raise PDFPluginError(f"real PDF file not found: {source_ref!r}")

        try:
            reader = self._reader(path)
        except Exception as exc:
            raise PDFPluginError(
                f"real failure opening PDF {source_ref!r}: {exc}"
            ) from exc

        if getattr(reader, "is_encrypted", False):
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise PDFPluginError(
                    f"encrypted PDF cannot be read without credentials: {source_ref!r}"
                ) from exc

            if not unlocked:
                raise PDFPluginError(
                    f"encrypted PDF requires a password: {source_ref!r}"
                )

        segments: list[GroundedTextSegment] = []

        try:
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if not page_text.strip():
                    continue

                segments.append(
                    GroundedTextSegment(
                        text=page_text,
                        locator_prefix=f"page:{page_number}",
                    )
                )
        except Exception as exc:
            raise PDFPluginError(
                f"real PDF page extraction failed for {source_ref!r}: {exc}"
            ) from exc

        if not segments:
            raise PDFPluginError(
                "PDF contains no extractable text; "
                "image-only/scanned PDF OCR is not implemented"
            )

        # Full text is retained for the existing quality / subject /
        # evidence-role gates. Atomic extraction uses text_segments,
        # preserving page provenance.
        text = "\n".join(segment.text for segment in segments)

        structured_data: dict[str, str] = {}
        if extract:
            provider = self._ai_provider or get_ai_provider()
            prompt = (
                f"From the following real, already-extracted PDF text "
                f"(path: {source_ref}), extract real information.\n\n"
                f"PDF TEXT:\n{text[:8000]}"
            )
            try:
                structured_data = provider.complete_structured(
                    prompt,
                    extract,
                )
            except Exception as exc:
                raise PDFPluginError(str(exc)) from exc

        return PageObservation(
            url=str(path.resolve()),
            title=path.name,
            text_content=text,
            structured_data=structured_data,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            text_segments=segments,
        )
