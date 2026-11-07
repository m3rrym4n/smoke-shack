from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Equipment


@dataclass(frozen=True)
class WatchedChannel:
    key: str
    source_entity: str
    target_entity: str | None


@dataclass(frozen=True)
class ConnectedEquipment:
    id: int
    channels: tuple[WatchedChannel, ...]
    status_entities: dict[str, str] = field(default_factory=dict)
    stale_after_seconds: int | None = None


def first_equipment_id(session: Session) -> int:
    return session.scalars(select(Equipment.id).order_by(Equipment.id).limit(1)).one()


def connected_equipment_id(session: Session) -> int | None:
    return session.scalar(select(Equipment.id).where(Equipment.connected.is_(True)))


def connected_equipment(session: Session) -> ConnectedEquipment | None:
    equipment = session.scalar(
        select(Equipment)
        .options(selectinload(Equipment.channels), selectinload(Equipment.entities))
        .where(Equipment.connected.is_(True))
    )
    if equipment is None:
        return None
    return ConnectedEquipment(
        id=equipment.id,
        channels=tuple(
            WatchedChannel(channel.key, channel.source_entity, channel.target_entity)
            for channel in equipment.channels
        ),
        status_entities={entity.role: entity.entity_id for entity in equipment.entities},
        stale_after_seconds=equipment.stale_after_seconds,
    )
