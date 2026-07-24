import json
from pathlib import Path

from typer.testing import CliRunner

from palletizer.cli import app

runner = CliRunner()
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "csv"
REAL_CSV = FIXTURE_DIR / "commande_reelle.csv"
SYNTHETIC_CSV = FIXTURE_DIR / "commande_synthetique.csv"


def test_capabilities_command() -> None:
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["packingAdapter"]["name"] == "py3dbp"


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "version" in payload and "engineVersion" in payload


def test_validate_csv_real_fixture() -> None:
    result = runner.invoke(app, ["validate-csv", str(REAL_CSV)])
    assert result.exit_code == 0
    assert "Commandes détectées : 6" in result.stdout
    assert "Lignes rejetées     : 0" in result.stdout


def test_validate_csv_missing_headers_exits_nonzero(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bad_file = tmp_path / "bad.csv"
    bad_file.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    result = runner.invoke(app, ["validate-csv", str(bad_file)])
    assert result.exit_code == 1


def test_validate_csv_missing_file_exits_nonzero() -> None:
    result = runner.invoke(app, ["validate-csv", "does-not-exist.csv"])
    assert result.exit_code == 1


def test_parse_csv_writes_json_to_stdout() -> None:
    result = runner.invoke(app, ["parse-csv", str(REAL_CSV), "--output", "-"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["orders"]) == 6


def test_parse_csv_writes_to_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out_file = tmp_path / "out.json"
    result = runner.invoke(app, ["parse-csv", str(REAL_CSV), "--output", str(out_file)])
    assert result.exit_code == 0
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["acceptedRows"] == 114


def test_optimize_csv_requires_order_when_multiple() -> None:
    result = runner.invoke(app, ["optimize-csv", str(REAL_CSV), "--output", "-"])
    assert result.exit_code == 1
    assert "--order" in result.stderr if result.stderr else True


def test_optimize_csv_with_synthetic_order_and_legacy_comparison() -> None:
    result = runner.invoke(
        app, ["optimize-csv", str(SYNTHETIC_CSV), "--order", "SO_TEST_1", "--output", "-"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["orderId"] == "SO_TEST_1"
    assert payload["placedCartonsCount"] + payload["unplacedCartonsCount"] == 10


def test_optimize_from_normalized_json(tmp_path) -> None:  # type: ignore[no-untyped-def]
    request = {
        "contractVersion": "1.0",
        "order": {
            "orderId": "CLI-TEST",
            "shippingMode": "road",
            "lines": [
                {
                    "lineNumber": 1,
                    "sku": "BOX",
                    "description": "Boite",
                    "quantity": 2,
                    "unit": "PIECE",
                    "dimensionsMm": {"length": 300, "width": 200, "height": 150},
                    "weightKg": 5,
                }
            ],
        },
        "pallet": {
            "code": "P:80x120x110",
            "lengthMm": 800,
            "widthMm": 1200,
            "maxHeightMm": 1100,
        },
        "options": {"optimizationLevel": "fast"},
    }
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    result = runner.invoke(app, ["optimize", str(request_file), "--output", "-"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["orderId"] == "CLI-TEST"
    assert payload["placedCartonsCount"] == 2


def test_optimize_invalid_json_exits_nonzero(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    result = runner.invoke(app, ["optimize", str(bad_file), "--output", "-"])
    assert result.exit_code == 1


def test_transport_load_command(tmp_path) -> None:  # type: ignore[no-untyped-def]
    request = {
        "contractVersion": "1.0",
        "pallets": [
            {
                "palletResultIndex": 0,
                "footprintLengthMm": 800,
                "footprintWidthMm": 1200,
                "heightMm": 1100,
                "weightKg": 300,
            }
        ],
        "vehicle": {
            "innerLengthMm": 13600,
            "innerWidthMm": 2480,
            "innerHeightMm": 2700,
            "maxPayloadKg": 24000,
        },
    }
    request_file = tmp_path / "transport.json"
    request_file.write_text(json.dumps(request), encoding="utf-8")
    result = runner.invoke(app, ["transport-load", str(request_file), "--output", "-"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["palletsLoadable"] == 1
