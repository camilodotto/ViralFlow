#!/usr/bin/env bash
set -Eeuo pipefail

PROGRAM_NAME="${0##*/}"
DEFAULT_REPOSITORY="https://github.com/camilodotto/ViralFlow.git"
DEFAULT_BRANCH="develop-SIF3-MAC"
DEFAULT_NEXTFLOW_VERSION="22.04.0"
DEFAULT_LIMA_VM_NAME="viralflow"

REPOSITORY="${VIRALFLOW_REPOSITORY:-${DEFAULT_REPOSITORY}}"
BRANCH="${VIRALFLOW_BRANCH:-${DEFAULT_BRANCH}}"
INSTALL_ROOT="${VIRALFLOW_INSTALL_ROOT:-${HOME}/.local/share/viralflow}"
REPO_DIR="${VIRALFLOW_REPO_DIR:-${HOME}/ViralFlow}"
BIN_DIR="${VIRALFLOW_BIN_DIR:-${HOME}/.local/bin}"
MAMBA_ROOT_PREFIX="${VIRALFLOW_MAMBA_ROOT_PREFIX:-${INSTALL_ROOT}/micromamba}"
NEXTFLOW_VERSION="${NEXTFLOW_VERSION:-${DEFAULT_NEXTFLOW_VERSION}}"
LIMA_VM_NAME="${VIRALFLOW_LIMA_VM_NAME:-${DEFAULT_LIMA_VM_NAME}}"

BUILD_CONTAINERS=1
UPDATE_REPOSITORY=1
DRY_RUN=0
INSIDE_LIMA=0
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
  --no-update              Do not update an existing checkout
  --dry-run                Show the selected installation without changing files
  -h, --help               Show this help

Environment variables:
  VIRALFLOW_REPOSITORY, VIRALFLOW_BRANCH, VIRALFLOW_REPO_DIR,
  VIRALFLOW_INSTALL_ROOT, VIRALFLOW_BIN_DIR, VIRALFLOW_MAMBA_ROOT_PREFIX,
  NEXTFLOW_VERSION, APPTAINER_VERSION, VIRALFLOW_LIMA_VM_NAME

Supported platforms:
  Linux/WSL amd64, Linux/WSL arm64, and macOS through Lima.
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
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --inside-lima)
        INSIDE_LIMA=1
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
      printf '%s/%s\n' "${HOME}" "${value#~/}"
      ;;
    *)
      printf '%s\n' "${value}"
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
    Darwin) printf 'macos\n' ;;
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
  if command -v apt-get >/dev/null 2>&1; then
    run_as_root apt-get update
    run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
      ca-certificates curl git bzip2 tar python3 python3-pip \
      uidmap squashfs-tools
  elif command -v dnf >/dev/null 2>&1; then
    run_as_root dnf install -y \
      ca-certificates curl git bzip2 tar python3 python3-pip \
      shadow-utils squashfs-tools
  elif command -v yum >/dev/null 2>&1; then
    run_as_root yum install -y \
      ca-certificates curl git bzip2 tar python3 python3-pip \
      shadow-utils squashfs-tools
  else
    die "No supported package manager found. Install curl, git, Python, uidmap and squashfs-tools manually."
  fi
}

