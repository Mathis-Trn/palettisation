"""Parseur du CSV métier réel (colonnes `DEPXENT;CDEXENT;MDTXENT;TYPEPALETTE;...`).

Caractéristiques confirmées par l'analyse du fichier réel joint (voir
`backend/CSV_ANALYSIS_REPORT.md`) : encodage UTF-8 avec BOM, séparateur `;`, 31 colonnes, plusieurs
commandes regroupées par `CDEXENT`, dimensions/volume/poids éclatés sur les colonnes
`CARTON_DETAIL_1..10` par le séparateur (décimales fragmentées).

Ne devine jamais silencieusement : toute ligne dont les `CARTON_DETAIL_*` ne peuvent être
reconstruits sans ambiguïté est rejetée avec le code `AMBIGUOUS_CARTON_DETAILS`, le numéro de ligne
et les fragments bruts.
"""

from __future__ import annotations

import csv
import io
import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from palletizer.domain.enums import ImportRejectionCode, ShippingMode
from palletizer.domain.errors import AmbiguousCartonDetailsError, CsvLimitExceededError
from palletizer.domain.models import (
    CsvImportError,
    CsvImportPreview,
    CsvImportWarning,
    Dimensions3D,
    LegacyExpectedResult,
    OrderLine,
    PalletSpec,
    ParsedCsvOrder,
)

# --- Limites de sécurité (anti-DoS / anti-explosion mémoire) ------------------------------------

MAX_CSV_BYTES = 20_000_000
MAX_CSV_ROWS = 200_000

# --- En-têtes attendus, dans l'ordre exact du fichier réel --------------------------------------

CARTON_DETAIL_COLUMNS = tuple(f"CARTON_DETAIL_{i}" for i in range(1, 11))
PALETTE_DETAIL_COLUMNS = tuple(f"PALETTE_DETAIL_{i}" for i in range(1, 11))
EXPECTED_HEADERS = (
    "DEPXENT",
    "CDEXENT",
    "MDTXENT",
    "TYPEPALETTE",
    "PALXENT",
    "LIGXLIG",
    "REFXLIG",
    "LIBXART",
    "QTCXLIG",
    "LIBXARC",
    *CARTON_DETAIL_COLUMNS,
    "QTEXARC",
    *PALETTE_DETAIL_COLUMNS,
)

# --- Valeurs par défaut appliquées aux lignes de commande (absentes du CSV historique) ----------
# Le CSV legacy ne renseigne aucune contrainte de rotation/fragilité/gerbage par SKU : les mêmes
# valeurs par défaut que l'ancien import CSV simplifié TypeScript sont reprises (ASSUMPTIONS.md).
DEFAULT_ALLOW_ROTATION = True
DEFAULT_UPRIGHT_ONLY = False
DEFAULT_FRAGILE = False
DEFAULT_STACKABLE = True

# --- Valeurs par défaut de palette (le CSV ne fournit que le format, pas les contraintes) --------
DEFAULT_EMPTY_PALLET_HEIGHT_MM = 144.0
DEFAULT_MAX_WEIGHT_KG = 800.0
DEFAULT_OVERHANG_MM = 0.0
DEFAULT_SAFETY_GAP_MM = 0.0
DEFAULT_MINIMUM_SUPPORT_RATIO = 0.8

_SHIPPING_MODE_MAP = {"M": ShippingMode.SEA, "A": ShippingMode.AIR}
_PALLET_FORMAT_RE = re.compile(r"^P:(\d+)x(\d+)x(\d+)$")

# --- Décodage des colonnes CARTON_DETAIL_1..10 (décimales éclatées) -----------------------------

_VOLUME_RELATIVE_TOLERANCE = 0.005
_DENSITY_MIN_KG_PER_L = 0.02
_DENSITY_MAX_KG_PER_L = 20.0
_MAX_PLAUSIBLE_WEIGHT_KG = 1000.0


@dataclass(frozen=True, slots=True)
class DecodedCartonDetails:
    length_cm: float
    width_cm: float
    height_cm: float
    weight_kg: float
    volume_cm3: float


def _fragment_group_to_number(group: Sequence[str]) -> float:
    if len(group) == 1:
        return float(group[0])
    whole, *decimals = group
    return float(f"{whole}.{''.join(decimals)}")


