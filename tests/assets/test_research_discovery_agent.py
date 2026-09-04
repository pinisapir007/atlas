from atlas.assets.research_discovery.agent import ResearchDiscoveryAgent
from atlas.brain.discovery.research_request import research_task_description
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Task
from atlas.integrations.base import PageObservation
from atlas.integrations.browser_use_observer import BrowserUseError

_REAL_LENGTH_TEXT = "real page text about a real business model with real detail. " * 3  # > MIN_TEXT_LENGTH


class _FakeObserver:
    """Real run() now calls observe() twice (SERP, then navigation into
    the top real result) -- `observations` supports a real sequence, one
    real PageObservation per real call, falling back to the last one
    given if more calls happen than observations were supplied (matches
    every existing single-observation test unchanged)."""

    def __init__(self, observation=None, observations=None, error=None, second_call_error=None):
        self._observations = observations if observations is not None else [observation]
        self._error = error
        self._second_call_error = second_call_error
        self.calls = []

    def observe(self, url, extract=None):
        self.calls.append((url, extract))
        if self._error:
            raise self._error
        if len(self.calls) == 2 and self._second_call_error:
            raise self._second_call_error
        index = min(len(self.calls) - 1, len(self._observations) - 1)
        return self._observations[index]


class _FakeAIProvider:
    """Stands in for evidence_validation.assess_observation_quality()'s
    real AI relevance call -- never a real Gemini/Claude call in tests."""

    name = "fake"

    def __init__(self, relevant: bool = True):
        self._relevant = relevant

    def complete(self, prompt):
        raise NotImplementedError

    def complete_structured(self, prompt, fields):
        return {"relevant": "yes" if self._relevant else "no", "reason": "fake judgment"}


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _task(category: str) -> Task:
    return Task(goal_id="g1", description=research_task_description(category))


def _observation(structured: dict, text_content: str = _REAL_LENGTH_TEXT) -> PageObservation:
    return PageObservation(
        url="https://duckduckgo.com/html/?q=x", title="results", text_content=text_content, structured_data=structured
    )


def test_run_saves_a_real_finding_per_real_result(tmp_path):
    kb = _kb(tmp_path)
    observation = _observation({
        "result_1_title": "SaaS revenue models explained",
        "result_1_url": "https://example.com/saas-guide",
        "result_1_snippet": "a real snippet",
        "result_2_title": "",  # honest gap -- only one real result found
        "result_2_url": "",
        "result_2_snippet": "",
    })
    agent = ResearchDiscoveryAgent(
        knowledge=kb, observer=_FakeObserver(observation=observation), ai_provider=_FakeAIProvider(relevant=True)
    )

    result = agent.run(task=_task("saas"))

    assert result["status"] == "done"
    assert result["findings_created"] == 1
    [finding] = kb.findings()
    assert finding.category == "saas"
    assert finding.source == "research_discovery"
    assert finding.evidence == "https://example.com/saas-guide"
    assert "SaaS revenue models explained" in finding.description


def test_run_with_an_unrelated_task_fails_honestly_never_crashing(tmp_path):
    # Delegator's unmatched-fallback path can hand ANY task to ANY
    # Triggerable asset -- this must never raise, or it would crash the
    # whole delegate()/tick() call for a task this agent has nothing to
    # do with.
    kb = _kb(tmp_path)
    agent = ResearchDiscoveryAgent(knowledge=kb, observer=_FakeObserver(), ai_provider=_FakeAIProvider())

    result = agent.run(task=Task(goal_id="g1", description="Grow monthly revenue"))

    assert result["status"] == "failed"
    assert "not a real research-trigger task" in result["reason"]
    assert kb.findings() == []


def test_run_records_an_honest_failure_never_fabricating_a_finding(tmp_path):
    kb = _kb(tmp_path)
    agent = ResearchDiscoveryAgent(
        knowledge=kb, observer=_FakeObserver(error=BrowserUseError("real search failure")), ai_provider=_FakeAIProvider()
    )

    result = agent.run(task=_task("saas"))

    assert result["status"] == "failed"
    assert "real search failure" in result["reason"]
    assert kb.findings() == []


def test_run_rejects_low_quality_evidence_via_the_real_shared_gate(tmp_path):
    # Reuse Before Build (Qualification Framework Step 1): the whole
    # observation must clear atlas.brain.evidence_validation's real,
    # already-tested quality gate before anything gets extracted/saved --
    # a too-short/irrelevant page must never become a Finding.
    kb = _kb(tmp_path)
    observation = _observation(
        {"result_1_title": "x", "result_1_url": "https://example.com/1", "result_1_snippet": "s"},
        text_content="too short",
    )
    agent = ResearchDiscoveryAgent(
        knowledge=kb, observer=_FakeObserver(observation=observation), ai_provider=_FakeAIProvider(relevant=True)
    )

    result = agent.run(task=_task("saas"))

    assert result["status"] == "failed"
    assert "failed evidence quality" in result["reason"]
    assert kb.findings() == []


