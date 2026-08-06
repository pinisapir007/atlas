import pytest

from atlas.brain.document_plugin import DocumentPlugin, DocumentPluginError, PathNotApprovedError
from atlas.brain.resource_allowlist import ResourceAllowlist


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


class _FakeAIProvider:
    name = "fake"

    def __init__(self, structured=None):
        self._structured = structured or {}
        self.calls = []

    def complete(self, prompt):
        raise AssertionError("complete() should not be called for structured extraction")

    def complete_structured(self, prompt, fields):
        self.calls.append((prompt, fields))
        return self._structured


def _allowlist():
    return ResourceAllowlist(store=_FakeStore())


def test_can_handle_recognizes_txt_and_md_files(tmp_path):
    plugin = DocumentPlugin(allowlist=_allowlist())
    assert plugin.can_handle(str(tmp_path / "notes.txt")) is True
    assert plugin.can_handle(str(tmp_path / "README.md")) is True


def test_can_handle_rejects_unsupported_extensions(tmp_path):
    plugin = DocumentPlugin(allowlist=_allowlist())
    assert plugin.can_handle(str(tmp_path / "video.mp4")) is False
    assert plugin.can_handle("https://example.com") is False


def test_observe_refuses_a_path_outside_the_approved_folder(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("real content")
    plugin = DocumentPlugin(allowlist=_allowlist())

    with pytest.raises(PathNotApprovedError):
        plugin.observe(str(doc))


def test_observe_reads_a_real_approved_file(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("Real research notes about a real keto product trend.")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    plugin = DocumentPlugin(allowlist=allowlist)

    observation = plugin.observe(str(doc))

    assert "Real research notes" in observation.text_content
    assert observation.title == "notes.txt"


def test_observe_raises_on_a_real_missing_file(tmp_path):
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    plugin = DocumentPlugin(allowlist=allowlist)

    with pytest.raises(DocumentPluginError, match="not found"):
        plugin.observe(str(tmp_path / "missing.txt"))


def test_observe_with_extract_routes_through_the_real_injected_ai_provider(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("Real notes mentioning a real product called KetoDNA.")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))
    fake_provider = _FakeAIProvider(structured={"product": "KetoDNA"})
    plugin = DocumentPlugin(allowlist=allowlist, ai_provider=fake_provider)

    observation = plugin.observe(str(doc), extract={"product": "the product name mentioned"})

    assert observation.structured_data == {"product": "KetoDNA"}
    assert len(fake_provider.calls) == 1


def test_a_real_provider_failure_during_extraction_is_wrapped_loudly(tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("real content")
    allowlist = _allowlist()
    allowlist.approve_folder(str(tmp_path))

    class _FailingProvider:
        name = "failing"

        def complete_structured(self, prompt, fields):
            raise RuntimeError("real provider outage")

    plugin = DocumentPlugin(allowlist=allowlist, ai_provider=_FailingProvider())

    with pytest.raises(DocumentPluginError, match="real provider outage"):
        plugin.observe(str(doc), extract={"x": "y"})


def test_name_is_document():
    assert DocumentPlugin(allowlist=_allowlist()).name == "document"
