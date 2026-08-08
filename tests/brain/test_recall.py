from atlas.brain.conversation_memory import ConversationMemory
from atlas.brain.decisions import Decision, DecisionLog
from atlas.brain.knowledge import KnowledgeBase
from atlas.brain.ledger import Ledger
from atlas.brain.memory import BrainMemory
from atlas.brain.models import Finding, Goal, LedgerEntry, Task
from atlas.brain.recall import recall
from atlas.brand.models import Brand
from atlas.brand.registry import BrandRegistry
from atlas.campaign.models import Campaign
from atlas.campaign.registry import CampaignRegistry


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_recall_with_no_stores_returns_empty():
    assert recall("keto") == []


def test_recall_finds_a_real_matching_goal():
    memory = BrainMemory(store=_FakeStore())
    memory.save_goal(Goal(description="grow the keto affiliate business"))
    memory.save_goal(Goal(description="unrelated goal about widgets"))

    hits = recall("keto", memory=memory)

    assert len(hits) == 1
    assert hits[0].store == "goal"
    assert "keto" in hits[0].summary


def test_recall_finds_a_real_matching_task():
    memory = BrainMemory(store=_FakeStore())
    memory.save_task(Task(goal_id="g1", description="research keto supplement demand"))

    hits = recall("keto", memory=memory)

    assert len(hits) == 1
    assert hits[0].store == "task"


def test_recall_is_case_insensitive():
    memory = BrainMemory(store=_FakeStore())
    memory.save_goal(Goal(description="grow the KETO business"))

    hits = recall("keto", memory=memory)

    assert len(hits) == 1


def test_recall_searches_across_multiple_real_stores_at_once():
    memory = BrainMemory(store=_FakeStore())
    memory.save_goal(Goal(description="keto affiliate growth"))
    knowledge = KnowledgeBase(store=_FakeStore())
    knowledge.save_finding(Finding(source="reddit", category="affiliate", description="real demand for keto products", evidence="https://example.com"))
    campaigns = CampaignRegistry(store=_FakeStore())
    campaigns.save_campaign(Campaign(business_objective="sell keto", category="affiliate", product_offer="KetoDNA"))

    hits = recall("keto", memory=memory, knowledge=knowledge, campaigns=campaigns)

    stores_hit = {h.store for h in hits}
    assert stores_hit == {"goal", "finding", "campaign"}


def test_recall_finds_a_real_decision():
    decisions = DecisionLog(store=_FakeStore())
    decisions.save_decision(Decision(category="affiliate", verdict="invest", confidence=0.8, factors={}, reasoning="strong keto evidence"))

    hits = recall("keto", decisions=decisions)

    assert len(hits) == 1
    assert hits[0].store == "decision"


def test_recall_finds_a_real_ledger_entry():
    ledger = Ledger(store=_FakeStore())
    ledger.record(LedgerEntry(goal_id="g1", kind="revenue_claimed", amount=100.0, category="affiliate", evidence="keto sale confirmed"))

    hits = recall("keto", ledger=ledger)

    assert len(hits) == 1
    assert hits[0].store == "ledger_entry"


def test_recall_finds_a_real_brand():
    brands = BrandRegistry(store=_FakeStore())
    brands.save_brand(Brand(name="KetoDNA Brand", niche="keto supplements", category="affiliate"))

    hits = recall("keto", brands=brands)

    assert len(hits) == 1
    assert hits[0].store == "brand"


def test_recall_finds_a_real_conversation():
    conversations = ConversationMemory(store=_FakeStore())
    conversations.record_turn("what is our keto strategy?", "we are pursuing the keto affiliate niche")

    hits = recall("keto", conversations=conversations)

    assert len(hits) == 1
    assert hits[0].store == "conversation"


def test_recall_orders_hits_most_recent_first():
    memory = BrainMemory(store=_FakeStore())
    memory.save_goal(Goal(description="keto goal one"))
    memory.save_goal(Goal(description="keto goal two"))

    hits = recall("keto", memory=memory)

    assert hits[0].created_at >= hits[1].created_at


def test_recall_respects_the_limit():
    memory = BrainMemory(store=_FakeStore())
    for i in range(10):
        memory.save_goal(Goal(description=f"keto goal {i}"))

    hits = recall("keto", memory=memory, limit=3)

    assert len(hits) == 3


def test_recall_with_no_match_returns_empty():
    memory = BrainMemory(store=_FakeStore())
    memory.save_goal(Goal(description="an unrelated widget goal"))

    hits = recall("keto", memory=memory)

    assert hits == []
