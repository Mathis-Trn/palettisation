"""Service applicatif headless : orchestration expansion → tri → placement → agrégation.

Utilisable comme simple bibliothèque Python (voir `backend/README.md`), sans FastAPI ni serveur.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime

from palletizer.domain.enums import (
    QUICK_STRATEGIES,
    REJECTION_MESSAGES,
    THOROUGH_STRATEGIES,
    OptimizationLevel,
    RejectionCode,
    SortStrategyName,
)
from palletizer.domain.errors import SolutionValidationError
from palletizer.domain.models import (
    CartonInstance,
    LegacyExpectedResult,
    OptimizationOptions,
    OptimizationResult,
    Order,
    OrderLine,
    PalletResult,
    PalletSpec,
    PalletToLoad,
    TransportLoadResult,
    UnplacedCarton,
    VehicleConfig,
)
from palletizer.packing.adapter import WorkingPallet, pack_with_strategy
from palletizer.packing.metrics import build_pallet_result, usable_volume_mm3
from palletizer.packing.transport_packer import compute_transport_load
from palletizer.packing.validation import validate_optimization_result

ENGINE_VERSION = "1.0.0"
PRACTICAL_INSTANCE_LIMIT = 500


def _sanitize_sku(sku: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in sku)
    return cleaned or "SKU"


def expand_order_lines(
    lines: Sequence[OrderLine],
) -> tuple[list[CartonInstance], list[UnplacedCarton]]:
    """Développe chaque ligne en instances individuelles, avec un identifiant déterministe basé
    sur un compteur global suivant l'ordre d'entrée (port de `optimizer/expand.ts`)."""
    instances: list[CartonInstance] = []
    invalid: list[UnplacedCarton] = []
    counter = 0
    for line in lines:
        if line.quantity <= 0:
            invalid.append(
                UnplacedCarton(
                    instance_id=f"{_sanitize_sku(line.sku)}__invalid_line_{line.line_number}",
                    sku=line.sku,
                    dimensions_mm=line.dimensions_mm,
                    code=RejectionCode.INVALID_DATA,
                    message=REJECTION_MESSAGES[RejectionCode.INVALID_DATA],
                    weight_kg=line.weight_kg,
                )
            )
            continue
        for _ in range(line.quantity):
            counter += 1
            instances.append(
                CartonInstance(
                    instance_id=f"{_sanitize_sku(line.sku)}__{counter:05d}",
                    sku=line.sku,
                    line_number=line.line_number,
                    dimensions_mm=line.dimensions_mm,
                    weight_kg=line.weight_kg,
                    allow_rotation=line.allow_rotation,
                    upright_only=line.upright_only,
                    fragile=line.fragile,
                    stackable=line.stackable,
                    max_supported_weight_kg=line.max_supported_weight_kg,
                    product_group=line.product_group,
                    incompatible_groups=line.incompatible_groups,
                )
            )
    return instances, invalid


def _sort_key_volume_desc(instance: CartonInstance) -> tuple[float, str]:
    return (-instance.dimensions_mm.volume_mm3, instance.instance_id)


def _sort_key_largest_dimension_desc(instance: CartonInstance) -> tuple[float, str]:
    d = instance.dimensions_mm
    return (-max(d.length_mm, d.width_mm, d.height_mm), instance.instance_id)


def _sort_key_weight_desc(instance: CartonInstance) -> tuple[float, str]:
    return (-(instance.weight_kg or 0.0), instance.instance_id)


def _sort_key_footprint_desc(instance: CartonInstance) -> tuple[float, str]:
    d = instance.dimensions_mm
    return (-(d.length_mm * d.width_mm), instance.instance_id)


_SORT_KEYS = {
    SortStrategyName.VOLUME_DESC: _sort_key_volume_desc,
    SortStrategyName.LARGEST_DIMENSION_DESC: _sort_key_largest_dimension_desc,
    SortStrategyName.WEIGHT_DESC: _sort_key_weight_desc,
    SortStrategyName.FOOTPRINT_DESC: _sort_key_footprint_desc,
}


def sort_instances(
    instances: Sequence[CartonInstance], strategy: SortStrategyName
) -> list[CartonInstance]:
    return sorted(instances, key=_SORT_KEYS[strategy])


def _strategy_rank(
    pallets: Sequence[WorkingPallet], spec: PalletSpec, strategy: SortStrategyName
) -> tuple[int, int, float, float, str]:
    """Clé de comparaison entre stratégies : moins de palettes, puis plus de cartons placés, puis
    meilleure occupation volumique, puis hauteur utilisée la plus faible, puis ordre stable."""
    placed_count = sum(len(pallet.boxes) for pallet in pallets)
    usable_total = usable_volume_mm3(spec) * len(pallets)
    used_total = sum(
        box.placed_dimensions_mm.volume_mm3 for pallet in pallets for box in pallet.boxes
    )
    volume_ratio = used_total / usable_total if usable_total > 0 else 0.0
    max_height = max(
        (
            max(
                (box.position_mm.z_mm + box.placed_dimensions_mm.height_mm for box in pallet.boxes),
                default=0.0,
            )
            for pallet in pallets
        ),
        default=0.0,
    )
    return (len(pallets), -placed_count, -volume_ratio, max_height, strategy.value)


class PalletizationService:
    """Point d'entrée headless : `PalletizationService().optimize(order, pallet_spec, options)`."""

    def optimize(
        self,
        order: Order,
        pallet_spec: PalletSpec,
        options: OptimizationOptions,
        legacy_expected_result: LegacyExpectedResult | None = None,
    ) -> OptimizationResult:
        start = time.perf_counter()
        instances, invalid_lines = expand_order_lines(order.lines)
        warnings: list[str] = []
        if len(instances) > PRACTICAL_INSTANCE_LIMIT:
            warnings.append(
                f"Plus de {PRACTICAL_INSTANCE_LIMIT} instances ({len(instances)}) à placer : le "
                "mode rapide est recommandé, le calcul peut être lent en mode approfondi."
            )

        strategies = (
            QUICK_STRATEGIES
            if options.optimization_level == OptimizationLevel.FAST
            else THOROUGH_STRATEGIES
        )

        best_pallets: list[WorkingPallet] | None = None
        best_unplaced: list[UnplacedCarton] = []
        best_rank: tuple[int, int, float, float, str] | None = None
        for strategy in strategies:
            ordered = sort_instances(instances, strategy)
            pallets, unplaced = pack_with_strategy(ordered, pallet_spec, options)
            rank = _strategy_rank(pallets, pallet_spec, strategy)
            if best_rank is None or rank < best_rank:
                best_rank = rank
                best_pallets = pallets
                best_unplaced = unplaced

        assert best_pallets is not None  # au moins une stratégie est toujours essayée

        pallet_results = tuple(
            build_pallet_result(index, pallet_spec, pallet.boxes)
            for index, pallet in enumerate(best_pallets)
        )
        all_unplaced = tuple(invalid_lines) + tuple(best_unplaced)

        total_count = len(instances) + len(invalid_lines)
        placed_count = sum(len(pallet.placed_cartons) for pallet in pallet_results)
        total_weight = sum(pallet.total_weight_kg for pallet in pallet_results)
        usable_vol_total = sum(pallet.usable_volume_mm3 for pallet in pallet_results)
        used_vol_total = sum(pallet.volume_used_mm3 for pallet in pallet_results)
        global_ratio = used_vol_total / usable_vol_total if usable_vol_total > 0 else 0.0

        if all_unplaced:
            warnings.append(f"{len(all_unplaced)} carton(s) n'ont pas pu être placés.")

        result = OptimizationResult(
            order_id=order.order_id,
            pallets=pallet_results,
            unplaced_cartons=all_unplaced,
            total_cartons_count=total_count,
            placed_cartons_count=placed_count,
            unplaced_cartons_count=len(all_unplaced),
            pallets_count=len(pallet_results),
            global_volume_usage_ratio=global_ratio,
            total_weight_kg=total_weight,
            warnings=tuple(warnings),
            computed_at_iso=datetime.now(UTC).isoformat(),
            engine_version=ENGINE_VERSION,
            level_used=options.optimization_level,
            duration_ms=(time.perf_counter() - start) * 1000,
            legacy_expected_result=legacy_expected_result,
        )

        expected_ids = [instance.instance_id for instance in instances] + [
            unplaced.instance_id for unplaced in invalid_lines
        ]
        issues = validate_optimization_result(result, expected_ids)
        if issues:
            raise SolutionValidationError(
                "Post-validation indépendante a rejeté la solution : " + "; ".join(issues)
            )
        return result


class TransportLoadingService:
    """Chargement headless des palettes déjà calculées dans un véhicule/conteneur."""

    def compute(self, pallets: list[PalletToLoad], vehicle: VehicleConfig) -> TransportLoadResult:
        return compute_transport_load(pallets, vehicle)

    def pallets_from_results(self, pallets: Sequence[PalletResult]) -> list[PalletToLoad]:
        """Convertit une liste de `PalletResult` en `PalletToLoad` (empreinte + poids)."""
        return [
            PalletToLoad(
                pallet_result_index=pallet.index,
                footprint_length_mm=pallet.spec.length_mm,
                footprint_width_mm=pallet.spec.width_mm,
                height_mm=pallet.spec.empty_pallet_height_mm + pallet.max_height_used_mm,
                weight_kg=pallet.total_weight_kg,
            )
            for pallet in pallets
        ]
