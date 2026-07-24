"""Tests à base de propriétés (Hypothesis) sur les invariants géométriques du moteur : quels que
soient les cartons générés aléatoirement, une solution ne doit jamais présenter de chevauchement,
de débordement, ni perdre ou dupliquer une instance."""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from palletizer.application.services import PalletizationService
from palletizer.domain.models import Dimensions3D, OrderLine
from palletizer.packing.validation import boxes_overlap, is_within_bounds
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
