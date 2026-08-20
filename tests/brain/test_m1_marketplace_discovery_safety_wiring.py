import inspect

import atlas.brain.browser_plugin as browser_plugin
import atlas.brain.browser_research as browser_research
import atlas.brain.knowledge_source_research as knowledge_source_research
import atlas.integrations.browser_use_observer as browser_use_observer

# M1 Marketplace Discovery is observe-only by design (docs/
# M1_DESIGN_EXECUTION_PLAN.md §2א) -- none of the modules involved in it
# may reference BrowserHands (click/input/submit/promote/account-change),
# in code or even in a comment/docstring that might mislead a future
# reader into thinking it's wired in. A static source check, not a mock of
# behavior that doesn't exist -- the real guarantee is that the import
# never happens at all.
_MODULES_UNDER_M1_MARKETPLACE_DISCOVERY = [
    browser_research,
    browser_plugin,
    knowledge_source_research,
    browser_use_observer,
]


def test_no_marketplace_discovery_module_references_browser_hands():
    for module in _MODULES_UNDER_M1_MARKETPLACE_DISCOVERY:
        source = inspect.getsource(module)
        assert "BrowserHands" not in source, f"{module.__name__} must not reference BrowserHands (observe-only, M1)"
        assert "browser_hands" not in source, f"{module.__name__} must not import atlas.hands.browser_hands (observe-only, M1)"
