"""Routes `/health` et `/api/v1/*`. Couche d'adaptation HTTP fine : toute la logique métier vit
dans `palletizer.application.services` et `palletizer.imports.legacy_csv`."""

from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from palletizer import __version__
from palletizer.application.services import (
    ENGINE_VERSION,
    PalletizationService,
    TransportLoadingService,
)
from palletizer.contracts import (
    CapabilitiesResponse,
    HealthResponse,
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

router = APIRouter()
_palletization_service = PalletizationService()
_transport_service = TransportLoadingService()

PACKING_ADAPTER_NAME = "py3dbp"
PACKING_ADAPTER_VERSION = "1.1.2"


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
