#!/usr/bin/env bash
# Watch every in-progress CI run on the current branch to completion and
# print one PASS/FAIL line each. One call replaces the ad-hoc
# list/sleep/list polling loops.
#   scripts/watch_ci.sh [limit]   (default: 6 newest runs)
set -u
limit="${1:-6}"
branch="$(git rev-parse --abbrev-ref HEAD)"
ids="$(gh run list --branch "$branch" --limit "$limit" \
  --json databaseId,status --jq '.[] | select(.status != "completed") | .databaseId')"
if [ -z "$ids" ]; then
  echo "no in-progress runs on $branch"
  gh run list --branch "$branch" --limit "$limit"
  exit 0
fi
rc=0
for id in $ids; do
  if gh run watch "$id" --exit-status >/dev/null 2>&1; then
    echo "PASS $id"
  else
    echo "FAIL $id"
    rc=1
  fi
done
exit $rc
