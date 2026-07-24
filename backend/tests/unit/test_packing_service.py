from palletizer.application.services import PalletizationService
from palletizer.domain.enums import OptimizationLevel, RejectionCode
from palletizer.domain.models import Dimensions3D
from palletizer.packing.validation import boxes_overlap, is_within_bounds
from tests.unit.helpers import ROUTIER_SPEC, make_line, make_options, make_order

service = PalletizationService()


def _assert_no_overlap_and_within_bounds(result) -> None:  # type: ignore[no-untyped-def]
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


def test_single_carton_places_on_one_pallet() -> None:
    order = make_order([make_line(quantity=1)])
    result = service.optimize(order, ROUTIER_SPEC, make_options())
    assert result.pallets_count == 1
    assert result.placed_cartons_count == 1
    assert result.unplaced_cartons_count == 0
    _assert_no_overlap_and_within_bounds(result)


def test_exact_fit_then_overflow_opens_second_pallet() -> None:
    # 600x400x239mm cartons, height already the smallest axis (so LWH/WLH uniquely minimize the
    # scoring height penalty : no tipping incentive). Usable volume = 1200x800x956 ->
    # 2x2x4 = 16 cartons fill exactly one pallet; a 17th must overflow to a second pallet.
    line = make_line(length=600, width=400, height=239, quantity=16, weight_kg=5)
    result = service.optimize(make_order([line]), ROUTIER_SPEC, make_options())
    assert result.pallets_count == 1
    assert result.placed_cartons_count == 16
    assert abs(result.pallets[0].volume_usage_ratio - 1.0) < 1e-9
    _assert_no_overlap_and_within_bounds(result)

    line17 = make_line(length=600, width=400, height=239, quantity=17, weight_kg=5)
    result17 = service.optimize(make_order([line17]), ROUTIER_SPEC, make_options())
    assert result17.pallets_count == 2
    assert result17.placed_cartons_count == 17
    _assert_no_overlap_and_within_bounds(result17)


def test_multi_sku_thorough_mode_keeps_invariants() -> None:
    lines = [
        make_line(
            sku="A", length=300, width=200, height=150, quantity=15, weight_kg=2, line_number=1
        ),
        make_line(
            sku="B", length=250, width=250, height=200, quantity=12, weight_kg=3, line_number=2
        ),
        make_line(
            sku="C", length=200, width=150, height=100, quantity=20, weight_kg=1, line_number=3
        ),
    ]
    result = service.optimize(
        make_order(lines), ROUTIER_SPEC, make_options(optimization_level=OptimizationLevel.THOROUGH)
    )
    assert result.total_cartons_count == 47
    assert result.placed_cartons_count + result.unplaced_cartons_count == 47
    _assert_no_overlap_and_within_bounds(result)


def test_height_exceeded_rejection() -> None:
    line = make_line(length=1000, width=700, height=2000, quantity=1)
    result = service.optimize(make_order([line]), ROUTIER_SPEC, make_options())
    assert result.placed_cartons_count == 0
    assert result.unplaced_cartons[0].code == RejectionCode.HEIGHT_EXCEEDED


def test_weight_exceeded_rejection() -> None:
    line = make_line(length=300, width=300, height=300, quantity=1, weight_kg=900)
    result = service.optimize(make_order([line]), ROUTIER_SPEC, make_options())
    assert result.placed_cartons_count == 0
    assert result.unplaced_cartons[0].code == RejectionCode.WEIGHT_EXCEEDED


def test_rotation_allowed_vs_forbidden() -> None:
    # 900x1000x200 doesn't fit as LWH (footprint 900x1000 > 1200x800 usable on the width axis)
    # but fits once rotated (e.g. WLH: footprint 1000x900 -> still no; some orientation with
    # footprint <=1200x800 does exist and is only reachable when rotation is allowed).
    line_allowed = make_line(length=900, width=1000, height=200, quantity=1, allow_rotation=True)
    result_allowed = service.optimize(make_order([line_allowed]), ROUTIER_SPEC, make_options())
    assert result_allowed.placed_cartons_count == 1

    line_forbidden = make_line(length=900, width=1000, height=200, quantity=1, allow_rotation=False)
    result_forbidden = service.optimize(make_order([line_forbidden]), ROUTIER_SPEC, make_options())
    assert result_forbidden.placed_cartons_count == 0
    assert result_forbidden.unplaced_cartons[0].code == RejectionCode.ROTATION_FORBIDDEN


def test_upright_only_restricts_orientations() -> None:
    line = make_line(
        length=900, width=1000, height=200, quantity=1, allow_rotation=True, upright_only=True
    )
    result = service.optimize(make_order([line]), ROUTIER_SPEC, make_options())
    # Only LWH/WLH tested; neither fits within an 1200x800 footprint for these dims -> rejected.
    assert result.placed_cartons_count == 0


def test_oversized_in_every_orientation() -> None:
    line = make_line(length=5000, width=5000, height=5000, quantity=1)
    result = service.optimize(make_order([line]), ROUTIER_SPEC, make_options())
    assert result.unplaced_cartons[0].code == RejectionCode.DIMENSIONS_EXCEED_PALLET