get_latest_apptainer_version() {
  local latest_url latest_tag
  latest_url="$(
    curl -fsSL -o /dev/null -w '%{url_effective}' \
      https://github.com/apptainer/apptainer/releases/latest
  )"
  latest_tag="${latest_url##*/}"
  [[ "${latest_tag}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
    die "Could not determine the latest stable Apptainer release."
  printf '%s\n' "${latest_tag#v}"
}

ensure_runtime_links() {
  local apptainer_bin unsquashfs_bin
  apptainer_bin="$(command -v apptainer || true)"
  [[ -n "${apptainer_bin}" ]] || die "Apptainer was not found after installation."

  if ! command -v singularity >/dev/null 2>&1; then
    run_as_root ln -sf "${apptainer_bin}" /usr/local/bin/singularity
  fi

  unsquashfs_bin="$(command -v unsquashfs || true)"
  if [[ -n "${unsquashfs_bin}" && ! -x /usr/local/bin/unsquashfs ]]; then
    run_as_root ln -sf "${unsquashfs_bin}" /usr/local/bin/unsquashfs
  fi
}

install_apptainer_debian() {
  local version architecture codename debian_major package install_script install_root
  version="${APPTAINER_VERSION:-$(get_latest_apptainer_version)}"
  architecture="$(dpkg --print-architecture)"
  codename="${VERSION_CODENAME:-}"

  case "${architecture}" in
    amd64|arm64) ;;
    *) die "Unsupported Debian architecture for Apptainer: ${architecture}" ;;
  esac

  if [[ "${architecture}" == "arm64" ]]; then
    debian_major="${VERSION_ID%%.*}"
    install_root="/opt/apptainer-${version}"
    install_script="/tmp/install-apptainer-unprivileged.sh"
    run_as_root apt-get update
    run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y curl cpio rpm2cpio
    run curl -fsSL \
      "https://raw.githubusercontent.com/apptainer/apptainer/v${version}/tools/install-unprivileged.sh" \
      -o "${install_script}"
    run chmod 755 "${install_script}"
    if (( DRY_RUN )); then
      printf '[dry-run] sudo bash %q -d %q -a aarch64 -v %q %q\n' \
        "${install_script}" "debian${debian_major}" "${version}" "${install_root}"
    elif [[ ! -x "${install_root}/bin/apptainer" ]]; then
      run_as_root bash "${install_script}" \
        -d "debian${debian_major}" -a aarch64 -v "${version}" "${install_root}"
    fi
    run_as_root ln -sf "${install_root}/bin/apptainer" /usr/local/bin/apptainer
    run_as_root ln -sf "${install_root}/bin/singularity" /usr/local/bin/singularity
    return
  fi

  case "${codename}" in
    bullseye|bookworm)
      package="apptainer_${version}_amd64.deb"
      ;;
    trixie)
      package="apptainer_${version}-trixie+_amd64.deb"
      ;;
    *)
      die "Debian/Raspberry Pi OS release '${codename:-unknown}' is not supported automatically."
      ;;
  esac

  run curl -fsSL \
    "https://github.com/apptainer/apptainer/releases/download/v${version}/${package}" \
    -o "/tmp/${package}"
  run_as_root apt-get install -y "/tmp/${package}"
}

install_apptainer() {
  if command -v apptainer >/dev/null 2>&1; then
    ensure_runtime_links
    return
  fi
  if (( DRY_RUN )); then
    log "Would install Apptainer for the detected Linux distribution."
    return
  fi

  [[ -r /etc/os-release ]] || die "Cannot identify the Linux distribution."
  # shellcheck disable=SC1091
  . /etc/os-release
  local id="${ID,,}"
  local id_like="${ID_LIKE:-}"
  id_like="${id_like,,}"

  case "${id}" in
    ubuntu|linuxmint)
      run_as_root apt-get update
      run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y software-properties-common
      run_as_root add-apt-repository -y ppa:apptainer/ppa
      run_as_root apt-get update
      run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y apptainer
      ;;
    debian|raspbian)
      install_apptainer_debian
      ;;
    fedora)
      run_as_root dnf install -y apptainer
      ;;
    rhel|centos|centos_stream|rocky|almalinux|ol|oraclelinux)
      if command -v dnf >/dev/null 2>&1; then
        run_as_root dnf install -y epel-release
        run_as_root dnf install -y apptainer
      else
        run_as_root yum install -y epel-release
        run_as_root yum install -y apptainer
      fi
      ;;
    *)
      if [[ "${id_like}" == *debian* ]]; then
        install_apptainer_debian
      else
        die "Automatic Apptainer installation is not supported for ${id}."
      fi
      ;;
  esac

  ensure_runtime_links
}

