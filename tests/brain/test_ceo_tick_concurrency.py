import os
import threading

from atlas.assets.affiliate_department.store import AffiliateStore
from atlas.brain.ceo import CEOBrain
from atlas.brain.decisions import DecisionLog
from atlas.brain.investigations import InvestigationStore
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.ledger import Ledger
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.memory import BrainMemory
from atlas.brain.opportunities import OpportunityStore
from atlas.brain.tick_lock import tick_lock
from atlas.campaign.registry import CampaignRegistry
from atlas.core.registry import Registry
from atlas.core.store import JSONStore
from atlas.influencer.registry import InfluencerRegistry
from atlas.orchestrator.registry import ExecutionPlanRegistry

_UNLIKELY_REAL_PID = 999_999_999


def _brain(tmp_path):
    return CEOBrain(
        memory=BrainMemory(tmp_path / "brain.json"),
        registry=Registry(store=JSONStore(tmp_path / "state.json")),
        knowledge=KnowledgeBase(tmp_path / "knowledge.json"),
        decisions=DecisionLog(tmp_path / "decisions.json"),
        ledger=Ledger(tmp_path / "ledger.json"),
        campaigns=CampaignRegistry(tmp_path / ".atlas" / "campaigns.json"),
        influencers=InfluencerRegistry(tmp_path / ".atlas" / "influencers.json"),
        execution_plans=ExecutionPlanRegistry(tmp_path / ".atlas" / "execution_plans.json"),
        affiliate_store=AffiliateStore(tmp_path / ".atlas" / "affiliate_intelligence.json"),
        opportunities=OpportunityStore(tmp_path / ".atlas" / "opportunities.json"),
        marketplace_catalog=MarketplaceCatalogStore(tmp_path / ".atlas" / "marketplace_catalog.json"),
        investigations=InvestigationStore(tmp_path / ".atlas" / "investigations.json"),
    )


# --- A-E: real concurrent contention, using real threads ----------------


def test_two_real_threads_racing_for_the_lock_only_one_ever_holds_it(tmp_path):
    lock_path = tmp_path / "tick.lock"
    first_has_lock = threading.Event()
    release_first = threading.Event()
    second_result = {}

    def first_holder():
        with tick_lock(lock_path):
            first_has_lock.set()
            release_first.wait(timeout=5)

    def second_attempt():
        first_has_lock.wait(timeout=5)  # only attempt once the first thread genuinely holds it
        try:
            with tick_lock(lock_path):
                second_result["acquired"] = True
        except Exception as exc:  # noqa: BLE001
            second_result["acquired"] = False
            second_result["error"] = str(exc)

    t1 = threading.Thread(target=first_holder)
    t2 = threading.Thread(target=second_attempt)
    t1.start()
    t2.start()
    t2.join(timeout=5)
    release_first.set()
    t1.join(timeout=5)

    assert second_result["acquired"] is False
    assert "already running" in second_result["error"]


def test_after_the_first_real_holder_releases_a_new_attempt_succeeds(tmp_path):
    lock_path = tmp_path / "tick.lock"

    with tick_lock(lock_path):
        pass  # first holder runs and releases cleanly

    acquired_after = False
    with tick_lock(lock_path):
        acquired_after = True

    assert acquired_after is True


# --- CEOBrain.tick() itself: real integration, not just the primitive ---


def test_ceo_tick_returns_empty_and_logs_when_the_lock_is_already_held(tmp_path):
    brain = _brain(tmp_path)
    goal = brain.add_goal("Grow revenue")
    tasks_before = len(brain.memory.tasks())

    lock_path = brain.memory.path.parent / "tick.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(f"{os.getpid()}\n")  # simulates a real tick already in flight, held by this same live process

    result = brain.tick()

    assert result == []
    assert len(brain.memory.tasks()) == tasks_before  # no duplicate Task dispatch happened
    log_entries = brain.memory.log()
    assert any(e.get("event") == "tick_skipped_lock_contention" for e in log_entries)

    lock_path.unlink()  # cleanup this test's own simulated lock


def test_ceo_tick_recovers_from_a_real_stale_lock_and_runs_normally(tmp_path):
    brain = _brain(tmp_path)
    brain.add_goal("Grow revenue")

    lock_path = brain.memory.path.parent / "tick.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(f"{_UNLIKELY_REAL_PID}\n")  # simulates a crashed previous tick that never released its lock

    result = brain.tick()

    assert result != []  # a real tick actually ran -- SimplePlanner created a task for the active goal
    assert not lock_path.exists()  # released normally afterward


def test_a_real_exception_during_tick_still_releases_the_lock(tmp_path, monkeypatch):
    brain = _brain(tmp_path)
    brain.add_goal("Grow revenue")

    def _boom(*args, **kwargs):
        raise RuntimeError("a real, simulated crash mid-tick")

    monkeypatch.setattr(brain.planner, "plan", _boom)

    try:
        brain.tick()
    except RuntimeError:
        pass  # this test only cares whether the lock survives the crash, not that tick() itself swallows it

    lock_path = brain.memory.path.parent / "tick.lock"
    assert not lock_path.exists()  # never a permanent lock after a real crash

    # And ATLAS is not permanently disabled -- a subsequent real tick can still run.
    monkeypatch.undo()
    result = brain.tick()
    assert isinstance(result, list)
