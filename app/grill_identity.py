from __future__ import annotations

from dataclasses import dataclass

from app.models import Equipment


@dataclass(frozen=True)
class GrillIdentity:
    maker: str | None
    model: str | None


def display_grill_identity(
    equipment: Equipment | None,
    fallback: GrillIdentity | None = None,
) -> GrillIdentity:
    """Prefer saved equipment names, then use the discovered device identity."""
    return GrillIdentity(
        maker=(equipment.maker if equipment is not None else None)
        or (fallback.maker if fallback is not None else None),
        model=(equipment.model if equipment is not None else None)
        or (fallback.model if fallback is not None else None),
    )
