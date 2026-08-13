"""Moteur de placement (points extrêmes) sur une palette, et boucle multi-palettes.

py3dbp (via `packing/py3dbp_adapter.py`, injecté comme `OrientationProvider`) n'est utilisé ici que
pour la primitive géométrique de rotation (les 6 permutations d'axes). La recherche de placement,
les contraintes métier (support, fragilité, gerbage, groupes incompatibles, espace de sécurité) et
le score de placement restent implémentés en Python, portés fidèlement de l'ancien moteur
TypeScript (`src/optimizer/engine.ts`, `packer.ts`) : py3dbp ne gère nativement ni la restriction
des rotations autorisées, ni l'espace de sécurité, ni le ratio de support, ni la fragilité, ni les
groupes incompatibles.

Garde-fou anti-boucle infinie : `can_instance_ever_fit` teste la faisabilité sur une palette VIDE
avant d'en ouvrir une nouvelle ; si même une palette vide ne peut accueillir le carton, il est
rejeté immédiatement avec un code précis, sans jamais ouvrir de palette supplémentaire pour rien.

Index spatial (performance) : `try_place_on_pallet` doit, pour chaque point/orientation candidat,
retrouver les cartons déjà placés qui pourraient chevaucher ou supporter le candidat. Scanner TOUS
les cartons de la palette à chaque tentative devient O(instances × cartons_déjà_placés) — dominant
sur les commandes volumineuses où une palette accumule des centaines/milliers de cartons (mesuré :
le calcul reste bloqué plusieurs dizaines de minutes sur un ordre réel de 29 138 cartons/65
références). `WorkingPallet.grid` bucketise les cartons déjà placés par cellule XY (`GRID_CELL_MM`)
et `_nearby_boxes` ne renvoie que les cartons dont l'empreinte pourrait chevaucher le candidat (avec
la marge de sécurité) : c'est une RÉDUCTION DE CANDIDATS, jamais un remplacement du test géométrique
exact (`boxes_overlap`, `check_support`), qui reste inchangé et décide seul du résultat — cette
optimisation ne peut donc jamais changer un placement, seulement le nombre de comparaisons
effectuées pour le trouver. `validate_optimization_result` (post-validation indépendante, appelée
sur CHAQUE résultat) reste en outre le filet de sécurité final si un bug venait quand même à
échapper à cette garantie.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace

from palletizer.application.ports import OrientationProvider
from palletizer.domain.enums import REJECTION_MESSAGES, OrientationCode, RejectionCode
from palletizer.domain.models import (
    CartonInstance,
    Dimensions3D,
    OptimizationOptions,
    PalletSpec,
    PlacedCarton,
    Position3D,
    UnplacedCarton,
)
from palletizer.packing import py3dbp_adapter
from palletizer.packing.constraints import allowed_orientations, is_compatible_with_pallet
from palletizer.packing.scoring import score_placement, score_upper_bound
from palletizer.packing.validation import EPSILON_MM, boxes_overlap, check_support, is_within_bounds

MAX_EXTREME_POINTS = 400
_ORIGIN = Position3D(0.0, 0.0, 0.0)

# Taille de cellule (mm) de l'index spatial XY. Purement un paramètre de performance : n'affecte
# jamais le résultat (voir docstring du module), seulement le nombre de cartons pré-filtrés avant
# le test géométrique exact. Choisie autour de l'ordre de grandeur d'un carton usuel (ni trop fine,
# ce qui multiplierait les cellules pour peu de gain, ni trop grossière, ce qui rapprocherait le
# comportement d'un scan linéaire complet).
GRID_CELL_MM = 300.0


@dataclass(slots=True)
class WorkingPallet:
    boxes: list[PlacedCarton] = field(default_factory=list)
    instances: list[CartonInstance] = field(default_factory=list)
    extreme_points: list[Position3D] = field(default_factory=lambda: [_ORIGIN])
    total_weight_kg: float = 0.0
    # Index spatial 3D (indices dans `boxes`) tenu à jour par `_register_placement` : voir la
    # docstring du module pour la garantie de sécurité (réduction de candidats uniquement).
    grid: dict[tuple[int, int, int], list[int]] = field(default_factory=dict)
    # Mémoïsation des échecs de placement à l'état ACTUEL de la palette (voir
    # `try_place_on_pallet` et `add_placed_box`, seul point qui la vide). Un ordre réel répète
    # très souvent la même référence (mêmes dimensions/poids/rotations) des centaines ou milliers
    # de fois d'affilée ; sans ce cache, la boucle multi-palettes relance une recherche
    # extreme-points complète contre CHAQUE palette déjà ouverte pour CHAQUE instance, même quand
    # une instance identique vient d'échouer contre la même palette inchangée l'instant d'avant.
    no_fit_cache: dict[tuple[Dimensions3D, float | None, tuple[OrientationCode, ...]], bool] = (
        field(default_factory=dict)
    )


def _dedupe_orientations(
    pairs: list[tuple[OrientationCode, Dimensions3D]],
) -> list[tuple[OrientationCode, Dimensions3D]]:
    """Élimine les orientations qui produisent des dimensions orientées IDENTIQUES (fréquent pour
    un carton dont deux arêtes sont égales, ex. base carrée) : `boxes_overlap`, `check_support` et
    `score_placement` ne dépendent que de `dims`, jamais du code d'orientation lui-même, donc deux
    orientations à `dims` identiques produisent EXACTEMENT le même candidat `(score, z, y, x, ...)`
    à un point donné, à l'exception de `code.value` (dernier élément du tie-break dans
    `try_place_on_pallet`). Ne conserver que l'orientation dont `code.value` est alphabétiquement le
    plus petit reproduit donc exactement le gagnant qu'aurait produit le tie-break existant — cette
    déduplication ne peut donc jamais changer un résultat, seulement le nombre de combinaisons
    (point × orientation) évaluées. Sans effet pour un carton dont les 3 arêtes sont distinctes."""
    best: dict[Dimensions3D, OrientationCode] = {}
    for code, dims in pairs:
        current = best.get(dims)
        if current is None or code.value < current.value:
            best[dims] = code
    return [(code, dims) for dims, code in best.items()]


def _points_close(a: Position3D, b: Position3D) -> bool:
    return (
        abs(a.x_mm - b.x_mm) <= EPSILON_MM
        and abs(a.y_mm - b.y_mm) <= EPSILON_MM
        and abs(a.z_mm - b.z_mm) <= EPSILON_MM
    )


def _cell_range(
    x0: float, x1: float, y0: float, y1: float, z0: float, z1: float
) -> tuple[int, int, int, int, int, int]:
    return (
        math.floor(x0 / GRID_CELL_MM),
        math.floor(x1 / GRID_CELL_MM),
        math.floor(y0 / GRID_CELL_MM),
        math.floor(y1 / GRID_CELL_MM),
        math.floor(z0 / GRID_CELL_MM),
        math.floor(z1 / GRID_CELL_MM),
    )


def _index_box(
    pallet: WorkingPallet, box_index: int, position: Position3D, dims: Dimensions3D
) -> None:
    """Enregistre le carton (déjà ajouté à `pallet.boxes`) dans chaque cellule 3D de la grille
    couverte par son volume RÉEL (sans marge de sécurité — la marge est appliquée côté requête dans
    `_nearby_boxes`, jamais ici, pour que l'index reste indépendant de la marge d'un éventuel futur
    candidat). L'indexation par Z (et pas seulement XY) est nécessaire : sur une palette où de
    nombreux petits cartons s'empilent dans la même empreinte au sol, un index purement XY
    renverrait presque tous les cartons de la palette à chaque requête, quel que soit le niveau
    interrogé."""
    ix0, ix1, iy0, iy1, iz0, iz1 = _cell_range(
        position.x_mm,
        position.x_mm + dims.length_mm,
        position.y_mm,
        position.y_mm + dims.width_mm,
        position.z_mm,
        position.z_mm + dims.height_mm,
    )
    for ix in range(ix0, ix1 + 1):
        for iy in range(iy0, iy1 + 1):
            for iz in range(iz0, iz1 + 1):
                pallet.grid.setdefault((ix, iy, iz), []).append(box_index)


def _nearby_boxes(
    pallet: WorkingPallet, point: Position3D, dims: Dimensions3D, margin_mm: float
) -> list[PlacedCarton]:
    """Sous-ensemble des cartons déjà placés dont le volume pourrait chevaucher ou supporter le
    candidat (point, dims) — réduction de candidats avant les tests géométriques EXACTS
    (`boxes_overlap`, `check_support`, `score_placement`), qui restent seuls responsables du
    résultat. `margin_mm` (calculé par l'appelant, voir `try_place_on_pallet`) doit couvrir le pire
    cas de marge nécessaire à CHACUN de ces trois usages ; appliquée ici sur les trois axes,
    y compris Z, pour ne jamais exclure à tort un carton dont le sommet touche exactement le
    candidat (cas `check_support`) à cause d'un simple alignement de bordure de cellule. Un
    box_index peut apparaître dans plusieurs cellules ; `seen` déduplique avant de renvoyer les
    objets `PlacedCarton`."""
    if not pallet.grid:
        return []
    x0 = point.x_mm - margin_mm
    x1 = point.x_mm + dims.length_mm + margin_mm
    y0 = point.y_mm - margin_mm
    y1 = point.y_mm + dims.width_mm + margin_mm
    z0 = point.z_mm - margin_mm
    z1 = point.z_mm + dims.height_mm + margin_mm
    ix0, ix1, iy0, iy1, iz0, iz1 = _cell_range(x0, x1, y0, y1, z0, z1)
    seen: set[int] = set()
    nearby: list[PlacedCarton] = []
    for ix in range(ix0, ix1 + 1):
        for iy in range(iy0, iy1 + 1):
            for iz in range(iz0, iz1 + 1):
                for box_index in pallet.grid.get((ix, iy, iz), ()):
                    if box_index not in seen:
                        seen.add(box_index)
                        nearby.append(pallet.boxes[box_index])
    return nearby


def add_placed_box(pallet: WorkingPallet, box: PlacedCarton) -> None:
    """Seul point d'entrée pour ajouter un carton placé à une palette : l'ajout à `pallet.boxes` et
    son indexation dans `pallet.grid` (voir `_nearby_boxes`) doivent rester atomiques, sous peine
    d'un carton présent dans `boxes` mais invisible de l'index spatial — ce qui ferait passer à tort
    des tests de collision/support à côté de lui. N'appeler `pallet.boxes.append(...)` nulle part
    ailleurs, y compris dans les tests qui construisent une `WorkingPallet` à la main."""
    pallet.boxes.append(box)
    _register_placement(pallet, box.position_mm, box.placed_dimensions_mm)
    # L'état de la palette vient de changer : tout échec mémoïsé dans `no_fit_cache` (voir
    # `try_place_on_pallet`) a été calculé pour l'ANCIEN état et n'est plus fiable — un nouvel
    # extreme point vient potentiellement d'apparaître là où l'ancien budget de points ne portait
    # pas. Vider entièrement plutôt que retirer sélectivement : correct par construction, et le
    # vidage lui-même est O(1) amorti face au coût d'une recherche complète évitée.
    pallet.no_fit_cache.clear()


def _register_placement(pallet: WorkingPallet, position: Position3D, dims: Dimensions3D) -> None:
    _index_box(pallet, len(pallet.boxes) - 1, position, dims)

    pallet.extreme_points = [p for p in pallet.extreme_points if not _points_close(p, position)]
    candidates = (
        Position3D(position.x_mm + dims.length_mm, position.y_mm, position.z_mm),
        Position3D(position.x_mm, position.y_mm + dims.width_mm, position.z_mm),
        Position3D(position.x_mm, position.y_mm, position.z_mm + dims.height_mm),
    )
    for candidate in candidates:
        if not any(_points_close(candidate, existing) for existing in pallet.extreme_points):
            pallet.extreme_points.append(candidate)
    if len(pallet.extreme_points) > MAX_EXTREME_POINTS:
        # Priorité de conservation en cas de dépassement du budget : garder les points les PLUS
        # HAUTS en premier (tri décroissant sur z), jamais les plus bas. Bug corrigé ici (le tri
        # était auparavant croissant, cf. historique) : une large première couche de petits cartons
        # génère des centaines de points bas (les interstices non encore comblés de cette couche),
        # qui submergeaient rapidement le budget de 400 et évinçaient les quelques points hauts
        # nécessaires pour démarrer une deuxième couche — la palette se retrouvait bloquée à 1-2
        # couches alors que la hauteur et le poids disponibles permettaient d'en empiler bien plus
        # (mesuré : jusqu'à 2x plus de palettes que nécessaire sur des commandes réelles composées
        # de nombreux petits cartons identiques). Les points bas restent nombreux et faciles à
        # régénérer à chaque nouveau placement ; les points hauts (qui ouvrent une nouvelle couche)
        # sont rares et doivent être protégés en priorité. L'ordre de tri n'affecte que QUELS
        # points survivent à la troncature, jamais le résultat d'une recherche de placement donnée :
        # celle-ci évalue tous les points restants et choisit le meilleur via un tie-break
        # déterministe complet, indépendant de l'ordre d'itération (voir `try_place_on_pallet`).
        pallet.extreme_points.sort(key=lambda p: (-p.z_mm, p.x_mm + p.y_mm))
        pallet.extreme_points = pallet.extreme_points[:MAX_EXTREME_POINTS]


def can_instance_ever_fit(
    instance: CartonInstance,
    spec: PalletSpec,
    options: OptimizationOptions,
    orientation_provider: OrientationProvider = py3dbp_adapter.oriented_dimensions,
) -> tuple[bool, RejectionCode | None]:
    """Faisabilité sur une palette VIDE. Distingue poids / rotation interdite / hauteur / bornes."""
    if (
        instance.weight_kg is not None
        and spec.max_weight_kg is not None
        and instance.weight_kg > spec.max_weight_kg + 1e-9
    ):
        return False, RejectionCode.WEIGHT_EXCEEDED

    max_x, max_y, max_z = spec.usable_length_mm, spec.usable_width_mm, spec.usable_height_mm
    allowed = allowed_orientations(instance, options.global_rotations_enabled)
    # `oriented_dimensions` est mémoïsée (voir py3dbp_adapter.py) : un ordre réel ne comporte
    # souvent qu'une poignée de dimensions distinctes répétées sur des milliers d'instances, donc
    # calculer une seule fois par orientation ici (plutôt que dans chaque boucle) évite des lookups
    # de cache et des allocations de tuple répétés pour rien.
    allowed_dims = _dedupe_orientations(
        [(code, orientation_provider(instance.dimensions_mm, code)) for code in allowed]
    )
    for _code, dims in allowed_dims:
        if (
            dims.length_mm <= max_x + EPSILON_MM
            and dims.width_mm <= max_y + EPSILON_MM
            and (dims.height_mm <= max_z + EPSILON_MM)
        ):
            return True, None

    any_fits_all = False
    any_fits_footprint_only = False
    all_dims = _dedupe_orientations(
        [
            (code, orientation_provider(instance.dimensions_mm, code))
            for code in py3dbp_adapter.ALL_ORIENTATIONS
        ]
    )
    for _code, dims in all_dims:
        fits_footprint = (
            dims.length_mm <= max_x + EPSILON_MM and dims.width_mm <= max_y + EPSILON_MM
        )
        if fits_footprint and dims.height_mm <= max_z + EPSILON_MM:
            any_fits_all = True
        if fits_footprint:
            any_fits_footprint_only = True

    if any_fits_all:
        return False, RejectionCode.ROTATION_FORBIDDEN
    if any_fits_footprint_only:
        return False, RejectionCode.HEIGHT_EXCEEDED
    return False, RejectionCode.DIMENSIONS_EXCEED_PALLET


def try_place_on_pallet(
    instance: CartonInstance,
    pallet: WorkingPallet,
    spec: PalletSpec,
    options: OptimizationOptions,
    orientation_provider: OrientationProvider = py3dbp_adapter.oriented_dimensions,
) -> PlacedCarton | None:
    """Meilleure position/orientation valide sur cette palette, ou None si aucune ne convient."""
    allowed = allowed_orientations(instance, options.global_rotations_enabled)
    # Un échec déjà confirmé pour ces dimensions/poids/orientations exactes CONTRE L'ÉTAT ACTUEL de
    # cette palette (voir `no_fit_cache` sur `WorkingPallet`, vidé au moindre changement d'état par
    # `add_placed_box`) restera un échec tant que rien n'a changé — le re-tester donnerait
    # exactement le même résultat, pour le même coût.
    cache_key = (instance.dimensions_mm, instance.weight_kg, allowed)
    if pallet.no_fit_cache.get(cache_key):
        return None

    if (
        spec.max_weight_kg is not None
        and instance.weight_kg is not None
        and pallet.total_weight_kg + instance.weight_kg > spec.max_weight_kg + 1e-9
    ):
        pallet.no_fit_cache[cache_key] = True
        return None

    max_x, max_y, max_z = spec.usable_length_mm, spec.usable_width_mm, spec.usable_height_mm
    # Calculées une seule fois par orientation, réutilisées pour tous les points candidats de
    # cette instance (une même instance a la même dimension d'origine, donc les mêmes dimensions
    # orientées, quel que soit le point testé) — voir la note de performance dans
    # `can_instance_ever_fit` ci-dessus. Dédupliquées par dimensions résultantes (voir
    # `_dedupe_orientations`) : un carton avec deux arêtes égales n'a souvent que 3 (voire 1)
    # dimensions orientées distinctes parmi les 6 codes, sans jamais changer le résultat.
    allowed_dims = _dedupe_orientations(
        [(code, orientation_provider(instance.dimensions_mm, code)) for code in allowed]
    )

    # `score_placement` compte les cartons de même SKU dont l'empreinte, dilatée de
    # `_ADJACENCY_DILATION_MM` (1mm, voir scoring.py), touche le candidat : la marge de requête
    # doit donc couvrir cette dilatation en plus de la marge de sécurité, pour que `nearby` reste
    # un sur-ensemble valide pour LES TROIS usages (collision, support, score) ci-dessous.
    query_margin_mm = max(spec.safety_gap_mm, 5.0)

    # Recherche best-first (branch-and-bound) : `check_support` et `score_placement` sont les
    # étapes coûteuses de cette boucle (mesuré : jusqu'à 50% du temps total sur les commandes qui
    # empilent des centaines de cartons quasi identiques sur la même palette, voir le profilage
    # qui a motivé cette optimisation). Chaque candidat qui passe les tests bon marché (bornes,
    # collision) reçoit d'abord une borne SUPÉRIEURE de score (`score_upper_bound`, sans support ni
    # adjacence). Triés par cette borne décroissante, les candidats sont ensuite évalués en détail
    # dans cet ordre ; dès qu'un candidat a une borne strictement inférieure au meilleur score déjà
    # CONFIRMÉ, lui et tous les suivants (bornes encore plus basses, par construction du tri) ne
    # peuvent plus gagner et sont écartés sans jamais appeler `check_support`/`score_placement`.
    # Le résultat est PROUVABLEMENT identique à une évaluation exhaustive : voir
    # `test_branch_and_bound_search_matches_exhaustive_search` (comparaison directe sur des ordres
    # aléatoires) et `scoring.py::score_upper_bound` pour la preuve d'admissibilité de la borne.
    cheap_candidates: list[
        tuple[float, Position3D, Dimensions3D, OrientationCode, list[PlacedCarton]]
    ] = []
    for point in pallet.extreme_points:
        for code, dims in allowed_dims:
            if not is_within_bounds(point, dims, max_x, max_y, max_z):
                continue
            nearby = _nearby_boxes(pallet, point, dims, query_margin_mm)
            if any(
                boxes_overlap(
                    point, dims, box.position_mm, box.placed_dimensions_mm, spec.safety_gap_mm
                )
                for box in nearby
            ):
                continue
            upper_bound = score_upper_bound(point, dims, len(nearby))
            cheap_candidates.append((upper_bound, point, dims, code, nearby))

    if not cheap_candidates:
        pallet.no_fit_cache[cache_key] = True
        return None

    cheap_candidates.sort(key=lambda c: c[0], reverse=True)

    best_key: tuple[float, float, float, float, str] | None = None
    best_position: Position3D | None = None
    best_dims: Dimensions3D | None = None
    best_orientation: OrientationCode | None = None
    best_score = 0.0
    for upper_bound, point, dims, code, nearby in cheap_candidates:
        if best_key is not None and upper_bound < -best_key[0]:
            break  # aucun candidat restant (bornes décroissantes) ne peut plus gagner ni égaler
        support = check_support(
            point,
            dims,
            instance.weight_kg,
            nearby,
            spec.minimum_support_ratio,
            options.fragile_max_weight_on_top_kg,
        )
        if not support.ok:
            continue
        score = score_placement(point, dims, support.support_ratio, instance.sku, nearby)
        key = (-score, point.z_mm, point.y_mm, point.x_mm, code.value)
        if best_key is None or key < best_key:
            best_key, best_position, best_dims, best_orientation, best_score = (
                key,
                point,
                dims,
                code,
                score,
            )

    if best_key is None:
        pallet.no_fit_cache[cache_key] = True
        return None

    assert best_position is not None and best_dims is not None and best_orientation is not None
    final_score, final_position, final_dims, final_orientation = (
        best_score,
        best_position,
        best_dims,
        best_orientation,
    )
    return PlacedCarton(
        instance_id=instance.instance_id,
        sku=instance.sku,
        original_dimensions_mm=instance.dimensions_mm,
        placed_dimensions_mm=final_dims,
        position_mm=final_position,
        orientation=final_orientation,
        pallet_index=0,
        placement_score=final_score,
        fragile=instance.fragile,
        stackable=instance.stackable,
        weight_kg=instance.weight_kg,
        max_supported_weight_kg=instance.max_supported_weight_kg,
        product_group=instance.product_group,
    )


def pack_with_strategy(
    instances: Sequence[CartonInstance],
    spec: PalletSpec,
    options: OptimizationOptions,
    orientation_provider: OrientationProvider = py3dbp_adapter.oriented_dimensions,
) -> tuple[list[WorkingPallet], list[UnplacedCarton]]:
    """Boucle multi-palettes déterministe (port de `packer.ts::packWithStrategy`).

    Pour chaque instance (déjà triée par l'appelant selon la stratégie) : tenter les palettes déjà
    ouvertes et compatibles (groupes) ; sinon, si une palette VIDE ne pourrait de toute façon pas
    l'accueillir, rejeter immédiatement (garde-fou anti-boucle infinie) ; sinon ouvrir une nouvelle
    palette, sur laquelle le placement est garanti de réussir.
    """
    open_pallets: list[WorkingPallet] = []
    unplaced: list[UnplacedCarton] = []

    for instance in instances:
        placed_on: WorkingPallet | None = None
        for index, pallet in enumerate(open_pallets):
            if not is_compatible_with_pallet(instance, pallet.instances):
                continue
            result = try_place_on_pallet(instance, pallet, spec, options, orientation_provider)
            if result is not None:
                placed = replace(result, pallet_index=index)
                add_placed_box(pallet, placed)
                pallet.instances.append(instance)
                if instance.weight_kg is not None:
                    pallet.total_weight_kg += instance.weight_kg
                placed_on = pallet
                break
        if placed_on is not None:
            continue

        fits, reason = can_instance_ever_fit(instance, spec, options, orientation_provider)
        if not fits:
            code = reason or RejectionCode.DIMENSIONS_EXCEED_PALLET
            unplaced.append(
                UnplacedCarton(
                    instance_id=instance.instance_id,
                    sku=instance.sku,
                    dimensions_mm=instance.dimensions_mm,
                    code=code,
                    message=REJECTION_MESSAGES[code],
                    weight_kg=instance.weight_kg,
                )
            )
            continue

        new_pallet = WorkingPallet()
        result = try_place_on_pallet(instance, new_pallet, spec, options, orientation_provider)
        if result is None:  # pragma: no cover - garde-fou : ne doit jamais se produire
            unplaced.append(
                UnplacedCarton(
                    instance_id=instance.instance_id,
                    sku=instance.sku,
                    dimensions_mm=instance.dimensions_mm,
                    code=RejectionCode.NO_STABLE_POSITION,
                    message=(
                        "Échec inattendu du placement sur une palette vide malgré un "
                        "pré-contrôle de faisabilité positif."
                    ),
                    weight_kg=instance.weight_kg,
                )
            )
            continue
        placed = replace(result, pallet_index=len(open_pallets))
        add_placed_box(new_pallet, placed)
        new_pallet.instances.append(instance)
        if instance.weight_kg is not None:
            new_pallet.total_weight_kg += instance.weight_kg
        open_pallets.append(new_pallet)

    return open_pallets, unplaced


# Au-delà de ce nombre d'instances, `pack_with_strategy_parallel` répartit le travail sur plusieurs
# processus plutôt que de tout traiter séquentiellement (voir sa docstring). En-dessous, le
# séquentiel est déjà rapide et le coût de démarrage de nouveaux processus (ré-import complet du
# paquet dans chacun, sous Windows) ne serait pas rentabilisé.
PARALLEL_BATCH_THRESHOLD = 3000


def _split_into_batches(
    instances: Sequence[CartonInstance], batch_count: int
) -> list[list[CartonInstance]]:
    if batch_count <= 1:
        return [list(instances)]
    batch_size = math.ceil(len(instances) / batch_count)
    if batch_size <= 0:
        return [list(instances)]
    return [list(instances[i : i + batch_size]) for i in range(0, len(instances), batch_size)]


def _reindex_pallets(pallets: list[WorkingPallet]) -> None:
    """Corrige `PlacedCarton.pallet_index` (exposé tel quel dans le contrat API, voir
    `contracts.py`) pour qu'il reflète la position FINALE de chaque palette dans `pallets`, après
    combinaison de plusieurs lots traités indépendamment (chaque lot recommence sa propre
    numérotation à partir de 0, voir `pack_with_strategy_parallel`)."""
    for index, pallet in enumerate(pallets):
        pallet.boxes = [
            box if box.pallet_index == index else replace(box, pallet_index=index)
            for box in pallet.boxes
        ]


def _combine_batch_results(
    batch_results: Sequence[tuple[list[WorkingPallet], list[UnplacedCarton]]],
    spec: PalletSpec,
    options: OptimizationOptions,
) -> tuple[list[WorkingPallet], list[UnplacedCarton]]:
    """Combine les résultats de plusieurs lots empaquetés indépendamment (voir
    `pack_with_strategy_parallel`) : conserve telles quelles les palettes déjà pleines de chaque
    lot, met de côté la dernière palette (potentiellement incomplète) de chaque lot multi-palette
    pour une passe de consolidation séquentielle commune, puis renumérote `pallet_index`. Extrait
    de `pack_with_strategy_parallel` pour être testable sans multiprocessing ni empaquetage réel."""
    full_pallets: list[WorkingPallet] = []
    tail_instances: list[CartonInstance] = []
    all_unplaced: list[UnplacedCarton] = []
    for pallets, unplaced in batch_results:
        all_unplaced.extend(unplaced)
        if not pallets:
            continue
        # Un lot qui ne produit qu'UNE SEULE palette n'a, par définition, aucune palette antérieure
        # "déjà pleine" à comparer : cette unique palette doit être gardée telle quelle, jamais
        # envoyée en reliquat. Le confondre avec un reliquat renverrait TOUTES les instances de ce
        # lot dans la passe de consolidation séquentielle (voir plus bas), annulant entièrement le
        # gain de parallélisme — exactement le cas des commandes à très forte densité par palette
        # (un article minuscule répété des milliers de fois : un seul lot suffit à remplir une
        # palette) qui ont motivé cette parallélisation en premier lieu.
        if len(pallets) == 1:
            full_pallets.extend(pallets)
            continue
        full_pallets.extend(pallets[:-1])
        tail_instances.extend(pallets[-1].instances)

    if tail_instances:
        consolidated_pallets, consolidated_unplaced = pack_with_strategy(
            tail_instances, spec, options
        )
        full_pallets.extend(consolidated_pallets)
        # Les instances de reliquat ont déjà été placées avec succès lors du premier passage (par
        # construction, elles viennent d'une palette qui les contenait) : un rejet ici serait
        # inattendu, mais on le propage plutôt que de le masquer silencieusement, par prudence.
        all_unplaced.extend(consolidated_unplaced)

    _reindex_pallets(full_pallets)
    return full_pallets, all_unplaced


def pack_with_strategy_parallel(
    instances: Sequence[CartonInstance],
    spec: PalletSpec,
    options: OptimizationOptions,
    max_workers: int | None = None,
) -> tuple[list[WorkingPallet], list[UnplacedCarton]]:
    """Variante de `pack_with_strategy` qui répartit une commande volumineuse sur plusieurs
    processus pour un gain de VITESSE réelle (parallélisme CPU, contourne le GIL), au prix d'un
    compromis explicite de compacité qu'une passe de consolidation cherche à limiter.

    Principe : diviser les instances (déjà triées par l'appelant) en `max_workers` lots contigus,
    empaqueter chaque lot INDÉPENDAMMENT et EN PARALLÈLE (chaque lot recommence sa propre séquence
    de palettes à partir de zéro, sans se coordonner avec les autres lots), puis consolider (voir
    `_combine_batch_results`). Traiter des lots indépendamment est nécessairement moins compact que
    tout traiter ensemble : chaque lot laisse sa propre dernière palette potentiellement incomplète,
    là où un traitement séquentiel unique n'en laisse qu'une seule au total. Cette consolidation ne
    peut jamais faire PIRE que de garder les reliquats séparés (au pire, elle retrouve le même
    nombre de palettes) et récupère typiquement une bonne partie de la perte de compacité.

    Aucune garantie de résultat IDENTIQUE au séquentiel (contrairement aux optimisations de
    `try_place_on_pallet`) : c'est un compromis compacité/vitesse assumé, réservé aux commandes
    dépassant `PARALLEL_BATCH_THRESHOLD`, où le séquentiel devient impraticable — voir les mesures
    de performance dans `backend/README.md`."""
    if max_workers is None or max_workers <= 1 or len(instances) < PARALLEL_BATCH_THRESHOLD:
        return pack_with_strategy(instances, spec, options)

    batches = _split_into_batches(instances, max_workers)
    if len(batches) <= 1:
        return pack_with_strategy(instances, spec, options)

    with ProcessPoolExecutor(max_workers=len(batches)) as executor:
        futures = [executor.submit(pack_with_strategy, batch, spec, options) for batch in batches]
        batch_results = [future.result() for future in futures]

    return _combine_batch_results(batch_results, spec, options)