def test_determinism_same_input_same_output() -> None:
    lines = [
        make_line(
            sku="A", length=300, width=200, height=150, quantity=10, weight_kg=2, line_number=1
        ),
        make_line(
            sku="B", length=250, width=250, height=200, quantity=9, weight_kg=3, line_number=2
        ),
    ]
    order = make_order(lines)
    result1 = service.optimize(order, ROUTIER_SPEC, make_options())
    result2 = service.optimize(order, ROUTIER_SPEC, make_options())

    def fingerprint(result):  # type: ignore[no-untyped-def]
        return [
            [(box.instance_id, box.position_mm, box.orientation) for box in pallet.placed_cartons]
            for pallet in result.pallets
        ], sorted(u.instance_id for u in result.unplaced_cartons)

    assert fingerprint(result1) == fingerprint(result2)


def test_volume_accounting_exact() -> None:
    line = make_line(length=600, width=400, height=239, quantity=16, weight_kg=5)
    result = service.optimize(make_order([line]), ROUTIER_SPEC, make_options())
    pallet = result.pallets[0]
    assert pallet.usable_volume_mm3 == 1200 * 800 * 956
    assert pallet.volume_used_mm3 == 16 * (600 * 400 * 239)
    assert abs(pallet.volume_usage_ratio - 1.0) < 1e-9


def test_non_stackable_base_forces_a_new_pallet_rather_than_rejection() -> None:
    # A lone carton always fits on a fresh empty pallet (support at z=0 is trivially ok), so a
    # stacking conflict on an already-open pallet must open a NEW pallet, never a final rejection.
    base = make_line(
        sku="BASE", length=1200, width=800, height=200, quantity=1, stackable=False, line_number=1
    )
    top = make_line(sku="TOP", length=1200, width=800, height=200, quantity=1, line_number=2)
    result = service.optimize(make_order([base, top]), ROUTIER_SPEC, make_options())
    assert result.pallets_count == 2
    assert result.placed_cartons_count == 2
    assert result.unplaced_cartons_count == 0
    _assert_no_overlap_and_within_bounds(result)


def test_fragile_weight_on_top_forces_a_new_pallet_rather_than_rejection() -> None:
    base = make_line(
        sku="FRAGILE", length=1200, width=800, height=200, quantity=1, fragile=True, line_number=1
    )
    heavy_top = make_line(
        sku="HEAVY", length=1200, width=800, height=200, quantity=1, weight_kg=50, line_number=2
    )
    result = service.optimize(
        make_order([base, heavy_top]), ROUTIER_SPEC, make_options(fragile_max_weight_on_top_kg=0.0)
    )
    assert result.pallets_count == 2
    assert result.placed_cartons_count == 2
    assert result.unplaced_cartons_count == 0


def test_incompatible_groups_open_new_pallet_instead_of_rejecting() -> None:
    a = make_line(
        sku="A",
        length=1200,
        width=800,
        height=500,
        quantity=1,
        product_group="chimie",
        incompatible_groups=("alimentaire",),
        line_number=1,
    )
    b = make_line(
        sku="B",
        length=1200,
        width=800,
        height=500,
        quantity=1,
        product_group="alimentaire",
        line_number=2,
    )
    result = service.optimize(make_order([a, b]), ROUTIER_SPEC, make_options())
    assert result.pallets_count == 2
    assert result.placed_cartons_count == 2
    assert result.unplaced_cartons_count == 0


def test_all_instances_accounted_for() -> None:
    lines = [
        make_line(sku="A", length=300, width=200, height=150, quantity=5, line_number=1),
        make_line(sku="OVER", length=5000, width=5000, height=5000, quantity=2, line_number=2),
    ]
    result = service.optimize(make_order(lines), ROUTIER_SPEC, make_options())
    assert result.total_cartons_count == 7
    assert result.placed_cartons_count + result.unplaced_cartons_count == 7


def test_result_passes_independent_validation_without_raising() -> None:
    # optimize() itself already calls validate_optimization_result internally and would raise
    # SolutionValidationError on any anomaly; a successful call is itself the assertion.
    lines = [make_line(sku="A", quantity=3, line_number=1)]
    service.optimize(make_order(lines), ROUTIER_SPEC, make_options())


def test_zero_quantity_line_rejected_as_invalid_without_blocking_others() -> None:
    good = make_line(sku="GOOD", quantity=2, line_number=1)
    bad = make_line(sku="BAD", quantity=0, line_number=2)
    result = service.optimize(make_order([good, bad]), ROUTIER_SPEC, make_options())
    assert result.placed_cartons_count == 2
    assert any(u.code == RejectionCode.INVALID_DATA for u in result.unplaced_cartons)


def test_dimensions3d_rejects_non_positive_values() -> None:
    import pytest

    with pytest.raises(ValueError):
        Dimensions3D(0, 10, 10)


def test_no_hang_when_nothing_fits_at_all() -> None:
    line = make_line(length=99999, width=99999, height=99999, quantity=100)
    result = service.optimize(make_order([line]), ROUTIER_SPEC, make_options())
    assert result.pallets_count == 0
    assert result.unplaced_cartons_count == 100
