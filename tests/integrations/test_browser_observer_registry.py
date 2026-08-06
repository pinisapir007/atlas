import pytest

from atlas.integrations.browser_observer_registry import BROWSER_OBSERVERS, get_browser_observer
from atlas.integrations.browser_use_observer import BrowserUseObserver


def test_registry_has_the_one_real_implementation():
    assert set(BROWSER_OBSERVERS) == {"browser_use"}
    assert isinstance(BROWSER_OBSERVERS["browser_use"], BrowserUseObserver)


def test_get_browser_observer_returns_the_real_instance():
    assert get_browser_observer("browser_use") is BROWSER_OBSERVERS["browser_use"]


def test_get_unknown_observer_raises():
    with pytest.raises(ValueError, match="unsupported browser observer"):
        get_browser_observer("stagehand")
