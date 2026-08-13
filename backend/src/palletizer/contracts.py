"""Contrat JSON normalisé, versionné (`contractVersion`), indépendant du CSV historique.

N'importe jamais FastAPI : ce module est utilisable par l'API, la CLI, ou tout autre client Python,
et reste une simple couche de validation/sérialisation (Pydantic) autour du domaine pur
(`palletizer.domain`).
"""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from palletizer.domain.enums import OptimizationLevel, OrientationCode, RejectionCode, ShippingMode
from palletizer.domain.models import (
    CsvImportPreview,
    Dimensions3D,
    OptimizationOptions,
    OptimizationResult,
    Order,
    OrderLine,
    PalletSpec,
    PalletToLoad,
    Position3D,
    TransportLoadResult,
    VehicleConfig,
)
from palletizer.jobs.models import Job, JobError, JobStatus

CONTRACT_VERSION = "1.0"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --- Requête /palletize --------------------------------------------------------------------


class DimensionsMmContract(_StrictModel):
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)

    def to_domain(self) -> Dimensions3D:
        return Dimensions3D(length_mm=self.length, width_mm=self.width, height_mm=self.height)


class OrderLineContract(_StrictModel):
    line_number: int = Field(alias="lineNumber", ge=1)
    sku: str = Field(min_length=1)
    description: str = ""
    quantity: int = Field(gt=0)
    unit: str = "PIECE"
    dimensions_mm: DimensionsMmContract = Field(alias="dimensionsMm")
    weight_kg: float | None = Field(default=None, alias="weightKg", ge=0)
    allow_rotation: bool = Field(default=True, alias="allowRotation")
    upright_only: bool = Field(default=False, alias="uprightOnly")
    fragile: bool = False
    stackable: bool = True
    max_supported_weight_kg: float | None = Field(default=None, alias="maxSupportedWeightKg", ge=0)
    product_group: str | None = Field(default=None, alias="productGroup")
    incompatible_groups: tuple[str, ...] = Field(default=(), alias="incompatibleGroups")

    def to_domain(self) -> OrderLine:
        return OrderLine(
            line_number=self.line_number,
            sku=self.sku,
            description=self.description,
            quantity=self.quantity,
            unit=self.unit,
            dimensions_mm=self.dimensions_mm.to_domain(),
            weight_kg=self.weight_kg,
            allow_rotation=self.allow_rotation,
            upright_only=self.upright_only,
            fragile=self.fragile,
            stackable=self.stackable,
            max_supported_weight_kg=self.max_supported_weight_kg,
            product_group=self.product_group,
            incompatible_groups=self.incompatible_groups,
        )


class OrderContract(_StrictModel):
    order_id: str = Field(alias="orderId", min_length=1)
    shipping_mode: ShippingMode = Field(alias="shippingMode")
    lines: tuple[OrderLineContract, ...]

    def to_domain(self) -> Order:
        return Order(
            order_id=self.order_id,
            shipping_mode=self.shipping_mode,
            lines=tuple(line.to_domain() for line in self.lines),
        )


class PalletContract(_StrictModel):
    code: str = ""
    length_mm: float = Field(alias="lengthMm", gt=0)
    width_mm: float = Field(alias="widthMm", gt=0)
    max_height_mm: float = Field(alias="maxHeightMm", gt=0)
    empty_pallet_height_mm: float = Field(default=144.0, alias="emptyPalletHeightMm", ge=0)
    max_height_includes_pallet: bool = Field(default=True, alias="maxHeightIncludesPallet")
    max_weight_kg: float | None = Field(default=None, alias="maxWeightKg", ge=0)
    overhang_mm: float = Field(default=0.0, alias="overhangMm", ge=0)
    safety_gap_mm: float = Field(default=0.0, alias="safetyGapMm", ge=0)

    def to_domain(self, minimum_support_ratio: float) -> PalletSpec:
        return PalletSpec(
            code=self.code,
            length_mm=self.length_mm,
            width_mm=self.width_mm,
            max_height_mm=self.max_height_mm,
            empty_pallet_height_mm=self.empty_pallet_height_mm,
            max_height_includes_pallet=self.max_height_includes_pallet,
            max_weight_kg=self.max_weight_kg,
            overhang_mm=self.overhang_mm,
            safety_gap_mm=self.safety_gap_mm,
            minimum_support_ratio=minimum_support_ratio,
        )


