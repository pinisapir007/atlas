from atlas.brain.feature_flags import opportunity_discovery_v1_enabled, pattern_hypothesis_enabled, sales_sync_enabled


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", raising=False)
    assert opportunity_discovery_v1_enabled() is False


def test_enabled_when_env_var_set(monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "1")
    assert opportunity_discovery_v1_enabled() is True


def test_disabled_when_env_var_is_empty_string(monkeypatch):
    monkeypatch.setenv("ATLAS_OPPORTUNITY_DISCOVERY_V1", "")
    assert opportunity_discovery_v1_enabled() is False



def test_sales_sync_is_off_by_default(monkeypatch):
    monkeypatch.delenv("ATLAS_SALES_SYNC_ENABLED", raising=False)
    assert sales_sync_enabled() is False


def test_sales_sync_can_be_explicitly_enabled(monkeypatch):
    monkeypatch.setenv("ATLAS_SALES_SYNC_ENABLED", "1")
    assert sales_sync_enabled() is True



def test_pattern_hypothesis_is_off_by_default(monkeypatch):
    monkeypatch.delenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        raising=False,
    )
    assert pattern_hypothesis_enabled() is False


def test_pattern_hypothesis_can_be_explicitly_enabled(monkeypatch):
    monkeypatch.setenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        "1",
    )
    assert pattern_hypothesis_enabled() is True


def test_pattern_hypothesis_empty_flag_is_disabled(monkeypatch):
    monkeypatch.setenv(
        "ATLAS_PATTERN_HYPOTHESIS_ENABLED",
        "",
    )
    assert pattern_hypothesis_enabled() is False
