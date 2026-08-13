"""Score d'un placement candidat — port fidèle de `src/optimizer/scoring.ts`, avec un correctif
sur le poids de la distance à l'origine (voir `_ORIGIN_DISTANCE_WEIGHT` ci-dessous).

Poids : hauteur résultante (-1.0), distance à l'origine (voir constante), ratio de support (+50),
contact avec les parois/le sol (+20 par axe), regroupement de cartons de même SKU adjacents (+5
par voisin).
"""

from __future__ import annotations

from collections.abc import Sequence

from palletizer.domain.models import Dimensions3D, PlacedCarton, Position3D
from palletizer.packing.validation import EPSILON_MM

_ADJACENCY_DILATION_MM = 1.0

# Poids de la pénalité de distance à l'origine (x+y, en mm). Historiquement -0.05 (valeur portée
# telle quelle depuis l'ancien moteur TypeScript) : correct pour des cartons de hauteur "normale"
# (>= quelques dizaines de mm), où le coût d'une couche supplémentaire (-1.0 * hauteur) domine
# largement ce terme. Bug réel découvert sur un carton plat (55x85x15mm, donc -1.0*15=-15 par
# couche) posé sur une grande palette (1200x800mm) : à -0.05/mm, s'éloigner jusqu'au coin opposé
# du plancher coûte jusqu'à -0.05*(1200+800)=-100 points — largement plus que le coût d'empiler
# PLUSIEURS couches supplémentaires près de l'origine. Le moteur préférait donc construire une
# pyramide décroissante près du coin d'origine plutôt que de terminer la couche courante, laissant
# de larges zones du plancher inutilisées (mesuré : une couche remplie à 146/189 avant bascule sur
# la couche suivante, puis 40, 12, 1, 1 — un empilement en pyramide au lieu d'un pavage plat).
# Réduit à -0.0005 (÷100) : sur la même palette, le pire écart possible (coin opposé, 2000mm)
# ne coûte plus que 1.0 point — négligeable face à N'IMPORTE QUELLE différence de hauteur réaliste
# (même un carton de 5mm coûte -5 par couche), donc ce terme redevient un pur départage entre
# positions par ailleurs équivalentes, comme semble l'avoir été son intention d'origine, sans
# jamais pouvoir l'emporter sur le choix hauteur/support/contact. Vérifié : sur le même cas
# (carton plat, 200 unités), la couche 0 passe de 146/189 à 191/200 rempli avant bascule.
_ORIGIN_DISTANCE_WEIGHT = 0.0005


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
        - _ORIGIN_DISTANCE_WEIGHT * origin_distance
        + 50.0 * support_ratio
        + 20.0 * wall_contact
        + 5.0 * adjacency_count
    )


def score_upper_bound(position: Position3D, dims: Dimensions3D, nearby_count: int) -> float:
    """Borne supérieure ADMISSIBLE du score qu'un candidat (position, dims) pourrait atteindre au
    mieux, calculable SANS les parties coûteuses de `score_placement` (ratio de support exact,
    comptage d'adjacence) — seulement à partir de la position, qui est connue immédiatement.

    Utilisée par `adapter.py::try_place_on_pallet` pour une recherche best-first (élagage/
    branch-and-bound) : les candidats sont triés par cette borne, et `check_support`/
    `score_placement` (les étapes coûteuses, voir le profilage qui a motivé cette optimisation) ne
    sont appelés que pour les candidats dont la borne dépasse encore le meilleur score CONFIRMÉ
    trouvé jusqu'ici. Comme aucun candidat ne peut dépasser sa propre borne supérieure, ceux qui
    n'ont aucune chance de gagner sont écartés sans jamais être évalués — le gagnant final est
    PROUVABLEMENT identique à celui d'une évaluation exhaustive de tous les candidats (voir le test
    de propriété qui compare les deux méthodes sur des ordres aléatoires).

    Bornes utilisées : `support_ratio <= 1.0` (maximum théorique) et `adjacency_count <=
    nearby_count` (l'adjacence ne compte qu'un sous-ensemble des cartons à proximité, jamais
    plus)."""
    resulting_height = position.z_mm + dims.height_mm
    origin_distance = position.x_mm + position.y_mm
    wall_contact = (
        int(position.x_mm <= EPSILON_MM)
        + int(position.y_mm <= EPSILON_MM)
        + int(position.z_mm <= EPSILON_MM)
    )
    return (
        -1.0 * resulting_height
        - _ORIGIN_DISTANCE_WEIGHT * origin_distance
        + 50.0 * 1.0
        + 20.0 * wall_contact
        + 5.0 * nearby_count
    )
