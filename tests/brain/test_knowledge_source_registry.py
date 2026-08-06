import pytest

from atlas.brain.browser_plugin import BrowserPlugin
from atlas.brain.document_plugin import DocumentPlugin
from atlas.brain.knowledge_source_registry import KNOWLEDGE_SOURCE_PLUGINS, select_plugin
from atlas.integrations.base import KnowledgeSourcePlugin


def test_registry_has_two_real_implementations():
    assert len(KNOWLEDGE_SOURCE_PLUGINS) == 2
    assert any(isinstance(p, BrowserPlugin) for p in KNOWLEDGE_SOURCE_PLUGINS)
    assert any(isinstance(p, DocumentPlugin) for p in KNOWLEDGE_SOURCE_PLUGINS)


def test_both_real_plugins_satisfy_the_protocol_structurally():
    for plugin in KNOWLEDGE_SOURCE_PLUGINS:
        assert isinstance(plugin, KnowledgeSourcePlugin)


def test_select_plugin_dispatches_a_url_to_the_browser_plugin():
    plugin = select_plugin("https://example.com")
    assert isinstance(plugin, BrowserPlugin)


def test_select_plugin_dispatches_a_text_file_to_the_document_plugin():
    plugin = select_plugin("C:/scratch/notes.txt")
    assert isinstance(plugin, DocumentPlugin)


def test_select_plugin_raises_for_an_unrecognized_source():
    with pytest.raises(ValueError, match="no registered knowledge source plugin"):
        select_plugin("some-random-string-not-a-real-source")
