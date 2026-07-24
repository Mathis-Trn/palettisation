"""Test d'intégration sur le CSV réel fourni (`commande_reelle.csv`), utilisé comme fixture
complète : chaque ligne doit être acceptée ou rejetée explicitement, jamais ignorée en silence.
Voir `backend/CSV_ANALYSIS_REPORT.md` pour le détail de l'analyse."""

from pathlib import Path

from palletizer.imports.legacy_csv import parse_legacy_csv

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "csv" / "commande_reelle.csv"


def _load_preview():  # type: ignore[no-untyped-def]
    content = FIXTURE_PATH.read_bytes()
    return parse_legacy_csv(content)


def test_every_row_is_explicitly_accepted_or_rejected() -> None:
    preview = _load_preview()
    assert preview.total_rows == 114
    assert preview.accepted_rows + preview.rejected_rows == preview.total_rows


def test_six_orders_detected_and_never_mixed() -> None:
    preview = _load_preview()
    order_ids = {order.order_id for order in preview.orders}
    assert order_ids == {
        "SO265669-X82921",
        "SO265838-X83118",
        "SO265841-X82965",
        "SO265875-X83120",
        "SO266346-X83375",
        "SO266633-X83698",
    }
    line_counts = {order.order_id: len(order.lines) for order in preview.orders}
    assert line_counts == {
        "SO265669-X82921": 19,
        "SO265838-X83118": 8,
        "SO265841-X82965": 3,
        "SO265875-X83120": 7,
        "SO266346-X83375": 12,
        "SO266633-X83698": 65,
    }


def test_pallet_formats_and_transport_modes_recognized() -> None:
    preview = _load_preview()
    by_id = {order.order_id: order for order in preview.orders}
    assert by_id["SO265669-X82921"].pallet_spec.code == "P:80x120x110"
    assert by_id["SO265838-X83118"].pallet_spec.code == "P:80x120x160"
    assert (
        by_id["SO265669-X82921"].pallet_spec.length_mm,
        by_id["SO265669-X82921"].pallet_spec.width_mm,
        by_id["SO265669-X82921"].pallet_spec.max_height_mm,
    ) == (800, 1200, 1100)


def test_legacy_expected_result_preserved_for_comparison_never_as_input() -> None:
    preview = _load_preview()
    by_id = {order.order_id: order for order in preview.orders}
    assert by_id["SO265669-X82921"].legacy_expected_result.pallet_count == 37
    assert by_id["SO266633-X83698"].legacy_expected_result.pallet_count == 0
    # Historical QTEXARC is preserved verbatim as opaque audit metadata (observed to always be
    # the literal "PALETTE" marker in this file), never treated as a quantity.
    assert all(
        v == "PALETTE" for order in preview.orders for v in order.legacy_expected_result.raw_qtexarc
    )


def test_all_accepted_lines_have_positive_dimensions_and_quantities() -> None:
    preview = _load_preview()
    for order in preview.orders:
        for line in order.lines:
            assert line.quantity > 0
            assert line.dimensions_mm.length_mm > 0
            assert line.dimensions_mm.width_mm > 0
            assert line.dimensions_mm.height_mm > 0
            assert line.weight_kg is not None and line.weight_kg > 0


def test_no_ambiguous_or_rejected_rows_on_this_particular_file() -> None:
    # Empirically verified: the real file's CARTON_DETAIL_* values all resolve unambiguously
    # under the documented tolerance/plausibility rules (see CSV_ANALYSIS_REPORT.md). This test
    # pins that finding so a future change to the decoder's tolerances is caught immediately.
    preview = _load_preview()
    assert preview.rejected_rows == 0
    assert preview.errors == ()
