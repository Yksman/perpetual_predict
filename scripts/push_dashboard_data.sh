#!/bin/bash
# Push exported JSON files to the git data branch.
# Usage: push_dashboard_data.sh [EXPORT_DIR] [BRANCH]

set -e

EXPORT_DIR="${1:-/tmp/perpetual_predict_export}"
BRANCH="${2:-data}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$EXPORT_DIR" ]; then
    echo "Error: Export directory not found: $EXPORT_DIR"
    exit 1
fi

cd "$REPO_DIR"

# Prevent concurrent pushes via mkdir (portable, works on macOS and Linux)
LOCKDIR="$REPO_DIR/.git/push_dashboard.lockdir"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    echo "Another push is in progress, skipping."
    exit 0
fi

# Save current branch
CURRENT=$(git branch --show-current)

# Stash any uncommitted changes
STASHED=false
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    git stash --quiet
    STASHED=true
fi

# Guarantee branch restoration, stash pop, and lock removal on ANY exit
cleanup() {
    git checkout "$CURRENT" --quiet 2>/dev/null || true
    if [ "$STASHED" = true ]; then
        git stash pop --quiet 2>/dev/null || true
    fi
    rmdir "$LOCKDIR" 2>/dev/null || true
}
trap cleanup EXIT

# Switch to data branch (create orphan if needed)
if git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    git checkout "$BRANCH" --quiet
else
    git checkout --orphan "$BRANCH" --quiet
    git rm -rf . --quiet 2>/dev/null || true
fi

# Copy JSON files
cp "$EXPORT_DIR"/*.json .

# Commit and push
git add *.json
if git diff --cached --quiet 2>/dev/null; then
    echo "No changes to push"
else
    git commit -m "data: update $(date -u +%Y-%m-%dT%H:%M:%SZ)" --quiet
    git push origin "$BRANCH" --force --quiet
    echo "Pushed to $BRANCH"
fi
