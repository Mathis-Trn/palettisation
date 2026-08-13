"""Fonction exécutée dans un processus worker séparé (`ProcessPoolExecutor`).

**Ce module ne doit importer ni FastAPI, ni `palletizer.api`, ni `palletizer.jobs.manager`.**
`multiprocessing` (mode *spawn*, utilisé par défaut sous Windows et macOS) réimporte le module
propriétaire de la fonction cible dans chaque processus enfant : si ce module importait FastAPI ou
recréait un gestionnaire de jobs, chaque worker recréerait inutilement une application HTTP
complète (lenteur au démarrage), voire, si le gestionnaire créait lui-même un `ProcessPoolExecutor`
au niveau module, provoquerait une récursion de création de pools. Ce module reste volontairement
minimal : uniquement le domaine et le service applicatif headless.
"""

from __future__ import annotations

import time

from palletizer.application.services import PalletizationService
from palletizer.domain.models import (
    LegacyExpectedResult,
    OptimizationOptions,
    OptimizationResult,
    Order,
    PalletSpec,
)


def run_optimize_job(
    order: Order,
    pallet_spec: PalletSpec,
    options: OptimizationOptions,
    legacy_expected_result: LegacyExpectedResult | None,
    test_delay_seconds: float = 0.0,
) -> OptimizationResult:
    """Exécute l'optimisation dans le processus worker. Doit rester une fonction de module de
    premier niveau (pas une closure/lambda/méthode liée) pour rester picklable par
    `multiprocessing` sous Windows (spawn).

    `test_delay_seconds` est un point d'extension **réservé aux tests** (scénario E2E « le calcul
    dure plus de 30 secondes », voir `frontend/tests/e2e`) : zéro par défaut, donc sans aucun effet
    en production. C'est un argument explicite de l'appel — pas une variable d'environnement lue
    dans le worker — précisément pour rester fiable même quand `ProcessPoolExecutor` réutilise un
    worker déjà démarré (l'argument est re-sérialisé à chaque soumission, contrairement à
    l'environnement du processus, figé au démarrage de ce worker).
    """
    if test_delay_seconds > 0:
        time.sleep(test_delay_seconds)
    service = PalletizationService()
    return service.optimize(order, pallet_spec, options, legacy_expected_result)