configure_apptainer_remote() {
  (( DRY_RUN )) && {
    log "Would configure the SylabsCloud Apptainer remote."
    return
  }
  command -v apptainer >/dev/null 2>&1 || return
  if ! apptainer remote list 2>/dev/null | grep -q SylabsCloud; then
    apptainer remote add --no-login SylabsCloud cloud.sylabs.io
  fi
  apptainer remote use SylabsCloud
}

configure_apptainer_fakeroot() {
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
  curl -Ls "https://micro.mamba.pm/api/micromamba/${platform}/1.5.7" |
    tar -xj -C "${temporary}" bin/micromamba
  install -m 755 "${temporary}/bin/micromamba" "${binary}"
  rm -rf "${temporary}"
  trap - RETURN
}

install_nextflow() {
  local binary="${BIN_DIR}/nextflow"
  if [[ -x "${binary}" ]]; then
    log "Nextflow launcher is already installed at ${binary}."
    return
  fi
  run mkdir -p "${BIN_DIR}"
  run curl -fsSL https://get.nextflow.io -o "${binary}"
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

  if MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${micromamba}" env list |
    awk 'NR > 1 {print $1}' | grep -qx viralflow; then
    MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${micromamba}" env update \
      -n viralflow -f "${env_file}" --prune -y
  else
    MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${micromamba}" env create \
      -n viralflow -f "${env_file}" -y
  fi

  MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" "${micromamba}" run \
    -n viralflow python -m pip install -e "${REPO_DIR}"

  local env_vfnext="${MAMBA_ROOT_PREFIX}/envs/viralflow/vfnext"
  rm -rf "${env_vfnext}"
  ln -s "${REPO_DIR}/vfnext" "${env_vfnext}"
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
    "${BIN_DIR}/micromamba" run -n viralflow \
    viralflow build-containers --arch "${architecture}"
}

verify_linux_installation() {
  (( DRY_RUN )) && return
  PATH="${BIN_DIR}:${PATH}" MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" \
    "${BIN_DIR}/micromamba" --version
  PATH="${BIN_DIR}:${PATH}" MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" \
    "${BIN_DIR}/micromamba" run -n viralflow viralflow --version
  PATH="${BIN_DIR}:${PATH}" \
    MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX}" \
    NXF_VER="${NEXTFLOW_VERSION}" \
    "${BIN_DIR}/micromamba" run -n viralflow "${BIN_DIR}/nextflow" -version
  singularity --version
}

configure_user_path() {
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
  if (( INSIDE_LIMA )); then
    log "Installing for Linux ${architecture} inside Lima."
  else
    log "Installing for Linux ${architecture}."
  fi
  install_linux_base_packages
  install_apptainer
  configure_apptainer_remote
  configure_apptainer_fakeroot
  install_micromamba "${architecture}"
  install_nextflow
  checkout_repository
  install_viralflow_environment "${architecture}"
  write_linux_launcher
  build_viralflow_containers "${architecture}"
  verify_linux_installation
}

ensure_homebrew() {
  (( DRY_RUN )) && return
  command -v brew >/dev/null 2>&1 ||
    die "Homebrew is required on macOS. Install it from https://brew.sh/."
}

ensure_lima_vm() {
  if ! command -v limactl >/dev/null 2>&1; then
    run brew install lima
  fi
  if ! limactl list 2>/dev/null | awk 'NR > 1 {print $1}' | grep -qx "${LIMA_VM_NAME}"; then
    run limactl create \
      --name "${LIMA_VM_NAME}" \
      --tty=false \
      --mount-writable \
      --arch aarch64 \
      template:ubuntu-lts
  fi
  run limactl start "${LIMA_VM_NAME}"
}

