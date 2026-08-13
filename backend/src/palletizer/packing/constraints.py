"""Contraintes appliquées AVANT le placement (py3dbp ne les gère pas nativement) :
orientations autorisées et compatibilité de groupes entre cartons d'une même palette.
"""

from __future__ import annotations

from collections.abc import Sequence

from palletizer.domain.enums import UPRIGHT_ORIENTATIONS, OrientationCode
from palletizer.domain.models import CartonInstance
from palletizer.packing.py3dbp_adapter import ALL_ORIENTATIONS


def allowed_orientations(
    instance: CartonInstance, global_rotations_enabled: bool
) -> tuple[OrientationCode, ...]:
    """Orientations à tester pour cette instance, selon ses réglages et le réglage global.

    Port fidèle de `src/optimizer/orientations.ts::getAllowedOrientations` : le réglage global
    « Autoriser les rotations » et `allowRotation` de la ligne sont combinés par un ET logique.
    """
    effective_rotation = instance.allow_rotation and global_rotations_enabled
    if not effective_rotation:
        return (OrientationCode.LWH,)
    if instance.upright_only:
        return UPRIGHT_ORIENTATIONS
    return ALL_ORIENTATIONS


def is_compatible_with_pallet(
    instance: CartonInstance, pallet_instances: Sequence[CartonInstance]
) -> bool:
    """Vérification bidirectionnelle des groupes incompatibles (port de `packer.ts`).

    Deux cartons de groupes mutuellement incompatibles ne sont jamais placés sur la même palette.
    Une palette vide est toujours compatible.
    """
    for other in pallet_instances:
        if (
            instance.product_group is not None
            and instance.product_group in other.incompatible_groups
        ):
            return False
        if other.product_group is not None and other.product_group in instance.incompatible_groups:
            return False
    return True