def decode_carton_details(raw_fields: Sequence[str], line_number: int) -> DecodedCartonDetails:
    """Reconstruit longueur/largeur/hauteur/volume/poids à partir des fragments
    `CARTON_DETAIL_1..10`, dont les décimales ont été éclatées par le séparateur `;`.

    Algorithme (documenté et testé dans `backend/CSV_ANALYSIS_REPORT.md`) : cherche toutes les
    partitions des fragments non vides en 5 groupes ordonnés (L, W, H, volume, poids), ne retient
    qu'un candidat cohérent (L×W×H ≈ volume à 0,5% près, densité implicite plausible entre 0,02 et
    20 kg/L), et seulement s'il est unique. Sinon : `AmbiguousCartonDetailsError`.
    """
    cleaned = [f.replace("﻿", "").strip() for f in raw_fields]
    fragments = [f for f in cleaned if f != ""]
    n = len(fragments)
    if n < 5:
        raise AmbiguousCartonDetailsError(
            line_number, list(raw_fields), "moins de 5 fragments non vides"
        )

    candidates: list[tuple[float, DecodedCartonDetails]] = []
    for cuts in itertools.combinations(range(1, n), 4):
        bounds = (0, *cuts, n)
        groups = [fragments[bounds[i] : bounds[i + 1]] for i in range(5)]
        try:
            length, width, height, volume, weight = (_fragment_group_to_number(g) for g in groups)
        except ValueError:
            continue
        if length <= 0 or width <= 0 or height <= 0 or volume <= 0 or weight <= 0:
            continue
        if weight > _MAX_PLAUSIBLE_WEIGHT_KG:
            continue
        predicted_volume = length * width * height
        rel_err = abs(predicted_volume - volume) / volume
        density_kg_per_l = weight / (volume / 1000.0)
        if not (_DENSITY_MIN_KG_PER_L <= density_kg_per_l <= _DENSITY_MAX_KG_PER_L):
            continue
        if rel_err <= _VOLUME_RELATIVE_TOLERANCE:
            candidates.append(
                (rel_err, DecodedCartonDetails(length, width, height, weight, volume))
            )

    if not candidates:
        raise AmbiguousCartonDetailsError(
            line_number, list(raw_fields), "aucun candidat cohérent trouvé"
        )
    candidates.sort(key=lambda c: c[0])
    if len(candidates) > 1 and abs(candidates[0][0] - candidates[1][0]) < 1e-9:
        raise AmbiguousCartonDetailsError(
            line_number, list(raw_fields), "plusieurs candidats à égalité"
        )
    return candidates[0][1]


def parse_pallet_format(raw: str) -> PalletSpec:
    """`P:{longueur_cm}x{largeur_cm}x{hauteur_cm}` -> `PalletSpec` (mm). Ex. `P:80x120x110` ->
    800x1200x1100mm, `P:80x120x160` -> 800x1200x1600mm.

    Ordre confirmé par l'exemple de contrat JSON normalisé du cahier des charges (section 7) :
    `"code": "P:80x120x110"` y est associé à `"lengthMm": 800, "widthMm": 1200` — c'est-à-dire le
    premier nombre du format devient directement `lengthMm` (pas de permutation), même si cela ne
    correspond pas à l'ordre length/width des presets "routier"/"maritime" du front existant (qui
    utilisaient 1200x800). Le contrat normalisé fait foi.
    """
    match = _PALLET_FORMAT_RE.match(raw.strip())
    if not match:
        raise ValueError(f"Format de palette non reconnu : {raw!r}")
    length_cm, width_cm, height_cm = (int(g) for g in match.groups())
    return PalletSpec(
        code=raw.strip(),
        length_mm=float(length_cm * 10),
        width_mm=float(width_cm * 10),
        max_height_mm=float(height_cm * 10),
        empty_pallet_height_mm=DEFAULT_EMPTY_PALLET_HEIGHT_MM,
        max_height_includes_pallet=True,
        max_weight_kg=DEFAULT_MAX_WEIGHT_KG,
        overhang_mm=DEFAULT_OVERHANG_MM,
        safety_gap_mm=DEFAULT_SAFETY_GAP_MM,
        minimum_support_ratio=DEFAULT_MINIMUM_SUPPORT_RATIO,
    )


def parse_shipping_mode(raw: str) -> tuple[ShippingMode, str | None]:
    mode = _SHIPPING_MODE_MAP.get(raw.strip().upper())
    if mode is None:
        return ShippingMode.UNKNOWN, f"mode de transport inconnu : {raw!r}"
    return mode, None


@dataclass(slots=True)
class _OrderAccumulator:
    depot: str
    mode_raw: str
    pallet_raw: str
    palxent_raw: str
    lines: list[OrderLine] = field(default_factory=list)
    palette_details: list[tuple[str, ...]] = field(default_factory=list)
    qtexarc_values: list[str] = field(default_factory=list)


