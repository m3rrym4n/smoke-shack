from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Equipment


def first_equipment_id(session: Session) -> int:
    return session.scalars(select(Equipment.id).order_by(Equipment.id).limit(1)).one()


def connected_equipment_id(session: Session) -> int | None:
    return session.scalar(select(Equipment.id).where(Equipment.connected.is_(True)))
