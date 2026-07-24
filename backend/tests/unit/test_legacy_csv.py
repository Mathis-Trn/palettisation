import pytest

from palletizer.domain.enums import ShippingMode
from palletizer.domain.errors import AmbiguousCartonDetailsError
from palletizer.imports.legacy_csv import (
    decode_carton_details,
    parse_legacy_csv,
    parse_pallet_format,
    parse_shipping_mode,
)

# Les 4 exemples documentés dans le cahier des charges (ce sont des lignes réelles du fichier).
DOCUMENTED_EXAMPLES = [
    (["8", "8", "18", "1152", "0", "88"], (8.0, 8.0, 18.0, 0.88, 1152.0)),
    (["8", "2", "8", "2", "18", "1210", "32", "0", "857"], (8.2, 8.2, 18.0, 0.857, 1210.32)),
    (
        ["8", "3", "10", "2", "3", "3", "279", "378", "0", "219"],
        (8.3, 10.2, 3.3, 0.219, 279.378),
    ),
    (
        ["4", "5", "4", "5", "15", "5", "313", "875", "0", "79"],
        (4.5, 4.5, 15.5, 0.79, 313.875),
    ),
]


@pytest.mark.parametrize("fragments,expected", DOCUMENTED_EXAMPLES)
def test_decode_carton_details_documented_examples(fragments, expected) -> None:
    length, width, height, weight, volume = expected
    decoded = decode_carton_details(fragments, line_number=1)
    assert decoded.length_cm == pytest.approx(length)
    assert decoded.width_cm == pytest.approx(width)
    assert decoded.height_cm == pytest.approx(height)
    assert decoded.weight_kg == pytest.approx(weight)
    assert decoded.volume_cm3 == pytest.approx(volume)


def test_decode_carton_details_trims_bom_and_trailing_empty_fields() -> None:
    fragments = ["﻿8", "8", "18", "1152", "0", "88", "", "", "", ""]
    decoded = decode_carton_details(fragments, line_number=1)
    assert decoded.length_cm == pytest.approx(8.0)


def test_decode_carton_details_rejects_too_few_fragments() -> None:
    with pytest.raises(AmbiguousCartonDetailsError):
        decode_carton_details(["8", "8", "18"], line_number=5)


# Fragments engineered so two DIFFERENT partitions both reach a perfect volume match (rel_err=0)
# AND both pass the density-plausibility filter: L=W=H=5 -> volume=125 either read directly as
# "125" (weight=0.2 from "0","2") or as "125" + a trailing ".0" absorbed from the next fragment
# (weight=2 alone) -- 0.2kg and 2kg are both physically plausible for a 125cm3 box, so neither can
# be discarded on plausibility grounds alone: a genuine, unavoidable ambiguity.
AMBIGUOUS_FRAGMENTS = ["5", "5", "5", "125", "0", "2"]


def test_decode_carton_details_rejects_genuinely_ambiguous_input() -> None:
    with pytest.raises(AmbiguousCartonDetailsError) as exc_info:
        decode_carton_details(AMBIGUOUS_FRAGMENTS, line_number=9)
    assert exc_info.value.reason == "plusieurs candidats à égalité"


def test_parse_pallet_format_routier_and_maritime() -> None:
    # Ordre confirmé par l'exemple de contrat JSON du cahier des charges : P:80x120x110 ->
    # lengthMm=800, widthMm=1200 (pas de permutation), même si cela diffère de l'ordre
    # length/width des anciens presets front "routier"/"maritime" (1200x800).
    routier = parse_pallet_format("P:80x120x110")
    assert (routier.length_mm, routier.width_mm, routier.max_height_mm) == (800, 1200, 1100)

    maritime = parse_pallet_format("P:80x120x160")
    assert (maritime.length_mm, maritime.width_mm, maritime.max_height_mm) == (800, 1200, 1600)


def test_parse_pallet_format_rejects_unknown_format() -> None:
    with pytest.raises(ValueError):
        parse_pallet_format("XYZ")


def test_parse_shipping_mode() -> None:
    assert parse_shipping_mode("M") == (ShippingMode.SEA, None)
    assert parse_shipping_mode("A") == (ShippingMode.AIR, None)
    mode, warning = parse_shipping_mode("Z")
    assert mode == ShippingMode.UNKNOWN
    assert warning is not None


