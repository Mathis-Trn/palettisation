"""Modèle de domaine pur (dataclasses gelées). Zéro dépendance à un framework web ou UI.

Unité canonique : millimètre pour les dimensions/positions, kilogramme pour les poids.
Repère : origine au coin inférieur de la zone utile de chargement, x = longueur, y = largeur,
z = hauteur (vertical). La position d'un carton placé est celle de son coin inférieur, pas de son
centre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from palletizer.domain.enums import OptimizationLevel, OrientationCode, RejectionCode, ShippingMode


@dataclass(frozen=True, slots=True)
class Dimensions3D:
    length_mm: float
    width_mm: float
    height_mm: float

    def __post_init__(self) -> None:
        if self.length_mm <= 0 or self.width_mm <= 0 or self.height_mm <= 0:
            raise ValueError(f"Dimensions non positives : {self}")

    @property
    def volume_mm3(self) -> float:
        return self.length_mm * self.width_mm * self.height_mm


@dataclass(frozen=True, slots=True)
class Position3D:
    x_mm: float
    y_mm: float
    z_mm: float


@dataclass(frozen=True, slots=True)
class OrderLine:
    line_number: int
    sku: str
    description: str
    quantity: int
    unit: str
    dimensions_mm: Dimensions3D
    weight_kg: float | None = None
    allow_rotation: bool = True
    upright_only: bool = False
    fragile: bool = False
    stackable: bool = True
    max_supported_weight_kg: float | None = None
    product_group: str | None = None
    incompatible_groups: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    shipping_mode: ShippingMode
    lines: tuple[OrderLine, ...]


@dataclass(frozen=True, slots=True)
class PalletSpec:
    code: str
    length_mm: float
    width_mm: float
    max_height_mm: float
    empty_pallet_height_mm: float = 144.0
    max_height_includes_pallet: bool = True
    max_weight_kg: float | None = None
    overhang_mm: float = 0.0
    safety_gap_mm: float = 0.0
    minimum_support_ratio: float = 0.8

    @property
    def usable_length_mm(self) -> float:
        return self.length_mm + self.overhang_mm

    @property
    def usable_width_mm(self) -> float:
        return self.width_mm + self.overhang_mm

    @property
    def usable_height_mm(self) -> float:
        if self.max_height_includes_pallet:
            return self.max_height_mm - self.empty_pallet_height_mm
        return self.max_height_mm


@dataclass(frozen=True, slots=True)
class OptimizationOptions:
    global_rotations_enabled: bool = True
    optimization_level: OptimizationLevel = OptimizationLevel.FAST
    fragile_max_weight_on_top_kg: float = 0.0


@dataclass(frozen=True, slots=True)
class CartonInstance:
    instance_id: str
    sku: str
    line_number: int
    dimensions_mm: Dimensions3D
    weight_kg: float | None
    allow_rotation: bool
    upright_only: bool
    fragile: bool
    stackable: bool
    max_supported_weight_kg: float | None = None
    product_group: str | None = None
    incompatible_groups: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PlacedCarton:
    instance_id: str
    sku: str
    original_dimensions_mm: Dimensions3D
    placed_dimensions_mm: Dimensions3D
    position_mm: Position3D
    orientation: OrientationCode
    pallet_index: int
    placement_score: float
    fragile: bool
    stackable: bool
    weight_kg: float | None = None
    max_supported_weight_kg: float | None = None
    product_group: str | None = None


@dataclass(frozen=True, slots=True)
class UnplacedCarton:
    instance_id: str
    sku: str
    dimensions_mm: Dimensions3D
    code: RejectionCode
    message: str
    weight_kg: float | None = None


@dataclass(frozen=True, slots=True)
class LegacyExpectedResult:
    """Résultat historique (PALXENT / PALETTE_DETAIL_* / QTEXARC), jamais utilisé comme entrée du
    solveur — conservé uniquement pour audit et comparaison."""

    pallet_count: int | None
    raw_pallet_details: tuple[tuple[str, ...], ...] = ()
    raw_qtexarc: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PalletResult:
    index: int
    spec: PalletSpec
    placed_cartons: tuple[PlacedCarton, ...]
    total_weight_kg: float
    usable_volume_mm3: float
    volume_used_mm3: float
    volume_usage_ratio: float
    footprint_usage_ratio: float
    max_height_used_mm: float


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    order_id: str
    pallets: tuple[PalletResult, ...]
    unplaced_cartons: tuple[UnplacedCarton, ...]
    total_cartons_count: int
    placed_cartons_count: int
    unplaced_cartons_count: int
    pallets_count: int
    global_volume_usage_ratio: float
    total_weight_kg: float
    warnings: tuple[str, ...]
    computed_at_iso: str
    engine_version: str
    level_used: OptimizationLevel
    duration_ms: float
    legacy_expected_result: LegacyExpectedResult | None = None


# --- Chargement transport (véhicule / conteneur) ---------------------------------------------


@dataclass(frozen=True, slots=True)
class VehicleConfig:
    name: str
    inner_length_mm: float
    inner_width_mm: float
    inner_height_mm: float
    max_payload_kg: float
    allow_pallet_rotation_floor: bool = True
    allow_pallet_stacking: bool = False


@dataclass(frozen=True, slots=True)
class PalletToLoad:
    pallet_result_index: int
    footprint_length_mm: float
    footprint_width_mm: float
    height_mm: float
    weight_kg: float


@dataclass(frozen=True, slots=True)
class LoadedPalletPlacement:
    pallet_result_index: int
    vehicle_index: int
    x_mm: float
    y_mm: float
    rotated: bool
    stack_level: int
    length_mm: float
    width_mm: float
    height_mm: float
    weight_kg: float


@dataclass(frozen=True, slots=True)
class VehicleLoadResult:
    index: int
    placements: tuple[LoadedPalletPlacement, ...]
    used_floor_area_ratio: float
    used_weight_kg: float


@dataclass(frozen=True, slots=True)
class TransportLoadResult:
    vehicles: tuple[VehicleLoadResult, ...]
    unassigned_pallet_indexes: tuple[int, ...]
    vehicles_needed: int
    pallets_loadable: int


# --- Import CSV : diagnostics ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CsvImportError:
    line_number: int | None
    column: str | None
    code: str
    message: str
    raw_fragments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CsvImportWarning:
    line_number: int | None
    message: str


@dataclass(frozen=True, slots=True)
class NormalizedCsvLine:
    line: OrderLine
    order_id: str
    depot: str
    shipping_mode_raw: str
    pallet_format_raw: str
    qtexarc_raw: str | None
    palette_detail_raw: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParsedCsvOrder:
    order_id: str
    shipping_mode: ShippingMode
    pallet_spec: PalletSpec
    lines: tuple[OrderLine, ...]
    legacy_expected_result: LegacyExpectedResult


@dataclass(frozen=True, slots=True)
class CsvImportPreview:
    orders: tuple[ParsedCsvOrder, ...]
    errors: tuple[CsvImportError, ...]
    warnings: tuple[CsvImportWarning, ...]
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    stats: dict[str, object] = field(default_factory=dict)
