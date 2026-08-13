"""Tests bas niveau du moteur de placement sur une seule palette (port des scénarios 10/11 de
`engine.test.ts` : `tryPlaceOnPallet` / `checkSupport`), distincts des tests de bout en bout du
service (`test_packing_service.py`) où un carton non plaçable sur une palette DÉJÀ OUVERTE
provoque l'ouverture d'une nouvelle palette plutôt qu'un rejet final."""

from palletizer.application.services import expand_order_lines
from palletizer.domain.enums import OrientationCode
from palletizer.domain.models import CartonInstance, Dimensions3D, PlacedCarton, Position3D
from palletizer.packing.adapter import (
    MAX_EXTREME_POINTS,
    WorkingPallet,
    _combine_batch_results,
    add_placed_box,
    try_place_on_pallet,
)
from palletizer.packing.validation import check_support
from tests.unit.helpers import ROUTIER_SPEC, make_line, make_options


def _fake_instance(instance_id: str, sku: str = "SKU") -> CartonInstance:
    return CartonInstance(
        instance_id=instance_id,
        sku=sku,
        line_number=1,
        dimensions_mm=Dimensions3D(100, 100, 100),
        weight_kg=1.0,
        allow_rotation=True,
        upright_only=False,
        fragile=False,
        stackable=True,
    )


def _fake_placed_box(
    instance: CartonInstance, pallet_index: int, x_mm: float = 0.0
) -> PlacedCarton:
    return PlacedCarton(
        instance_id=instance.instance_id,
        sku=instance.sku,
        original_dimensions_mm=instance.dimensions_mm,
        placed_dimensions_mm=instance.dimensions_mm,
        position_mm=Position3D(x_mm, 0.0, 0.0),
        orientation=OrientationCode.LWH,
        pallet_index=pallet_index,
        placement_score=0.0,
        fragile=False,
        stackable=True,
        weight_kg=instance.weight_kg,
    )


def _one_instance(line):  # type: ignore[no-untyped-def]
    instances, invalid = expand_order_lines([line])
    assert not invalid
    return instances[0]


def test_try_place_on_pallet_rejects_stacking_on_non_stackable_base() -> None:
    base_line = make_line(
        sku="BASE", length=1200, width=800, height=200, quantity=1, stackable=False, line_number=1
    )
    top_line = make_line(sku="TOP", length=1200, width=800, height=200, quantity=1, line_number=2)
    base_instance = _one_instance(base_line)
    top_instance = _one_instance(top_line)

    pallet = WorkingPallet()
    placed_base = try_place_on_pallet(base_instance, pallet, ROUTIER_SPEC, make_options())
    assert placed_base is not None
    add_placed_box(pallet, placed_base)

    result = try_place_on_pallet(top_instance, pallet, ROUTIER_SPEC, make_options())
    assert result is None  # aucune position valide : le seul point libre est au-dessus du socle


def test_extreme_point_truncation_keeps_high_points_over_low_ones() -> None:
    """Régression : quand le nombre de points de placement candidats dépasse `MAX_EXTREME_POINTS`,
    la troncature doit conserver en priorité les points les plus HAUTS (nécessaires pour démarrer
    une nouvelle couche), jamais les plus bas. Bug historique : le tri de troncature était croissant
    sur z, donc favorisait les points bas — une large première couche de petits cartons identiques
    génère bien plus de points bas (les interstices non encore comblés) que de points hauts,
    évinçant systématiquement les rares points hauts avant même qu'une deuxième couche ne puisse
    démarrer. Mesuré sur un ordre réel : jusqu'à 2x plus de palettes que nécessaire. Ce test cible
    le mécanisme de troncature directement (sans recherche de placement complète), pour rester
    rapide."""
    pallet = WorkingPallet()
    low_points = [Position3D(float(i) * 5, 0.0, 0.0) for i in range(MAX_EXTREME_POINTS + 10)]
    high_point = Position3D(50_000.0, 50_000.0, 500.0)
    pallet.extreme_points = [*low_points, high_point]

    dummy_box = PlacedCarton(
        instance_id="dummy",
        sku="DUMMY",
        original_dimensions_mm=Dimensions3D(10, 10, 10),
        placed_dimensions_mm=Dimensions3D(10, 10, 10),
        position_mm=Position3D(-100_000.0, -100_000.0, -100_000.0),
        orientation=OrientationCode.LWH,
        pallet_index=0,
        placement_score=0.0,
        fragile=False,
        stackable=True,
    )
    add_placed_box(pallet, dummy_box)

    assert len(pallet.extreme_points) == MAX_EXTREME_POINTS
    assert any(p.z_mm == 500.0 for p in pallet.extreme_points)


