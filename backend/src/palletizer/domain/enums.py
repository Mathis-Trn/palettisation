"""Énumérations du domaine. Aucune dépendance à un framework."""

from enum import StrEnum


class OrientationCode(StrEnum):
    """Les 6 permutations des axes longueur (L) / largeur (W) / hauteur (H).

    Le code se lit comme l'ordre (axe_x, axe_y, axe_z) après rotation : ``WLH`` signifie que la
    largeur d'origine est posée le long de l'axe X, la longueur d'origine le long de l'axe Y, la
    hauteur d'origine restant verticale (axe Z).
    """

    LWH = "LWH"
    WLH = "WLH"
    LHW = "LHW"
    HWL = "HWL"
    WHL = "WHL"
    HLW = "HLW"


UPRIGHT_ORIENTATIONS = (OrientationCode.LWH, OrientationCode.WLH)
"""Orientations qui conservent la hauteur d'origine verticale (sens vertical obligatoire)."""


class RejectionCode(StrEnum):
    DIMENSIONS_EXCEED_PALLET = "DIMENSIONS_EXCEED_PALLET"
    HEIGHT_EXCEEDED = "HEIGHT_EXCEEDED"
    WEIGHT_EXCEEDED = "WEIGHT_EXCEEDED"
    ROTATION_FORBIDDEN = "ROTATION_FORBIDDEN"
    STACKING_CONSTRAINT = "STACKING_CONSTRAINT"
    NO_STABLE_POSITION = "NO_STABLE_POSITION"
    INVALID_DATA = "INVALID_DATA"
    INCOMPATIBLE_GROUP = "INCOMPATIBLE_GROUP"


REJECTION_MESSAGES: dict[RejectionCode, str] = {
    RejectionCode.DIMENSIONS_EXCEED_PALLET: (
        "Le carton dépasse les dimensions utiles de la palette dans toutes les orientations "
        "autorisées."
    ),
    RejectionCode.HEIGHT_EXCEEDED: "Aucune orientation autorisée ne respecte la hauteur utile.",
    RejectionCode.WEIGHT_EXCEEDED: "Le poids du carton dépasse la charge maximale de la palette.",
    RejectionCode.ROTATION_FORBIDDEN: (
        "Le carton ne tient dans aucune orientation autorisée par ses réglages de rotation."
    ),
    RejectionCode.STACKING_CONSTRAINT: (
        "Aucune position stable respectant les règles de gerbage/fragilité n'a été trouvée."
    ),
    RejectionCode.NO_STABLE_POSITION: "Aucune position avec un support suffisant n'a été trouvée.",
    RejectionCode.INVALID_DATA: "Donnée de ligne de commande invalide.",
    RejectionCode.INCOMPATIBLE_GROUP: (
        "Le carton est incompatible avec toutes les palettes ouvertes et ne peut être replacé."
    ),
}


class ImportRejectionCode(StrEnum):
    """Codes de rejet spécifiques à l'import CSV legacy (distincts des rejets de placement)."""

    AMBIGUOUS_CARTON_DETAILS = "AMBIGUOUS_CARTON_DETAILS"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_PALLET_FORMAT = "INVALID_PALLET_FORMAT"
    INVALID_QUANTITY = "INVALID_QUANTITY"


class ShippingMode(StrEnum):
    SEA = "sea"
    AIR = "air"
    ROAD = "road"
    UNKNOWN = "unknown"


class OptimizationLevel(StrEnum):
    FAST = "fast"
    THOROUGH = "thorough"


class SortStrategyName(StrEnum):
    VOLUME_DESC = "volume-desc"
    LARGEST_DIMENSION_DESC = "largest-dimension-desc"
    WEIGHT_DESC = "weight-desc"
    FOOTPRINT_DESC = "footprint-desc"


QUICK_STRATEGIES = (SortStrategyName.VOLUME_DESC,)
THOROUGH_STRATEGIES = (
    SortStrategyName.VOLUME_DESC,
    SortStrategyName.LARGEST_DIMENSION_DESC,
    SortStrategyName.WEIGHT_DESC,
    SortStrategyName.FOOTPRINT_DESC,
)
