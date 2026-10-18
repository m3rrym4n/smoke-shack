from __future__ import annotations

import json
import subprocess
from pathlib import Path


def render(notes: list[dict[str, str]]) -> str:
    module = Path("app/static/js/components/cook-notes.js").resolve().as_uri()
    script = (
        f"import {{ cookNotesMarkup }} from {json.dumps(module)}; "
        f"console.log(cookNotesMarkup({json.dumps(notes)}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.rstrip("\n")


def test_cook_with_notes_shows_notes_and_preserves_line_breaks() -> None:
    markup = render([{"title": "Plan", "body": "Wrap at 165\nRest for an hour"}])
    assert '<section class="board cook-notes">' in markup
    assert "Plan" in markup
    assert "Wrap at 165\nRest for an hour" in markup


def test_cook_without_notes_has_no_notes_pane() -> None:
    assert render([]) == ""


def test_cook_notes_escape_html() -> None:
    markup = render([{"title": "<b>Plan</b>", "body": '<script>alert("x")</script>'}])
    assert "<b>" not in markup
    assert "<script>" not in markup
    assert "&lt;b&gt;Plan&lt;/b&gt;" in markup
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in markup