class OptionsContract(_StrictModel):
    optimization_level: OptimizationLevel = Field(
        default=OptimizationLevel.FAST, alias="optimizationLevel"
    )
    minimum_support_ratio: float = Field(default=0.8, alias="minimumSupportRatio", ge=0, le=1)
    global_rotations_enabled: bool = Field(default=True, alias="globalRotationsEnabled")
    fragile_max_weight_on_top_kg: float = Field(default=0.0, alias="fragileMaxWeightOnTopKg", ge=0)

    def to_domain(self) -> OptimizationOptions:
        return OptimizationOptions(
            global_rotations_enabled=self.global_rotations_enabled,
            optimization_level=self.optimization_level,
            fragile_max_weight_on_top_kg=self.fragile_max_weight_on_top_kg,
        )


class PalletizeRequest(_StrictModel):
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    order: OrderContract
    pallet: PalletContract
    options: OptionsContract = OptionsContract()


# --- Réponse /palletize -----------------------------------------------------------------------


class Position3DContract(_StrictModel):
    x: float
    y: float
    z: float

    @classmethod
    def from_domain(cls, position: Position3D) -> Position3DContract:
        return cls(x=position.x_mm, y=position.y_mm, z=position.z_mm)


class DimensionsContract(_StrictModel):
    length: float
    width: float
    height: float

    @classmethod
    def from_domain(cls, dims: Dimensions3D) -> DimensionsContract:
        return cls(length=dims.length_mm, width=dims.width_mm, height=dims.height_mm)


class PlacedCartonContract(_StrictModel):
    instance_id: str = Field(alias="instanceId")
    sku: str
    original_dimensions_mm: DimensionsContract = Field(alias="originalDimensionsMm")
    placed_dimensions_mm: DimensionsContract = Field(alias="placedDimensionsMm")
    position_mm: Position3DContract = Field(alias="positionMm")
    orientation: OrientationCode
    pallet_index: int = Field(alias="palletIndex")
    placement_score: float = Field(alias="placementScore")
    weight_kg: float | None = Field(default=None, alias="weightKg")
    fragile: bool
    stackable: bool
    product_group: str | None = Field(default=None, alias="productGroup")


class UnplacedCartonContract(_StrictModel):
    instance_id: str = Field(alias="instanceId")
    sku: str
    dimensions_mm: DimensionsContract = Field(alias="dimensionsMm")
    code: RejectionCode
    message: str
    weight_kg: float | None = Field(default=None, alias="weightKg")


class PalletConfigContract(_StrictModel):
    """Miroir de l'objet `pallet` de la requête, renvoyé avec chaque palette du résultat pour que
    le rendu 3D dispose de toutes les dimensions/contraintes sans requête supplémentaire."""

    code: str
    length_mm: float = Field(alias="lengthMm")
    width_mm: float = Field(alias="widthMm")
    max_height_mm: float = Field(alias="maxHeightMm")
    empty_pallet_height_mm: float = Field(alias="emptyPalletHeightMm")
    max_height_includes_pallet: bool = Field(alias="maxHeightIncludesPallet")
    max_weight_kg: float | None = Field(default=None, alias="maxWeightKg")
    overhang_mm: float = Field(alias="overhangMm")
    safety_gap_mm: float = Field(alias="safetyGapMm")
    minimum_support_ratio: float = Field(alias="minimumSupportRatio")


class PalletResultContract(_StrictModel):
    index: int
    config: PalletConfigContract
    total_weight_kg: float = Field(alias="totalWeightKg")
    usable_volume_mm3: float = Field(alias="usableVolumeMm3")
    volume_used_mm3: float = Field(alias="volumeUsedMm3")
    volume_usage_ratio: float = Field(alias="volumeUsageRatio")
    footprint_usage_ratio: float = Field(alias="footprintUsageRatio")
    max_height_used_mm: float = Field(alias="maxHeightUsedMm")
    placed_cartons: tuple[PlacedCartonContract, ...] = Field(alias="placedCartons")


class LegacyExpectedResultContract(_StrictModel):
    pallet_count: int | None = Field(alias="palletCount")


