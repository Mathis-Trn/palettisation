"""Score d'un placement candidat — port fidèle de `src/optimizer/scoring.ts`.

Poids empiriques conservés à l'identique : hauteur résultante (-1.0), distance à l'origine
(-0.05), ratio de support (+50), contact avec les parois/le sol (+20 par axe), regroupement de
cartons de même SKU adjacents (+5 par voisin).
"""

from __future__ import annotations

from collections.abc import Sequence

from palletizer.domain.models import Dimensions3D, PlacedCarton, Position3D
from palletizer.packing.validation import EPSILON_MM

_ADJACENCY_DILATION_MM = 1.0


def _dilated_footprints_touch(
    a_pos: Position3D,
    a_dims: Dimensions3D,
    b_pos: Position3D,
    b_dims: Dimensions3D,
    dilation: float,
) -> bool:
    ax0, ax1 = a_pos.x_mm - dilation, a_pos.x_mm + a_dims.length_mm + dilation
    bx0, bx1 = b_pos.x_mm - dilation, b_pos.x_mm + b_dims.length_mm + dilation
    if ax1 <= bx0 or bx1 <= ax0:
        return False
    ay0, ay1 = a_pos.y_mm - dilation, a_pos.y_mm + a_dims.width_mm + dilation
    by0, by1 = b_pos.y_mm - dilation, b_pos.y_mm + b_dims.width_mm + dilation
    return not (ay1 <= by0 or by1 <= ay0)


def score_placement(
    position: Position3D,
    dims: Dimensions3D,
    support_ratio: float,
    sku: str,
    existing: Sequence[PlacedCarton],
) -> float:
    resulting_height = position.z_mm + dims.height_mm
    origin_distance = position.x_mm + position.y_mm
    wall_contact = (
        int(position.x_mm <= EPSILON_MM)
        + int(position.y_mm <= EPSILON_MM)
        + int(position.z_mm <= EPSILON_MM)
    )
    same_level_same_sku = (
        box
        for box in existing
        if box.sku == sku and abs(box.position_mm.z_mm - position.z_mm) <= EPSILON_MM
    )
    adjacency_count = sum(
        1
        for box in same_level_same_sku
        if _dilated_footprints_touch(
            position, dims, box.position_mm, box.placed_dimensions_mm, _ADJACENCY_DILATION_MM
        )
    )
    return (
        -1.0 * resulting_height
        - 0.05 * origin_distance
        + 50.0 * support_ratio
        + 20.0 * wall_contact
        + 5.0 * adjacency_count
    )
