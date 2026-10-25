from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_logic(expression: str) -> object:
    module = Path("app/static/js/photo-logic.js").resolve().as_uri()
    script = (
        f'import {{ PHOTO_MAX_BYTES, downscaleSize, validatePhotoFile }} from "{module}"; '
        f"{expression}"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_downscale_size_limits_long_edge_without_upscaling() -> None:
    expression = (
        "console.log(JSON.stringify([downscaleSize(4000, 3000), "
        "downscaleSize(1200, 1600), downscaleSize(900, 600), "
        "downscaleSize(3000, 4000), downscaleSize(0, 100)]))"
    )
    assert run_logic(expression) == [
        {"width": 1600, "height": 1200},
        {"width": 1200, "height": 1600},
        {"width": 900, "height": 600},
        {"width": 1200, "height": 1600},
        None,
    ]


def test_photo_file_validation_checks_presence_type_and_five_mb_limit() -> None:
    expression = (
        "console.log(JSON.stringify([validatePhotoFile(null), "
        "validatePhotoFile({type:'text/plain',size:10}), "
        "validatePhotoFile({type:'image/jpeg',size:PHOTO_MAX_BYTES}), "
        "validatePhotoFile({type:'image/png',size:PHOTO_MAX_BYTES+1})]))"
    )
    assert run_logic(expression) == [
        "Choose a photo.",
        "Choose an image file.",
        None,
        "Photo must be 5 MB or smaller.",
    ]
