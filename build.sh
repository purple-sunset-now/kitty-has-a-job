#!/usr/bin/env bash
# Rebuild dist/kitty-has-a-job.zip with only the files the skill needs.
set -euo pipefail
cd "$(dirname "$0")"
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir "$stage/kitty-has-a-job"
cp -R SKILL.md LICENSE references scripts "$stage/kitty-has-a-job/"
find "$stage" \( -name __pycache__ -o -name .DS_Store \) -prune -exec rm -rf {} +
mkdir -p dist
rm -f dist/kitty-has-a-job.zip
(cd "$stage" && zip -qr "$OLDPWD/dist/kitty-has-a-job.zip" kitty-has-a-job)
unzip -l dist/kitty-has-a-job.zip | tail -1
