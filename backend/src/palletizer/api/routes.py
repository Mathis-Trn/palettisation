"""Routes `/health` et `/api/v1/*`. Couche d'adaptation HTTP fine : toute la logique métier vit
dans `palletizer.application.services` et `palletizer.imports.legacy_csv`."""

from __future__ import annotations

import hashlib
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile

from palletizer import __version__
from palletizer.application.services import (
    ENGINE_VERSION,
    PalletizationService,
    TransportLoadingService,
)
from palletizer.contracts import (
    CapabilitiesResponse,
    HealthResponse,
    JobCreatedResponse,
    JobStatusResponse,
    PalletizeRequest,
    PalletizeResponse,
    ParseCsvResponse,
    TransportLoadRequest,
    TransportLoadResponse,
)
from palletizer.domain.enums import OptimizationLevel
from palletizer.domain.errors import CsvLimitExceededError
from palletizer.domain.models import OptimizationOptions, Order
from palletizer.imports.legacy_csv import MAX_CSV_BYTES, MAX_CSV_ROWS, parse_legacy_csv
from palletizer.jobs import config as jobs_config
from palletizer.jobs.manager import JobManager
from palletizer.jobs.models import JobStatus
from palletizer.jobs.runner import run_optimize_job
from palletizer.jobs.store import InMemoryJobStore

router = APIRouter()
_palletization_service = PalletizationService()
_transport_service = TransportLoadingService()

PACKING_ADAPTER_NAME = "py3dbp"
PACKING_ADAPTER_VERSION = "1.1.2"

# Instancié une seule fois par processus serveur, au chargement du module (donc dans le processus
# MAIN uniquement — les workers du ProcessPoolExecutor n'importent que `jobs.runner`, jamais ce
# module, voir la docstring de `jobs/runner.py`). `InMemoryJobStore` ne convient qu'à une seule
# instance backend (voir `jobs/store.py`) ; remplacer par une implémentation Redis pour un
# déploiement multi-instance ne change rien ici au-delà du constructeur.
_job_manager = JobManager(
    store=InMemoryJobStore(),
    executor=ProcessPoolExecutor(max_workers=jobs_config.max_concurrent_jobs()),
    run_fn=run_optimize_job,
    timeout_seconds=jobs_config.job_timeout_seconds(),
    retention_seconds=jobs_config.job_retention_seconds(),
)


def _fingerprint_request(request: PalletizeRequest) -> str:
    """Empreinte déterministe d'une requête normalisée, utilisée pour détecter et fusionner des
    soumissions concurrentes strictement identiques plutôt que de lancer deux fois le même calcul.
    """
    canonical = request.model_dump_json(by_alias=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _test_delay_seconds(header_value: str | None) -> float:
    """Point d'extension **réservé aux tests E2E** (scénario « le calcul dure plus de 30
    secondes », voir `frontend/tests/e2e`) : totalement inerte tant que le serveur n'a pas été
    démarré avec `PALLETIZER_ENABLE_TEST_HOOKS=1` (jamais activé en production ni dans
    `docker-compose.yml`), même si un client envoie l'en-tête. Cela garantit qu'aucune requête
    externe ne peut artificiellement ralentir un déploiement réel."""
    if os.environ.get("PALLETIZER_ENABLE_TEST_HOOKS") != "1" or not header_value:
        return 0.0
    try:
        return max(0.0, float(header_value))
    except ValueError:
        return 0.0


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(version=__version__, engineVersion=ENGINE_VERSION)


@router.get("/api/v1/capabilities")
def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        supportedPalletFormats=("P:{longueur_cm}x{largeur_cm}x{hauteur_cm}",),
        constraints=(
            "allowRotation",
            "uprightOnly",
            "fragile",
            "stackable",
            "maxSupportedWeightKg",
            "incompatibleGroups",
            "safetyGapMm",
            "overhangMm",
            "minimumSupportRatio",
            "maxWeightKg",
        ),
        limits={
            "maxCsvBytes": MAX_CSV_BYTES,
            "maxCsvRows": MAX_CSV_ROWS,
            "practicalInstanceLimit": 500,
        },
        packingAdapter={"name": PACKING_ADAPTER_NAME, "version": PACKING_ADAPTER_VERSION},
    )


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=413, detail=f"Fichier trop volumineux (max {MAX_CSV_BYTES} octets)."
        )
    return content


