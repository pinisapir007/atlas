from atlas.core.store import JSONStore, read_json, write_json_atomic


def test_jsonstore_round_trips_per_asset_state(tmp_path):
    store = JSONStore(tmp_path / "state.json")
    store.set("maya", {"last_verb": "run", "result": "ok"})

    assert store.get("maya") == {"last_verb": "run", "result": "ok"}
    assert store.get("unknown_asset") == {}


def test_jsonstore_persists_across_instances(tmp_path):
    path = tmp_path / "state.json"
    JSONStore(path).set("maya", {"status": "stopped"})

    assert JSONStore(path).get("maya") == {"status": "stopped"}


def test_read_json_returns_default_when_file_missing(tmp_path):
    assert read_json(tmp_path / "missing.json", {"fallback": True}) == {"fallback": True}


def test_write_json_atomic_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "doc.json"
    write_json_atomic(path, {"a": 1})

    assert read_json(path, {}) == {"a": 1}
    assert not path.with_name(path.name + ".tmp").exists()


def test_write_json_atomic_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "doc.json"
    write_json_atomic(path, {"a": 1})

    assert read_json(path, {}) == {"a": 1}