def test_run_rejects_ai_judged_irrelevant_evidence(tmp_path):
    kb = _kb(tmp_path)
    observation = _observation({"result_1_title": "x", "result_1_url": "https://example.com/1", "result_1_snippet": "s"})
    agent = ResearchDiscoveryAgent(
        knowledge=kb, observer=_FakeObserver(observation=observation), ai_provider=_FakeAIProvider(relevant=False)
    )

    result = agent.run(task=_task("saas"))

    assert result["status"] == "failed"
    assert "failed evidence quality" in result["reason"]
    assert kb.findings() == []


def test_run_discovers_a_real_subject_bearing_finding_from_the_top_real_result(tmp_path):
    # Root Cause A closure (docs/DESIGN_GAP_A_SUBJECT_DISCOVERY.md): the
    # only path in this whole agent that ever fills Finding.subject.
    kb = _kb(tmp_path)
    serp = _observation({
        "result_1_title": "50 Best Digital Products to Sell in 2026",
        "result_1_url": "https://sellramp.com/blog/best-digital-products-to-sell-2026",
        "result_1_snippet": "a real snippet",
    })
    page = _observation({"candidate_1": "Notion templates", "candidate_2": "Canva templates"})
    agent = ResearchDiscoveryAgent(
        knowledge=kb,
        observer=_FakeObserver(observations=[serp, page]),
        ai_provider=_FakeAIProvider(relevant=True),
    )

    result = agent.run(task=_task("digital_product"))

    assert result["status"] == "done"
    subjects = sorted(f.subject for f in kb.findings() if f.subject)
    assert subjects == ["Canva templates", "Notion templates"]
    subject_finding = next(f for f in kb.findings() if f.subject == "Notion templates")
    assert subject_finding.evidence == "https://sellramp.com/blog/best-digital-products-to-sell-2026"
    assert subject_finding.category == "digital_product"
    # the navigation call used the real destination URL, not the SERP URL
    assert agent._observer.calls[1][0] == "https://sellramp.com/blog/best-digital-products-to-sell-2026"


def test_run_rejects_a_candidate_that_is_just_the_category_echoed_back(tmp_path):
    kb = _kb(tmp_path)
    serp = _observation({
        "result_1_title": "How YouTube Makes Money",
        "result_1_url": "https://example.com/youtube-model",
        "result_1_snippet": "s",
    })
    page = _observation({"candidate_1": "YouTube"})
    agent = ResearchDiscoveryAgent(
        knowledge=kb, observer=_FakeObserver(observations=[serp, page]), ai_provider=_FakeAIProvider(relevant=True)
    )

    agent.run(task=_task("youtube"))

    assert all(f.subject == "" for f in kb.findings())


def test_run_rejects_a_candidate_that_is_just_the_source_sites_own_brand(tmp_path):
    kb = _kb(tmp_path)
    serp = _observation({
        "result_1_title": "20 Profitable SaaS Ideas for 2026",
        "result_1_url": "https://elementor.com/blog/profitable-saas-ideas/",
        "result_1_snippet": "s",
    })
    page = _observation({"candidate_1": "Elementor", "candidate_2": "Salesforce"})
    agent = ResearchDiscoveryAgent(
        knowledge=kb, observer=_FakeObserver(observations=[serp, page]), ai_provider=_FakeAIProvider(relevant=True)
    )

    agent.run(task=_task("saas"))

    subjects = [f.subject for f in kb.findings() if f.subject]
    assert subjects == ["Salesforce"]  # "Elementor" (the source site's own name) rejected


def test_run_normalizes_a_scheme_missing_url_before_navigating(tmp_path):
    kb = _kb(tmp_path)
    serp = _observation({
        "result_1_title": "Best Affiliate Products To Sell In 2026",
        "result_1_url": "sellvia.com/blog/affiliate-products-to-sell/",  # real, observed gap: missing scheme
        "result_1_snippet": "s",
    })
    page = _observation({"candidate_1": "AdsPower"})
    observer = _FakeObserver(observations=[serp, page])
    agent = ResearchDiscoveryAgent(knowledge=kb, observer=observer, ai_provider=_FakeAIProvider(relevant=True))

    agent.run(task=_task("affiliate"))

    assert observer.calls[1][0] == "https://sellvia.com/blog/affiliate-products-to-sell/"
    assert any(f.subject == "AdsPower" for f in kb.findings())


