"""Tests à base de propriétés (Hypothesis) sur les invariants géométriques du moteur : quels que
soient les cartons générés aléatoirement, une solution ne doit jamais présenter de chevauchement,
de débordement, ni perdre ou dupliquer une instance."""

from dataclasses import replace

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from palletizer.application.services import PalletizationService, expand_order_lines, sort_instances
from palletizer.domain.enums import QUICK_STRATEGIES
from palletizer.domain.models import CartonInstance, Dimensions3D, OrderLine
from palletizer.packing.adapter import (
    WorkingPallet,
    _dedupe_orientations,
    _nearby_boxes,
    pack_with_strategy,
    try_place_on_pallet,
)
from palletizer.packing.constraints import allowed_orientations
from palletizer.packing.py3dbp_adapter import oriented_dimensions
from palletizer.packing.scoring import score_placement
from palletizer.packing.validation import boxes_overlap, check_support, is_within_bounds
from tests.unit.helpers import ROUTIER_SPEC, make_options, make_order

service = PalletizationService()

_small_dimension = st.integers(min_value=100, max_value=500)
_small_weight = st.floats(min_value=0.1, max_value=20.0, allow_nan=False, allow_infinity=False)


@st.composite
def _order_lines(draw: st.DrawFn) -> list[OrderLine]:
    count = draw(st.integers(min_value=1, max_value=4))
    lines = []
    for i in range(count):
        length = draw(_small_dimension)
        width = draw(_small_dimension)
        height = draw(_small_dimension)
        quantity = draw(st.integers(min_value=1, max_value=6))
        weight = draw(_small_weight)
        lines.append(
            OrderLine(
                line_number=i + 1,
                sku=f"SKU{i}",
                description=f"SKU{i}",
                quantity=quantity,
                unit="PIECE",
                dimensions_mm=Dimensions3D(length, width, height),
                weight_kg=weight,
                allow_rotation=draw(st.booleans()),
                upright_only=draw(st.booleans()),
                fragile=False,
                stackable=True,
            )
        )
    return lines


