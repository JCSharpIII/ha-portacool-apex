#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./release.sh 0.1.3 "Short release title" "Release notes..."
#
# Example:
#   ./release.sh 0.1.3 "Pump disable + water sensors" "$(cat RELEASE_NOTES.md)"

VERSION="${1:-}"
TITLE="${2:-}"
NOTES="${3:-}"

if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version e.g. 0.1.3> <title> <notes>"
  exit 1
fi

REPO_SLUG="JCSharpIII/ha-portacool-apex"
TAG="v$VERSION"
MANIFEST_PATH="custom_components/portacool_apex/manifest.json"

# Basic checks
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Not a git repo"; exit 1; }

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "main" ]]; then
  echo "ERROR: You're on '$BRANCH'. Switch to main first:"
  echo "  git switch main"
  exit 1
fi

# Ensure origin points to your repo
REMOTE_URL="$(git remote get-url origin || true)"
if [[ "$REMOTE_URL" != *"JCSharpIII/ha-portacool-apex"* ]]; then
  echo "WARNING: origin doesn't look like $REPO_SLUG"
  echo "origin is: $REMOTE_URL"
fi

echo "== Fetching origin =="
git fetch origin --tags

echo "== Current status =="
git status --porcelain

# Commit everything if there are changes
if [[ -n "$(git status --porcelain)" ]]; then
  echo "== Committing changes =="
  git add -A
  git commit -m "Release $TAG"
else
  echo "No working tree changes to commit."
fi

# Bump manifest.json version if present
if [[ -f "$MANIFEST_PATH" ]]; then
  echo "== Updating manifest version to $VERSION =="
  python3 - <<PY
import json
p="$MANIFEST_PATH"
with open(p,"r",encoding="utf-8") as f:
    data=json.load(f)
data["version"]="$VERSION"
with open(p,"w",encoding="utf-8") as f:
    json.dump(data,f,indent=2,sort_keys=False)
    f.write("\n")
print("Updated", p, "version ->", data["version"])
PY

  git add "$MANIFEST_PATH"
  # Only commit if version changed
  if ! git diff --cached --quiet; then
    git commit -m "Bump version to $VERSION"
  fi
else
  echo "NOTE: $MANIFEST_PATH not found, skipping manifest version bump."
fi

echo "== Pushing main =="
git push origin main

# Tag handling (delete/recreate tag locally if it already exists)
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "== Tag $TAG already exists locally; moving it to HEAD =="
  git tag -d "$TAG" >/dev/null
fi

echo "== Creating tag $TAG at HEAD =="
git tag -a "$TAG" -m "Release $TAG"

echo "== Pushing tag =="
git push origin "$TAG"

echo "== Done. =="
echo "Tag: $TAG"

# Optional: Create GitHub Release (requires gh)
if command -v gh >/dev/null 2>&1; then
  if [[ -z "$TITLE" ]]; then TITLE="$TAG"; fi
  if [[ -z "$NOTES" ]]; then
    echo
    echo "gh is installed, but no notes were provided."
    echo "Run:"
    echo "  gh release create $TAG --repo $REPO_SLUG --title \"$TITLE\" --notes \"<notes>\""
  else
    echo
    echo "== Creating GitHub Release via gh =="
    gh release create "$TAG" --repo "$REPO_SLUG" --title "$TITLE" --notes "$NOTES"
  fi
else
  echo
  echo "gh not found (optional). Install with:"
  echo "  brew install gh"
  echo "Then login:"
  echo "  gh auth login"
  echo "To create the GitHub Release:"
  echo "  gh release create $TAG --repo $REPO_SLUG --title \"$TITLE\" --notes \"<notes>\""
fi
