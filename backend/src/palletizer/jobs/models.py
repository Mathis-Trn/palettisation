"""Modèle de domaine des jobs de palettisation asynchrones.

Ce module ne dépend ni de FastAPI, ni du gestionnaire de jobs (`manager.py`) : il ne fait que
décrire l'état d'un job de façon simple et sérialisable, pour permettre de remplacer le stockage
en mémoire (`store.py::InMemoryJobStore`) par une implémentation Redis plus tard sans changer ce
fichier ni le service applicatif (`palletizer.application.services`), qui n'importe jamais ce
paquet — c'est le gestionnaire de jobs qui dépend du service applicatif, jamais l'inverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from palletizer.domain.models import OptimizationResult


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


TERMINAL_STATUSES = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.EXPIRED}
)


@dataclass(frozen=True, slots=True)
class JobError:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class Job:
    """Snapshot immuable de l'état d'un job à un instant donné. Toute transition d'état crée un
    nouveau `Job` (via `dataclasses.replace`) plutôt que de muter l'existant, pour rester
    trivialement sérialisable (Redis, etc.) sans piéger d'objets non-picklables (futures...)."""

    job_id: str
    status: JobStatus
    created_at: datetime
    fingerprint: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: OptimizationResult | None = None
    error: JobError | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES
