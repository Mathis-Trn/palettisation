from palletizer.domain.enums import OptimizationLevel, ShippingMode
from palletizer.domain.models import (
    Dimensions3D,
    OptimizationOptions,
    Order,
    OrderLine,
    PalletSpec,
)

ROUTIER_SPEC = PalletSpec(
    code="P:80x120x110",
    length_mm=1200,
    width_mm=800,
    max_height_mm=1100,
    empty_pallet_height_mm=144,
    max_height_includes_pallet=True,
    max_weight_kg=800,
    overhang_mm=0,
    safety_gap_mm=0,
    minimum_support_ratio=0.8,
)


def make_options(**overrides: object) -> OptimizationOptions:
    base = {
        "global_rotations_enabled": True,
        "optimization_level": OptimizationLevel.FAST,
        "fragile_max_weight_on_top_kg": 0.0,
    }
    base.update(overrides)
    return OptimizationOptions(**base)  # type: ignore[arg-type]


def make_line(
    sku: str = "BOX-A",
    length: float = 400,
    width: float = 300,
    height: float = 250,
    quantity: int = 1,
    weight_kg: float | None = 5.0,
    allow_rotation: bool = True,
    upright_only: bool = False,
    fragile: bool = False,
    stackable: bool = True,
    max_supported_weight_kg: float | None = None,
    product_group: str | None = None,
    incompatible_groups: tuple[str, ...] = (),
    line_number: int = 1,
) -> OrderLine:
    return OrderLine(
        line_number=line_number,
        sku=sku,
        description=sku,
        quantity=quantity,
        unit="PIECE",
        dimensions_mm=Dimensions3D(length, width, height),
        weight_kg=weight_kg,
        allow_rotation=allow_rotation,
        upright_only=upright_only,
        fragile=fragile,
        stackable=stackable,
        max_supported_weight_kg=max_supported_weight_kg,
        product_group=product_group,
        incompatible_groups=incompatible_groups,
    )


def make_order(lines: list[OrderLine], order_id: str = "TEST-1") -> Order:
    return Order(order_id=order_id, shipping_mode=ShippingMode.ROAD, lines=tuple(lines))
