"""Adaptateur anticorruption autour de py3dbp==1.1.2.

**Aucun objet `py3dbp` ne sort de ce module.** Toute autre partie du code métier ne manipule que
des types du domaine (`Dimensions3D`, `OrientationCode`).

## Correspondance des axes (domaine ↔ py3dbp ↔ Three.js)

Le domaine utilise x = longueur, y = largeur, z = hauteur (vertical), origine au coin de la
palette (voir `palletizer.domain.models`).

py3dbp modélise un `Item`/`Bin` par trois attributs nommés `width`, `height`, `depth`, et une
position `[p0, p1, p2]` où **l'index correspond à l'axe testé par `Bin.put_item`** : l'axe 0
avance de `width`, l'axe 1 de `height`, l'axe 2 de `depth` (vérifié empiriquement dans
`tests/integration/test_py3dbp_probe.py::test_probe_axis_index_meaning` en lisant
`py3dbp.main.Bin.put_item`).

Nous choisissons le mapping suivant à la construction des objets py3dbp :

    py3dbp.width  = domaine.length_mm   (axe 0 de py3dbp == axe x du domaine)
    py3dbp.height = domaine.height_mm   (axe 1 de py3dbp == axe z du domaine, vertical)
    py3dbp.depth  = domaine.width_mm    (axe 2 de py3dbp == axe y du domaine)

Donc `position_py3dbp = [px, py, pz]` se retraduit en `Position3D(x_mm=px, y_mm=pz, z_mm=py)`.

Ce mapping fait coïncider sémantiquement `py3dbp.height` avec la verticale du domaine (pratique
pour le débogage), au prix d'un réordonnancement d'indices (l'axe vertical du domaine est l'indice
1 de py3dbp, pas l'indice 2) — documenté ici pour éviter toute confusion future. Le composant
Three.js (`coordinate-utils.ts` côté front) ne voit jamais ce détail : il ne consomme que le
`Position3D`/`Dimensions3D` du domaine, inchangés depuis la version TypeScript.

## Table de rotation

`Item.get_dimension()` renvoie les 3 étendues occupées selon `rotation_type` (0 à 5), calculée à
partir de `(width, height, depth)`. La table exacte a été vérifiée empiriquement avec des valeurs
distinctes dans `tests/integration/test_py3dbp_probe.py::test_probe_rotation_dimension_table`, puis
recombinée avec le mapping ci-dessus pour obtenir la correspondance avec les 6
`OrientationCode` du domaine (voir `ROTATION_TYPE_TO_ORIENTATION` ci-dessous, et
`tests/unit/test_py3dbp_adapter.py` pour la vérification automatisée à chaque exécution des tests).

py3dbp ne fournit **aucun moyen natif de restreindre les rotations testées** par carton
(`Bin.put_item` boucle toujours sur `RotationType.ALL`) : c'est pourquoi `packing/adapter.py`
n'utilise pas `Packer.pack()` tel quel, mais un placement point-par-point qui n'invoque
`Item.get_dimension()` que pour les orientations explicitement autorisées par
`packing/constraints.py`.
"""

from __future__ import annotations

from py3dbp import Item as Py3dbpItem
from py3dbp.constants import RotationType

from palletizer.domain.enums import OrientationCode
from palletizer.domain.models import Dimensions3D

# Table figée, dérivée de la sonde empirique (voir docstring du module) : pour chaque rotation_type
# py3dbp, quel OrientationCode du domaine cela représente avec le mapping width=L, height=H,
# depth=W choisi ci-dessus.
ROTATION_TYPE_TO_ORIENTATION: dict[int, OrientationCode] = {
    RotationType.RT_WHD: OrientationCode.LWH,
    RotationType.RT_HWD: OrientationCode.HWL,
    RotationType.RT_HDW: OrientationCode.HLW,
    RotationType.RT_DHW: OrientationCode.WLH,
    RotationType.RT_DWH: OrientationCode.WHL,
    RotationType.RT_WDH: OrientationCode.LHW,
}
ORIENTATION_TO_ROTATION_TYPE: dict[OrientationCode, int] = {
    code: rt for rt, code in ROTATION_TYPE_TO_ORIENTATION.items()
}

# Ordre déterministe des 6 orientations, identique à l'ordre de déclaration du domaine (repris de
# l'ancien moteur TypeScript pour préserver le comportement/les égalités de tri).
ALL_ORIENTATIONS: tuple[OrientationCode, ...] = (
    OrientationCode.LWH,
    OrientationCode.WLH,
    OrientationCode.LHW,
    OrientationCode.HWL,
    OrientationCode.WHL,
    OrientationCode.HLW,
)


def _make_probe_item(dims: Dimensions3D) -> Py3dbpItem:
    return Py3dbpItem(
        "probe", width=dims.length_mm, height=dims.height_mm, depth=dims.width_mm, weight=0.0
    )


def oriented_dimensions(dims: Dimensions3D, orientation: OrientationCode) -> Dimensions3D:
    """Dimensions occupées (en mm, axes du domaine) après application d'une orientation.

    Délègue le calcul de permutation à `py3dbp.Item.get_dimension()` (c'est la seule
    responsabilité de py3dbp utilisée ici : aucun objet py3dbp n'est retourné).
    """
    item = _make_probe_item(dims)
    item.rotation_type = ORIENTATION_TO_ROTATION_TYPE[orientation]
    py_w, py_h, py_d = item.get_dimension()
    # py_w/py_h/py_d sont dans le référentiel py3dbp (axe0=largeur py3dbp, axe1=hauteur py3dbp,
    # axe2=profondeur py3dbp) ; on retraduit vers le domaine avec le mapping documenté plus haut :
    # axe0(py3dbp width) -> x du domaine (length), axe1(py3dbp height) -> z du domaine (height),
    # axe2(py3dbp depth) -> y du domaine (width).
    return Dimensions3D(length_mm=float(py_w), width_mm=float(py_d), height_mm=float(py_h))
