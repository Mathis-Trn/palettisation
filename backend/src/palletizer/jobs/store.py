"""Interface de stockage des jobs (`JobStore`) et implémentation en mémoire.

`InMemoryJobStore` ne convient qu'à **une seule instance backend** : les jobs vivent dans la
mémoire du processus Python et disparaissent au redémarrage, et ne sont pas partagés entre
plusieurs réplicas d'un déploiement multi-instance. Pour un déploiement distribué, remplacer par
une implémentation Redis (ou équivalent) respectant le protocole `JobStore` ci-dessous — aucun
autre code (gestionnaire de jobs, routes API) n'a besoin de changer.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Protocol

from palletizer.jobs.models import Job


class JobStore(Protocol):
    """Interface de persistance des jobs, indépendante de l'implémentation concrète."""

    def create(self, job: Job) -> None:
        """Enregistre un nouveau job. `job.job_id` doit être unique."""
        ...

    def get(self, job_id: str) -> Job | None: ...

    def save(self, job: Job) -> None:
        """Remplace l'état complet d'un job existant (transition d'état)."""
        ...

    def find_active_by_fingerprint(self, fingerprint: str) -> Job | None:
        """Renvoie un job non terminal (queued/running) partageant la même empreinte de requête,
        pour éviter de lancer deux fois la même optimisation en parallèle."""
        ...

    def all_ids(self) -> list[str]: ...

    def delete(self, job_id: str) -> None: ...

    def delete_finished_before(self, cutoff: datetime) -> list[str]:
        """Purge les jobs terminaux dont `finished_at` précède `cutoff` (politique de rétention).
        Retourne les identifiants supprimés. Une implémentation Redis peut préférer une expiration
        native (TTL sur la clé) plutôt qu'un scan explicite — l'appelant ne dépend que du contrat
        « renvoie les ids supprimés », pas du mécanisme."""
        ...


class InMemoryJobStore:
    """Implémentation en mémoire du processus, protégée par un verrou pour un accès concurrent
    sûr depuis le thread de surveillance du gestionnaire de jobs et les requêtes HTTP.

    **Limite documentée** : ne convient qu'à une seule instance backend (voir docstring du
    module). Ne persiste rien sur disque ; un redémarrage du processus perd tous les jobs en cours.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def save(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def find_active_by_fingerprint(self, fingerprint: str) -> Job | None:
        with self._lock:
            for job in self._jobs.values():
                if job.fingerprint == fingerprint and not job.is_terminal:
                    return job
            return None

    def all_ids(self) -> list[str]:
        with self._lock:
            return list(self._jobs.keys())

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def delete_finished_before(self, cutoff: datetime) -> list[str]:
        """Purge les jobs terminaux dont `finished_at` précède `cutoff` (politique de rétention).
        Retourne les identifiants supprimés, pour journalisation par l'appelant."""
        with self._lock:
            to_delete = [
                job_id
                for job_id, job in self._jobs.items()
                if job.is_terminal and job.finished_at is not None and job.finished_at < cutoff
            ]
            for job_id in to_delete:
                del self._jobs[job_id]
            return to_delete
