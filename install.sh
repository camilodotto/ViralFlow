#!/usr/bin/env bash
set -Eeuo pipefail

PROGRAM_NAME="${0##*/}"
DEFAULT_REPOSITORY="https://github.com/camilodotto/ViralFlow.git"
DEFAULT_BRANCH="feat/develop/ubuntu26.04"
DEFAULT_NEXTFLOW_VERSION="23.10.1"
MICROMAMBA_VERSION="2.9.0"

REPOSITORY="${VIRALFLOW_REPOSITORY:-${DEFAULT_REPOSITORY}}"
BRANCH="${VIRALFLOW_BRANCH:-${DEFAULT_BRANCH}}"
INSTALL_ROOT="${VIRALFLOW_INSTALL_ROOT:-${HOME}/.local/share/viralflow}"
REPO_DIR="${VIRALFLOW_REPO_DIR:-${HOME}/ViralFlow}"
BIN_DIR="${VIRALFLOW_BIN_DIR:-${HOME}/.local/bin}"
MAMBA_ROOT_PREFIX="${VIRALFLOW_MAMBA_ROOT_PREFIX:-${INSTALL_ROOT}/micromamba}"
NEXTFLOW_VERSION="${NEXTFLOW_VERSION:-${DEFAULT_NEXTFLOW_VERSION}}"

BUILD_CONTAINERS=1
UPDATE_REPOSITORY=1
DRY_RUN=0
SKIP_SYSTEM_PACKAGES=0
CONFIGURE_PATH=1
FORCE_PLATFORM=""
FORCE_ARCH=""

log() {
  printf '[ViralFlow] %s\n' "$*"
}

warn() {
  printf '[ViralFlow] WARNING: %s\n' "$*" >&2
}

die() {
  printf '[ViralFlow] ERROR: %s\n' "$*" >&2
  exit 1
}

quote_command() {
  printf ' %q' "$@"
  printf '\n'
}

run() {
  if (( DRY_RUN )); then
    printf '[dry-run]'
    quote_command "$@"
    return 0
  fi
  "$@"
}

run_as_root() {
  if (( EUID == 0 )); then
    run "$@"
  else
    command -v sudo >/dev/null 2>&1 || die "sudo is required to install system packages."
    run sudo "$@"
  fi
}

usage() {
  cat <<EOF
Usage: ${PROGRAM_NAME} [options]

Install ViralFlow and its command-line dependencies.

Options:
  --repo-dir PATH          ViralFlow checkout directory (default: ~/ViralFlow)
  --install-root PATH      Dependency data directory
                           (default: ~/.local/share/viralflow)
  --bin-dir PATH           User commands directory (default: ~/.local/bin)
  --repository URL         Git repository to clone
  --branch NAME            Git branch to install (default: ${DEFAULT_BRANCH})
  --nextflow-version VER   Nextflow version used by ViralFlow
                           (default: ${DEFAULT_NEXTFLOW_VERSION})
  --skip-containers        Do not download/build ViralFlow containers
  --skip-system-packages   Use preinstalled system dependencies (no sudo/apt)
  --no-path-update         Do not edit shell startup files
  --no-update              Do not update an existing checkout
  --dry-run                Show the selected installation without changing files
  -h, --help               Show this help

Environment variables:
  VIRALFLOW_REPOSITORY, VIRALFLOW_BRANCH, VIRALFLOW_REPO_DIR,
  VIRALFLOW_INSTALL_ROOT, VIRALFLOW_BIN_DIR, VIRALFLOW_MAMBA_ROOT_PREFIX,
  NEXTFLOW_VERSION

Supported platforms:
  Ubuntu Linux/WSL amd64 and arm64. Validation target: Ubuntu 26.04 amd64.
EOF
}

