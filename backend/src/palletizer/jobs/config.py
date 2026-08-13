"""Configuration des jobs asynchrones, entièrement pilotée par variables d'environnement — voir
`backend/.env.example` et le README racine pour la description de chacune."""

from __future__ import annotations

import os

DEFAULT_JOB_TIMEOUT_SECONDS = 3600.0
DEFAULT_JOB_RETENTION_SECONDS = 3600.0
DEFAULT_MAX_CONCURRENT_JOBS = 1


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def job_timeout_seconds() -> float:
    """Durée maximale d'un calcul (`PALLETIZATION_JOB_TIMEOUT_SECONDS`, 3600s = 1h par défaut) :
    appliquée côté worker/job par `JobManager`, jamais comme un unique appel HTTP long."""
    return _env_float("PALLETIZATION_JOB_TIMEOUT_SECONDS", DEFAULT_JOB_TIMEOUT_SECONDS)


def job_retention_seconds() -> float:
    """Durée pendant laquelle un job terminé (et son résultat) reste consultable avant purge
    (`PALLETIZATION_JOB_RETENTION_SECONDS`, 3600s par défaut)."""
    return _env_float("PALLETIZATION_JOB_RETENTION_SECONDS", DEFAULT_JOB_RETENTION_SECONDS)


def max_concurrent_jobs() -> int:
    """Nombre de calculs exécutés en parallèle (`PALLETIZATION_MAX_CONCURRENT_JOBS`, 1 par
    défaut) — dimensionne le pool de workers du gestionnaire de jobs."""
    return _env_int("PALLETIZATION_MAX_CONCURRENT_JOBS", DEFAULT_MAX_CONCURRENT_JOBS)
