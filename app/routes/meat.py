from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Meat
from app.pantry_photos import delete_photo, photo_response, save_photo
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
    session: SessionDep, type_filter: str | None = Query(default=None, alias="type")
) -> list[Meat]:
    query = select(Meat)
    if type_filter is not None:
        query = query.where(func.lower(Meat.type).contains(type_filter.lower()))
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


@router.post("/{meat_id}/photo", response_model=MeatResponse)
async def upload_meat_photo(
    meat_id: int,
    request: Request,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> Meat:
    item = _get_meat(meat_id, session)
    item.photo_path = await save_photo(
        file, request.app.state.photo_dir, "meat", item.id, item.photo_path
    )
    session.commit()
    session.refresh(item)
    return item


@router.get("/{meat_id}/photo", response_class=FileResponse)
def get_meat_photo(meat_id: int, session: SessionDep) -> FileResponse:
    return photo_response(_get_meat(meat_id, session).photo_path)


@router.delete("/{meat_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_meat_photo(meat_id: int, session: SessionDep) -> Response:
    item = _get_meat(meat_id, session)
    old_path = item.photo_path
    item.photo_path = None
    session.commit()
    delete_photo(old_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{meat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_meat(meat_id: int, session: SessionDep) -> Response:
    item = _get_meat(meat_id, session)
    if session.scalar(select(Cook.id).where(Cook.meat_id == meat_id).limit(1)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Meat is referenced by a cook")
    photo_path = item.photo_path
    session.delete(item)
    session.commit()
    delete_photo(photo_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