parse_arguments() {
  while (( $# > 0 )); do
    case "$1" in
      --repo-dir)
        REPO_DIR="${2:?Missing value for --repo-dir}"
        shift 2
        ;;
      --install-root)
        INSTALL_ROOT="${2:?Missing value for --install-root}"
        MAMBA_ROOT_PREFIX="${INSTALL_ROOT}/micromamba"
        shift 2
        ;;
      --bin-dir)
        BIN_DIR="${2:?Missing value for --bin-dir}"
        shift 2
        ;;
      --repository)
        REPOSITORY="${2:?Missing value for --repository}"
        shift 2
        ;;
      --branch)
        BRANCH="${2:?Missing value for --branch}"
        shift 2
        ;;
      --nextflow-version)
        NEXTFLOW_VERSION="${2:?Missing value for --nextflow-version}"
        shift 2
        ;;
      --skip-containers)
        BUILD_CONTAINERS=0
        shift
        ;;
      --no-update)
        UPDATE_REPOSITORY=0
        shift
        ;;
      --skip-system-packages)
        SKIP_SYSTEM_PACKAGES=1
        shift
        ;;
      --no-path-update)
        CONFIGURE_PATH=0
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --platform)
        FORCE_PLATFORM="${2:?Missing value for --platform}"
        shift 2
        ;;
      --arch)
        FORCE_ARCH="${2:?Missing value for --arch}"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done
}

normalize_path() {
  local value="$1"
  case "${value}" in
    "~")
      printf '%s\n' "${HOME}"
      ;;
    "~/"*)
      printf '%s/%s\n' "${HOME}" "${value#\~/}"
      ;;
    *)
      realpath -m -- "${value}"
      ;;
  esac
}

detect_platform() {
  if [[ -n "${FORCE_PLATFORM}" ]]; then
    printf '%s\n' "${FORCE_PLATFORM}"
    return
  fi

  case "$(uname -s)" in
    Linux) printf 'linux\n' ;;
    *) die "Unsupported operating system: $(uname -s)" ;;
  esac
}

detect_architecture() {
  local machine
  if [[ -n "${FORCE_ARCH}" ]]; then
    printf '%s\n' "${FORCE_ARCH}"
    return
  fi

  machine="$(uname -m)"
  case "${machine}" in
    x86_64|amd64) printf 'amd64\n' ;;
    aarch64|arm64) printf 'arm64\n' ;;
    *) die "Unsupported architecture: ${machine}" ;;
  esac
}

is_wsl() {
  [[ -r /proc/sys/kernel/osrelease ]] &&
    grep -qi microsoft /proc/sys/kernel/osrelease
}

install_linux_base_packages() {
  (( SKIP_SYSTEM_PACKAGES == 0 )) || return 0
  run_as_root apt-get update
  run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ca-certificates curl git bzip2 tar python3 uidmap squashfs-tools
}

install_apptainer() {
  if command -v apptainer >/dev/null 2>&1; then
    log "Using installed $(apptainer --version)."
    return
  fi
  (( SKIP_SYSTEM_PACKAGES == 0 )) || die "Apptainer must be installed when --skip-system-packages is used."
  run_as_root apt-get update
  run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y software-properties-common
  run_as_root add-apt-repository -y ppa:apptainer/ppa
  run_as_root apt-get update
  run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y apptainer
}

configure_apptainer_fakeroot() {
  (( BUILD_CONTAINERS )) || return 0
  local user uid
  (( DRY_RUN )) && {
    log "Would verify the Apptainer fakeroot mapping for the current user."
    return
  }

  user="$(id -un)"
  uid="$(id -u)"
  if {
    grep -Eq "^(${user}|${uid}):" /etc/subuid 2>/dev/null &&
      grep -Eq "^(${user}|${uid}):" /etc/subgid 2>/dev/null
  }; then
    return
  fi

  log "Configuring an Apptainer fakeroot mapping for ${user}."
  (( SKIP_SYSTEM_PACKAGES == 0 )) || die "Missing fakeroot mapping. Ask an administrator to run: sudo apptainer config fakeroot --add ${user}"
  if ! run_as_root apptainer config fakeroot --add "${user}"; then
    warn "Could not create a fakeroot mapping automatically."
    warn "Container builds may require: sudo apptainer config fakeroot --add ${user}"
  fi
}

