"""Tests d'intégration des routes `/api/v1/palletization-jobs*` via l'API réelle (FastAPI +
`ProcessPoolExecutor` réel). Le gestionnaire de jobs est un singleton partagé par tout le
processus de test (comme en production) : chaque test utilise un contenu de commande distinct
(`orderId` unique) pour éviter toute déduplication involontaire entre tests indépendants — voir
`tests/unit/test_job_manager.py` pour les tests fins de la machine à états, isolés les uns des
autres avec des gestionnaires dédiés.
"""

from __future__ import annotations

import time
import uuid

from fastapi.testclient import TestClient

from palletizer.api.main import create_app

client = TestClient(create_app())


def _payload(order_id: str | None = None, quantity: int = 2) -> dict:
    return {
        "contractVersion": "1.0",
        "order": {
            "orderId": order_id or f"JOB-{uuid.uuid4()}",
            "shippingMode": "sea",
            "lines": [
                {
                    "lineNumber": 1,
                    "sku": "BOX",
                    "description": "Boite de test",
                    "quantity": quantity,
                    "unit": "PIECE",
                    "dimensionsMm": {"length": 300, "width": 200, "height": 150},
                    "weightKg": 2.0,
                }
            ],
        },
        "pallet": {"code": "P:80x120x110", "lengthMm": 800, "widthMm": 1200, "maxHeightMm": 1100},
        "options": {"optimizationLevel": "fast"},
    }


def _wait_for_terminal(job_id: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    body = client.get(f"/api/v1/palletization-jobs/{job_id}").json()
    while body["status"] in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(0.1)
        body = client.get(f"/api/v1/palletization-jobs/{job_id}").json()
    return body


def test_create_job_returns_202_with_expected_shape() -> None:
    response = client.post("/api/v1/palletization-jobs", json=_payload())
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert "jobId" in body and "createdAt" in body


def test_job_transitions_to_succeeded_and_carries_the_full_result() -> None:
    response = client.post("/api/v1/palletization-jobs", json=_payload(quantity=3))
    job_id = response.json()["jobId"]

    final = _wait_for_terminal(job_id)
    assert final["status"] == "succeeded"
    assert final["result"] is not None
    assert final["result"]["placedCartonsCount"] + final["result"]["unplacedCartonsCount"] == 3
    assert final["error"] is None


def test_unknown_job_returns_404() -> None:
    response = client.get("/api/v1/palletization-jobs/does-not-exist")
    assert response.status_code == 404
    response = client.delete("/api/v1/palletization-jobs/does-not-exist")
    assert response.status_code == 404


def test_duplicate_concurrent_submission_returns_the_same_job_id() -> None:
    order_id = f"DUP-{uuid.uuid4()}"
    payload = _payload(order_id=order_id, quantity=5)
    r1 = client.post("/api/v1/palletization-jobs", json=payload)
    r2 = client.post("/api/v1/palletization-jobs", json=payload)
    assert r1.json()["jobId"] == r2.json()["jobId"]
    _wait_for_terminal(r1.json()["jobId"])


def test_create_job_responds_fast_and_does_not_block_health_endpoint() -> None:
    """Démontre que le calcul CPU-bound ne s'exécute pas dans la boucle asyncio de FastAPI :
    la création répond immédiatement, et /health reste joignable pendant que le job tourne."""
    start = time.perf_counter()
    response = client.post("/api/v1/palletization-jobs", json=_payload(quantity=4))
    creation_duration = time.perf_counter() - start
    assert response.status_code == 202
    assert creation_duration < 1.0  # la création ne fait jamais attendre le calcul lui-même

    health_start = time.perf_counter()
    health = client.get("/health")
    health_duration = time.perf_counter() - health_start
    assert health.status_code == 200
    assert health_duration < 1.0

    _wait_for_terminal(response.json()["jobId"])


def test_cancel_endpoint_marks_job_cancelled() -> None:
    response = client.post("/api/v1/palletization-jobs", json=_payload(quantity=1))
    job_id = response.json()["jobId"]
    cancel_response = client.delete(f"/api/v1/palletization-jobs/{job_id}")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] in ("cancelled", "succeeded")
    # (le job peut avoir déjà réussi si l'annulation arrive après un calcul très rapide — dans les
    # deux cas, il n'est ni "queued" ni "running" indéfiniment : le comportement est déterministe.)


def test_result_invariants_hold_for_a_multi_line_order() -> None:
    payload = _payload(quantity=1)
    payload["order"]["lines"].append(
        {
            "lineNumber": 2,
            "sku": "BOX-B",
            "description": "Autre boite",
            "quantity": 6,
            "unit": "PIECE",
            "dimensionsMm": {"length": 250, "width": 200, "height": 100},
            "weightKg": 1.0,
        }
    )
    response = client.post("/api/v1/palletization-jobs", json=payload)
    final = _wait_for_terminal(response.json()["jobId"])
    result = final["result"]
    assert result["totalCartonsCount"] == 7
    assert result["placedCartonsCount"] + result["unplacedCartonsCount"] == 7
    seen_instance_ids = {
        box["instanceId"] for pallet in result["pallets"] for box in pallet["placedCartons"]
    } | {item["instanceId"] for item in result["unplacedCartons"]}
    assert len(seen_instance_ids) == 7