class PalletizeResponse(_StrictModel):
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    order_id: str = Field(alias="orderId")
    engine_version: str = Field(alias="engineVersion")
    duration_ms: float = Field(alias="durationMs")
    warnings: tuple[str, ...]
    total_cartons_count: int = Field(alias="totalCartonsCount")
    placed_cartons_count: int = Field(alias="placedCartonsCount")
    unplaced_cartons_count: int = Field(alias="unplacedCartonsCount")
    pallets_count: int = Field(alias="palletsCount")
    global_volume_usage_ratio: float = Field(alias="globalVolumeUsageRatio")
    total_weight_kg: float = Field(alias="totalWeightKg")
    pallets: tuple[PalletResultContract, ...]
    unplaced_cartons: tuple[UnplacedCartonContract, ...] = Field(alias="unplacedCartons")
    legacy_expected_result: LegacyExpectedResultContract | None = Field(
        default=None, alias="legacyExpectedResult"
    )

    @classmethod
    def from_domain(cls, result: OptimizationResult) -> PalletizeResponse:
        return cls(
            orderId=result.order_id,
            engineVersion=result.engine_version,
            durationMs=result.duration_ms,
            warnings=result.warnings,
            totalCartonsCount=result.total_cartons_count,
            placedCartonsCount=result.placed_cartons_count,
            unplacedCartonsCount=result.unplaced_cartons_count,
            palletsCount=result.pallets_count,
            globalVolumeUsageRatio=result.global_volume_usage_ratio,
            totalWeightKg=result.total_weight_kg,
            pallets=tuple(
                PalletResultContract(
                    index=pallet.index,
                    config=PalletConfigContract(
                        code=pallet.spec.code,
                        lengthMm=pallet.spec.length_mm,
                        widthMm=pallet.spec.width_mm,
                        maxHeightMm=pallet.spec.max_height_mm,
                        emptyPalletHeightMm=pallet.spec.empty_pallet_height_mm,
                        maxHeightIncludesPallet=pallet.spec.max_height_includes_pallet,
                        maxWeightKg=pallet.spec.max_weight_kg,
                        overhangMm=pallet.spec.overhang_mm,
                        safetyGapMm=pallet.spec.safety_gap_mm,
                        minimumSupportRatio=pallet.spec.minimum_support_ratio,
                    ),
                    totalWeightKg=pallet.total_weight_kg,
                    usableVolumeMm3=pallet.usable_volume_mm3,
                    volumeUsedMm3=pallet.volume_used_mm3,
                    volumeUsageRatio=pallet.volume_usage_ratio,
                    footprintUsageRatio=pallet.footprint_usage_ratio,
                    maxHeightUsedMm=pallet.max_height_used_mm,
                    placedCartons=tuple(
                        PlacedCartonContract(
                            instanceId=box.instance_id,
                            sku=box.sku,
                            originalDimensionsMm=DimensionsContract.from_domain(
                                box.original_dimensions_mm
                            ),
                            placedDimensionsMm=DimensionsContract.from_domain(
                                box.placed_dimensions_mm
                            ),
                            positionMm=Position3DContract.from_domain(box.position_mm),
                            orientation=box.orientation,
                            palletIndex=box.pallet_index,
                            placementScore=box.placement_score,
                            weightKg=box.weight_kg,
                            fragile=box.fragile,
                            stackable=box.stackable,
                            productGroup=box.product_group,
                        )
                        for box in pallet.placed_cartons
                    ),
                )
                for pallet in result.pallets
            ),
            unplacedCartons=tuple(
                UnplacedCartonContract(
                    instanceId=item.instance_id,
                    sku=item.sku,
                    dimensionsMm=DimensionsContract.from_domain(item.dimensions_mm),
                    code=item.code,
                    message=item.message,
                    weightKg=item.weight_kg,
                )
                for item in result.unplaced_cartons
            ),
            legacyExpectedResult=(
                LegacyExpectedResultContract(palletCount=result.legacy_expected_result.pallet_count)
                if result.legacy_expected_result is not None
                else None
            ),
        )


# --- Chargement transport ----------------------------------------------------------------------


class VehicleContract(_StrictModel):
    name: str = "vehicule"
    inner_length_mm: float = Field(alias="innerLengthMm", gt=0)
    inner_width_mm: float = Field(alias="innerWidthMm", gt=0)
    inner_height_mm: float = Field(alias="innerHeightMm", gt=0)
    max_payload_kg: float = Field(alias="maxPayloadKg", gt=0)
    allow_pallet_rotation_floor: bool = Field(default=True, alias="allowPalletRotationFloor")
    allow_pallet_stacking: bool = Field(default=False, alias="allowPalletStacking")

    def to_domain(self) -> VehicleConfig:
        return VehicleConfig(
            name=self.name,
            inner_length_mm=self.inner_length_mm,
            inner_width_mm=self.inner_width_mm,
            inner_height_mm=self.inner_height_mm,
            max_payload_kg=self.max_payload_kg,
            allow_pallet_rotation_floor=self.allow_pallet_rotation_floor,
            allow_pallet_stacking=self.allow_pallet_stacking,
        )


