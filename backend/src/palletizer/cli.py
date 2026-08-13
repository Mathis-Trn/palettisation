"""CLI headless (`palletizer`) — aucun serveur, aucun navigateur requis.

Sorties : résultat JSON sur stdout (ou fichier via `--output`), logs/diagnostics sur stderr.
Codes de sortie non nuls en cas d'erreur. Messages en français par défaut.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

from palletizer import __version__
from palletizer.application.services import ENGINE_VERSION, PalletizationService
from palletizer.contracts import (
    CapabilitiesResponse,
    PalletizeRequest,
    PalletizeResponse,
    ParseCsvResponse,
)
from palletizer.domain.enums import OptimizationLevel
from palletizer.domain.errors import CsvLimitExceededError, PalletizerError
from palletizer.domain.models import OptimizationOptions, Order
from palletizer.imports.legacy_csv import MAX_CSV_BYTES, MAX_CSV_ROWS, parse_legacy_csv

app = typer.Typer(
    name="palletizer",
    help="Moteur headless de palettisation 3D et de chargement transport.",
    no_args_is_help=True,
)


def _err(message: str) -> None:
    typer.echo(message, err=True)


def _read_bytes(path: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()
    file_path = Path(path)
    if not file_path.exists():
        _err(f"Erreur : fichier introuvable : {path}")
        raise typer.Exit(code=1)
    return file_path.read_bytes()


def _write_output(content: str, output: str | None) -> None:
    if output is None or output == "-":
        typer.echo(content)
    else:
        Path(output).write_text(content, encoding="utf-8")
        _err(f"Résultat écrit dans {output}")


@app.command("validate-csv")
def validate_csv(path: str = typer.Argument(..., help="Chemin du CSV, ou '-' pour stdin.")) -> None:
    """Valide la structure du CSV et affiche un rapport (commandes, lignes acceptées/rejetées)."""
    content = _read_bytes(path)
    try:
        preview = parse_legacy_csv(content)
    except CsvLimitExceededError as exc:
        _err(f"Erreur : {exc}")
        raise typer.Exit(code=1) from exc

    if not preview.orders and preview.errors and preview.errors[0].code == "MISSING_REQUIRED_FIELD":
        _err(f"Erreur : {preview.errors[0].message}")
        raise typer.Exit(code=1)

    typer.echo(f"Lignes totales      : {preview.total_rows}")
    typer.echo(f"Lignes acceptées    : {preview.accepted_rows}")
    typer.echo(f"Lignes rejetées     : {preview.rejected_rows}")
    typer.echo(f"Commandes détectées : {len(preview.orders)}")
    for order in preview.orders:
        typer.echo(
            f"  - {order.order_id} : {len(order.lines)} ligne(s), "
            f"format {order.pallet_spec.code}, mode {order.shipping_mode.value}, "
            f"historique PALXENT={order.legacy_expected_result.pallet_count}"
        )
    if preview.errors:
        typer.echo("Erreurs :")
        for error in preview.errors:
            typer.echo(f"  - ligne {error.line_number} [{error.code}] {error.message}")
    if preview.warnings:
        typer.echo("Avertissements :")
        for warning in preview.warnings:
            typer.echo(f"  - {warning.message}")

    if preview.rejected_rows > 0:
        _err(f"Attention : {preview.rejected_rows} ligne(s) rejetée(s), voir le détail ci-dessus.")


@app.command("parse-csv")
def parse_csv_command(
    path: str = typer.Argument(..., help="Chemin du CSV, ou '-' pour stdin."),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Fichier de sortie, ou '-' pour stdout."
    ),
) -> None:
    """Analyse le CSV et écrit le JSON normalisé (commandes, lignes, erreurs, avertissements)."""
    content = _read_bytes(path)
    try:
        preview = parse_legacy_csv(content)
    except CsvLimitExceededError as exc:
        _err(f"Erreur : {exc}")
        raise typer.Exit(code=1) from exc

    response = ParseCsvResponse.from_domain(preview)
    _write_output(response.model_dump_json(by_alias=True, indent=2), output)
    if preview.rejected_rows > 0:
        _err(f"Attention : {preview.rejected_rows} ligne(s) rejetée(s).")


@app.command("optimize")
def optimize_command(
    path: str = typer.Argument(..., help="Chemin du JSON normalisé (contrat), ou '-' pour stdin."),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Fichier de sortie, ou '-' pour stdout."
    ),
) -> None:
    """Exécute l'optimisation à partir d'un JSON normalisé conforme au contrat."""
    raw = _read_bytes(path)
    try:
        request = PalletizeRequest.model_validate_json(raw)
    except Exception as exc:  # pydantic.ValidationError
        _err(f"Erreur de validation du contrat JSON : {exc}")
        raise typer.Exit(code=1) from exc

    order = request.order.to_domain()
    pallet_spec = request.pallet.to_domain(request.options.minimum_support_ratio)
    options = request.options.to_domain()

    try:
        result = PalletizationService().optimize(order, pallet_spec, options)
    except PalletizerError as exc:
        _err(f"Erreur du moteur : {exc}")
        raise typer.Exit(code=1) from exc

    response = PalletizeResponse.from_domain(result)
    _write_output(response.model_dump_json(by_alias=True, indent=2), output)
    for warning in result.warnings:
        _err(f"Avertissement : {warning}")


@app.command("optimize-csv")
def optimize_csv_command(
    path: str = typer.Argument(..., help="Chemin du CSV, ou '-' pour stdin."),
    order: str | None = typer.Option(
        None, "--order", help="Identifiant de commande (CDEXENT) à optimiser."
    ),
    level: str = typer.Option("fast", "--level", help="fast | thorough"),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Fichier de sortie, ou '-' pour stdout."
    ),
) -> None:
    """Analyse le CSV puis optimise une commande (sélection --order obligatoire si plusieurs)."""
    content = _read_bytes(path)
    try:
        preview = parse_legacy_csv(content)
    except CsvLimitExceededError as exc:
        _err(f"Erreur : {exc}")
        raise typer.Exit(code=1) from exc

    if not preview.orders:
        _err("Erreur : aucune commande valide détectée dans le CSV.")
        raise typer.Exit(code=1)

    if order is None:
        if len(preview.orders) > 1:
            available = ", ".join(o.order_id for o in preview.orders)
            _err(f"Erreur : plusieurs commandes détectées ({available}). Précisez --order.")
            raise typer.Exit(code=1)
        selected = preview.orders[0]
    else:
        matches = [o for o in preview.orders if o.order_id == order]
        if not matches:
            _err(f"Erreur : commande {order!r} introuvable dans le CSV.")
            raise typer.Exit(code=1)
        selected = matches[0]

    try:
        optimization_level = OptimizationLevel(level)
    except ValueError as exc:
        _err(f"Erreur : niveau d'optimisation invalide {level!r} (attendu fast|thorough).")
        raise typer.Exit(code=1) from exc

    domain_order = Order(
        order_id=selected.order_id, shipping_mode=selected.shipping_mode, lines=selected.lines
    )
    options = OptimizationOptions(optimization_level=optimization_level)
    try:
        result = PalletizationService().optimize(
            domain_order,
            selected.pallet_spec,
            options,
            legacy_expected_result=selected.legacy_expected_result,
        )
    except PalletizerError as exc:
        _err(f"Erreur du moteur : {exc}")
        raise typer.Exit(code=1) from exc

    response = PalletizeResponse.from_domain(result)
    _write_output(response.model_dump_json(by_alias=True, indent=2), output)
    if selected.legacy_expected_result.pallet_count is not None:
        _err(
            f"Comparaison historique : PALXENT={selected.legacy_expected_result.pallet_count} "
            f"vs calculé={result.pallets_count}"
        )
    for warning in result.warnings:
        _err(f"Avertissement : {warning}")


@app.command("capabilities")
def capabilities_command() -> None:
    """Affiche les capacités du moteur (formats supportés, limites, adaptateur de packing)."""
    from palletizer.api.routes import PACKING_ADAPTER_NAME, PACKING_ADAPTER_VERSION

    response = CapabilitiesResponse(
        supportedPalletFormats=("P:{longueur_cm}x{largeur_cm}x{hauteur_cm}",),
        constraints=(
            "allowRotation",
            "uprightOnly",
            "fragile",
            "stackable",
            "maxSupportedWeightKg",
            "incompatibleGroups",
            "safetyGapMm",
            "overhangMm",
            "minimumSupportRatio",
            "maxWeightKg",
        ),
        limits={
            "maxCsvBytes": MAX_CSV_BYTES,
            "maxCsvRows": MAX_CSV_ROWS,
            "practicalInstanceLimit": 500,
        },
        packingAdapter={"name": PACKING_ADAPTER_NAME, "version": PACKING_ADAPTER_VERSION},
    )
    typer.echo(response.model_dump_json(by_alias=True, indent=2))


@app.command("transport-load")
def transport_load_command(
    path: str = typer.Argument(
        ..., help="Chemin du JSON (contrat TransportLoadRequest : pallets + vehicle), ou '-'."
    ),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Fichier de sortie, ou '-' pour stdout."
    ),
) -> None:
    """Calcule le chargement des palettes dans un véhicule/conteneur."""
    from palletizer.application.services import TransportLoadingService
    from palletizer.contracts import TransportLoadRequest, TransportLoadResponse

    raw = _read_bytes(path)
    try:
        request = TransportLoadRequest.model_validate_json(raw)
    except Exception as exc:
        _err(f"Erreur de validation du contrat JSON : {exc}")
        raise typer.Exit(code=1) from exc

    pallets = [p.to_domain() for p in request.pallets]
    vehicle = request.vehicle.to_domain()
    result = TransportLoadingService().compute(pallets, vehicle)
    response = TransportLoadResponse.from_domain(result)
    _write_output(response.model_dump_json(by_alias=True, indent=2), output)


@app.command("version")
def version_command() -> None:
    """Affiche la version du package et du moteur."""
    typer.echo(json.dumps({"version": __version__, "engineVersion": ENGINE_VERSION}))


if __name__ == "__main__":
    app()
