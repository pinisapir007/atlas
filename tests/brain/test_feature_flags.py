from atlas.brain.feature_flags import opportunity_discovery_v1_enabled


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", raising=False)
    assert opportunity_discovery_v1_enabled() is False


def test_enabled_when_env_var_set(monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    assert opportunity_discovery_v1_enabled() is True


def test_disabled_when_env_var_is_empty_string(monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "")
    assert opportunity_discovery_v1_enabled() is False
