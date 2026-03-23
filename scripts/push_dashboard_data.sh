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

# Save current branch
CURRENT=$(git branch --show-current)

# Stash any uncommitted changes
STASHED=false
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    git stash --quiet
    STASHED=true
fi

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

# Return to original branch
git checkout "$CURRENT" --quiet

# Restore stashed changes
if [ "$STASHED" = true ]; then
    git stash pop --quiet
fi
