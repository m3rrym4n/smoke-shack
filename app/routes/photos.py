from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Cook, Event, Photo
from app.schemas import PhotoResponse, PhotoUpdate

router = APIRouter(tags=["photos"])
SessionDep = Annotated[Session, Depends(get_session)]

MAX_PHOTO_BYTES = 15 * 1024 * 1024
PHOTO_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _get_photo(photo_id: int, session: Session) -> Photo:
    photo = session.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    return photo


def _photo_json(photo: Photo) -> PhotoResponse:
    return PhotoResponse(
        id=photo.id,
        cook_id=photo.cook_id,
        event_id=photo.event_id,
        caption=photo.caption,
        url=f"/api/photos/{photo.id}/file",
    )


@router.post(
    "/api/cooks/{cook_id}/photos",
    response_model=PhotoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_photo(
    cook_id: int,
    request: Request,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    caption: Annotated[str | None, Form()] = None,
    event_id: Annotated[int | None, Form()] = None,
) -> PhotoResponse:
    if session.get(Cook, cook_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cook not found")
    event = session.get(Event, event_id) if event_id is not None else None
    if event_id is not None and (event is None or event.cook_id != cook_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Event must belong to the same cook",
        )
    extension = PHOTO_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported photo type")

    directory: Path = request.app.state.photo_dir / str(cook_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4()}{extension}"
    size = 0
    try:
        with path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_PHOTO_BYTES:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        "Photo exceeds 15 MB limit",
                    )
                destination.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    photo = Photo(cook_id=cook_id, event_id=event_id, path=str(path), caption=caption)
    session.add(photo)
    if event is not None:
        event.photo_path = str(path)
    try:
        session.commit()
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    session.refresh(photo)
    return _photo_json(photo)


@router.get("/api/photos/{photo_id}/file", response_class=FileResponse)
def photo_file(photo_id: int, session: SessionDep) -> FileResponse:
    photo = _get_photo(photo_id, session)
    path = Path(photo.path)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo file not found")
    media_type = next(
        (
            content_type
            for content_type, extension in PHOTO_TYPES.items()
            if extension == path.suffix
        ),
        "application/octet-stream",
    )
    return FileResponse(path, media_type=media_type)


@router.get("/api/cooks/{cook_id}/photos", response_model=list[PhotoResponse])
def list_photos(cook_id: int, session: SessionDep) -> list[PhotoResponse]:
    if session.get(Cook, cook_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cook not found")
    photos = session.scalars(select(Photo).where(Photo.cook_id == cook_id).order_by(Photo.id))
    return [_photo_json(photo) for photo in photos]


@router.patch("/api/photos/{photo_id}", response_model=PhotoResponse)
def update_photo(photo_id: int, payload: PhotoUpdate, session: SessionDep) -> PhotoResponse:
    photo = _get_photo(photo_id, session)
    if "caption" in payload.model_fields_set:
        photo.caption = payload.caption
    session.commit()
    session.refresh(photo)
    return _photo_json(photo)


@router.delete("/api/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(photo_id: int, session: SessionDep) -> Response:
    photo = _get_photo(photo_id, session)
    path = Path(photo.path)
    if photo.event_id is not None:
        event = session.get(Event, photo.event_id)
        if event is not None and event.photo_path == photo.path:
            event.photo_path = None
    session.delete(photo)
    session.commit()
    path.unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
