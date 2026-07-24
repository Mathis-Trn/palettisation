"""Tests bas niveau du moteur de placement sur une seule palette (port des scénarios 10/11 de
`engine.test.ts` : `tryPlaceOnPallet` / `checkSupport`), distincts des tests de bout en bout du
service (`test_packing_service.py`) où un carton non plaçable sur une palette DÉJÀ OUVERTE
provoque l'ouverture d'une nouvelle palette plutôt qu'un rejet final."""

from palletizer.application.services import expand_order_lines
from palletizer.domain.models import Dimensions3D, Position3D
from palletizer.packing.adapter import WorkingPallet, try_place_on_pallet
from palletizer.packing.validation import check_support
from tests.unit.helpers import ROUTIER_SPEC, make_line, make_options


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
    pallet.boxes.append(placed_base)

    result = try_place_on_pallet(top_instance, pallet, ROUTIER_SPEC, make_options())
    assert result is None  # aucune position valide : le seul point libre est au-dessus du socle


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
