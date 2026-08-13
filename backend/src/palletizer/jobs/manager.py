"""Gestionnaire de jobs de palettisation asynchrones.

Le calcul est CPU-bound (extreme-points + py3dbp) : il ne doit jamais s'exécuter dans la boucle
asyncio de FastAPI. Ce module reste indépendant de FastAPI, et le service applicatif ne dépend pas
de lui (voir `jobs/models.py`) — c'est ce gestionnaire qui appelle le service, jamais l'inverse.

Le pool d'exécution (`concurrent.futures.Executor`) est injecté plutôt que codé en dur : la
production utilise un `ProcessPoolExecutor` (vrai parallélisme, contourne le GIL) ; les tests
peuvent injecter un `ThreadPoolExecutor` (rapide, sans coût de démarrage de processus) sans changer
le comportement testé — seul le parallélisme réel diffère.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import CancelledError, Executor, Future
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from palletizer.domain.models import (
    LegacyExpectedResult,
    OptimizationOptions,
    OptimizationResult,
    Order,
    PalletSpec,
)
from palletizer.jobs.models import Job, JobError, JobStatus
from palletizer.jobs.store import JobStore

logger = logging.getLogger("palletizer.jobs")

RunFn = Callable[
    [Order, PalletSpec, OptimizationOptions, LegacyExpectedResult | None, float], OptimizationResult
]


class JobManager:
    """Orchestration : soumission, suivi (queued → running → terminal), expiration, rétention,
    annulation best-effort. Le stockage de l'état vit derrière `JobStore` (voir `store.py`) ;
    ce gestionnaire ne connaît que l'interface, jamais l'implémentation concrète.

    **Annulation** : `cancel()` interrompt réellement et de façon garantie un job encore
    `queued` (le `Future` n'a pas commencé, `Future.cancel()` réussit toujours dans ce cas). Un
    job déjà `running` ne peut pas être interrompu immédiatement de façon fiable avec
    `ProcessPoolExecutor` (aucune API stdlib ne permet de tuer un worker en cours de tâche sans
    invalider tout le pool) : il est marqué `cancelled` (son résultat sera ignoré une fois prêt),
    mais le calcul sous-jacent peut continuer jusqu'à son terme ou jusqu'au timeout. Documenté
    honnêtement plutôt que de prétendre un arrêt immédiat — voir le frontend, qui n'affiche le
    bouton d'annulation que pour un job encore `queued`.
    """

    def __init__(
        self,
        store: JobStore,
        executor: Executor,
        run_fn: RunFn,
        *,
        timeout_seconds: float,
        retention_seconds: float,
        watch_interval_seconds: float = 0.5,
    ) -> None:
        self._store = store
        self._executor = executor
        self._run_fn = run_fn
        self._timeout_seconds = timeout_seconds
        self._retention_seconds = retention_seconds
        self._watch_interval_seconds = watch_interval_seconds

        self._lock = threading.Lock()
        self._futures: dict[str, Future[OptimizationResult]] = {}

        self._stop_event = threading.Event()
        self._watcher = threading.Thread(target=self._watch_loop, daemon=True)
        self._watcher.start()

    # --- API publique -----------------------------------------------------------------------

    def submit(
        self,
        order: Order,
        pallet_spec: PalletSpec,
        options: OptimizationOptions,
        legacy_expected_result: LegacyExpectedResult | None,
        fingerprint: str,
        test_delay_seconds: float = 0.0,
    ) -> Job:
        """Crée un nouveau job, ou renvoie un job actif existant partageant la même empreinte
        (évite de lancer deux fois la même optimisation en parallèle). `test_delay_seconds` est
        réservé aux tests (voir `jobs/runner.py`) ; toujours 0 en production."""
        with self._lock:
            existing = self._store.find_active_by_fingerprint(fingerprint)
            if existing is not None:
                logger.info(
                    "job_deduplicated job_id=%s fingerprint=%s", existing.job_id, fingerprint
                )
                return existing

            job = Job(
                job_id=str(uuid.uuid4()),
                status=JobStatus.QUEUED,
                created_at=datetime.now(UTC),
                fingerprint=fingerprint,
            )
            self._store.create(job)
            future = self._executor.submit(
                self._run_fn,
                order,
                pallet_spec,
                options,
                legacy_expected_result,
                test_delay_seconds,
            )
            self._futures[job.job_id] = future
            logger.info("job_submitted job_id=%s", job.job_id)
            return job

    def get(self, job_id: str) -> Job | None:
        self._tick()
        return self._store.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
        job = self._store.get(job_id)
        if job is None:
            return None
        if job.is_terminal:
            return job

        with self._lock:
            future = self._futures.get(job_id)
        cancelled_before_start = future.cancel() if future is not None else True

        updated = replace(
            job,
            status=JobStatus.CANCELLED,
            finished_at=datetime.now(UTC),
            error=(
                None
                if cancelled_before_start
                else JobError(
                    code="CANCELLED_WHILE_RUNNING",
                    message=(
                        "Annulation demandée pendant l'exécution : le calcul sous-jacent a pu se "
                        "poursuivre jusqu'à son terme ou jusqu'au timeout, mais son résultat est "
                        "ignoré."
                    ),
                )
            ),
        )
        self._store.save(updated)
        logger.info(
            "job_cancelled job_id=%s cancelled_before_start=%s", job_id, cancelled_before_start
        )
        return updated

    def shutdown(self, *, wait: bool = False) -> None:
        self._stop_event.set()
        self._watcher.join(timeout=2.0)
        self._executor.shutdown(wait=wait, cancel_futures=True)

    # --- Boucle de surveillance ---------------------------------------------------------------

    def _tick(self) -> None:
        """Une itération de la boucle de surveillance, exposée pour permettre aux tests de
        forcer une vérification synchrone sans dépendre du minuteur du thread d'arrière-plan."""
        with self._lock:
            job_ids = list(self._futures.keys())

        now = datetime.now(UTC)
        for job_id in job_ids:
            with self._lock:
                future = self._futures.get(job_id)
            job = self._store.get(job_id)
            if future is None or job is None or job.is_terminal:
                continue

            if future.done():
                self._finalize(job_id, job, future)
            elif future.running() and job.status == JobStatus.QUEUED:
                self._store.save(replace(job, status=JobStatus.RUNNING, started_at=now))
            elif (
                job.status == JobStatus.RUNNING
                and job.started_at is not None
                and (now - job.started_at).total_seconds() > self._timeout_seconds
            ):
                self._expire(job_id, job, future)

        self._cleanup_retention()

    def _watch_loop(self) -> None:
        while not self._stop_event.wait(self._watch_interval_seconds):
            try:
                self._tick()
            except Exception:  # pragma: no cover - garde-fou : ne doit jamais tuer le thread
                logger.exception("job_watch_loop_error")

    def _finalize(self, job_id: str, job: Job, future: Future[OptimizationResult]) -> None:
        now = datetime.now(UTC)
        # Un job qui se termine si vite que le thread de surveillance ne l'a jamais observé
        # `running` n'a jamais eu `started_at` renseigné par `_tick` : on le complète ici, car un
        # job terminé a nécessairement démarré (approximé par l'instant de finalisation, l'écart
        # étant de toute façon sous la résolution du polling).
        started_at = job.started_at or now
        try:
            result = future.result()
        except CancelledError:
            updated = replace(
                job, status=JobStatus.CANCELLED, started_at=started_at, finished_at=now
            )
        except Exception as exc:  # noqa: BLE001 - erreur métier structurée, jamais de traceback exposée
            logger.warning("job_failed job_id=%s error=%s", job_id, exc)
            updated = replace(
                job,
                status=JobStatus.FAILED,
                started_at=started_at,
                finished_at=now,
                error=JobError(code=type(exc).__name__, message=str(exc)),
            )
        else:
            updated = replace(
                job,
                status=JobStatus.SUCCEEDED,
                started_at=started_at,
                finished_at=now,
                result=result,
            )
            logger.info("job_succeeded job_id=%s", job_id)
        self._store.save(updated)
        with self._lock:
            self._futures.pop(job_id, None)

    def _expire(self, job_id: str, job: Job, future: Future[OptimizationResult]) -> None:
        future.cancel()  # best-effort : sans effet si déjà en cours d'exécution
        updated = replace(
            job,
            status=JobStatus.EXPIRED,
            finished_at=datetime.now(UTC),
            error=JobError(
                code="TIMEOUT",
                message=f"Le calcul a dépassé le délai maximal de {self._timeout_seconds:.0f}s.",
            ),
        )
        self._store.save(updated)
        logger.warning("job_expired job_id=%s timeout_seconds=%s", job_id, self._timeout_seconds)

    def _cleanup_retention(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(seconds=self._retention_seconds)
        deleted = self._store.delete_finished_before(cutoff)
        if deleted:
            with self._lock:
                for job_id in deleted:
                    self._futures.pop(job_id, None)
            logger.info("jobs_purged_by_retention job_ids=%s", deleted)