def _exhaustive_try_place_on_pallet(
    instance: CartonInstance,
    pallet: WorkingPallet,
    spec: object,
    options: object,
) -> tuple[object, object, object, float] | None:
    """Référence VOLONTAIREMENT naïve : réimplémentation de la recherche exhaustive
    (pré-optimisation best-first, voir `adapter.py::try_place_on_pallet`) qui évalue
    `check_support`/`score_placement` pour TOUS les candidats valides, sans élagage. Utilisée
    uniquement pour prouver, par comparaison directe, que la version optimisée (avec élagage par
    borne supérieure) renvoie exactement le même gagnant qu'une évaluation exhaustive — jamais
    utilisée par le moteur lui-même."""
    if (
        spec.max_weight_kg is not None  # type: ignore[attr-defined]
        and instance.weight_kg is not None
        and pallet.total_weight_kg + instance.weight_kg > spec.max_weight_kg + 1e-9  # type: ignore[attr-defined]
    ):
        return None
    allowed = allowed_orientations(instance, options.global_rotations_enabled)  # type: ignore[attr-defined]
    allowed_dims = _dedupe_orientations(
        [(code, oriented_dimensions(instance.dimensions_mm, code)) for code in allowed]
    )
    max_x, max_y, max_z = (
        spec.usable_length_mm,  # type: ignore[attr-defined]
        spec.usable_width_mm,  # type: ignore[attr-defined]
        spec.usable_height_mm,  # type: ignore[attr-defined]
    )
    query_margin_mm = max(spec.safety_gap_mm, 5.0)  # type: ignore[attr-defined]
    candidates = []
    for point in pallet.extreme_points:
        for code, dims in allowed_dims:
            if not is_within_bounds(point, dims, max_x, max_y, max_z):
                continue
            nearby = _nearby_boxes(pallet, point, dims, query_margin_mm)
            if any(
                boxes_overlap(
                    point, dims, box.position_mm, box.placed_dimensions_mm, spec.safety_gap_mm
                )  # type: ignore[attr-defined]
                for box in nearby
            ):
                continue
            support = check_support(
                point,
                dims,
                instance.weight_kg,
                nearby,
                spec.minimum_support_ratio,  # type: ignore[attr-defined]
                options.fragile_max_weight_on_top_kg,  # type: ignore[attr-defined]
            )
            if not support.ok:
                continue
            score = score_placement(point, dims, support.support_ratio, instance.sku, nearby)
            candidates.append(
                (score, point.z_mm, point.y_mm, point.x_mm, code.value, point, dims, code)
            )
    if not candidates:
        return None
    best = min(candidates, key=lambda c: (-c[0], c[1], c[2], c[3], c[4]))
    score, _, _, _, _, position, dims, orientation = best
    return position, dims, orientation, score


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_order_lines(), _order_lines())
def test_branch_and_bound_search_matches_exhaustive_search(
    build_lines: list[OrderLine], probe_lines: list[OrderLine]
) -> None:
    """`try_place_on_pallet` élague les candidats via une borne supérieure de score
    (`scoring.py::score_upper_bound`) au lieu d'évaluer exhaustivement chaque position — voir la
    docstring de `try_place_on_pallet`. Ce test compare directement son résultat à une
    réimplémentation exhaustive volontairement naïve, sur des palettes construites à partir
    d'ordres aléatoires : le gagnant (position, dimensions, orientation, score) doit être
    identique dans TOUS les cas, sinon l'élagage aurait exclu à tort un candidat valide."""
    build_instances, _ = expand_order_lines(build_lines)
    ordered = sort_instances(build_instances, QUICK_STRATEGIES[0])
    pallets, _ = pack_with_strategy(ordered, ROUTIER_SPEC, make_options())

    probe_instances, _ = expand_order_lines(probe_lines)

    for pallet in pallets[:2]:
        for probe in probe_instances[:2]:
            actual = try_place_on_pallet(probe, pallet, ROUTIER_SPEC, make_options())
            reference = _exhaustive_try_place_on_pallet(probe, pallet, ROUTIER_SPEC, make_options())
            if reference is None:
                assert actual is None
            else:
                ref_position, ref_dims, ref_orientation, ref_score = reference
                assert actual is not None
                assert actual.position_mm == ref_position
                assert actual.placed_dimensions_mm == ref_dims
                assert actual.orientation == ref_orientation
                assert abs(actual.placement_score - ref_score) < 1e-9


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_order_lines())
def test_no_overlap_and_within_bounds_for_random_small_orders(lines: list[OrderLine]) -> None:
    order = make_order(lines)
    result = service.optimize(order, ROUTIER_SPEC, make_options())

    for pallet in result.pallets:
        boxes = list(pallet.placed_cartons)
        max_x = pallet.spec.usable_length_mm
        max_y = pallet.spec.usable_width_mm
        max_z = pallet.spec.usable_height_mm
        for i, box in enumerate(boxes):
            assert is_within_bounds(box.position_mm, box.placed_dimensions_mm, max_x, max_y, max_z)
            for other in boxes[i + 1 :]:
                assert not boxes_overlap(
                    box.position_mm,
                    box.placed_dimensions_mm,
                    other.position_mm,
                    other.placed_dimensions_mm,
                    pallet.spec.safety_gap_mm,
                )


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_order_lines())
def test_every_instance_is_placed_or_rejected_exactly_once(lines: list[OrderLine]) -> None:
    order = make_order(lines)
    result = service.optimize(order, ROUTIER_SPEC, make_options())
    assert result.placed_cartons_count + result.unplaced_cartons_count == result.total_cartons_count

    all_ids = [box.instance_id for pallet in result.pallets for box in pallet.placed_cartons] + [
        u.instance_id for u in result.unplaced_cartons
    ]
    assert len(all_ids) == len(set(all_ids))


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    _order_lines(), st.floats(min_value=0.0, max_value=40.0, allow_nan=False, allow_infinity=False)
)
def test_no_overlap_with_nonzero_safety_gap(lines: list[OrderLine], safety_gap_mm: float) -> None:
    """Couvre l'index spatial (`packing/adapter.py::_nearby_boxes`) avec une marge de sécurité non
    nulle : c'est précisément le cas où un bug de marge dans la réduction de candidats pourrait
    exclure à tort un carton que le test géométrique exact aurait dû comparer. `safety_gap_mm=0`
    (déjà couvert par `ROUTIER_SPEC` dans les autres tests de ce module) est le cas le plus simple ;
    celui-ci exerce spécifiquement le calcul de marge décrit dans `_nearby_boxes`."""
    spec = replace(ROUTIER_SPEC, safety_gap_mm=safety_gap_mm)
    order = make_order(lines)
    result = service.optimize(order, spec, make_options())

    for pallet in result.pallets:
        boxes = list(pallet.placed_cartons)
        for i, box in enumerate(boxes):
            for other in boxes[i + 1 :]:
                assert not boxes_overlap(
                    box.position_mm,
                    box.placed_dimensions_mm,
                    other.position_mm,
                    other.placed_dimensions_mm,
                    safety_gap_mm,
                )


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(_order_lines())
def test_determinism_holds_for_random_orders(lines: list[OrderLine]) -> None:
    order = make_order(lines)
    first = service.optimize(order, ROUTIER_SPEC, make_options())
    second = service.optimize(order, ROUTIER_SPEC, make_options())

    def fingerprint(result):  # type: ignore[no-untyped-def]
        return [
            [(box.instance_id, box.position_mm, box.orientation) for box in pallet.placed_cartons]
            for pallet in result.pallets
        ], sorted(u.instance_id for u in result.unplaced_cartons)

    assert fingerprint(first) == fingerprint(second)