validate_macos_shared_home_mount() {
  local macos_home="${HOME}"
  if (( DRY_RUN )); then
    log "Would verify that ${macos_home} is mounted with write access inside Lima."
    return
  fi

  limactl shell "${LIMA_VM_NAME}" -- /bin/bash -lc '
    set -euo pipefail
    test -d "$1"
    test -w "$1"
  ' bash "${macos_home}" ||
    die "The macOS home directory (${macos_home}) is not mounted with write access inside the Lima VM."
}

write_macos_launcher() {
  local launcher="${BIN_DIR}/viralflow"
  run mkdir -p "${BIN_DIR}"
  if (( DRY_RUN )); then
    log "Would create the macOS Lima launcher at ${launcher}."
    return
  fi

  cat >"${launcher}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
VM_NAME=$(printf '%q' "${LIMA_VM_NAME}")
BIN_DIR=$(printf '%q' "${BIN_DIR}")
MAMBA_ROOT_PREFIX=$(printf '%q' "${MAMBA_ROOT_PREFIX}")

limactl start "\${VM_NAME}" >/dev/null
exec limactl shell "\${VM_NAME}" -- /bin/bash -lc '
  set -euo pipefail
  workdir="\$1"
  bin_dir="\$2"
  mamba_root="\$3"
  shift 3
  cd "\${workdir}"
  export MAMBA_ROOT_PREFIX="\${mamba_root}"
  export NXF_VER=$(printf '%q' "${NEXTFLOW_VERSION}")
  export PATH="\${bin_dir}:\${PATH}"
  exec "\${bin_dir}/micromamba" run -n viralflow viralflow "\$@"
' bash "\${PWD}" "\${BIN_DIR}" "\${MAMBA_ROOT_PREFIX}" "\$@"
EOF
  chmod 755 "${launcher}"
}

run_installer_inside_lima() {
  local script_path script_dir
  script_path="${BASH_SOURCE[0]}"
  if [[ ! -r "${script_path}" || "${script_path}" == /dev/fd/* ]]; then
    script_dir="${HOME}/.cache/viralflow-installer"
    run mkdir -p "${script_dir}"
    script_path="${script_dir}/install.sh"
    run curl -fsSL \
      "https://raw.githubusercontent.com/camilodotto/ViralFlow/${BRANCH}/install.sh" \
      -o "${script_path}"
  else
    script_path="$(cd "$(dirname "${script_path}")" && pwd)/$(basename "${script_path}")"
  fi

  local args=(
    --inside-lima
    --platform linux
    --arch arm64
    --repo-dir "${REPO_DIR}"
    --install-root "${INSTALL_ROOT}"
    --bin-dir "${BIN_DIR}"
    --repository "${REPOSITORY}"
    --branch "${BRANCH}"
    --nextflow-version "${NEXTFLOW_VERSION}"
  )
  (( BUILD_CONTAINERS )) || args+=(--skip-containers)
  (( UPDATE_REPOSITORY )) || args+=(--no-update)
  (( DRY_RUN )) && args+=(--dry-run)

  if (( DRY_RUN )); then
    printf '[dry-run] limactl shell %q -- /bin/bash %q' "${LIMA_VM_NAME}" "${script_path}"
    quote_command "${args[@]}"
    return
  fi
  limactl shell "${LIMA_VM_NAME}" -- /bin/bash "${script_path}" "${args[@]}"
}

install_macos() {
  log "Installing for macOS through an ARM64 Lima VM."
  ensure_homebrew
  ensure_lima_vm
  validate_macos_shared_home_mount
  run_installer_inside_lima
  write_macos_launcher
  (( DRY_RUN )) || "${BIN_DIR}/viralflow" --version
}

print_summary() {
  cat <<EOF

ViralFlow installation completed.

Repository: ${REPO_DIR}
Command:    ${BIN_DIR}/viralflow

The installer added this directory to your shell PATH configuration when needed:
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
    macos)
      install_macos
      ;;
    *)
      die "Unsupported platform: ${platform}"
      ;;
  esac

  configure_user_path
  print_summary
}

main "$@"