def test_check_support_ratio_below_minimum_is_rejected() -> None:
    base = Position3D(0, 0, 0)
    base_dims = Dimensions3D(600, 400, 200)
    # Candidate shifted by half its own footprint on X -> ~50% overlap with the single support box.
    candidate_pos = Position3D(300, 0, 200)
    candidate_dims = Dimensions3D(600, 400, 200)
    from palletizer.domain.enums import OrientationCode
    from palletizer.domain.models import PlacedCarton

    existing = [
        PlacedCarton(
            instance_id="base",
            sku="BASE",
            original_dimensions_mm=base_dims,
            placed_dimensions_mm=base_dims,
            position_mm=base,
            orientation=OrientationCode.LWH,
            pallet_index=0,
            placement_score=0.0,
            fragile=False,
            stackable=True,
            weight_kg=5.0,
        )
    ]
    result = check_support(candidate_pos, candidate_dims, 5.0, existing, 0.8, 0.0)
    assert not result.ok
    assert abs(result.support_ratio - 0.5) < 1e-9

    full_overlap = check_support(Position3D(0, 0, 200), candidate_dims, 5.0, existing, 0.8, 0.0)
    assert full_overlap.ok
    assert abs(full_overlap.support_ratio - 1.0) < 1e-9


def test_check_support_fragility_weight_on_top() -> None:
    from palletizer.domain.enums import OrientationCode
    from palletizer.domain.models import PlacedCarton

    dims = Dimensions3D(600, 400, 200)
    fragile_base = [
        PlacedCarton(
            instance_id="fragile",
            sku="F",
            original_dimensions_mm=dims,
            placed_dimensions_mm=dims,
            position_mm=Position3D(0, 0, 0),
            orientation=OrientationCode.LWH,
            pallet_index=0,
            placement_score=0.0,
            fragile=True,
            stackable=True,
            weight_kg=5.0,
        )
    ]
    too_heavy = check_support(
        Position3D(0, 0, 200), dims, 10.0, fragile_base, 0.8, fragile_max_weight_on_top_kg=0.0
    )
    assert not too_heavy.ok

    light_enough = check_support(
        Position3D(0, 0, 200), dims, 0.0, fragile_base, 0.8, fragile_max_weight_on_top_kg=0.0
    )
    assert light_enough.ok


def test_combine_batch_results_keeps_single_pallet_batches_without_consolidation() -> None:
    """Régression : un lot qui ne produit qu'UNE SEULE palette ne doit jamais être envoyé en
    reliquat de consolidation (voir la docstring de `_combine_batch_results` dans
    `packing/adapter.py`). Bug historique : confondre cette unique palette avec un "reliquat"
    renvoyait TOUTES les instances du lot dans la passe de consolidation séquentielle, annulant
    entièrement le gain de parallélisme (`pack_with_strategy_parallel`) — exactement le cas des
    commandes à très forte densité par palette qui ont motivé cette parallélisation. Ce test
    construit directement deux lots à une palette chacun (sans empaquetage réel) et vérifie qu'ils
    sont conservés TELS QUELS : mêmes objets palette, mêmes instances, seul `pallet_index` est
    renuméroté pour refléter la position finale."""
    instance_a1 = _fake_instance("A1")
    instance_a2 = _fake_instance("A2")
    pallet_a = WorkingPallet(instances=[instance_a1, instance_a2])
    add_placed_box(pallet_a, _fake_placed_box(instance_a1, pallet_index=0, x_mm=0.0))
    add_placed_box(pallet_a, _fake_placed_box(instance_a2, pallet_index=0, x_mm=200.0))

    instance_b1 = _fake_instance("B1")
    pallet_b = WorkingPallet(instances=[instance_b1])
    add_placed_box(pallet_b, _fake_placed_box(instance_b1, pallet_index=0, x_mm=0.0))

    batch_results = [([pallet_a], []), ([pallet_b], [])]
    combined_pallets, unplaced = _combine_batch_results(batch_results, ROUTIER_SPEC, make_options())

    assert unplaced == []
    assert len(combined_pallets) == 2  # aucune consolidation : chaque lot gardé tel quel
    assert combined_pallets[0] is pallet_a
    assert combined_pallets[1] is pallet_b
    assert {box.instance_id for box in combined_pallets[0].boxes} == {"A1", "A2"}
    assert {box.instance_id for box in combined_pallets[1].boxes} == {"B1"}
    # pallet_index renuméroté pour refléter la position finale (le lot B recommençait à 0)
    assert all(box.pallet_index == 0 for box in combined_pallets[0].boxes)
    assert all(box.pallet_index == 1 for box in combined_pallets[1].boxes)


