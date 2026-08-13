from palletizer.domain.enums import UPRIGHT_ORIENTATIONS, OrientationCode
from palletizer.domain.models import Dimensions3D
from palletizer.packing.py3dbp_adapter import (
    ALL_ORIENTATIONS,
    ROTATION_TYPE_TO_ORIENTATION,
    oriented_dimensions,
)


def test_rotation_table_is_a_bijection_onto_all_six_orientation_codes() -> None:
    assert set(ROTATION_TYPE_TO_ORIENTATION.values()) == set(OrientationCode)
    assert len(ROTATION_TYPE_TO_ORIENTATION) == 6


def test_oriented_dimensions_matches_expected_axis_permutation() -> None:
    dims = Dimensions3D(length_mm=100, width_mm=200, height_mm=300)
    expected = {
        OrientationCode.LWH: (100, 200, 300),
        OrientationCode.WLH: (200, 100, 300),
        OrientationCode.LHW: (100, 300, 200),
        OrientationCode.HWL: (300, 200, 100),
        OrientationCode.WHL: (200, 300, 100),
        OrientationCode.HLW: (300, 100, 200),
    }
    for code, (length, width, height) in expected.items():
        result = oriented_dimensions(dims, code)
        assert (result.length_mm, result.width_mm, result.height_mm) == (length, width, height), (
            code
        )


def test_upright_orientations_keep_original_height_vertical() -> None:
    dims = Dimensions3D(length_mm=111, width_mm=222, height_mm=333)
    for code in UPRIGHT_ORIENTATIONS:
        assert oriented_dimensions(dims, code).height_mm == 333


def test_all_orientations_declared_exactly_once() -> None:
    assert len(ALL_ORIENTATIONS) == 6
    assert set(ALL_ORIENTATIONS) == set(OrientationCode)
