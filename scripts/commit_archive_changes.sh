#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

SYNC_SCOPE="${SYNC_SCOPE:-all}"
GITHUB_ACTOR="${GITHUB_ACTOR:-}"
ARCHIVE_CURL_BIN="${ARCHIVE_CURL_BIN:-curl}"

write_result() {
  local changed="$1"
  local superseded="$2"
  {
    echo "changed=${changed}"
    echo "superseded=${superseded}"
  } >> "$GITHUB_OUTPUT"
}

if git diff --quiet && [ -z "$(git status --porcelain)" ]; then
  write_result false false
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
allowed_paths=(
  README.md docs/data docs/app.js docs/index.html
  scripts/update_nte_static.py scripts/update_tof_static.py scripts/update_p5x_static.py
  scripts/build_tof_availability.py scripts/build_p5x_availability.py
  scripts/sync_hoyofiles.py scripts/import_endfield_archive.py
  scripts/validate_endfield_archive.py scripts/sync_wuwa.py
  scripts/sync_arknights_pc.py scripts/validate_arknights_pc.py
  scripts/sync_android_apks.py scripts/probe_url_status.py
  scripts/check_docs_file_sizes.py scripts/update_readme_summary.py
)
existing_paths=()
for path in "${allowed_paths[@]}"; do
  if [ -e "$path" ]; then
    existing_paths+=("$path")
  fi
done
git add -- "${existing_paths[@]}"

if git diff --cached --quiet; then
  echo "::warning::The sync produced only unstaged or ignored paths; nothing will be committed."
  write_result false false
  exit 0
fi

git commit -m "Auto update archive data"
local_commit="$(git rev-parse HEAD)"
base_commit="$(git rev-parse HEAD^)"
push_log="$(mktemp)"
trap 'rm -f "$push_log"' EXIT

set +e
git push origin HEAD:main 2>&1 | tee "$push_log"
push_status="${PIPESTATUS[0]}"
set -e

if [ "$push_status" -eq 0 ]; then
  write_result true false
  exit 0
fi

git fetch --quiet origin main
remote_commit="$(git rev-parse origin/main)"

if [ "$remote_commit" = "$local_commit" ]; then
  echo "::warning::git push reported an error, but origin/main already contains the generated commit."
  write_result true false
  exit 0
fi

if [ "$remote_commit" = "$base_commit" ]; then
  echo "::error::git push failed while origin/main remained unchanged at ${base_commit}; refusing to start a retry loop."
  exit "$push_status"
fi

if [ "$GITHUB_ACTOR" = "github-actions[bot]" ]; then
  echo "::error::origin/main changed during an automatic retry; refusing to dispatch another workflow run."
  exit 1
fi

echo "::warning::origin/main changed from ${base_commit} to ${remote_commit}; queueing one clean ${SYNC_SCOPE} sync."
"$ARCHIVE_CURL_BIN" --fail --silent --show-error \
  --request POST \
  --header "Accept: application/vnd.github+json" \
  --header "Authorization: Bearer ${GITHUB_TOKEN:-}" \
  --header "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/sync-archive.yml/dispatches" \
  --data "{\"ref\":\"main\",\"inputs\":{\"scope\":\"${SYNC_SCOPE}\"}}"

write_result false true
echo "::notice::This run was superseded by a newer main commit; one clean sync was queued."
