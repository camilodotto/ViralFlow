#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="${REPO_ROOT}/install.sh"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "${TEMP_ROOT}"' EXIT

bash -n "${INSTALLER}"
bash "${INSTALLER}" --help >"${TEMP_ROOT}/help"
grep -q -- '--skip-system-packages' "${TEMP_ROOT}/help"

for architecture in amd64 arm64; do
  bash "${INSTALLER}" --dry-run --platform linux --arch "${architecture}" \
    --skip-system-packages --skip-containers --no-path-update \
    --repo-dir "${TEMP_ROOT}/preview-${architecture}" \
    --install-root "${TEMP_ROOT}/data-${architecture}" \
    --bin-dir "${TEMP_ROOT}/bin-${architecture}" >"${TEMP_ROOT}/${architecture}.log"
  grep -q "Platform: linux ${architecture}" "${TEMP_ROOT}/${architecture}.log"
  [[ ! -e "${TEMP_ROOT}/preview-${architecture}" ]]
  [[ ! -e "${TEMP_ROOT}/data-${architecture}" ]]
  [[ ! -e "${TEMP_ROOT}/bin-${architecture}" ]]
done

# Exercise installation and reinstallation without network or privileged writes.
mkdir -p "${TEMP_ROOT}/commands with spaces"
export VIRALFLOW_TEST_LOG="${TEMP_ROOT}/commands.log"
cat >"${TEMP_ROOT}/commands with spaces/micromamba" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"${VIRALFLOW_TEST_LOG}"
if [[ "${1:-}" == env && "${2:-}" == create ]]; then
  mkdir -p "${MAMBA_ROOT_PREFIX}/envs/viralflow/conda-meta"
fi
EOF
cat >"${TEMP_ROOT}/commands with spaces/nextflow" <<'EOF'
#!/usr/bin/env bash
NXF_VER=${NXF_VER:-'23.10.1'}
NXF_PACK=one
EOF
cat >"${TEMP_ROOT}/commands with spaces/apptainer" <<'EOF'
#!/usr/bin/env bash
printf 'apptainer version 1.5.3\n'
EOF
for command in sudo curl; do
  cat >"${TEMP_ROOT}/commands with spaces/${command}" <<'EOF'
#!/usr/bin/env bash
printf 'Unexpected privileged operation or download\n' >&2
exit 99
EOF
done
chmod +x "${TEMP_ROOT}/commands with spaces/"*

for attempt in 1 2; do
  PATH="${TEMP_ROOT}/commands with spaces:${PATH}" \
    bash "${INSTALLER}" --skip-system-packages --skip-containers \
    --no-path-update --no-update --repo-dir "${REPO_ROOT}" \
    --install-root "${TEMP_ROOT}/dependency data" \
    --bin-dir "${TEMP_ROOT}/commands with spaces" >"${TEMP_ROOT}/install-${attempt}.log"
  grep -q 'ViralFlow installation completed' "${TEMP_ROOT}/install-${attempt}.log"
  bash -n "${TEMP_ROOT}/commands with spaces/viralflow"
done
[[ "$(grep -c '^env create ' "${VIRALFLOW_TEST_LOG}")" == 1 ]]
[[ "$(grep -c '^env update ' "${VIRALFLOW_TEST_LOG}")" == 1 ]]

if bash "${INSTALLER}" --unknown >"${TEMP_ROOT}/error.log" 2>&1; then
  printf 'An invalid installer option was accepted\n' >&2
  exit 1
fi
printf 'Installer tests passed\n'
