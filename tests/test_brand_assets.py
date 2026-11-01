import struct
import xml.etree.ElementTree as ET
from pathlib import Path

BRAND_DIR = Path(__file__).parents[1] / "assets" / "brand"


def test_brand_svgs_are_vector_only() -> None:
    for name in ("smoke-shack-icon.svg", "smoke-shack-header.svg"):
        source = (BRAND_DIR / name).read_text(encoding="utf-8")
        ET.fromstring(source)
        lowered = source.lower()
        assert "<image" not in lowered
        assert "data:" not in lowered


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_brand_png_dimensions() -> None:
    expected_sizes = {
        "smoke-shack-icon-512.png": (512, 512),
        "smoke-shack-icon-256.png": (256, 256),
        "smoke-shack-icon-128.png": (128, 128),
        "smoke-shack-header-1280x640.png": (1280, 640),
    }
    for name, expected in expected_sizes.items():
        assert _png_size(BRAND_DIR / name) == expected
