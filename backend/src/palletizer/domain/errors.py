"""Exceptions du domaine. Aucune dépendance à un framework."""


class PalletizerError(Exception):
    """Base de toutes les erreurs métier du moteur."""


class InvalidOrderLineError(PalletizerError):
    """Ligne de commande invalide (dimensions/poids/quantité incohérents)."""


class InvalidPalletSpecError(PalletizerError):
    """Spécification de palette invalide (dimensions ou limites incohérentes)."""


class UnsolvableEmptyPalletError(PalletizerError):
    """Un carton ne peut tenir sur une palette vide : garde-fou anti-boucle infinie."""


class SolutionValidationError(PalletizerError):
    """La post-validation indépendante a détecté une solution de packing invalide."""


class AmbiguousCartonDetailsError(PalletizerError):
    """Le décodeur CSV n'a pas pu résoudre sans ambiguïté les colonnes CARTON_DETAIL_*."""

    def __init__(self, line_number: int, raw_fragments: list[str], reason: str) -> None:
        self.line_number = line_number
        self.raw_fragments = raw_fragments
        self.reason = reason
        super().__init__(
            f"Ligne {line_number} : impossible de décoder CARTON_DETAIL_* sans ambiguïté "
            f"({reason}) — fragments bruts: {raw_fragments}"
        )


class CsvLimitExceededError(PalletizerError):
    """Le CSV dépasse une limite de sécurité (taille, nombre de lignes, nombre d'instances)."""
