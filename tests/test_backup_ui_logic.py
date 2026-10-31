from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_footer_links_to_backup_view() -> None:
    page = Path("app/static/index.html").read_text()
    assert 'href="#backup"' in page
    assert "Backup &amp; Restore" in page


def test_backup_view_renders_backup_and_restore_sections() -> None:
    view = Path("app/static/js/views/backup.js").read_text()
    assert "Download backup" in view
    assert 'href="/api/backup"' in view
    assert "Restore REPLACES all current data" in view
    assert 'accept=".zip,application/zip"' in view
    assert "window.confirm" not in view


def test_restore_is_disabled_without_a_file() -> None:
    module = Path("app/static/js/backup-logic.js").resolve().as_uri()
    script = f'''
      const logic = await import({json.dumps(module)});
      console.log(JSON.stringify([
        logic.restoreEnabled(null),
        logic.restoreEnabled(undefined),
        logic.restoreEnabled({{name: "backup.zip"}}),
      ]));
    '''
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == [False, False, True]

    view = Path("app/static/js/views/backup.js").read_text()
    assert 'class="pbtn begin-restore" type="button" disabled' in view
