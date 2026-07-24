from pathlib import Path

from fastapi.testclient import TestClient

from palletizer.api.main import create_app

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "csv" / "commande_reelle.csv"
SYNTHETIC_FIXTURE_PATH = (
    Path(__file__).parent.parent / "fixtures" / "csv" / "commande_synthetique.csv"
)

client = TestClient(create_app())


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body and "engineVersion" in body


def test_capabilities() -> None:
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["contractVersion"] == "1.0"
    assert body["packingAdapter"]["name"] == "py3dbp"
    assert "limits" in body


def test_palletize_with_normalized_json() -> None:
    payload = {
        "contractVersion": "1.0",
        "order": {
            "orderId": "TEST-1",
            "shippingMode": "sea",
            "lines": [
                {
                    "lineNumber": 1,
                    "sku": "BOX-A",
                    "description": "Boite test",
                    "quantity": 4,
                    "unit": "PIECE",
                    "dimensionsMm": {"length": 300, "width": 200, "height": 150},
                    "weightKg": 2.0,
                    "allowRotation": True,
                    "uprightOnly": False,
                    "fragile": False,
                    "stackable": True,
                }
            ],
        },
        "pallet": {
            "code": "P:80x120x110",
            "lengthMm": 800,
            "widthMm": 1200,
            "maxHeightMm": 1100,
            "emptyPalletHeightMm": 144,
            "maxHeightIncludesPallet": True,
            "maxWeightKg": 1000,
        },
        "options": {"optimizationLevel": "fast", "minimumSupportRatio": 0.8},
    }
    response = client.post("/api/v1/palletize", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["orderId"] == "TEST-1"
    assert body["placedCartonsCount"] + body["unplacedCartonsCount"] == 4


def test_palletize_validation_error_returns_structured_envelope() -> None:
    response = client.post("/api/v1/palletize", json={"contractVersion": "1.0"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "correlation_id" in body["error"]


def test_parse_csv_upload_detects_orders() -> None:
    with FIXTURE_PATH.open("rb") as fh:
        response = client.post(
            "/api/v1/orders/parse-csv",
            files={"file": ("commande_reelle.csv", fh, "text/csv")},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["orders"]) == 6
    assert body["acceptedRows"] == 114


def test_palletize_csv_requires_order_id_when_multiple_orders() -> None:
    with FIXTURE_PATH.open("rb") as fh:
        response = client.post(
            "/api/v1/palletize/csv",
            files={"file": ("commande_reelle.csv", fh, "text/csv")},
        )
    assert response.status_code == 400
    assert "orderId" in response.json()["error"]["message"]


def test_palletize_csv_with_explicit_order_id() -> None:
    # Uses a small synthetic order (not the real fixture, whose quantities run into the
    # thousands and would make a full optimize() call far too slow for a quick API test).
    with SYNTHETIC_FIXTURE_PATH.open("rb") as fh:
        response = client.post(
            "/api/v1/palletize/csv",
            files={"file": ("commande_synthetique.csv", fh, "text/csv")},
            data={"orderId": "SO_TEST_1"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["orderId"] == "SO_TEST_1"
    assert body["placedCartonsCount"] + body["unplacedCartonsCount"] == 10


def test_transport_load_endpoint() -> None:
    payload = {
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
            "name": "Camion",
            "innerLengthMm": 13600,
            "innerWidthMm": 2480,
            "innerHeightMm": 2700,
            "maxPayloadKg": 24000,
        },
    }
    response = client.post("/api/v1/transport/load", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["palletsLoadable"] == 1


def test_request_correlation_id_header_present() -> None:
    response = client.get("/health")
    assert "x-request-id" in response.headers