install_micromamba() {
  local architecture platform binary temporary
  architecture="$1"
  binary="${BIN_DIR}/micromamba"
  if [[ -x "${binary}" ]]; then
    log "Micromamba is already installed at ${binary}."
    return
  fi

  case "${architecture}" in
    amd64) platform="linux-64" ;;
    arm64) platform="linux-aarch64" ;;
    *) die "Unsupported Micromamba architecture: ${architecture}" ;;
  esac

  run mkdir -p "${BIN_DIR}" "${MAMBA_ROOT_PREFIX}"
  if (( DRY_RUN )); then
    log "Would install Micromamba (${platform}) at ${binary}."
    return
  fi

  temporary="$(mktemp -d)"
  trap 'rm -rf "${temporary:-}"' RETURN
  curl -fLsS "https://micro.mamba.pm/api/micromamba/${platform}/${MICROMAMBA_VERSION}" |
    tar -xj -C "${temporary}" bin/micromamba
  install -m 755 "${temporary}/bin/micromamba" "${binary}"
  rm -rf "${temporary}"
  trap - RETURN
}

install_nextflow() {
  local binary="${BIN_DIR}/nextflow"
  if [[ -x "${binary}" ]] &&
    grep -aq '^NXF_PACK=one$' "${binary}" &&
    grep -aFq "NXF_VER=\${NXF_VER:-'${NEXTFLOW_VERSION}'}" "${binary}"; then
    log "Nextflow ${NEXTFLOW_VERSION} is already installed at ${binary}."
    return
  fi
  run mkdir -p "${BIN_DIR}"
  run curl -fLsS \
    "https://github.com/nextflow-io/nextflow/releases/download/v${NEXTFLOW_VERSION}/nextflow" \
    -o "${binary}"
  run chmod 755 "${binary}"
}

checkout_repository() {
  if [[ -d "${REPO_DIR}/.git" ]]; then
    local current_branch dirty
    current_branch="$(git -C "${REPO_DIR}" branch --show-current)"
    [[ "${current_branch}" == "${BRANCH}" ]] ||
      die "${REPO_DIR} is on branch '${current_branch}', expected '${BRANCH}'."

    dirty="$(git -C "${REPO_DIR}" status --porcelain)"
    if [[ -n "${dirty}" ]]; then
      warn "${REPO_DIR} has local changes; the checkout will not be updated."
      return
    fi
    if (( UPDATE_REPOSITORY )); then
      run git -C "${REPO_DIR}" pull --ff-only origin "${BRANCH}"
    fi
    return
  fi

  [[ ! -e "${REPO_DIR}" ]] ||
    die "${REPO_DIR} exists but is not a Git repository."
  run mkdir -p "$(dirname "${REPO_DIR}")"
  run git clone --branch "${BRANCH}" --single-branch "${REPOSITORY}" "${REPO_DIR}"
}

install_viralflow_environment() {
  local architecture="$1"
  local micromamba="${BIN_DIR}/micromamba"
  local env_file="${REPO_DIR}/envs/${architecture}.yml"

  if (( DRY_RUN )); then
    log "Would create/update the viralflow Micromamba environment from ${env_file}."
    return
  fi
  [[ -f "${env_file}" ]] || die "Environment file not found: ${env_file}"

  if [[ -d "${MAMBA_ROOT_PREFIX}/envs/viralflow/conda-meta" ]]; then
    MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${micromamba}" env update \
      -n viralflow -f "${env_file}" --prune -y
  else
    MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${micromamba}" env create \
      -n viralflow -f "${env_file}" -y
  fi

  MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${micromamba}" run \
    -n viralflow python -m pip install -e "${REPO_DIR}"

}

write_linux_launcher() {
  local launcher="${BIN_DIR}/viralflow"
  run mkdir -p "${BIN_DIR}"
  if (( DRY_RUN )); then
    log "Would create the ViralFlow launcher at ${launcher}."
    return
  fi

  cat >"${launcher}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export MAMBA_ROOT_PREFIX=$(printf '%q' "${MAMBA_ROOT_PREFIX}")
export NXF_HOME=$(printf '%q' "${INSTALL_ROOT}/nextflow")
export NXF_VER=$(printf '%q' "${NEXTFLOW_VERSION}")
export PATH=$(printf '%q' "${BIN_DIR}"):\${PATH}
exec $(printf '%q' "${BIN_DIR}/micromamba") run -n viralflow viralflow "\$@"
EOF
  chmod 755 "${launcher}"
}

