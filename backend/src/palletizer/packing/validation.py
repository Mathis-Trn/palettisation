"""Géométrie et post-validation indépendante — port fidèle de `geometry.ts` / `support.ts`.

Ces fonctions ne font confiance à aucune sortie de py3dbp : elles sont utilisées à la fois pendant
la recherche de placement (`packing/adapter.py`) et comme garde-fou final indépendant
(`validate_optimization_result`), qui refuse toute solution contenant une collision, un
débordement, une hauteur ou un poids dépassés.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from palletizer.domain.enums import RejectionCode
from palletizer.domain.models import (
    Dimensions3D,
    OptimizationResult,
    PlacedCarton,
    Position3D,
)

EPSILON_MM = 1e-6


def boxes_overlap(
    a_pos: Position3D,
    a_dims: Dimensions3D,
    b_pos: Position3D,
    b_dims: Dimensions3D,
    safety_gap_mm: float = 0.0,
) -> bool:
    """AABB avec espace de sécurité appliqué uniquement sur X/Y (moitié de part et d'autre) ;
    l'axe Z (empilage) autorise un contact exact, sans espace."""
    gap = safety_gap_mm / 2.0
    ax0, ax1 = a_pos.x_mm - gap, a_pos.x_mm + a_dims.length_mm + gap
    bx0, bx1 = b_pos.x_mm - gap, b_pos.x_mm + b_dims.length_mm + gap
    if ax1 <= bx0 + EPSILON_MM or bx1 <= ax0 + EPSILON_MM:
        return False

    ay0, ay1 = a_pos.y_mm - gap, a_pos.y_mm + a_dims.width_mm + gap
    by0, by1 = b_pos.y_mm - gap, b_pos.y_mm + b_dims.width_mm + gap
    if ay1 <= by0 + EPSILON_MM or by1 <= ay0 + EPSILON_MM:
        return False

    az0, az1 = a_pos.z_mm, a_pos.z_mm + a_dims.height_mm
    bz0, bz1 = b_pos.z_mm, b_pos.z_mm + b_dims.height_mm
    return not (az1 <= bz0 + EPSILON_MM or bz1 <= az0 + EPSILON_MM)


def footprint_intersection_area(
    a_pos: Position3D, a_dims: Dimensions3D, b_pos: Position3D, b_dims: Dimensions3D
) -> float:
    """Aire d'intersection 2D (X/Y) entre deux empreintes, indépendamment de Z."""
    x_overlap = max(
        0.0,
        min(a_pos.x_mm + a_dims.length_mm, b_pos.x_mm + b_dims.length_mm)
        - max(a_pos.x_mm, b_pos.x_mm),
    )
    y_overlap = max(
        0.0,
        min(a_pos.y_mm + a_dims.width_mm, b_pos.y_mm + b_dims.width_mm)
        - max(a_pos.y_mm, b_pos.y_mm),
    )
    return x_overlap * y_overlap


def is_within_bounds(
    pos: Position3D, dims: Dimensions3D, max_x: float, max_y: float, max_z: float
) -> bool:
    if pos.x_mm < -EPSILON_MM or pos.y_mm < -EPSILON_MM or pos.z_mm < -EPSILON_MM:
        return False
    return (
        pos.x_mm + dims.length_mm <= max_x + EPSILON_MM
        and pos.y_mm + dims.width_mm <= max_y + EPSILON_MM
        and pos.z_mm + dims.height_mm <= max_z + EPSILON_MM
    )


@dataclass(frozen=True, slots=True)
class SupportCheckResult:
    ok: bool
    support_ratio: float
    reason: RejectionCode | None = None
    detail: str | None = None


def check_support(
    candidate_pos: Position3D,
    candidate_dims: Dimensions3D,
    candidate_weight_kg: float | None,
    existing: Sequence[PlacedCarton],
    minimum_support_ratio: float,
    fragile_max_weight_on_top_kg: float,
) -> SupportCheckResult:
    """Port de `support.ts::checkSupport` : approximation logicielle 2D (surface de contact +
    centre de gravité projeté), pas une simulation physique."""
    if candidate_pos.z_mm <= EPSILON_MM:
        return SupportCheckResult(ok=True, support_ratio=1.0)

    supporting = [
        box
        for box in existing
        if abs((box.position_mm.z_mm + box.placed_dimensions_mm.height_mm) - candidate_pos.z_mm)
        <= EPSILON_MM
    ]

    for box in supporting:
        if not box.stackable:
            return SupportCheckResult(
                False,
                0.0,
                RejectionCode.STACKING_CONSTRAINT,
                f"le support {box.instance_id} n'est pas gerbable",
            )
        if (
            box.fragile
            and candidate_weight_kg is not None
            and candidate_weight_kg > fragile_max_weight_on_top_kg
        ):
            return SupportCheckResult(
                False,
                0.0,
                RejectionCode.STACKING_CONSTRAINT,
                f"le support {box.instance_id} est fragile "
                f"(max {fragile_max_weight_on_top_kg}kg au-dessus)",
            )
        if (
            box.max_supported_weight_kg is not None
            and candidate_weight_kg is not None
            and candidate_weight_kg > box.max_supported_weight_kg
        ):
            return SupportCheckResult(
                False,
                0.0,
                RejectionCode.STACKING_CONSTRAINT,
                f"le poids ({candidate_weight_kg}kg) dépasse la capacité portante de "
                f"{box.instance_id} ({box.max_supported_weight_kg}kg)",
            )

    footprint_area = candidate_dims.length_mm * candidate_dims.width_mm
    contact_area = sum(
        footprint_intersection_area(
            candidate_pos, candidate_dims, box.position_mm, box.placed_dimensions_mm
        )
        for box in supporting
    )
    support_ratio = contact_area / footprint_area if footprint_area > 0 else 0.0
    if support_ratio < minimum_support_ratio - 1e-9:
        return SupportCheckResult(
            False,
            support_ratio,
            RejectionCode.NO_STABLE_POSITION,
            f"ratio de support {support_ratio:.3f} < {minimum_support_ratio}",
        )

    center_x = candidate_pos.x_mm + candidate_dims.length_mm / 2
    center_y = candidate_pos.y_mm + candidate_dims.width_mm / 2
    center_supported = any(
        box.position_mm.x_mm - EPSILON_MM
        <= center_x
        <= box.position_mm.x_mm + box.placed_dimensions_mm.length_mm + EPSILON_MM
        and box.position_mm.y_mm - EPSILON_MM
        <= center_y
        <= box.position_mm.y_mm + box.placed_dimensions_mm.width_mm + EPSILON_MM
        for box in supporting
    )
    if not center_supported:
        return SupportCheckResult(
            False,
            support_ratio,
            RejectionCode.NO_STABLE_POSITION,
            "le centre de gravité projeté n'est couvert par aucun support",
        )
    return SupportCheckResult(True, support_ratio)


def validate_optimization_result(
    result: OptimizationResult, expected_instance_ids: Sequence[str]
) -> list[str]:
    """Post-validation indépendante et exhaustive. Retourne la liste des anomalies détectées
    (vide si la solution est valide). Ne fait confiance à aucune sortie de l'adaptateur py3dbp."""
    issues: list[str] = []
    seen_instance_ids: set[str] = set()

    for pallet in result.pallets:
        boxes = list(pallet.placed_cartons)
        spec = pallet.spec
        max_x, max_y, max_z = spec.usable_length_mm, spec.usable_width_mm, spec.usable_height_mm

        for i, box in enumerate(boxes):
            if box.instance_id in seen_instance_ids:
                issues.append(f"instance {box.instance_id} placée plusieurs fois")
            seen_instance_ids.add(box.instance_id)

            if not is_within_bounds(box.position_mm, box.placed_dimensions_mm, max_x, max_y, max_z):
                issues.append(
                    f"carton {box.instance_id} hors des bornes de la palette {pallet.index}"
                )
            if box.position_mm.x_mm < 0 or box.position_mm.y_mm < 0 or box.position_mm.z_mm < 0:
                issues.append(f"carton {box.instance_id} a une coordonnée négative")

            for other in boxes[i + 1 :]:
                if boxes_overlap(
                    box.position_mm,
                    box.placed_dimensions_mm,
                    other.position_mm,
                    other.placed_dimensions_mm,
                    spec.safety_gap_mm,
                ):
                    issues.append(
                        f"chevauchement détecté entre {box.instance_id} et {other.instance_id} "
                        f"sur la palette {pallet.index}"
                    )

        total_weight = sum(box.weight_kg or 0.0 for box in boxes)
        if spec.max_weight_kg is not None and total_weight > spec.max_weight_kg + 1e-6:
            issues.append(
                f"palette {pallet.index} dépasse le poids maximal "
                f"({total_weight}kg > {spec.max_weight_kg}kg)"
            )

    for unplaced in result.unplaced_cartons:
        if unplaced.instance_id in seen_instance_ids:
            issues.append(f"instance {unplaced.instance_id} à la fois placée et rejetée")
        seen_instance_ids.add(unplaced.instance_id)

    expected_ids = set(expected_instance_ids)
    if seen_instance_ids != expected_ids:
        missing = expected_ids - seen_instance_ids
        extra = seen_instance_ids - expected_ids
        if missing:
            issues.append(f"instances jamais classées (ni placées ni rejetées) : {sorted(missing)}")
        if extra:
            issues.append(f"instances inconnues dans le résultat : {sorted(extra)}")

    return issues
