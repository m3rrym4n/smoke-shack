from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.pantry_photos import sniff_photo_type

router = APIRouter(prefix="/api/showcase", tags=["showcase"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
ShowcaseKind = Literal["logo", "photo"]
SHOWCASE_KINDS: tuple[ShowcaseKind, ...] = ("logo", "photo")


def _validate_svg(content: bytes) -> None:
    try:
        svg = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "SVG must be valid UTF-8 text",
        ) from error

    if not re.search(r"<svg\b", svg, re.IGNORECASE):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File is not a valid SVG image")
    checks = (
        (r"<!DOCTYPE\b", "SVG must not contain a DOCTYPE declaration"),
        (r"<!ENTITY\b", "SVG must not contain an ENTITY declaration"),
        (r"<script\b", "SVG must not contain script elements"),
        (r"<foreignObject\b", "SVG must not contain foreignObject elements"),
        (r"javascript\s*:", "SVG must not contain javascript: URLs"),
        (r"\son[a-z0-9_:.-]*\s*=", "SVG must not contain event handler attributes"),
    )
    for pattern, detail in checks:
        if re.search(pattern, svg, re.IGNORECASE):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)

    href_pattern = re.compile(
        r"(?:^|\s)(?:xlink:)?href\s*=\s*(?:([\"'])(.*?)\1|([^\s>]+))",
        re.IGNORECASE | re.DOTALL,
    )
    for match in href_pattern.finditer(svg):
        reference = (match.group(2) if match.group(1) else match.group(3)).strip()
        if not reference.lower().startswith(("#", "data:image/")):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "SVG href references must start with # or data:image/",
            )


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
    try:
        with temporary.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                        "Image exceeds the 5 MB limit",
                    )
                output.write(chunk)
        content = temporary.read_bytes()
        try:
            _, extension = sniff_photo_type(content)
        except HTTPException:
            extension = None
        if extension is None and kind == "logo" and re.search(rb"<svg\b", content, re.IGNORECASE):
            _validate_svg(content)
            extension = ".svg"
        elif extension is None:
            allowed = "PNG, JPEG, WebP, or SVG" if kind == "logo" else "PNG, JPEG, or WebP"
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Image must be a {allowed} file",
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
    headers = {
        "ETag": etag,
        "Cache-Control": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }
    if path.suffix == ".svg":
        headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        )
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return FileResponse(path, media_type=IMAGE_TYPES[path.suffix], headers=headers)


@router.delete("/{kind}", status_code=status.HTTP_204_NO_CONTENT)
def delete_showcase_image(kind: ShowcaseKind, request: Request) -> Response:
    directory: Path = request.app.state.showcase_dir
    for extension in IMAGE_TYPES:
        (directory / f"{kind}{extension}").unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