class PalletToLoadContract(_StrictModel):
    pallet_result_index: int = Field(alias="palletResultIndex", ge=0)
    footprint_length_mm: float = Field(alias="footprintLengthMm", gt=0)
    footprint_width_mm: float = Field(alias="footprintWidthMm", gt=0)
    height_mm: float = Field(alias="heightMm", gt=0)
    weight_kg: float = Field(alias="weightKg", ge=0)

    def to_domain(self) -> PalletToLoad:
        return PalletToLoad(
            pallet_result_index=self.pallet_result_index,
            footprint_length_mm=self.footprint_length_mm,
            footprint_width_mm=self.footprint_width_mm,
            height_mm=self.height_mm,
            weight_kg=self.weight_kg,
        )


class TransportLoadRequest(_StrictModel):
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    pallets: tuple[PalletToLoadContract, ...]
    vehicle: VehicleContract


class LoadedPalletPlacementContract(_StrictModel):
    pallet_result_index: int = Field(alias="palletResultIndex")
    vehicle_index: int = Field(alias="vehicleIndex")
    x: float
    y: float
    rotated: bool
    stack_level: int = Field(alias="stackLevel")
    length_mm: float = Field(alias="lengthMm")
    width_mm: float = Field(alias="widthMm")
    height_mm: float = Field(alias="heightMm")
    weight_kg: float = Field(alias="weightKg")


class VehicleLoadResultContract(_StrictModel):
    index: int
    placements: tuple[LoadedPalletPlacementContract, ...]
    used_floor_area_ratio: float = Field(alias="usedFloorAreaRatio")
    used_weight_kg: float = Field(alias="usedWeightKg")


class TransportLoadResponse(_StrictModel):
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    vehicles: tuple[VehicleLoadResultContract, ...]
    unassigned_pallet_indexes: tuple[int, ...] = Field(alias="unassignedPalletIndexes")
    vehicles_needed: int = Field(alias="vehiclesNeeded")
    pallets_loadable: int = Field(alias="palletsLoadable")

    @classmethod
    def from_domain(cls, result: TransportLoadResult) -> TransportLoadResponse:
        return cls(
            vehicles=tuple(
                VehicleLoadResultContract(
                    index=vehicle.index,
                    placements=tuple(
                        LoadedPalletPlacementContract(
                            palletResultIndex=p.pallet_result_index,
                            vehicleIndex=p.vehicle_index,
                            x=p.x_mm,
                            y=p.y_mm,
                            rotated=p.rotated,
                            stackLevel=p.stack_level,
                            lengthMm=p.length_mm,
                            widthMm=p.width_mm,
                            heightMm=p.height_mm,
                            weightKg=p.weight_kg,
                        )
                        for p in vehicle.placements
                    ),
                    usedFloorAreaRatio=vehicle.used_floor_area_ratio,
                    usedWeightKg=vehicle.used_weight_kg,
                )
                for vehicle in result.vehicles
            ),
            unassignedPalletIndexes=result.unassigned_pallet_indexes,
            vehiclesNeeded=result.vehicles_needed,
            palletsLoadable=result.pallets_loadable,
        )


# --- Import CSV : /orders/parse-csv --------------------------------------------------------------


class CsvImportErrorContract(_StrictModel):
    line_number: int | None = Field(alias="lineNumber")
    column: str | None = None
    code: str
    message: str
    raw_fragments: tuple[str, ...] = Field(default=(), alias="rawFragments")


class CsvImportWarningContract(_StrictModel):
    line_number: int | None = Field(alias="lineNumber")
    message: str


class ParsedCsvOrderContract(_StrictModel):
    order_id: str = Field(alias="orderId")
    shipping_mode: ShippingMode = Field(alias="shippingMode")
    pallet: PalletContract
    lines: tuple[OrderLineContract, ...]
    legacy_pallet_count: int | None = Field(default=None, alias="legacyPalletCount")


class CsvImportStatsContract(_StrictModel):
    orders_count: int = Field(alias="ordersCount")
    pallet_formats: tuple[str, ...] = Field(alias="palletFormats")
    shipping_modes: tuple[str, ...] = Field(alias="shippingModes")


