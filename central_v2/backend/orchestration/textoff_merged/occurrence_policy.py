"""Central V2: declarative policy for approved occurrence types.

M1 only: this module does not change the operational Cleaner/Level II worker.
Protection is integrated and verified in M2.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class OccurrencePolicy:
    label: str
    protect_from_transparency_basic: bool


# Stable IDs persisted as ``tipo`` in Auto-Cleaner Check manifests.
# Deliberately conservative for types requiring specialized/manual review.
OCCURRENCE_POLICIES = {
    "residuo_transparencia": OccurrencePolicy("Resíduo de transparência", False),
    "residuo_degrade": OccurrencePolicy("Resíduo de degradê", True),
    "residuo_gradiente": OccurrencePolicy("Resíduo de gradiente", True),
    "balao_estilizado": OccurrencePolicy("Balão estilizado", True),
    "fragmento_balao": OccurrencePolicy("Fragmento de balão", True),
    "texto_residual": OccurrencePolicy("Texto residual", False),
    "outro": OccurrencePolicy("Outro defeito", True),
}


def policy_for(occurrence_type: str) -> OccurrencePolicy:
    """Reject unknown classifications instead of silently ignoring them."""
    try:
        return OCCURRENCE_POLICIES[occurrence_type]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Tipo de ocorrência desconhecido: {occurrence_type!r}") from exc


def protected_types_for_transparency_basic() -> frozenset[str]:
    """Return type IDs whose approved regions must survive Level II."""
    return frozenset(
        type_id for type_id, policy in OCCURRENCE_POLICIES.items()
        if policy.protect_from_transparency_basic
    )
