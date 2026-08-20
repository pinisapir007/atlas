from atlas.assets.deep_research.agent import DeepResearchAgent
from atlas.brain.discovery.deep_research_request import deep_research_task_description
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.models import Task
from atlas.integrations.base import PageObservation
from atlas.integrations.browser_use_observer import BrowserUseError

_REAL_LENGTH_TEXT = "real page text about a real business model with real detail. " * 3


class _FakeObserver:
    """Always raises on every real call when `error` is set (simulates
    every one of a DeepResearchAgent run's real steps failing); otherwise
    cycles through a fixed real observation queue, one per real call,
    repeating the last one once exhausted."""

    def __init__(self, observations=None, error=None):
        self._observations = observations or []
        self._error = error
        self.calls = []

    def observe(self, url, extract=None):
        self.calls.append(url)
        if self._error:
            raise self._error
        index = min(len(self.calls) - 1, len(self._observations) - 1)
        return self._observations[index]


class _FakeAIProvider:
    name = "fake"

    def complete(self, prompt):
        raise NotImplementedError

    def complete_structured(self, prompt, fields):
        return {"relevant": "yes", "reason": "fake judgment"}


def _kb(tmp_path):
    return KnowledgeBase(tmp_path / "knowledge.json")


def _task(category: str) -> Task:
    return Task(goal_id="g1", description=deep_research_task_description(category))


def _observation(structured: dict) -> PageObservation:
    return PageObservation(
        url="https://duckduckgo.com/html/?q=x", title="results", text_content=_REAL_LENGTH_TEXT, structured_data=structured
    )


def test_run_with_an_unrelated_task_fails_honestly_never_crashing(tmp_path):
    kb = _kb(tmp_path)
    agent = DeepResearchAgent(knowledge=kb, observer=_FakeObserver(), ai_provider=_FakeAIProvider())

    result = agent.run(task=Task(goal_id="g1", description="Grow monthly revenue"))

    assert result["status"] == "failed"
    assert "not a real deep-research task" in result["reason"]


def test_run_rejects_a_shallow_research_task_never_treating_it_as_deep(tmp_path):
    # The two triggers are deliberately distinct -- a shallow
    # request_research Task must never accidentally dispatch here.
    from atlas.brain.discovery.research_request import research_task_description

    kb = _kb(tmp_path)
    agent = DeepResearchAgent(knowledge=kb, observer=_FakeObserver(), ai_provider=_FakeAIProvider())

    result = agent.run(task=Task(goal_id="g1", description=research_task_description("saas")))

    assert result["status"] == "failed"


def test_run_stops_early_once_enough_real_evidence_exists(tmp_path):
    # Step 1 alone produces 2 real, evidenced findings -- clears
    # decision_engine.MIN_INDEPENDENT_SOURCES(2) -- so step 2/3 must
    # never run.
    kb = _kb(tmp_path)
    serp = _observation({
        "result_1_title": "SaaS revenue models explained",
        "result_1_url": "https://example.com/saas-guide",
        "result_1_snippet": "s",
        "result_2_title": "Another real SaaS article",
        "result_2_url": "https://example.com/saas-guide-2",
        "result_2_snippet": "s",
    })
    agent = DeepResearchAgent(knowledge=kb, observer=_FakeObserver(observations=[serp]), ai_provider=_FakeAIProvider())

    result = agent.run(task=_task("saas"))

    assert result["status"] == "done"
    assert result["stop_reason"] == "enough_evidence"
    assert result["steps_taken"] == 1
    assert result["findings_created"] == 2


def test_run_stops_on_no_progress_when_a_real_step_finds_nothing_new(tmp_path):
    kb = _kb(tmp_path)
    empty_serp = _observation({"result_1_title": "", "result_1_url": "", "result_1_snippet": ""})
    agent = DeepResearchAgent(
        knowledge=kb, observer=_FakeObserver(observations=[empty_serp]), ai_provider=_FakeAIProvider()
    )

    result = agent.run(task=_task("saas"))

    assert result["status"] == "done"
    assert result["stop_reason"] == "no_progress"
    assert result["steps_taken"] == 1
    assert result["findings_created"] == 0


def test_run_reaches_max_steps_honestly_when_every_real_step_fails(tmp_path):
    kb = _kb(tmp_path)
    agent = DeepResearchAgent(
        knowledge=kb, observer=_FakeObserver(error=BrowserUseError("real search failure")), ai_provider=_FakeAIProvider()
    )

    result = agent.run(task=_task("saas"))

    assert result["status"] == "done"
    assert result["stop_reason"] == "max_steps_reached"
    assert result["steps_taken"] == 3
    assert result["findings_created"] == 0
    assert all(step["status"] == "failed" for step in result["steps"])


def test_run_uses_a_genuinely_different_real_query_per_step(tmp_path):
    kb = _kb(tmp_path)
    agent = DeepResearchAgent(
        knowledge=kb, observer=_FakeObserver(error=BrowserUseError("x")), ai_provider=_FakeAIProvider()
    )

    result = agent.run(task=_task("saas"))

    queries = [step["query"] for step in result["steps"]]
    assert len(set(queries)) == 3  # three genuinely distinct real query angles, not the same one repeated


def test_run_attributes_findings_to_deep_research_not_shallow_research(tmp_path):
    kb = _kb(tmp_path)
    serp = _observation({
        "result_1_title": "t", "result_1_url": "https://example.com/1", "result_1_snippet": "s",
        "result_2_title": "t2", "result_2_url": "https://example.com/2", "result_2_snippet": "s",
    })
    agent = DeepResearchAgent(knowledge=kb, observer=_FakeObserver(observations=[serp]), ai_provider=_FakeAIProvider())

    agent.run(task=_task("saas"))

    assert kb.findings() != []
    assert all(f.source == "deep_research" for f in kb.findings())


def test_report_is_a_real_aggregate_scoped_to_this_agents_own_findings(tmp_path):
    kb = _kb(tmp_path)
    serp = _observation({
        "result_1_title": "t", "result_1_url": "https://example.com/1", "result_1_snippet": "s",
        "result_2_title": "t2", "result_2_url": "https://example.com/2", "result_2_snippet": "s",
    })
    agent = DeepResearchAgent(knowledge=kb, observer=_FakeObserver(observations=[serp]), ai_provider=_FakeAIProvider())
    agent.run(task=_task("saas"))

    report = agent.report()

    assert report["status"] == "done"
    assert report["total_findings"] == 2
