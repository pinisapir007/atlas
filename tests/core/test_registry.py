from pathlib import Path

import pytest

from atlas.core.loader import discover_manifests
from atlas.core.registry import Registry, UnsupportedVerb
from atlas.core.store import JSONStore

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "assets"


def _registry(tmp_path):
    records = discover_manifests([FIXTURES])
    return Registry(records, store=JSONStore(tmp_path / "state.json"))


def test_start_stop_status(tmp_path):
    registry = _registry(tmp_path)
    assert registry.dispatch("sample-agent", "status") == "stopped"
    registry.dispatch("sample-agent", "start")
    assert registry.dispatch("sample-agent", "status") == "running"


def test_dispatch_persists_state(tmp_path):
    registry = _registry(tmp_path)
    registry.dispatch("sample-agent", "start")
    store = JSONStore(tmp_path / "state.json")
    assert store.get("sample-agent")["last_verb"] == "start"


def test_entrypointless_asset_rejects_runnable_verbs(tmp_path):
    registry = _registry(tmp_path)
    with pytest.raises(UnsupportedVerb):
        registry.dispatch("sample-business", "start")


def test_unknown_verb_rejected(tmp_path):
    registry = _registry(tmp_path)
    with pytest.raises(UnsupportedVerb):
        registry.dispatch("sample-agent", "nope")


def test_unknown_asset_raises_keyerror(tmp_path):
    registry = _registry(tmp_path)
    with pytest.raises(KeyError):
        registry.get_record("does-not-exist")
