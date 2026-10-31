from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.deps import get_session
from app.models import Meat, MeatGroup, MeatGroupType

router = APIRouter(prefix="/api/meat-groups", tags=["meat-groups"])
SessionDep = Annotated[Session, Depends(get_session)]


class GroupName(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value


class GroupTypes(BaseModel):
    types: list[str]

    @field_validator("types")
    @classmethod
    def normalize_types(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))


def _get_group(group_id: int, session: Session) -> MeatGroup:
    group = session.get(MeatGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meat group not found")
    return group


def _group_json(group: MeatGroup) -> dict[str, Any]:
    return {"id": group.id, "name": group.name, "types": [item.type_key for item in group.types]}


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Meat group name already exists") from error


@router.get("")
def list_groups(session: SessionDep) -> dict[str, Any]:
    groups = list(
        session.scalars(
            select(MeatGroup).options(selectinload(MeatGroup.types)).order_by(MeatGroup.name)
        )
    )
    grouped = select(MeatGroupType.type_key)
    ungrouped = list(
        session.scalars(
            select(Meat.type)
            .distinct()
            .where(func.lower(func.trim(Meat.type)).not_in(grouped))
            .order_by(Meat.type)
        )
    )
    return {"groups": [_group_json(group) for group in groups], "ungrouped_types": ungrouped}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupName, session: SessionDep) -> dict[str, Any]:
    group = MeatGroup(name=payload.name)
    session.add(group)
    _commit(session)
    session.refresh(group)
    return _group_json(group)


@router.patch("/{group_id}")
def rename_group(group_id: int, payload: GroupName, session: SessionDep) -> dict[str, Any]:
    group = _get_group(group_id, session)
    group.name = payload.name
    _commit(session)
    session.refresh(group)
    return _group_json(group)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, session: SessionDep) -> Response:
    session.delete(_get_group(group_id, session))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{group_id}/types")
def replace_group_types(
    group_id: int, payload: GroupTypes, session: SessionDep
) -> dict[str, Any]:
    group = _get_group(group_id, session)
    session.execute(delete(MeatGroupType).where(MeatGroupType.group_id == group.id))
    if payload.types:
        session.execute(delete(MeatGroupType).where(MeatGroupType.type_key.in_(payload.types)))
        session.add_all(
            MeatGroupType(group_id=group.id, type_key=type_key) for type_key in payload.types
        )
    session.commit()
    session.refresh(group)
    return _group_json(group)
