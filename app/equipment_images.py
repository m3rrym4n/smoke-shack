from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.pantry_photos import MAX_PHOTO_BYTES, PHOTO_TYPES, sniff_photo_type
from app.routes.showcase import _validate_svg

logger = logging.getLogger(__name__)

ImageKind = Literal["photo", "logo"]
SVG_TYPE = "image/svg+xml"


async def save_equipment_image(
    file: UploadFile,
    photo_dir: Path,
    equipment_id: int,
    kind: ImageKind,
    old_path: str | None,
) -> str:
    data = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > MAX_PHOTO_BYTES:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    "Image exceeds 5 MB limit",
                )
    finally:
        await file.close()

    content = bytes(data)
    if kind == "logo" and re.search(rb"<svg\b", content, re.IGNORECASE):
        _validate_svg(content)
        extension = ".svg"
    else:
        try:
            _, extension = sniff_photo_type(content)
        except HTTPException as exc:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "Unsupported image type",
            ) from exc

    directory = photo_dir / "equipment" / str(equipment_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{kind}{extension}"
    temporary = directory / f".{kind}-{uuid4()}.upload"
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    if old_path is not None and Path(old_path) != path:
        delete_equipment_image(old_path)
    return str(path)


def delete_equipment_image(image_path: str | None) -> None:
    if image_path is None:
        return
    try:
        Path(image_path).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete equipment image %s", image_path, exc_info=True)


def equipment_image_response(image_path: str | None) -> FileResponse:
    if image_path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipment image not found")
    path = Path(image_path)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipment image file not found")
    media_type = SVG_TYPE if path.suffix == ".svg" else next(
        (content_type for content_type, suffix in PHOTO_TYPES.items() if path.suffix == suffix),
        None,
    )
    if media_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipment image file not found")
    headers = {"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"}
    if media_type == SVG_TYPE:
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        )
    return FileResponse(path, media_type=media_type, headers=headers)
