from atlas.brain.conversation_memory import ConversationMemory


class _FakeStore:
    def __init__(self):
        self._data = None

    def read(self):
        return self._data

    def write(self, data):
        self._data = data


def test_record_and_read_back_a_real_turn():
    memory = ConversationMemory(store=_FakeStore())

    entry = memory.record_turn("status", "Goals: 1 | Approvals waiting: 0")

    entries = memory.entries()
    assert len(entries) == 1
    assert entries[0].id == entry.id
    assert entries[0].input_line == "status"
    assert entries[0].response_summary == "Goals: 1 | Approvals waiting: 0"


def test_entries_persist_across_separate_instances_of_the_same_store():
    store = _FakeStore()
    memory1 = ConversationMemory(store=store)
    memory1.record_turn("status", "response 1")

    memory2 = ConversationMemory(store=store)
    entries = memory2.entries()

    assert len(entries) == 1
    assert entries[0].input_line == "status"


def test_recent_returns_only_the_last_n_entries_in_order():
    memory = ConversationMemory(store=_FakeStore())
    for i in range(5):
        memory.record_turn(f"line {i}", f"response {i}")

    recent = memory.recent(limit=2)

    assert len(recent) == 2
    assert recent[0].input_line == "line 3"
    assert recent[1].input_line == "line 4"
