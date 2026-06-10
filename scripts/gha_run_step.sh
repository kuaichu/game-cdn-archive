#!/usr/bin/env bash
set -u
set -o pipefail

step_name="${1:-}"
if [ -z "$step_name" ]; then
  echo "::error::Missing step name."
  exit 2
fi
shift

if [ "$#" -eq 0 ]; then
  echo "::error::Missing command for ${step_name}."
  exit 2
fi

log_dir="${RUNNER_TEMP:-/tmp}/game-cdn-archive-step-logs"
mkdir -p "$log_dir"
safe_name="$(printf '%s' "$step_name" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9_.-')"
log_file="${log_dir}/${safe_name}.log"
retry_count="${GHA_RUN_RETRIES:-0}"
retry_delay="${GHA_RUN_RETRY_DELAY:-15}"
attempt=0
max_attempts=$((retry_count + 1))

while :; do
  attempt=$((attempt + 1))
  : > "$log_file"
  echo "::group::${step_name} (attempt ${attempt}/${max_attempts})"
  set +e
  "$@" 2>&1 | tee "$log_file"
  status="${PIPESTATUS[0]}"
  set -e
  echo "::endgroup::"

  if [ "$status" -eq 0 ]; then
    exit 0
  fi

  if [ "$attempt" -lt "$max_attempts" ]; then
    echo "::warning::${step_name} failed on attempt ${attempt}/${max_attempts} with exit code ${status}. Retrying in ${retry_delay}s."
    sleep "$retry_delay"
    continue
  fi
  break
done

error_summary="$(python3 scripts/extract_error_summary.py "$log_file")"
{
  echo "FAILED_STEP_NAME=${step_name}"
  echo "FAILED_STEP_EXIT_CODE=${status}"
  echo "FAILED_STEP_ERROR<<__GAME_CDN_ERROR__"
  printf '%s\n' "$error_summary"
  echo "__GAME_CDN_ERROR__"
} >> "$GITHUB_ENV"
exit "$status"
