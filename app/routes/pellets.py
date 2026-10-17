from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Pellet
from app.schemas import PelletCreate, PelletResponse, PelletUpdate

router = APIRouter(prefix="/api/pellets", tags=["pellets"])
SessionDep = Annotated[Session, Depends(get_session)]


def _get_pellet(pellet_id: int, session: Session) -> Pellet:
    item = session.get(Pellet, pellet_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pellet not found")
    return item


@router.get("", response_model=list[PelletResponse])
def list_pellets(session: SessionDep) -> list[Pellet]:
    query = select(Pellet).order_by(Pellet.vendor, Pellet.product_name, Pellet.id)
    return list(session.scalars(query))


@router.post("", response_model=PelletResponse, status_code=status.HTTP_201_CREATED)
def create_pellet(payload: PelletCreate, session: SessionDep) -> Pellet:
    item = Pellet(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/{pellet_id}", response_model=PelletResponse)
def get_pellet(pellet_id: int, session: SessionDep) -> Pellet:
    return _get_pellet(pellet_id, session)


@router.patch("/{pellet_id}", response_model=PelletResponse)
def update_pellet(pellet_id: int, payload: PelletUpdate, session: SessionDep) -> Pellet:
    item = _get_pellet(pellet_id, session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{pellet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pellet(pellet_id: int, session: SessionDep) -> Response:
    item = _get_pellet(pellet_id, session)
    if session.scalar(select(Cook.id).where(Cook.pellet_id == pellet_id).limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pellet is referenced by a cook")
    session.delete(item)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
