from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/showcase", tags=["showcase"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
}
ShowcaseKind = Literal["logo", "photo"]
SHOWCASE_KINDS: tuple[ShowcaseKind, ...] = ("logo", "photo")


def _image_extension(header: bytes) -> str | None:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    return None


def _find_image(directory: Path, kind: ShowcaseKind) -> Path | None:
    return next(
        (
            directory / f"{kind}{extension}"
            for extension in IMAGE_TYPES
            if (directory / f"{kind}{extension}").is_file()
        ),
        None,
    )


def _image_urls(directory: Path) -> dict[str, str | None]:
    return {
        f"{kind}_url": f"/api/showcase/{kind}" if _find_image(directory, kind) else None
        for kind in SHOWCASE_KINDS
    }


def _etag(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f'"{digest}"'


@router.get("")
def get_showcase(request: Request) -> dict[str, str | None]:
    return _image_urls(request.app.state.showcase_dir)


@router.put("/{kind}")
async def put_showcase_image(
    kind: ShowcaseKind,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> dict[str, str]:
    directory: Path = request.app.state.showcase_dir
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / f".{kind}-{uuid4()}.upload"
    size = 0
    header = b""
    try:
        with temporary.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                        "Image exceeds the 5 MB limit",
                    )
                if len(header) < 16:
                    header += chunk[: 16 - len(header)]
                output.write(chunk)
        extension = _image_extension(header)
        if extension is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Image must be a PNG, JPEG, or WebP file",
            )
        final_path = directory / f"{kind}{extension}"
        os.replace(temporary, final_path)
        for other_extension in IMAGE_TYPES:
            if other_extension != extension:
                (directory / f"{kind}{other_extension}").unlink(missing_ok=True)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return {f"{kind}_url": f"/api/showcase/{kind}"}


@router.get("/{kind}", response_class=FileResponse)
def get_showcase_image(kind: ShowcaseKind, request: Request) -> Response:
    path = _find_image(request.app.state.showcase_dir, kind)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Showcase image not found")
    etag = _etag(path)
    headers = {"ETag": etag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return FileResponse(path, media_type=IMAGE_TYPES[path.suffix], headers=headers)


@router.delete("/{kind}", status_code=status.HTTP_204_NO_CONTENT)
def delete_showcase_image(kind: ShowcaseKind, request: Request) -> Response:
    directory: Path = request.app.state.showcase_dir
    for extension in IMAGE_TYPES:
        (directory / f"{kind}{extension}").unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
