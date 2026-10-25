from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Meat
from app.schemas import MeatCreate, MeatResponse, MeatUpdate

router = APIRouter(prefix="/api/meat", tags=["meat"])
SessionDep = Annotated[Session, Depends(get_session)]


def _get_meat(meat_id: int, session: Session) -> Meat:
    item = session.get(Meat, meat_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meat not found")
    return item


@router.get("", response_model=list[MeatResponse])
def list_meat(
    session: SessionDep,
    type_filter: str | None = Query(default=None, alias="type"),
    cooked: bool | None = None,
) -> list[Meat]:
    query = select(Meat)
    if type_filter is not None:
        query = query.where(func.lower(Meat.type).contains(type_filter.lower()))
    if cooked is not None:
        query = query.where(Meat.cooked == cooked)
    return list(session.scalars(query.order_by(Meat.purchased_on.desc(), Meat.id.desc())))


@router.post("", response_model=MeatResponse, status_code=status.HTTP_201_CREATED)
def create_meat(payload: MeatCreate, session: SessionDep) -> Meat:
    item = Meat(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/{meat_id}", response_model=MeatResponse)
def get_meat(meat_id: int, session: SessionDep) -> Meat:
    return _get_meat(meat_id, session)


@router.patch("/{meat_id}", response_model=MeatResponse)
def update_meat(meat_id: int, payload: MeatUpdate, session: SessionDep) -> Meat:
    item = _get_meat(meat_id, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{meat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meat(meat_id: int, session: SessionDep) -> Response:
    item = _get_meat(meat_id, session)
    if session.scalar(select(Cook.id).where(Cook.meat_id == meat_id).limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Meat is referenced by a cook")
    session.delete(item)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
