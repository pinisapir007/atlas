import pytest

from atlas.brain.pdf_plugin import (
    PDFPathNotApprovedError,
    PDFPlugin,
    PDFPluginError,
)


class _Allow:
    def __init__(self, approved=True):
        self.approved = approved

    def is_approved(self, path):
        return self.approved


class _Page:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class _Reader:
    is_encrypted = False

    def __init__(self, pages):
        self.pages = [_Page(text) for text in pages]


def test_pdf_plugin_reads_real_page_structure(tmp_path):
    path = tmp_path / "book.pdf"
    path.write_bytes(b"%PDF-test")

    plugin = PDFPlugin(
        allowlist=_Allow(),
        reader_factory=lambda _: _Reader(
            [
                "First page real text.",
                "Second page real evidence.\nAnother sentence.",
            ]
        ),
    )

    obs = plugin.observe(str(path))

    assert obs.url == str(path.resolve())
    assert obs.title == "book.pdf"
    assert obs.fetched_at
    assert len(obs.text_segments) == 2

    assert obs.text_segments[0].locator_prefix == "page:1"
    assert obs.text_segments[0].text == "First page real text."

    assert obs.text_segments[1].locator_prefix == "page:2"
    assert "Second page real evidence." in obs.text_segments[1].text


def test_pdf_plugin_rejects_unapproved_path_before_read(tmp_path):
    path = tmp_path / "private.pdf"
    path.write_bytes(b"%PDF-test")

    plugin = PDFPlugin(
        allowlist=_Allow(False),
        reader_factory=lambda _: _Reader(["should never read"]),
    )

    with pytest.raises(PDFPathNotApprovedError):
        plugin.observe(str(path))


def test_image_only_pdf_is_not_fabricated_as_text(tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF-test")

    plugin = PDFPlugin(
        allowlist=_Allow(),
        reader_factory=lambda _: _Reader(["", "   "]),
    )

    with pytest.raises(PDFPluginError, match="no extractable text"):
        plugin.observe(str(path))


def test_password_encrypted_pdf_fails_closed(tmp_path):
    path = tmp_path / "locked.pdf"
    path.write_bytes(b"%PDF-test")

    class _EncryptedReader:
        is_encrypted = True
        pages = []

        def decrypt(self, password):
            return 0

    plugin = PDFPlugin(
        allowlist=_Allow(),
        reader_factory=lambda _: _EncryptedReader(),
    )

    with pytest.raises(PDFPluginError, match="requires a password"):
        plugin.observe(str(path))
