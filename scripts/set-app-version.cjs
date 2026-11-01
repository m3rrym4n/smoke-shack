const fs = require("node:fs");

const version = process.argv[2];
const configPath = process.argv[3] || "smoke-shack/config.yaml";

if (!version) {
  console.error("Usage: node scripts/set-app-version.cjs <version> [config-path]");
  process.exit(1);
}

const config = fs.readFileSync(configPath, "utf8");
const versionLine = /^(\s*)version\s*:.*$/m;

if (!versionLine.test(config)) {
  console.error(`No version line found in ${configPath}`);
  process.exit(1);
}

fs.writeFileSync(configPath, config.replace(versionLine, `$1version: "${version}"`));
