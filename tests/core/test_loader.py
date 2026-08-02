from pathlib import Path

from atlas.core.loader import discover_manifests

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "assets"


def test_discovers_all_fixture_manifests():
    records = discover_manifests([FIXTURES])
    ids = {r.id for r in records}
    assert ids == {"sample-agent", "sample-business", "sample-triggerable"}


def test_entrypoint_is_optional():
    records = {r.id: r for r in discover_manifests([FIXTURES])}
    assert records["sample-business"].entrypoint is None
    assert records["sample-agent"].entrypoint == "tests.fixtures.assets.agent_sample.agent:SampleAgent"


def test_missing_dir_is_ignored():
    assert discover_manifests([FIXTURES / "does-not-exist"]) == []
