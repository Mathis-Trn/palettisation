"""Port (interface) découplant `packing/adapter.py` de la bibliothèque de bin-packing concrète.

Remplacer py3dbp par une autre bibliothèque plus tard ne nécessite que d'écrire un nouveau module
respectant cette signature (par ex. `packing/other_lib_adapter.py::oriented_dimensions`) et de
changer l'import par défaut dans `packing/adapter.py` — ni le domaine ni l'API ne changent.
"""

from __future__ import annotations

from typing import Protocol

from palletizer.domain.enums import OrientationCode
from palletizer.domain.models import Dimensions3D


class OrientationProvider(Protocol):
    """Calcule les dimensions occupées par un carton selon une orientation donnée."""

    def __call__(self, dims: Dimensions3D, orientation: OrientationCode) -> Dimensions3D: ...