def _sample_csv_bytes(rows: str) -> bytes:
    header = (
        "DEPXENT;CDEXENT;MDTXENT;TYPEPALETTE;PALXENT;LIGXLIG;REFXLIG;LIBXART;QTCXLIG;LIBXARC;"
        + ";".join(f"CARTON_DETAIL_{i}" for i in range(1, 11))
        + ";QTEXARC;"
        + ";".join(f"PALETTE_DETAIL_{i}" for i in range(1, 11))
    )
    return ("﻿" + header + "\n" + rows).encode("utf-8")


def test_parse_legacy_csv_bom_does_not_pollute_depxent() -> None:
    rows = (
        "DIP;SO1;M;P:80x120x110;10;1;SKU1;Desc;5;PIECE;8;8;18;1152;0;88;;;;;"
        "PALETTE;1;2;3;4;5;6;7;8;;\n"
    )
    preview = parse_legacy_csv(_sample_csv_bytes(rows))
    assert len(preview.orders) == 1
    assert preview.orders[0].order_id == "SO1"
    # No leading BOM character should leak into any parsed value.
    assert not any("﻿" in line.sku for order in preview.orders for line in order.lines)


def test_parse_legacy_csv_groups_by_order_and_keeps_legacy_result() -> None:
    rows = (
        "DIP;SO1;M;P:80x120x110;37;1;SKU1;Desc1;5;PIECE;8;8;18;1152;0;88;;;;;PALETTE;1;2;3;4;5;6;7;8;;\n"
        "DIP;SO1;M;P:80x120x110;37;2;SKU2;Desc2;6;PIECE;8;8;18;1152;0;88;;;;;PALETTE;1;2;3;4;5;6;7;8;;\n"
        "DIP;SO2;A;P:80x120x160;4;1;SKU3;Desc3;7;PIECE;8;8;18;1152;0;88;;;;;PALETTE;1;2;3;4;5;6;7;8;;\n"
    )
    preview = parse_legacy_csv(_sample_csv_bytes(rows))
    assert preview.accepted_rows == 3
    assert preview.rejected_rows == 0
    by_id = {order.order_id: order for order in preview.orders}
    assert set(by_id) == {"SO1", "SO2"}
    assert len(by_id["SO1"].lines) == 2
    assert len(by_id["SO2"].lines) == 1
    assert by_id["SO1"].legacy_expected_result.pallet_count == 37
    assert by_id["SO2"].legacy_expected_result.pallet_count == 4
    assert by_id["SO1"].shipping_mode == ShippingMode.SEA
    assert by_id["SO2"].shipping_mode == ShippingMode.AIR


def test_parse_legacy_csv_rejects_ambiguous_line_without_blocking_others() -> None:
    bad_details = ";".join(AMBIGUOUS_FRAGMENTS) + ";;;;"
    rows = (
        "DIP;SO1;M;P:80x120x110;37;1;SKU1;Desc1;5;PIECE;8;8;18;1152;0;88;;;;;PALETTE;1;2;3;4;5;6;7;8;;\n"
        f"DIP;SO1;M;P:80x120x110;37;2;BADSKU;Bad;6;PIECE;{bad_details};PALETTE;1;2;3;4;5;6;7;8;;\n"
    )
    preview = parse_legacy_csv(_sample_csv_bytes(rows))
    assert preview.accepted_rows == 1
    assert preview.rejected_rows == 1
    assert preview.errors[0].code == "AMBIGUOUS_CARTON_DETAILS"
    assert len(preview.orders[0].lines) == 1


def test_parse_legacy_csv_missing_headers_reports_single_error() -> None:
    preview = parse_legacy_csv(b"a;b;c\n1;2;3\n")
    assert preview.orders == ()
    assert preview.errors[0].code == "MISSING_REQUIRED_FIELD"


def test_parse_legacy_csv_invalid_quantity_rejected() -> None:
    rows = (
        "DIP;SO1;M;P:80x120x110;37;1;SKU1;Desc1;0;PIECE;8;8;18;1152;0;88;;;;;"
        "PALETTE;1;2;3;4;5;6;7;8;;\n"
    )
    preview = parse_legacy_csv(_sample_csv_bytes(rows))
    assert preview.rejected_rows == 1
    assert preview.errors[0].code == "INVALID_QUANTITY"
