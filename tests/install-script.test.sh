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
    -u SHELL \
    HOME="${home}" \
    bash "${INSTALLER}" \
      --dry-run \
      --platform "${platform}" \
      --arch "${architecture}" \
      --skip-containers \
      --repo-dir "${home}/ViralFlow" >"${output}"

  grep -q "Platform: ${platform} ${architecture}" "${output}"
  grep -q "Repository: ${home}/ViralFlow" "${output}"
  grep -q "Would ensure ${home}/.local/bin is in PATH through ${home}/.bashrc" "${output}"
  if [[ "${platform}" == "macos" ]]; then
    grep -q "Would verify that ${home} is mounted with write access inside Lima" "${output}"
    grep -q "Would create /var/lib/viralflow inside Lima" "${output}"
    grep -q -- '--install-root /var/lib/viralflow' "${output}"
    grep -q -- '--bin-dir /var/lib/viralflow/bin' "${output}"
  fi
}

bash -n "${INSTALLER}"
bash "${INSTALLER}" --help | grep -q -- '--skip-containers'
grep -q '"${BIN_DIR}/micromamba" run -n viralflow "${BIN_DIR}/nextflow" -version' "${INSTALLER}"

run_dry_install linux amd64
run_dry_install linux arm64
run_dry_install macos arm64

printf 'install.sh tests passed\n'
