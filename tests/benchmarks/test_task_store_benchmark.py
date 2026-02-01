"""Benchmark for TaskStore operations (enqueue vs enqueue_batch)."""

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from egregora.database.duckdb_manager import temp_storage
from egregora.database.task_store import TaskStore

@pytest.fixture
def task_store():
    with temp_storage() as storage:
        store = TaskStore(storage)
        yield store

def test_benchmark_enqueue_sequential(task_store, benchmark):
    """Benchmark sequential enqueueing of tasks."""
    num_tasks = 1000
    payload = {"url": "https://example.com/some/path", "meta": "data"}

    def run_sequential():
        for i in range(num_tasks):
            task_store.enqueue(f"task_{i}", payload)

    benchmark(run_sequential)

def test_benchmark_enqueue_batch(task_store, benchmark):
    """Benchmark real batch enqueueing."""
    num_tasks = 1000
    payload = {"url": "https://example.com/some/path", "meta": "data"}

    # Pre-generate task tuples to match enqueue_batch signature
    tasks = []
    for i in range(num_tasks):
        tasks.append((f"task_{i}", payload))

    def run_batch():
        task_store.enqueue_batch(tasks)

    benchmark(run_batch)
