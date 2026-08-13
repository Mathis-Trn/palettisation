"""Tests unitaires du gestionnaire de jobs, avec un `ThreadPoolExecutor` et des fonctions de
calcul factices (rapides, déterministes) plutôt que le vrai moteur — voir
`tests/integration/test_jobs_api.py` pour un test d'intégration de bout en bout via l'API réelle.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from palletizer.jobs.manager import JobManager
from palletizer.jobs.models import JobStatus
from palletizer.jobs.store import InMemoryJobStore
from tests.unit.helpers import ROUTIER_SPEC, make_line, make_options, make_order

ORDER = make_order([make_line(quantity=1)])
OPTIONS = make_options()


def _new_manager(
    run_fn, *, max_workers=2, timeout_seconds=5.0, retention_seconds=5.0, watch_interval=0.02
) -> JobManager:
    """Fabrique un `JobManager` de test. L'appelant est responsable de `manager.shutdown()`
    (généralement dans un `try/finally`)."""
    return JobManager(
        store=InMemoryJobStore(),
        executor=ThreadPoolExecutor(max_workers=max_workers),
        run_fn=run_fn,
        timeout_seconds=timeout_seconds,
        retention_seconds=retention_seconds,
        watch_interval_seconds=watch_interval,
    )


@pytest.fixture
def fast_success_manager():
    def run(order, pallet_spec, options, legacy, test_delay_seconds):
        return "RESULT"

    manager = _new_manager(run)
    yield manager
    manager.shutdown()


def _wait_for_status(
    manager: JobManager, job_id: str, statuses: set[JobStatus], timeout: float = 3.0
):
    deadline = time.monotonic() + timeout
    job = manager.get(job_id)
    while job is not None and job.status not in statuses and time.monotonic() < deadline:
        time.sleep(0.01)
        job = manager.get(job_id)
    return job


def test_create_then_transitions_to_succeeded(fast_success_manager) -> None:
    job = fast_success_manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-1")
    assert job.status == JobStatus.QUEUED

    final = _wait_for_status(fast_success_manager, job.job_id, {JobStatus.SUCCEEDED})
    assert final is not None
    assert final.status == JobStatus.SUCCEEDED
    assert final.result == "RESULT"
    assert final.started_at is not None
    assert final.finished_at is not None


def test_queued_to_running_to_succeeded_transition_observed() -> None:
    started = threading.Event()
    release = threading.Event()

    def run(order, pallet_spec, options, legacy, test_delay_seconds):
        started.set()
        release.wait(timeout=5)
        return "OK"

    manager = _new_manager(run, max_workers=1, watch_interval=0.02)
    try:
        job = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-2")
        assert job.status == JobStatus.QUEUED

        assert started.wait(timeout=2)
        running = _wait_for_status(manager, job.job_id, {JobStatus.RUNNING})
        assert running is not None
        assert running.status == JobStatus.RUNNING
        assert running.started_at is not None

        release.set()
        final = _wait_for_status(manager, job.job_id, {JobStatus.SUCCEEDED})
        assert final is not None and final.status == JobStatus.SUCCEEDED
    finally:
        release.set()
        manager.shutdown()


def test_failure_is_reported_as_structured_error_without_traceback() -> None:
    def run(order, pallet_spec, options, legacy, test_delay_seconds):
        raise ValueError("dimensions invalides")

    manager = _new_manager(run)
    try:
        job = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-3")
        final = _wait_for_status(manager, job.job_id, {JobStatus.FAILED})
        assert final is not None
        assert final.status == JobStatus.FAILED
        assert final.error is not None
        assert final.error.code == "ValueError"
        assert final.error.message == "dimensions invalides"
        assert "Traceback" not in final.error.message
    finally:
        manager.shutdown()


def test_job_expires_after_configured_timeout() -> None:
    def run(order, pallet_spec, options, legacy, test_delay_seconds):
        time.sleep(2.0)
        return "TOO_LATE"

    manager = _new_manager(run, timeout_seconds=0.15, watch_interval=0.02)
    try:
        job = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-4")
        final = _wait_for_status(manager, job.job_id, {JobStatus.EXPIRED}, timeout=3.0)
        assert final is not None
        assert final.status == JobStatus.EXPIRED
        assert final.error is not None
        assert final.error.code == "TIMEOUT"
    finally:
        manager.shutdown()


def test_retention_purges_finished_jobs_after_configured_delay() -> None:
    manager = _new_manager(lambda *a: "OK", retention_seconds=0.1, watch_interval=0.02)
    try:
        job = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-5")
        _wait_for_status(manager, job.job_id, {JobStatus.SUCCEEDED})

        deadline = time.monotonic() + 2.0
        while manager.get(job.job_id) is not None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert manager.get(job.job_id) is None
    finally:
        manager.shutdown()


def test_unknown_job_returns_none() -> None:
    manager = _new_manager(lambda *a: "OK")
    try:
        assert manager.get("does-not-exist") is None
        assert manager.cancel("does-not-exist") is None
    finally:
        manager.shutdown()


def test_identical_concurrent_submission_is_deduplicated() -> None:
    call_count = {"n": 0}
    gate = threading.Event()

    def run(order, pallet_spec, options, legacy, test_delay_seconds):
        call_count["n"] += 1
        gate.wait(timeout=5)
        return "OK"

    manager = _new_manager(run, max_workers=2)
    try:
        job1 = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "same-fingerprint")
        job2 = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "same-fingerprint")
        assert job1.job_id == job2.job_id
        gate.set()
        _wait_for_status(manager, job1.job_id, {JobStatus.SUCCEEDED})
        assert call_count["n"] == 1
    finally:
        gate.set()
        manager.shutdown()


def test_max_concurrent_jobs_limits_parallelism() -> None:
    gate = threading.Event()
    started = threading.Event()

    def blocking_run(order, pallet_spec, options, legacy, test_delay_seconds):
        started.set()
        gate.wait(timeout=5)
        return "A"

    def fast_run(order, pallet_spec, options, legacy, test_delay_seconds):
        return "B"

    call_log: list[str] = []

    def dispatcher(order, pallet_spec, options, legacy, test_delay_seconds):
        # La première soumission (fingerprint "blocking") bloque ; les suivantes sont rapides.
        if not call_log:
            call_log.append("blocking")
            return blocking_run(order, pallet_spec, options, legacy, test_delay_seconds)
        call_log.append("fast")
        return fast_run(order, pallet_spec, options, legacy, test_delay_seconds)

    manager = _new_manager(dispatcher, max_workers=1, watch_interval=0.02)
    try:
        job_a = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-blocking")
        assert started.wait(timeout=2)

        job_b = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-fast")
        time.sleep(0.1)
        still_queued = manager.get(job_b.job_id)
        assert still_queued is not None
        assert still_queued.status == JobStatus.QUEUED

        gate.set()
        final_a = _wait_for_status(manager, job_a.job_id, {JobStatus.SUCCEEDED})
        final_b = _wait_for_status(manager, job_b.job_id, {JobStatus.SUCCEEDED})
        assert final_a is not None and final_a.status == JobStatus.SUCCEEDED
        assert final_b is not None and final_b.status == JobStatus.SUCCEEDED
    finally:
        gate.set()
        manager.shutdown()


def test_cancel_while_queued_prevents_execution() -> None:
    gate = threading.Event()
    executed_fingerprints: list[str] = []

    def run(order, pallet_spec, options, legacy, test_delay_seconds):
        executed_fingerprints.append("ran")
        gate.wait(timeout=5)
        return "A"

    manager = _new_manager(run, max_workers=1, watch_interval=0.02)
    try:
        job_a = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-a")
        job_b = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-b")

        cancelled = manager.cancel(job_b.job_id)
        assert cancelled is not None
        assert cancelled.status == JobStatus.CANCELLED
        assert cancelled.error is None  # annulation garantie avant démarrage : pas d'ambiguïté

        gate.set()
        _wait_for_status(manager, job_a.job_id, {JobStatus.SUCCEEDED})
        time.sleep(0.1)
        assert "ran" not in executed_fingerprints or len(executed_fingerprints) == 1
    finally:
        gate.set()
        manager.shutdown()


def test_cancel_already_terminal_job_is_a_no_op() -> None:
    manager = _new_manager(lambda *a: "OK", watch_interval=0.02)
    try:
        job = manager.submit(ORDER, ROUTIER_SPEC, OPTIONS, None, "fp-terminal")
        _wait_for_status(manager, job.job_id, {JobStatus.SUCCEEDED})
        result = manager.cancel(job.job_id)
        assert result is not None
        assert result.status == JobStatus.SUCCEEDED
    finally:
        manager.shutdown()