class ParseCsvResponse(_StrictModel):
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    orders: tuple[ParsedCsvOrderContract, ...]
    errors: tuple[CsvImportErrorContract, ...]
    warnings: tuple[CsvImportWarningContract, ...]
    total_rows: int = Field(alias="totalRows")
    accepted_rows: int = Field(alias="acceptedRows")
    rejected_rows: int = Field(alias="rejectedRows")
    stats: CsvImportStatsContract

    @classmethod
    def from_domain(cls, preview: CsvImportPreview) -> ParseCsvResponse:
        return cls(
            orders=tuple(
                ParsedCsvOrderContract(
                    orderId=order.order_id,
                    shippingMode=order.shipping_mode,
                    pallet=PalletContract(
                        code=order.pallet_spec.code,
                        lengthMm=order.pallet_spec.length_mm,
                        widthMm=order.pallet_spec.width_mm,
                        maxHeightMm=order.pallet_spec.max_height_mm,
                        emptyPalletHeightMm=order.pallet_spec.empty_pallet_height_mm,
                        maxHeightIncludesPallet=order.pallet_spec.max_height_includes_pallet,
                        maxWeightKg=order.pallet_spec.max_weight_kg,
                        overhangMm=order.pallet_spec.overhang_mm,
                        safetyGapMm=order.pallet_spec.safety_gap_mm,
                    ),
                    lines=tuple(
                        OrderLineContract(
                            lineNumber=line.line_number,
                            sku=line.sku,
                            description=line.description,
                            quantity=line.quantity,
                            unit=line.unit,
                            dimensionsMm=DimensionsMmContract(
                                length=line.dimensions_mm.length_mm,
                                width=line.dimensions_mm.width_mm,
                                height=line.dimensions_mm.height_mm,
                            ),
                            weightKg=line.weight_kg,
                            allowRotation=line.allow_rotation,
                            uprightOnly=line.upright_only,
                            fragile=line.fragile,
                            stackable=line.stackable,
                        )
                        for line in order.lines
                    ),
                    legacyPalletCount=order.legacy_expected_result.pallet_count,
                )
                for order in preview.orders
            ),
            errors=tuple(
                CsvImportErrorContract(
                    lineNumber=err.line_number,
                    column=err.column,
                    code=err.code,
                    message=err.message,
                    rawFragments=err.raw_fragments,
                )
                for err in preview.errors
            ),
            warnings=tuple(
                CsvImportWarningContract(lineNumber=w.line_number, message=w.message)
                for w in preview.warnings
            ),
            totalRows=preview.total_rows,
            acceptedRows=preview.accepted_rows,
            rejectedRows=preview.rejected_rows,
            stats=CsvImportStatsContract(
                ordersCount=len(preview.orders),
                palletFormats=tuple(cast("list[str]", preview.stats.get("pallet_formats", []))),
                shippingModes=tuple(cast("list[str]", preview.stats.get("shipping_modes", []))),
            ),
        )


# --- /health et /capabilities --------------------------------------------------------------------


class HealthResponse(_StrictModel):
    status: str = "ok"
    version: str
    engine_version: str = Field(alias="engineVersion")


class CapabilitiesResponse(_StrictModel):
    contract_version: str = Field(default=CONTRACT_VERSION, alias="contractVersion")
    units: dict[str, str] = Field(
        default={"dimensions": "mm", "weight": "kg"},
    )
    supported_pallet_formats: tuple[str, ...] = Field(alias="supportedPalletFormats")
    constraints: tuple[str, ...]
    limits: dict[str, int] = Field(alias="limits")
    packing_adapter: dict[str, str] = Field(alias="packingAdapter")


# --- Jobs de palettisation asynchrones (/api/v1/palletization-jobs) ----------------------------


class JobErrorContract(_StrictModel):
    code: str
    message: str

    @classmethod
    def from_domain(cls, error: JobError) -> JobErrorContract:
        return cls(code=error.code, message=error.message)


class JobCreatedResponse(_StrictModel):
    job_id: str = Field(alias="jobId")
    status: JobStatus
    created_at: str = Field(alias="createdAt")


class JobStatusResponse(_StrictModel):
    job_id: str = Field(alias="jobId")
    status: JobStatus
    created_at: str = Field(alias="createdAt")
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")
    result: PalletizeResponse | None = None
    error: JobErrorContract | None = None

    @classmethod
    def from_domain(cls, job: Job) -> JobStatusResponse:
        return cls(
            jobId=job.job_id,
            status=job.status,
            createdAt=job.created_at.isoformat(),
            startedAt=job.started_at.isoformat() if job.started_at else None,
            finishedAt=job.finished_at.isoformat() if job.finished_at else None,
            result=PalletizeResponse.from_domain(job.result) if job.result is not None else None,
            error=JobErrorContract.from_domain(job.error) if job.error is not None else None,
        )
