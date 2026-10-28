const isMain = process.env.GITHUB_REF_NAME === "main";

const plugins = [
  "@semantic-release/commit-analyzer",
  "@semantic-release/release-notes-generator",
];

if (isMain) {
  plugins.push(["@semantic-release/changelog", { changelogFile: "CHANGELOG.md" }]);
}

plugins.push([
  "@semantic-release/exec",
  {
    prepareCmd:
      "printf '%s\\n' '${nextRelease.version}' > app/build_info.txt && printf 'IMAGE_TAG=%s\\n' '${nextRelease.version}' >> \"$GITHUB_ENV\"",
  },
]);

if (isMain) {
  plugins.push([
    "@semantic-release/git",
    {
      assets: ["CHANGELOG.md"],
      message: "chore(release): ${nextRelease.version} [skip ci]\\n\\n${nextRelease.notes}",
    },
  ]);
}

module.exports = {
  branches: ["main", { name: "dev", prerelease: "dev", channel: "dev" }],
  tagFormat: "v${version}",
  plugins,
};