build_viralflow_containers() {
  local architecture="$1"
  (( BUILD_CONTAINERS )) || {
    log "Container construction was skipped."
    return
  }
  if (( DRY_RUN )); then
    log "Would run: viralflow build-containers --arch ${architecture}"
    return
  fi

  PATH="${BIN_DIR}:${PATH}" \
    MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" \
    NXF_HOME="${INSTALL_ROOT}/nextflow" NXF_VER="${NEXTFLOW_VERSION}" \
    "${BIN_DIR}/micromamba" run -n viralflow \
    viralflow build-containers --arch "${architecture}"
}

verify_linux_installation() {
  (( DRY_RUN )) && return 0
  PATH="${BIN_DIR}:${PATH}" MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" \
    "${BIN_DIR}/micromamba" --version
  PATH="${BIN_DIR}:${PATH}" MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" \
    "${BIN_DIR}/micromamba" run -n viralflow viralflow --version
  PATH="${BIN_DIR}:${PATH}" \
    MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" \
    NXF_HOME="${INSTALL_ROOT}/nextflow" NXF_VER="${NEXTFLOW_VERSION}" \
    "${BIN_DIR}/micromamba" run -n viralflow "${BIN_DIR}/nextflow" -version
  apptainer --version
}

configure_user_path() {
  (( CONFIGURE_PATH )) || return 0

  case ":${PATH}:" in
    *":${BIN_DIR}:"*) return ;;
  esac

  local files=("${HOME}/.bashrc")
  if [[ -f "${HOME}/.zshrc" || "${SHELL:-}" == */zsh ]]; then
    files+=("${HOME}/.zshrc")
  fi

  local file line
  line="export PATH=\"${BIN_DIR}:\$PATH\""
  for file in "${files[@]}"; do
    if (( DRY_RUN )); then
      log "Would ensure ${BIN_DIR} is in PATH through ${file}."
      continue
    fi
    touch "${file}"
    if ! grep -Fqx "${line}" "${file}"; then
      {
        printf '\n# Added by ViralFlow installer\n'
        printf '%s\n' "${line}"
      } >>"${file}"
      log "Added ${BIN_DIR} to PATH in ${file}."
    fi
  done
}

install_linux() {
  local architecture="$1"
  log "Installing for Ubuntu Linux ${architecture}."
  install_linux_base_packages
  install_apptainer
  configure_apptainer_fakeroot
  install_micromamba "${architecture}"
  install_nextflow
  checkout_repository
  install_viralflow_environment "${architecture}"
  write_linux_launcher
  verify_linux_installation
  build_viralflow_containers "${architecture}"
}

print_summary() {
  cat <<EOF

ViralFlow installation completed (or previewed with --dry-run).

Repository: ${REPO_DIR}
Command:    ${BIN_DIR}/viralflow

Command directory (added to PATH unless --no-path-update was selected):
  ${BIN_DIR}

For the current terminal session, run:
  export PATH="${BIN_DIR}:\$PATH"

Example:
  viralflow run --params-file ${REPO_DIR}/test_files/sars-cov-2.params
EOF
}

main() {
  parse_arguments "$@"
  INSTALL_ROOT="$(normalize_path "${INSTALL_ROOT}")"
  REPO_DIR="$(normalize_path "${REPO_DIR}")"
  BIN_DIR="$(normalize_path "${BIN_DIR}")"
  MAMBA_ROOT_PREFIX="$(normalize_path "${MAMBA_ROOT_PREFIX}")"

  local platform architecture
  platform="$(detect_platform)"
  architecture="$(detect_architecture)"

  log "Repository: ${REPOSITORY} (${BRANCH})"
  log "Checkout: ${REPO_DIR}"
  log "Platform: ${platform} ${architecture}"

  case "${platform}" in
    linux)
      if is_wsl; then
        log "WSL environment detected."
      fi
      install_linux "${architecture}"
      ;;
    *)
      die "Unsupported platform: ${platform}"
      ;;
  esac

  configure_user_path
  print_summary
}

main "$@"
