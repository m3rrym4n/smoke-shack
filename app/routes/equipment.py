from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_session
from app.equipment_images import (
    delete_equipment_image,
    equipment_image_response,
    save_equipment_image,
)
from app.models import Equipment

router = APIRouter(prefix="/api/equipment", tags=["equipment"])
SessionDep = Annotated[Session, Depends(get_session)]


class EquipmentResponse(BaseModel):
    id: int
    nickname: str
    maker: str | None
    model: str | None
    type: str
    fuel_type: str | None
    units: str
    connected: bool
    has_photo: bool
    photo_url: str | None
    has_logo: bool
    logo_url: str | None


def equipment_response(item: Equipment) -> EquipmentResponse:
    return EquipmentResponse(
        id=item.id,
        nickname=item.nickname,
        maker=item.maker,
        model=item.model,
        type=item.type,
        fuel_type=item.fuel_type,
        units=item.units,
        connected=item.connected,
        has_photo=item.photo_path is not None,
        photo_url=f"/api/equipment/{item.id}/photo" if item.photo_path is not None else None,
        has_logo=item.logo_path is not None,
        logo_url=f"/api/equipment/{item.id}/logo" if item.logo_path is not None else None,
    )


def _get_equipment(equipment_id: int, session: Session) -> Equipment:
    item = session.get(Equipment, equipment_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipment not found")
    return item


@router.get("/{equipment_id}", response_model=EquipmentResponse)
def get_equipment(equipment_id: int, session: SessionDep) -> EquipmentResponse:
    return equipment_response(_get_equipment(equipment_id, session))


@router.post("/{equipment_id}/{kind}", response_model=EquipmentResponse)
async def upload_equipment_image(
    equipment_id: int,
    kind: Literal["photo", "logo"],
    request: Request,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> EquipmentResponse:
    item = _get_equipment(equipment_id, session)
    field = f"{kind}_path"
    path = await save_equipment_image(
        file,
        request.app.state.photo_dir,
        item.id,
        kind,
        getattr(item, field),
    )
    setattr(item, field, path)
    session.commit()
    session.refresh(item)
    return equipment_response(item)


@router.get("/{equipment_id}/{kind}", response_class=FileResponse)
def get_equipment_image(
    equipment_id: int,
    kind: Literal["photo", "logo"],
    session: SessionDep,
) -> FileResponse:
    item = _get_equipment(equipment_id, session)
    return equipment_image_response(getattr(item, f"{kind}_path"))


@router.delete("/{equipment_id}/{kind}", status_code=status.HTTP_204_NO_CONTENT)
def remove_equipment_image(
    equipment_id: int,
    kind: Literal["photo", "logo"],
    session: SessionDep,
) -> Response:
    item = _get_equipment(equipment_id, session)
    field = f"{kind}_path"
    old_path = getattr(item, field)
    setattr(item, field, None)
    session.commit()
    delete_equipment_image(old_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
