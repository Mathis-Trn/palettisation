from palletizer.domain.models import PalletToLoad, VehicleConfig
from palletizer.packing.transport_packer import compute_transport_load

TRUCK = VehicleConfig(
    name="Camion 13.6m",
    inner_length_mm=13600,
    inner_width_mm=2480,
    inner_height_mm=2700,
    max_payload_kg=24000,
    allow_pallet_rotation_floor=True,
    allow_pallet_stacking=False,
)


def _pallet(
    index: int, length: float = 1200, width: float = 800, height: float = 1000, weight: float = 300
) -> PalletToLoad:
    return PalletToLoad(
        pallet_result_index=index,
        footprint_length_mm=length,
        footprint_width_mm=width,
        height_mm=height,
        weight_kg=weight,
    )


def test_all_pallets_fit_in_one_vehicle() -> None:
    pallets = [_pallet(i) for i in range(6)]
    result = compute_transport_load(pallets, TRUCK)
    assert result.vehicles_needed == 1
    assert result.pallets_loadable == 6
    assert result.unassigned_pallet_indexes == ()


def test_no_overlap_between_placements_on_same_vehicle() -> None:
    pallets = [_pallet(i) for i in range(10)]
    result = compute_transport_load(pallets, TRUCK)
    for vehicle in result.vehicles:
        placements = list(vehicle.placements)
        for i, a in enumerate(placements):
            for b in placements[i + 1 :]:
                if a.stack_level != b.stack_level:
                    continue
                overlap_x = a.x_mm < b.x_mm + b.length_mm and b.x_mm < a.x_mm + a.length_mm
                overlap_y = a.y_mm < b.y_mm + b.width_mm and b.y_mm < a.y_mm + a.width_mm
                assert not (overlap_x and overlap_y)


def test_weight_limit_forces_multiple_vehicles() -> None:
    heavy = VehicleConfig(
        name="Petit camion",
        inner_length_mm=13600,
        inner_width_mm=2480,
        inner_height_mm=2700,
        max_payload_kg=500,
        allow_pallet_rotation_floor=True,
        allow_pallet_stacking=False,
    )
    pallets = [_pallet(i, weight=300) for i in range(4)]
    result = compute_transport_load(pallets, heavy)
    assert result.vehicles_needed >= 2
    assert result.pallets_loadable == 4
    for vehicle in result.vehicles:
        assert vehicle.used_weight_kg <= heavy.max_payload_kg + 1e-6


def test_oversized_pallet_is_unassigned_without_infinite_loop() -> None:
    tiny_vehicle = VehicleConfig(
        name="Fourgon",
        inner_length_mm=1000,
        inner_width_mm=1000,
        inner_height_mm=1000,
        max_payload_kg=1000,
        allow_pallet_rotation_floor=True,
        allow_pallet_stacking=False,
    )
    pallets = [_pallet(0, length=1200, width=800)]
    result = compute_transport_load(pallets, tiny_vehicle)
    assert result.vehicles_needed == 0
    assert result.pallets_loadable == 0
    assert result.unassigned_pallet_indexes == (0,)


def test_stacking_enabled_places_extra_pallet_above_a_floor_pallet() -> None:
    stacking_vehicle = VehicleConfig(
        name="Camion double étage",
        inner_length_mm=1300,
        inner_width_mm=900,
        inner_height_mm=2200,
        max_payload_kg=5000,
        allow_pallet_rotation_floor=True,
        allow_pallet_stacking=True,
    )
    pallets = [_pallet(0, height=1000), _pallet(1, height=1000)]
    result = compute_transport_load(pallets, stacking_vehicle)
    assert result.pallets_loadable == 2
    assert result.vehicles_needed == 1
    levels = sorted(p.stack_level for p in result.vehicles[0].placements)
    assert levels == [0, 1]


def test_mixed_footprint_pallets_sorted_largest_first_and_all_loadable() -> None:
    pallets = [_pallet(0, length=600, width=400), _pallet(1, length=1200, width=800)]
    result = compute_transport_load(pallets, TRUCK)
    assert result.pallets_loadable == 2
