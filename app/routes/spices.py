from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Spice, cook_spices
from app.pantry_photos import delete_photo, photo_response, save_photo
from app.schemas import SpiceCreate, SpiceResponse, SpiceUpdate

router = APIRouter(prefix="/api/spices", tags=["spices"])
SessionDep = Annotated[Session, Depends(get_session)]


def _get_spice(spice_id: int, session: Session) -> Spice:
    item = session.get(Spice, spice_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Spice not found")
    return item


def _is_custom_blend(item: Spice) -> bool:
    return item.brand.casefold() == "custom" and item.name.casefold() == "custom blend"


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A spice with this brand and name already exists"
        ) from error


@router.get("", response_model=list[SpiceResponse])
def list_spices(session: SessionDep, brand: str | None = None) -> list[Spice]:
    query = select(Spice)
    if brand is not None:
        query = query.where(func.lower(Spice.brand) == brand.lower())
    query = query.order_by(func.lower(Spice.brand), func.lower(Spice.name), Spice.id)
    return list(session.scalars(query))


@router.post("", response_model=SpiceResponse, status_code=status.HTTP_201_CREATED)
def create_spice(payload: SpiceCreate, session: SessionDep) -> Spice:
    item = Spice(**payload.model_dump(), is_custom=payload.brand.casefold() == "custom")
    session.add(item)
    _commit(session)
    session.refresh(item)
    return item


@router.get("/{spice_id}", response_model=SpiceResponse)
def get_spice(spice_id: int, session: SessionDep) -> Spice:
    return _get_spice(spice_id, session)


@router.patch("/{spice_id}", response_model=SpiceResponse)
def update_spice(spice_id: int, payload: SpiceUpdate, session: SessionDep) -> Spice:
    item = _get_spice(spice_id, session)
    changes = payload.model_dump(exclude_unset=True)
    if _is_custom_blend(item) and any(field in changes for field in ("brand", "name")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Custom blend cannot be renamed")
    for field, value in changes.items():
        setattr(item, field, value)
    if "brand" in changes:
        item.is_custom = item.brand.casefold() == "custom"
    _commit(session)
    session.refresh(item)
    return item


@router.post("/{spice_id}/photo", response_model=SpiceResponse)
async def upload_spice_photo(
    spice_id: int,
    request: Request,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> Spice:
    item = _get_spice(spice_id, session)
    item.photo_path = await save_photo(
        file, request.app.state.photo_dir, "spices", item.id, item.photo_path
    )
    session.commit()
    session.refresh(item)
    return item


@router.get("/{spice_id}/photo", response_class=FileResponse)
def get_spice_photo(spice_id: int, session: SessionDep) -> FileResponse:
    return photo_response(_get_spice(spice_id, session).photo_path)


@router.delete("/{spice_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_spice_photo(spice_id: int, session: SessionDep) -> Response:
    item = _get_spice(spice_id, session)
    old_path = item.photo_path
    item.photo_path = None
    session.commit()
    delete_photo(old_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{spice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spice(spice_id: int, session: SessionDep) -> Response:
    item = _get_spice(spice_id, session)
    if _is_custom_blend(item):
        raise HTTPException(status.HTTP_409_CONFLICT, "Custom blend cannot be deleted")
    if session.scalar(
        select(cook_spices.c.cook_id).where(cook_spices.c.spice_id == spice_id).limit(1)
    ) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Spice is referenced by a cook")
    photo_path = item.photo_path
    session.delete(item)
    session.commit()
    delete_photo(photo_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
