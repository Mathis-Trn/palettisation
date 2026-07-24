"""Schémas spécifiques à la couche HTTP (enveloppe d'erreur, corrélation). Les schémas métier
(requête/réponse `/palletize`, `/orders/parse-csv`, `/transport/load`) vivent dans
`palletizer.contracts`, réutilisables sans FastAPI."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
