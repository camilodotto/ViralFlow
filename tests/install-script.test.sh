#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="${REPO_ROOT}/install.sh"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "${TEMP_ROOT}"' EXIT

run_dry_install() {
  local platform="$1"
  local architecture="$2"
  local home="${TEMP_ROOT}/${platform}-${architecture}"
  local output="${home}.log"

  mkdir -p "${home}"
  env -u MAMBA_ROOT_PREFIX \
    HOME="${home}" \
    bash "${INSTALLER}" \
      --dry-run \
      --platform "${platform}" \
      --arch "${architecture}" \
      --skip-containers \
      --repo-dir "${home}/ViralFlow" >"${output}"

  grep -q "Platform: ${platform} ${architecture}" "${output}"
  grep -q "Repository: ${home}/ViralFlow" "${output}"
}

bash -n "${INSTALLER}"
bash "${INSTALLER}" --help | grep -q -- '--skip-containers'

run_dry_install linux amd64
run_dry_install linux arm64
run_dry_install macos arm64

printf 'install.sh tests passed\n'
