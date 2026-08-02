from atlas.brain.store import JSONFileStore


def test_read_returns_none_when_file_missing(tmp_path):
    assert JSONFileStore(tmp_path / "brain.json").read() is None


def test_write_then_read_round_trips(tmp_path):
    store = JSONFileStore(tmp_path / "brain.json")
    store.write({"goals": {"g1": {"description": "grow revenue"}}})

    assert store.read() == {"goals": {"g1": {"description": "grow revenue"}}}


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "brain.json"
    JSONFileStore(path).write({"a": 1})

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
