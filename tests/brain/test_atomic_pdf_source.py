import atlas.brain.knowledge_source_research as research

from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.knowledge_source_research import (
    collect_atomic_evidence_from_source,
)
from atlas.brain.pdf_plugin import PDFPlugin


class _Allow:
    def is_approved(self, path):
        return True


class _Page:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class _Reader:
    is_encrypted = False

    def __init__(self):
        self.pages = [
            _Page(
                "General introduction to the report and its market. "
                "Additional context ensures this is a substantive source."
            ),
            _Page(
                "Customers repeatedly complain about slow delivery.\n"
                "The listed price is $29."
            ),
        ]


class _Provider:
    name = "fake"

    def complete_structured(self, prompt, fields):
        if "verdict" in fields:
            return {"verdict": "same", "reason": "same subject"}

        if "role" in fields:
            return {
                "role": "direct_assertion",
                "reason": "direct source",
            }

        if "atomic_1_statement" in fields:
            if "Customers repeatedly complain about slow delivery." in prompt:
                return {
                    "atomic_1_statement": "Customers report slow delivery.",
                    "atomic_1_quote": "Customers repeatedly complain about slow delivery.",
                }
            return {
                "atomic_1_statement": "",
                "atomic_1_quote": "",
            }

        return {
            "relevant": "yes",
            "reason": "relevant real source",
        }


def test_pdf_atomic_collection_preserves_page_and_line_locator(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "report.pdf"
    path.write_bytes(b"%PDF-test")

    plugin = PDFPlugin(
        allowlist=_Allow(),
        reader_factory=lambda _: _Reader(),
    )

    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    created = collect_atomic_evidence_from_source(
        source_ref=str(path),
        category="customer_research",
        source="pdf_research",
        task_description="identify customer pain",
        knowledge=knowledge,
        ai_provider=_Provider(),
        max_atomics_per_chunk=1,
    )

    assert len(created) == 1
    finding = created[0]

    assert finding.evidence == str(path.resolve())
    assert finding.evidence_locator == "page:2;lines:1"
    assert (
        finding.evidence_excerpt
        == "Customers repeatedly complain about slow delivery."
    )
    assert finding.observed_at
    assert len(finding.content_hash) == 64


def test_repeated_same_pdf_atomic_collection_is_idempotent(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "report.pdf"
    path.write_bytes(b"%PDF-test")

    plugin = PDFPlugin(
        allowlist=_Allow(),
        reader_factory=lambda _: _Reader(),
    )

    monkeypatch.setattr(
        research,
        "select_plugin",
        lambda source_ref: plugin,
    )

    knowledge = KnowledgeBase(tmp_path / "knowledge.json")

    kwargs = dict(
        source_ref=str(path),
        category="customer_research",
        source="pdf_research",
        task_description="identify customer pain",
        knowledge=knowledge,
        ai_provider=_Provider(),
        max_atomics_per_chunk=1,
    )

    first = collect_atomic_evidence_from_source(**kwargs)
    second = collect_atomic_evidence_from_source(**kwargs)

    assert len(first) == 1
    assert second == []
    assert len(knowledge.findings()) == 1
