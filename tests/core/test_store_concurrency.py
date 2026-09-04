import multiprocessing as mp
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from atlas.brain.conversation_memory import ConversationMemory
from atlas.brain.marketplace_catalog import MarketplaceCatalogStore
from atlas.brain.marketplace_extraction import MarketplaceProductRecord
from atlas.brain.memory import BrainMemory
from atlas.core.store import JSONStore, _interprocess_lock


def _fork_context():
    try:
        return mp.get_context("fork")
    except ValueError:
        pytest.skip("inter-process concurrency qualification requires POSIX fork")


def _run_processes(processes, timeout=10):
    for process in processes:
        process.start()

    for process in processes:
        process.join(timeout)
        if process.is_alive():
            process.terminate()
            process.join()
            pytest.fail("concurrency worker hung")
        assert process.exitcode == 0


def test_concurrent_sets_preserve_every_asset_without_crashing(tmp_path):
    store = JSONStore(tmp_path / "state.json")
    workers = 32
    barrier = threading.Barrier(workers)

    def write_one(index: int) -> None:
        barrier.wait(timeout=5)
        store.set(f"asset-{index}", {"value": index})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(write_one, i) for i in range(workers)]
        for future in futures:
            future.result()

    for i in range(workers):
        assert store.get(f"asset-{i}") == {"value": i}


def test_multi_process_sets_preserve_every_asset(tmp_path):
    ctx = _fork_context()
    workers = 16
    path = tmp_path / "state.json"
    barrier = ctx.Barrier(workers)

    def write_one(index):
        store = JSONStore(path)
        barrier.wait(timeout=10)
        store.set(f"asset-{index}", {"value": index})

    processes = [
        ctx.Process(target=write_one, args=(i,))
        for i in range(workers)
    ]

    _run_processes(processes)

    store = JSONStore(path)
    for i in range(workers):
        assert store.get(f"asset-{i}") == {"value": i}


def test_crash_does_not_leave_stale_interprocess_lock(tmp_path):
    ctx = _fork_context()
    path = tmp_path / "state.json"

    def crash_while_locked():
        with _interprocess_lock(path):
            os._exit(23)

    def write_after_crash():
        JSONStore(path).set("after-crash", {"ok": True})

    crasher = ctx.Process(target=crash_while_locked)
    crasher.start()
    crasher.join(5)

    if crasher.is_alive():
        crasher.terminate()
        crasher.join()
        pytest.fail("crashing process did not exit")

    assert crasher.exitcode == 23

    follower = ctx.Process(target=write_after_crash)
    follower.start()
    follower.join(5)

    if follower.is_alive():
        follower.terminate()
        follower.join()
        pytest.fail("stale lock blocked the next writer")

    assert follower.exitcode == 0
    assert JSONStore(path).get("after-crash") == {"ok": True}


def test_brain_memory_multi_process_updates_are_not_lost(tmp_path):
    ctx = _fork_context()
    workers = 16
    path = tmp_path / "brain.json"
    barrier = ctx.Barrier(workers)

    def write_one(index):
        brain = BrainMemory(path)
        barrier.wait(timeout=10)
        brain.append_log({"worker": index})

    processes = [
        ctx.Process(target=write_one, args=(i,))
        for i in range(workers)
    ]

    _run_processes(processes)

    entries = BrainMemory(path).log()
    seen = {entry["worker"] for entry in entries}

    assert len(entries) == workers
    assert seen == set(range(workers))


def test_conversation_memory_multi_process_turns_are_not_lost(tmp_path):
    ctx = _fork_context()
    workers = 16
    path = tmp_path / "conversations.json"
    barrier = ctx.Barrier(workers)

    def write_one(index):
        memory = ConversationMemory(path)
        barrier.wait(timeout=10)
        memory.record_turn(
            input_line=f"input-{index}",
            response_summary=f"response-{index}",
        )

    processes = [
        ctx.Process(target=write_one, args=(i,))
        for i in range(workers)
    ]

    _run_processes(processes)

    entries = ConversationMemory(path).entries()
    seen = {
        int(entry.input_line.split("-")[1])
        for entry in entries
    }

    assert len(entries) == workers
    assert seen == set(range(workers))


def test_marketplace_catalog_multi_process_updates_are_not_lost(tmp_path):
    ctx = _fork_context()
    workers = 16
    path = tmp_path / "marketplace_catalog.json"
    barrier = ctx.Barrier(workers)

    def write_one(index):
        store = MarketplaceCatalogStore(path)
        record = MarketplaceProductRecord(
            product_name=f"Concurrent Product {index}",
            category="test",
            price=100.0 + index,
            commission_pct=50.0,
            vendor=f"vendor-{index}",
            cart_conversion_pct=None,
            secondary_rate_pct=None,
            observed_date_raw=None,
            net_earnings_per_sale=None,
            earnings_per_cart_visitor=None,
            source_url="https://example.com/test",
            observed_at=f"2026-08-26T08:00:{index:02d}",
            field_notes="concurrency regression test",
        )

        barrier.wait(timeout=10)
        store.save_records_with_identity([record])

    processes = [
        ctx.Process(target=write_one, args=(i,))
        for i in range(workers)
    ]

    _run_processes(processes)

    products = MarketplaceCatalogStore(path)._read()["products"]
    names = {
        product["product_name"]
        for product in products.values()
    }

    assert len(products) == workers
    assert names == {
        f"Concurrent Product {i}"
        for i in range(workers)
    }
