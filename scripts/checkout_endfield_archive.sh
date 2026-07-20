#!/usr/bin/env bash
set -euo pipefail

destination="${1:-/tmp/ak-endfield-api-archive}"
repository="https://github.com/daydreamer-json/ak-endfield-api-archive.git"

rm -rf -- "$destination"
git clone \
  --branch archive \
  --single-branch \
  --depth 1 \
  --filter=blob:none \
  --no-checkout \
  "$repository" \
  "$destination"

git -C "$destination" sparse-checkout set --no-cone --stdin <<'EOF'
/output/akEndfield/launcher/game/1/all.json
/output/akEndfield/launcher/game/1/all_patch.json
/output/mirror_file_list.json
EOF
git -C "$destination" checkout