@router.post("/api/v1/orders/parse-csv")
async def parse_csv(file: UploadFile = File(...)) -> ParseCsvResponse:
    content = await _read_upload(file)
    try:
        preview = parse_legacy_csv(content)
    except CsvLimitExceededError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return ParseCsvResponse.from_domain(preview)


@router.post("/api/v1/palletize")
def palletize(request: PalletizeRequest) -> PalletizeResponse:
    order = request.order.to_domain()
    pallet_spec = request.pallet.to_domain(request.options.minimum_support_ratio)
    options = request.options.to_domain()
    result = _palletization_service.optimize(order, pallet_spec, options)
    return PalletizeResponse.from_domain(result)


@router.post("/api/v1/palletize/csv")
async def palletize_csv(
    file: UploadFile = File(...),
    order_id: str | None = Form(default=None, alias="orderId"),
    optimization_level: str | None = Form(default=None, alias="optimizationLevel"),
    minimum_support_ratio: float = Form(default=0.8, alias="minimumSupportRatio"),
) -> PalletizeResponse:
    content = await _read_upload(file)
    try:
        preview = parse_legacy_csv(content)
    except CsvLimitExceededError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    if not preview.orders:
        raise HTTPException(status_code=400, detail="Aucune commande valide détectée dans le CSV.")

    if order_id is None:
        if len(preview.orders) > 1:
            available = ", ".join(o.order_id for o in preview.orders)
            raise HTTPException(
                status_code=400,
                detail=f"Plusieurs commandes détectées ({available}) : précisez orderId.",
            )
        selected = preview.orders[0]
    else:
        matches = [o for o in preview.orders if o.order_id == order_id]
        if not matches:
            raise HTTPException(
                status_code=404, detail=f"Commande {order_id!r} introuvable dans le CSV."
            )
        selected = matches[0]

    order = Order(
        order_id=selected.order_id, shipping_mode=selected.shipping_mode, lines=selected.lines
    )
    level = OptimizationLevel(optimization_level) if optimization_level else OptimizationLevel.FAST
    options = OptimizationOptions(optimization_level=level)
    pallet_spec = replace(selected.pallet_spec, minimum_support_ratio=minimum_support_ratio)
    result = _palletization_service.optimize(
        order, pallet_spec, options, legacy_expected_result=selected.legacy_expected_result
    )
    return PalletizeResponse.from_domain(result)


@router.post("/api/v1/transport/load")
def transport_load(request: TransportLoadRequest) -> TransportLoadResponse:
    pallets = [p.to_domain() for p in request.pallets]
    vehicle = request.vehicle.to_domain()
    result = _transport_service.compute(pallets, vehicle)
    return TransportLoadResponse.from_domain(result)


@router.post("/api/v1/palletization-jobs", status_code=202)
def create_palletization_job(
    request: PalletizeRequest,
    response: Response,
    x_test_delay_seconds: str | None = Header(
        default=None, alias="X-Palletizer-Test-Delay-Seconds"
    ),
) -> JobCreatedResponse:
    """Démarre un calcul hors du cycle de requête HTTP (voir `jobs/manager.py`) : ce calcul étant
    CPU-bound et pouvant durer jusqu'à `PALLETIZATION_JOB_TIMEOUT_SECONDS`, il ne s'exécute jamais
    dans la boucle asyncio de FastAPI ni dans le cycle de vie de cette requête, qui répond
    immédiatement avec le statut initial du job."""
    order = request.order.to_domain()
    pallet_spec = request.pallet.to_domain(request.options.minimum_support_ratio)
    options = request.options.to_domain()
    fingerprint = _fingerprint_request(request)
    delay = _test_delay_seconds(x_test_delay_seconds)

    job = _job_manager.submit(order, pallet_spec, options, None, fingerprint, delay)
    if job.status != JobStatus.QUEUED:
        # Un job actif identique existait déjà : on renvoie son état réel (pas nécessairement
        # "queued") plutôt que de mentir sur le statut de création.
        response.status_code = 200
    return JobCreatedResponse(
        jobId=job.job_id, status=job.status, createdAt=job.created_at.isoformat()
    )


@router.get("/api/v1/palletization-jobs/{job_id}")
def get_palletization_job(job_id: str) -> JobStatusResponse:
    job = _job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} introuvable.")
    return JobStatusResponse.from_domain(job)


@router.delete("/api/v1/palletization-jobs/{job_id}")
def cancel_palletization_job(job_id: str) -> JobStatusResponse:
    job = _job_manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} introuvable.")
    return JobStatusResponse.from_domain(job)