def parse_legacy_csv(content: bytes) -> CsvImportPreview:
    if len(content) > MAX_CSV_BYTES:
        raise CsvLimitExceededError(
            f"Le fichier dépasse la taille maximale autorisée ({MAX_CSV_BYTES} octets)."
        )

    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    fieldnames = reader.fieldnames or []
    missing = [h for h in EXPECTED_HEADERS if h not in fieldnames]
    if missing:
        return CsvImportPreview(
            orders=(),
            errors=(
                CsvImportError(
                    line_number=0,
                    column=None,
                    code="MISSING_REQUIRED_FIELD",
                    message=f"Colonnes obligatoires manquantes : {', '.join(missing)}",
                ),
            ),
            warnings=(),
            total_rows=0,
            accepted_rows=0,
            rejected_rows=0,
        )

    rows = list(reader)
    if len(rows) > MAX_CSV_ROWS:
        raise CsvLimitExceededError(
            f"Le fichier dépasse le nombre maximal de lignes autorisées ({MAX_CSV_ROWS})."
        )

    errors: list[CsvImportError] = []
    warnings: list[CsvImportWarning] = []
    accumulators: dict[str, _OrderAccumulator] = {}
    accepted = 0
    rejected = 0

    for row_index, row in enumerate(rows):
        line_number = row_index + 2  # ligne d'en-tête + index 1-based
        try:
            order_id = (row.get("CDEXENT") or "").strip()
            if not order_id:
                raise ValueError("CDEXENT (identifiant de commande) manquant")

            quantity_raw = (row.get("QTCXLIG") or "").strip()
            if not quantity_raw.isdigit() or int(quantity_raw) <= 0:
                raise ValueError(f"QTCXLIG invalide : {quantity_raw!r}")
            quantity = int(quantity_raw)

            line_number_raw = (row.get("LIGXLIG") or "").strip()
            csv_line_number = int(line_number_raw) if line_number_raw.isdigit() else line_number

            carton_fragments = [row.get(col, "") or "" for col in CARTON_DETAIL_COLUMNS]
            decoded = decode_carton_details(carton_fragments, line_number)

            order_line = OrderLine(
                line_number=csv_line_number,
                sku=(row.get("REFXLIG") or "").strip(),
                description=(row.get("LIBXART") or "").strip(),
                quantity=quantity,
                unit=(row.get("LIBXARC") or "").strip(),
                dimensions_mm=Dimensions3D(
                    length_mm=decoded.length_cm * 10,
                    width_mm=decoded.width_cm * 10,
                    height_mm=decoded.height_cm * 10,
                ),
                weight_kg=decoded.weight_kg,
                allow_rotation=DEFAULT_ALLOW_ROTATION,
                upright_only=DEFAULT_UPRIGHT_ONLY,
                fragile=DEFAULT_FRAGILE,
                stackable=DEFAULT_STACKABLE,
            )
        except (AmbiguousCartonDetailsError, ValueError) as exc:
            code = (
                ImportRejectionCode.AMBIGUOUS_CARTON_DETAILS.value
                if isinstance(exc, AmbiguousCartonDetailsError)
                else ImportRejectionCode.INVALID_QUANTITY.value
            )
            errors.append(
                CsvImportError(
                    line_number=line_number,
                    column=None,
                    code=code,
                    message=str(exc),
                    raw_fragments=tuple(row.get(col, "") or "" for col in CARTON_DETAIL_COLUMNS),
                )
            )
            rejected += 1
            continue

        accumulator = accumulators.get(order_id)
        if accumulator is None:
            accumulator = _OrderAccumulator(
                depot=(row.get("DEPXENT") or "").strip(),
                mode_raw=(row.get("MDTXENT") or "").strip(),
                pallet_raw=(row.get("TYPEPALETTE") or "").strip(),
                palxent_raw=(row.get("PALXENT") or "").strip(),
            )
            accumulators[order_id] = accumulator
        accumulator.lines.append(order_line)
        accumulator.palette_details.append(
            tuple(row.get(col, "") or "" for col in PALETTE_DETAIL_COLUMNS)
        )
        accumulator.qtexarc_values.append((row.get("QTEXARC") or "").strip())
        accepted += 1

    orders: list[ParsedCsvOrder] = []
    for order_id, accumulator in accumulators.items():
        try:
            spec = parse_pallet_format(accumulator.pallet_raw)
        except ValueError as exc:
            errors.append(
                CsvImportError(
                    line_number=None,
                    column="TYPEPALETTE",
                    code=ImportRejectionCode.INVALID_PALLET_FORMAT.value,
                    message=f"{order_id} : {exc}",
                )
            )
            continue

        mode, mode_warning = parse_shipping_mode(accumulator.mode_raw)
        if mode_warning:
            warnings.append(
                CsvImportWarning(line_number=None, message=f"{order_id} : {mode_warning}")
            )

        palxent = int(accumulator.palxent_raw) if accumulator.palxent_raw.isdigit() else None
        legacy = LegacyExpectedResult(
            pallet_count=palxent,
            raw_pallet_details=tuple(accumulator.palette_details),
            raw_qtexarc=tuple(accumulator.qtexarc_values),
        )
        orders.append(
            ParsedCsvOrder(
                order_id=order_id,
                shipping_mode=mode,
                pallet_spec=spec,
                lines=tuple(accumulator.lines),
                legacy_expected_result=legacy,
            )
        )

    stats = {
        "orders_count": len(orders),
        "pallet_formats": sorted({o.pallet_spec.code for o in orders}),
        "shipping_modes": sorted({o.shipping_mode.value for o in orders}),
    }
    return CsvImportPreview(
        orders=tuple(orders),
        errors=tuple(errors),
        warnings=tuple(warnings),
        total_rows=len(rows),
        accepted_rows=accepted,
        rejected_rows=rejected,
        stats=stats,
    )
