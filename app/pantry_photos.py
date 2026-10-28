from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def sniff_photo_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported photo type")


async def save_photo(
    file: UploadFile,
    photo_dir: Path,
    kind: str,
    item_id: int,
    old_path: str | None,
) -> str:
    data = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > MAX_PHOTO_BYTES:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    "Photo exceeds 5 MB limit",
                )
    finally:
        await file.close()

    _, extension = sniff_photo_type(bytes(data))
    directory = photo_dir / kind
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{item_id}{extension}"
    temporary = directory / f".{item_id}.upload"
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    if old_path is not None and Path(old_path) != path:
        delete_photo(old_path)
    return str(path)


def delete_photo(photo_path: str | None) -> None:
    if photo_path is None:
        return
    try:
        Path(photo_path).unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not delete pantry photo %s", photo_path, exc_info=True)


def photo_response(photo_path: str | None) -> FileResponse:
    if photo_path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not found")
    path = Path(photo_path)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo file not found")
    media_type = next(
        (content_type for content_type, suffix in PHOTO_TYPES.items() if path.suffix == suffix),
        None,
    )
    if media_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo file not found")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": "no-cache"})