def test_combine_batch_results_consolidates_multi_pallet_batch_tail() -> None:
    """La dernière palette d'un lot à PLUSIEURS palettes est bien mise de côté et repassée par la
    consolidation séquentielle, tandis que la/les palette(s) précédente(s) de ce même lot (déjà
    pleines) sont conservées telles quelles — contrepartie du test ci-dessus, qui vérifie que ce
    même mécanisme NE s'applique PAS à un lot à une seule palette."""
    full_instance = _fake_instance("FULL", sku="FULL")
    pallet_full = WorkingPallet(instances=[full_instance])
    add_placed_box(pallet_full, _fake_placed_box(full_instance, pallet_index=0))

    tail_instance = _fake_instance("TAIL", sku="TAIL")
    pallet_tail = WorkingPallet(instances=[tail_instance])
    add_placed_box(pallet_tail, _fake_placed_box(tail_instance, pallet_index=1))

    batch_results = [([pallet_full, pallet_tail], [])]
    combined_pallets, unplaced = _combine_batch_results(batch_results, ROUTIER_SPEC, make_options())

    assert unplaced == []
    all_ids = {box.instance_id for pallet in combined_pallets for box in pallet.boxes}
    assert all_ids == {"FULL", "TAIL"}
    # la palette non-dernière du lot est conservée telle quelle (même objet)
    assert combined_pallets[0] is pallet_full
    # la palette "tail" a bien été reconsolidée séquentiellement (nouvelle palette, pas l'originale)
    assert not any(p is pallet_tail for p in combined_pallets)


def test_flat_carton_fills_current_layer_before_stacking() -> None:
    """Régression : un carton PLAT (hauteur très petite devant l'empreinte de la palette) doit
    remplir la couche courante avant d'en démarrer une nouvelle, jamais l'inverse.

    Bug réel : le poids de la distance à l'origine dans `scoring.py::score_placement`
    (`_ORIGIN_DISTANCE_WEIGHT`, historiquement -0.05) coûte jusqu'à -0.05*(1200+800)=-100 points
    pour rejoindre le coin opposé du plancher d'une palette 1200x800mm — largement plus que le
    coût d'empiler PLUSIEURS couches supplémentaires d'un carton de 15mm de haut (-1.0*15=-15 par
    couche). Le moteur préférait donc construire une pyramide décroissante près du coin d'origine
    plutôt que de terminer la couche courante (mesuré sur un ordre réel : 146/189 cartons sur la
    couche 0 avant bascule, puis 40, 12, 1, 1 — une pyramide au lieu d'un pavage plat). Corrigé en
    réduisant ce poids à -0.0005, où même le pire écart de distance ne pèse plus qu'1 point,
    négligeable face à toute différence de hauteur réaliste. Ce test répète l'ordre réel qui a
    révélé le bug (carton 55x85x15mm, palette 1200x800mm) et vérifie que la couche 0 se remplit
    presque intégralement avant qu'un carton n'atterrisse sur la couche 1."""
    flat_line = make_line(
        sku="FLAT", length=55, width=85, height=15, quantity=200, weight_kg=0.8, line_number=1
    )
    instances, invalid = expand_order_lines([flat_line])
    assert not invalid

    pallet = WorkingPallet()
    for instance in instances:
        placed = try_place_on_pallet(instance, pallet, ROUTIER_SPEC, make_options())
        assert placed is not None
        add_placed_box(pallet, placed)

    ground_layer_count = sum(1 for box in pallet.boxes if box.position_mm.z_mm <= 1e-6)
    # Le pavage théorique maximal de cette empreinte sur ce carton est de 189 (21x9, voir le
    # diagnostic) ; avant correction, la couche 0 s'arrêtait à 146 (77 %). On exige ici une bien
    # meilleure occupation de la couche 0, sans figer le test sur la valeur exacte 189.
    assert ground_layer_count >= 180, (
        f"couche 0 sous-remplie ({ground_layer_count} cartons) : le moteur a probablement "
        "recommencé à empiler en pyramide au lieu de terminer le pavage du plancher"
    )
