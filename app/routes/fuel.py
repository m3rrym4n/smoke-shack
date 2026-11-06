from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Fuel
from app.pantry_photos import delete_photo, photo_response, save_photo
from app.schemas import FuelCreate, FuelResponse, FuelType, FuelUpdate, clean_upc

router = APIRouter(prefix="/api/fuel", tags=["fuel"])
SessionDep = Annotated[Session, Depends(get_session)]


def _get_fuel(fuel_id: int, session: Session) -> Fuel:
    item = session.get(Fuel, fuel_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuel not found")
    return item


@router.get("", response_model=list[FuelResponse])
def list_fuel(
    session: SessionDep,
    type: FuelType | None = None,
    upc: str | None = None,
    include_empty: bool = False,
) -> list[Fuel]:
    query = select(Fuel).order_by(Fuel.vendor, Fuel.product_name, Fuel.id)
    if type is not None:
        query = query.where(Fuel.type == type)
    if not include_empty:
        query = query.where(Fuel.emptied_on.is_(None))
    if upc is not None:
        try:
            cleaned_upc = clean_upc(upc)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        query = query.where(Fuel.upc == cleaned_upc)
    return list(session.scalars(query))


@router.post("", response_model=FuelResponse, status_code=status.HTTP_201_CREATED)
def create_fuel(payload: FuelCreate, session: SessionDep) -> Fuel:
    item = Fuel(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/{fuel_id}", response_model=FuelResponse)
def get_fuel(fuel_id: int, session: SessionDep) -> Fuel:
    return _get_fuel(fuel_id, session)


@router.patch("/{fuel_id}", response_model=FuelResponse)
def update_fuel(fuel_id: int, payload: FuelUpdate, session: SessionDep) -> Fuel:
    item = _get_fuel(fuel_id, session)
    changes = payload.model_dump(exclude_unset=True)
    purchased_on = changes.get("purchased_on", item.purchased_on)
    emptied_on = changes.get("emptied_on", item.emptied_on)
    if emptied_on is not None:
        if emptied_on < purchased_on:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty date cannot be before purchase date"
            )
        if emptied_on > date.today():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Empty date cannot be in the future"
            )
    for field, value in changes.items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    return item


@router.post("/{fuel_id}/photo", response_model=FuelResponse)
async def upload_fuel_photo(
    fuel_id: int, request: Request, session: SessionDep, file: Annotated[UploadFile, File()]
) -> Fuel:
    item = _get_fuel(fuel_id, session)
    item.photo_path = await save_photo(
        file, request.app.state.photo_dir, "fuel", item.id, item.photo_path
    )
    session.commit()
    session.refresh(item)
    return item


@router.get("/{fuel_id}/photo", response_class=FileResponse)
def get_fuel_photo(fuel_id: int, session: SessionDep) -> FileResponse:
    return photo_response(_get_fuel(fuel_id, session).photo_path)


@router.delete("/{fuel_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_fuel_photo(fuel_id: int, session: SessionDep) -> Response:
    item = _get_fuel(fuel_id, session)
    old_path = item.photo_path
    item.photo_path = None
    session.commit()
    delete_photo(old_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{fuel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fuel(fuel_id: int, session: SessionDep) -> Response:
    item = _get_fuel(fuel_id, session)
    if session.scalar(select(Cook.id).where(Cook.fuel_id == fuel_id).limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Fuel is referenced by a cook")
    photo_path = item.photo_path
    session.delete(item)
    session.commit()
    delete_photo(photo_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
