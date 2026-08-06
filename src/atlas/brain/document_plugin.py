"""DocumentPlugin (2026-08-06, Knowledge Sources V1) — the second
real KnowledgeSourcePlugin, proving the plugin claim for real: added
as one new class plus one registry line (see
knowledge_source_registry.py), with zero change to the Protocol, the
dispatch loop, or BrowserPlugin.

Scoped honestly to what's real today: plain text and Markdown files
via stdlib file reading only -- no PDF-parsing library is installed
anywhere in this codebase, and claiming PDF support without one would
be exactly the fabricated-capability mistake this codebase avoids
everywhere else. A real PDF plugin is a real, separate, later
decision once a real parsing dependency is deliberately added, not
silently implied here.

Reuses ResourceAllowlist (Resource Discovery Engine V1) rather than
inventing a second local-file-access allowlist -- a document path is
exactly the same real risk (autonomous local file access) that
allowlist already exists to gate.
"""

from pathlib import Path

from atlas.brain.resource_allowlist import ResourceAllowlist
from atlas.integrations.ai_provider_registry import get_ai_provider
from atlas.integrations.base import AIProvider, PageObservation

SUPPORTED_SUFFIXES = {".txt", ".md"}


class DocumentPluginError(Exception):
    """A real failure reading or extracting from a document — never
    swallowed into a fabricated/partial observation, the same
    loud-failure discipline every other real plugin in this codebase
    already establishes."""


class PathNotApprovedError(ValueError):
    """Raised when `source_ref` is not within a real,
    founder-approved folder on the real ResourceAllowlist — the same
    fail-closed check resource_discovery_engine already performs for
    scanning, applied here to reading."""


class DocumentPlugin:
    """Real KnowledgeSourcePlugin for local text/Markdown documents.
    `name` satisfies the Protocol structurally (duck-typed,
    @runtime_checkable), the same pattern every other real provider
    in this codebase uses."""

    name = "document"

    def __init__(self, allowlist: ResourceAllowlist | None = None, ai_provider: AIProvider | None = None):
        self._allowlist = allowlist if allowlist is not None else ResourceAllowlist()
        self._ai_provider = ai_provider

    def can_handle(self, source_ref: str) -> bool:
        return Path(source_ref).suffix.lower() in SUPPORTED_SUFFIXES

    def observe(self, source_ref: str, extract: dict[str, str] | None = None) -> PageObservation:
        if not self._allowlist.is_approved(source_ref):
            raise PathNotApprovedError(f"path not approved for autonomous reading: {source_ref!r}")

        path = Path(source_ref)
        if not path.is_file():
            raise DocumentPluginError(f"real file not found: {source_ref!r}")

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise DocumentPluginError(f"real failure reading {source_ref!r}: {exc}") from exc

        structured_data: dict[str, str] = {}
        if extract:
            provider = self._ai_provider or get_ai_provider()
            prompt = (
                f"From the following real, already-read document text (path: {source_ref}), "
                f"extract real information.\n\nDOCUMENT TEXT:\n{text[:8000]}"
            )
            try:
                structured_data = provider.complete_structured(prompt, extract)
            except Exception as exc:  # noqa: BLE001 -- any real provider failure surfaces loudly
                raise DocumentPluginError(str(exc)) from exc

        return PageObservation(
            url=str(path.resolve()),
            title=path.name,
            text_content=text,
            structured_data=structured_data,
        )
