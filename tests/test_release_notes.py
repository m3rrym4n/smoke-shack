import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_notes_use_public_github_links_without_issue_links() -> None:
    script = r"""
import { createRequire } from "node:module";
import { generateNotes } from "@semantic-release/release-notes-generator";

const require = createRequire(import.meta.url);
const config = require("./release.config.cjs");

const entry = config.plugins.find(
  (plugin) => Array.isArray(plugin) &&
    plugin[0] === "@semantic-release/release-notes-generator",
);

if (!entry) {
  throw new Error("release notes generator is not configured");
}

const [pluginName, pluginConfig] = entry;
const privateIpv4 = /(?:^|[^0-9])(?:10|127|192\.168|172\.(?:1[6-9]|2[0-9]|3[01]))\./;

if (pluginConfig.host !== "https://github.com") {
  throw new Error(`unexpected release notes host: ${pluginConfig.host}`);
}
if (privateIpv4.test(JSON.stringify(pluginConfig))) {
  throw new Error("release notes config contains a private IPv4 address");
}
if (pluginConfig.parserOpts?.issuePrefixes?.includes("#")) {
  throw new Error("issue references must not be linked");
}

const notes = await generateNotes(pluginConfig, {
  commits: [{ hash: "abcdef1234567890", message: "fix: keep #123 stable" }],
  lastRelease: { gitTag: "v1.0.0" },
  nextRelease: { version: "1.0.1", gitTag: "v1.0.1" },
  options: { repositoryUrl: "https://forge.example/m3rrym4n/smoke-shack.git" },
  cwd: process.cwd(),
});

process.stdout.write(JSON.stringify({ pluginName, pluginConfig, notes }));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    configured = json.loads(result.stdout)

    assert configured["pluginName"] == "@semantic-release/release-notes-generator"
    assert configured["pluginConfig"]["host"] == "https://github.com"
    assert (
        "https://github.com/m3rrym4n/smoke-shack/compare/v1.0.0...v1.0.1"
        in configured["notes"]
    )
    assert (
        "https://github.com/m3rrym4n/smoke-shack/commit/abcdef1234567890"
        in configured["notes"]
    )
    assert "#123" in configured["notes"]
    assert "issues/123" not in configured["notes"]
