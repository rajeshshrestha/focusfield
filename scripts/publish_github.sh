#!/usr/bin/env bash
# Public GitHub publication from a local clone; requires GitHub CLI authentication.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OWNER="rajeshshrestha"
REPO="focusfield"
FULL="$OWNER/$REPO"

if ! command -v gh >/dev/null 2>&1; then
  echo 'Install GitHub CLI (gh) first: https://cli.github.com/' >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo 'Sign in first with: gh auth login' >&2
  exit 1
fi
if [[ "$(gh api user --jq .login)" != "$OWNER" ]]; then
  echo "The logged-in GitHub account is not $OWNER. Refusing to publish elsewhere." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Commit or stash local changes before publishing.' >&2
  exit 1
fi

if gh repo view "$FULL" >/dev/null 2>&1; then
  VISIBILITY="$(gh repo view "$FULL" --json visibility --jq .visibility)"
  if [[ "$VISIBILITY" != "PUBLIC" ]]; then
    echo "Repository $FULL already exists but is not public. Stopping; no visibility changed." >&2
    exit 1
  fi
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "https://github.com/$FULL.git"
  fi
else
  gh repo create "$FULL" --public --source=. --remote=origin --description 'A calm Pomodoro timer for Linux, with task tracking and focus insights'
fi

REMOTE="$(git remote get-url origin)"
case "$REMOTE" in
  "https://github.com/$FULL.git"|"git@github.com:$FULL.git"|"https://github.com/$FULL"|"git@github.com:$FULL") ;;
  *) echo "Unexpected origin: $REMOTE" >&2; exit 1 ;;
esac

git push -u origin main
git push origin v1.0.0
printf '\nPublished source and v1.0.0 tag to https://github.com/%s\n' "$FULL"
echo 'GitHub Actions will build and attach release assets to the tagged release.'
