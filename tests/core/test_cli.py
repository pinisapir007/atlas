from atlas.cli import main


def test_list_includes_maya(capsys):
    main(["list"])
    out = capsys.readouterr().out
    assert "maya" in out


def test_start_maya_succeeds(capsys):
    exit_code = main(["start", "maya"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "ok" in out


def test_status_default_is_stopped(capsys):
    # Each CLI invocation builds a fresh Registry (a fresh process, in real
    # use), so an in-memory-only asset like MayaAgent never carries state
    # across separate calls. Cross-invocation state belongs in the Store,
    # which is covered by tests/core/test_registry.py.
    main(["status", "maya"])
    out = capsys.readouterr().out
    assert "stopped" in out


def test_info_prints_metadata(capsys):
    main(["info", "maya"])
    out = capsys.readouterr().out
    assert "kind: agent" in out


def test_unknown_asset_exits_nonzero():
    assert main(["status", "does-not-exist"]) == 1
