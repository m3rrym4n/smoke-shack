const isMain = process.env.GITHUB_REF_NAME === "main";

const releaseNoteSections = {
  feat: "Features",
  fix: "Bug Fixes",
  perf: "Performance Improvements",
  revert: "Reverts",
};

function transformReleaseNoteCommit(commit) {
  const notes = commit.notes.map((note) => ({ ...note, title: "BREAKING CHANGES" }));
  const type = commit.revert ? "Reverts" : releaseNoteSections[commit.type];

  if (!type && notes.length === 0) return undefined;

  return {
    ...commit,
    notes,
    type: type || commit.type,
    scope: commit.scope === "*" ? "" : commit.scope,
    shortHash: commit.hash?.substring(0, 7) || commit.shortHash,
    references: [],
  };
}

const plugins = [
  "@semantic-release/commit-analyzer",
  [
    "@semantic-release/release-notes-generator",
    {
      host: "https://github.com",
      parserOpts: { issuePrefixes: ["FORGEJO-ISSUE-"] },
      writerOpts: { transform: transformReleaseNoteCommit },
    },
  ],
];

if (isMain) {
  plugins.push(["@semantic-release/changelog", { changelogFile: "CHANGELOG.md" }]);
}

plugins.push([
  "@semantic-release/exec",
  {
    prepareCmd:
      "printf '%s\\n' '${nextRelease.version}' > app/build_info.txt" +
      (isMain ? " && node scripts/set-app-version.cjs '${nextRelease.version}'" : "") +
      " && printf 'IMAGE_TAG=%s\\n' '${nextRelease.version}' >> \"$GITHUB_ENV\"",
  },
]);

if (isMain) {
  plugins.push([
    "@semantic-release/git",
    {
      assets: ["CHANGELOG.md", "smoke-shack/config.yaml"],
      message: "chore(release): ${nextRelease.version} [skip ci]\\n\\n${nextRelease.notes}",
    },
  ]);
}

module.exports = {
  branches: ["main", { name: "dev", prerelease: "dev", channel: "dev" }],
  tagFormat: "v${version}",
  plugins,
};
