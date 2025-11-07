#!/usr/bin/env bash
set -euo pipefail

changelog_file="$(mktemp)"
cz bump --changelog-to-stdout --git-output-to-stderr > "$changelog_file"

git push origin main
sleep 1
git push --tags
sleep 1
gh release create "v$(cz version -p)" --verify-tag -t "Release v$(cz version -p)" -d -F "$changelog_file"
rm "$changelog_file"
