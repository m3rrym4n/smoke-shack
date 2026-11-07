import re
from pathlib import Path

STYLESHEET = Path(__file__).parents[1] / "app/static/css/signage.css"


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_dropdown_options_and_groups_share_readable_colors() -> None:
    css = STYLESHEET.read_text()
    rule = re.search(r"select option,select optgroup\{([^}]*)\}", css)

    assert rule is not None
    declarations = dict(
        declaration.split(":", 1)
        for declaration in rule.group(1).split(";")
        if declaration
    )
    assert "color" in declarations
    assert "background-color" in declarations
    assert _contrast_ratio(
        declarations["color"], declarations["background-color"]
    ) >= 4.5