def test_run_degrades_honestly_when_navigation_into_the_top_result_fails(tmp_path):
    # Known Limitation discipline: a real navigation failure on the
    # second call must never crash run() or fabricate a Finding -- the
    # base findings from _save_findings() still get saved.
    kb = _kb(tmp_path)
    serp = _observation({"result_1_title": "t", "result_1_url": "https://example.com/1", "result_1_snippet": "s"})
    agent = ResearchDiscoveryAgent(
        knowledge=kb,
        observer=_FakeObserver(observations=[serp], second_call_error=BrowserUseError("real navigation failure")),
        ai_provider=_FakeAIProvider(relevant=True),
    )

    result = agent.run(task=_task("saas"))

    assert result["status"] == "done"
    assert result["findings_created"] == 1  # the base, subject-less Finding still saved
    assert all(f.subject == "" for f in kb.findings())


def test_report_is_a_real_aggregate_scoped_to_this_agents_own_findings(tmp_path):
    kb = _kb(tmp_path)
    observation = _observation({"result_1_title": "a", "result_1_url": "https://x.com/1", "result_1_snippet": "s"})
    agent = ResearchDiscoveryAgent(
        knowledge=kb, observer=_FakeObserver(observation=observation), ai_provider=_FakeAIProvider(relevant=True)
    )
    agent.run(task=_task("saas"))
    agent.run(task=_task("marketplace"))

    report = agent.report()

    assert report["status"] == "done"
    assert report["total_findings"] == 2


class _FakeSearchProvider:
    def __init__(self, name: str, url: str):
        self.name = name
        self._url = url

    def search_url(self, query: str) -> str:
        return self._url


class _FallbackObserver:
    def __init__(self, successful_observation):
        self._successful_observation = successful_observation
        self.calls = []

    def observe(self, url, extract=None):
        self.calls.append((url, extract))
        if "first-search.example" in url:
            raise BrowserUseError("first search provider failed")
        return self._successful_observation


def test_run_falls_back_to_second_search_provider_when_first_search_fails(tmp_path):
    kb = _kb(tmp_path)

    serp = _observation({
        "result_1_title": "Real SaaS comparison",
        "result_1_url": "https://example.com/saas",
        "result_1_snippet": "real evidence",
    })

    observer = _FallbackObserver(serp)

    first = _FakeSearchProvider(
        "first",
        "https://first-search.example/?q=test",
    )
    second = _FakeSearchProvider(
        "second",
        "https://second-search.example/?q=test",
    )

    agent = ResearchDiscoveryAgent(
        knowledge=kb,
        observer=observer,
        ai_provider=_FakeAIProvider(relevant=True),
        search_providers=[first, second],
    )

    result = agent.run(task=_task("saas"))

    assert result["status"] == "done"
    assert result["findings_created"] >= 1
    assert observer.calls[0][0].startswith("https://first-search.example/")
    assert observer.calls[1][0].startswith("https://second-search.example/")


class _FakeStructuredSearchProvider:
    name = "structured"

    def search(self, query: str, max_results: int = 5):
        return [
            {
                "title": "Real service business software",
                "url": "https://example.com/service-software",
                "snippet": "Real comparison of software tools for service businesses.",
            }
        ]


class _StructuredSearchNavigationObserver:
    """Structured search itself must not need a SERP browser page.
    BrowserObserver is used only for the real destination-page navigation."""
    def __init__(self):
        self.calls = []

    def observe(self, url, extract=None):
        self.calls.append((url, extract))
        return _observation({
            "candidate_1": "ServiceTitan",
            "candidate_2": "Jobber",
        })


def test_run_accepts_structured_search_results_without_serp_browser_scraping(tmp_path):
    kb = _kb(tmp_path)
    observer = _StructuredSearchNavigationObserver()

    agent = ResearchDiscoveryAgent(
        knowledge=kb,
        observer=observer,
        ai_provider=_FakeAIProvider(relevant=True),
        search_providers=[_FakeStructuredSearchProvider()],
    )

    result = agent.run(task=_task("service_business"))

    assert result["status"] == "done"
    assert result["search_provider"] == "structured"
    assert result["findings_created"] >= 1

    # Browser is used only after search, to inspect the real top result.
    assert len(observer.calls) == 1
    assert observer.calls[0][0] == "https://example.com/service-software"

    findings = kb.findings()
    assert any(f.evidence == "https://example.com/service-software" for f in findings)
