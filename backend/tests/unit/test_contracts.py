import json

from palletizer.application.services import PalletizationService
from palletizer.contracts import CONTRACT_VERSION, PalletizeRequest, PalletizeResponse

# Exemple exact du cahier des charges (section 7), utilisé mot pour mot.
EXAMPLE_REQUEST_JSON = """
{
  "contractVersion": "1.0",
  "order": {
    "orderId": "SO265669-X82921",
    "shippingMode": "sea",
    "lines": [
      {
        "lineNumber": 1,
        "sku": "HANDSCRUB1",
        "description": "Solution lavante exfoliante 350 ml / 12 fl oz",
        "quantity": 20,
        "unit": "PIECE",
        "dimensionsMm": {
          "length": 80,
          "width": 80,
          "height": 180
        },
        "weightKg": 0.88,
        "allowRotation": true,
        "uprightOnly": false,
        "fragile": false,
        "stackable": true
      }
    ]
  },
  "pallet": {
    "code": "P:80x120x110",
    "lengthMm": 800,
    "widthMm": 1200,
    "maxHeightMm": 1100,
    "emptyPalletHeightMm": 144,
    "maxHeightIncludesPallet": true,
    "maxWeightKg": 1000
  },
  "options": {
    "optimizationLevel": "fast",
    "minimumSupportRatio": 0.8
  }
}
"""


def test_example_request_from_spec_parses_and_matches_pallet_format() -> None:
    request = PalletizeRequest.model_validate_json(EXAMPLE_REQUEST_JSON)
    assert request.contract_version == CONTRACT_VERSION
    assert request.order.order_id == "SO265669-X82921"
    assert request.pallet.length_mm == 800
    assert request.pallet.width_mm == 1200
    assert request.order.lines[0].dimensions_mm.to_domain().length_mm == 80


def test_example_request_round_trips_through_the_full_service() -> None:
    request = PalletizeRequest.model_validate_json(EXAMPLE_REQUEST_JSON)
    order = request.order.to_domain()
    pallet_spec = request.pallet.to_domain(request.options.minimum_support_ratio)
    options = request.options.to_domain()

    service = PalletizationService()
    result = service.optimize(order, pallet_spec, options)

    response = PalletizeResponse.from_domain(result)
    payload = json.loads(response.model_dump_json(by_alias=True))
    assert payload["contractVersion"] == CONTRACT_VERSION
    assert payload["orderId"] == "SO265669-X82921"
    assert payload["placedCartonsCount"] + payload["unplacedCartonsCount"] == 20
    assert "pallets" in payload and isinstance(payload["pallets"], list)


def test_request_rejects_unknown_fields() -> None:
    import pytest
    from pydantic import ValidationError

    bad_json = EXAMPLE_REQUEST_JSON.replace(
        '"contractVersion": "1.0",', '"contractVersion": "1.0", "bogusField": 1,'
    )
    with pytest.raises(ValidationError):
        PalletizeRequest.model_validate_json(bad_json)
