# ViralFlow

This repository contains the code of ViralFlow, a workflow that performs a reference-guided genome assembly of non-segmented viruses written in Nextflow. The workflow was developed to work with Illumina paired-end reads. Tests with other technologies should be performed.

If you use this workflow for academic purposes, please cite:  
[ViralFlow v1.0—a computational workflow for streamlining viral genomic surveillance](https://academic.oup.com/nargab/article/6/2/lqae056/7682253).

## Documentation

The official documentation can be accessed [here](https://viralflow.github.io/index-en.html) in English or [here](https://viralflow.github.io/) in Portuguese.

ViralFlow is a Nextflow pipeline and should be treated as such; check `vfnext/` for more details.  
A wrapper for the pipeline is provided for user convenience.

## Command-line installation

This branch uses Apptainer and includes separate environments for AMD64 and
ARM64. To install ViralFlow with Micromamba, Nextflow, Apptainer and its
containers:

```bash
curl -fsSLO https://raw.githubusercontent.com/camilodotto/ViralFlow/develop-SIF3-MAC/install.sh
chmod +x install.sh
./install.sh
```

The installer supports Linux/WSL AMD64, Linux/WSL ARM64 and macOS through a
Lima ARM64 virtual machine. By default, it installs the `viralflow` command in
`~/.local/bin`.

Apptainer is required. A pre-existing Singularity CE installation is not enough
for this branch, because local container build and update commands call
`apptainer` directly.

To install without downloading and building the containers immediately:

```bash
./install.sh --skip-containers
```

The container build downloads several gigabytes and may take a long time,
especially on ARM64. It can be executed later with:

```bash
viralflow build-containers --arch amd64
# or:
viralflow build-containers --arch arm64
```

See all available options with:

```bash
./install.sh --help
```

## Manual command-line installation

The automated installer performs the steps below: installs system packages,
installs or configures Apptainer, installs Micromamba and Nextflow under the
user account, clones this ViralFlow branch, creates the architecture-specific
Micromamba environment, installs the wrapper with `pip`, creates a `viralflow`
launcher and optionally builds the containers.

Use the manual procedure only if you need to control each step yourself.

### Common paths

The installer uses these paths by default; the manual commands below use the
same layout:

```bash
export VIRALFLOW_REPO="$HOME/ViralFlow"
export VIRALFLOW_BIN="$HOME/.local/bin"
export MAMBA_ROOT_PREFIX="$HOME/.local/share/viralflow/micromamba"
export NXF_VER="22.04.0"

mkdir -p "$VIRALFLOW_BIN" "$MAMBA_ROOT_PREFIX"
export PATH="$VIRALFLOW_BIN:$PATH"
```

To keep `viralflow`, `micromamba` and `nextflow` available in new shells:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### Linux or WSL on AMD64

Install base packages:

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates curl git bzip2 tar python3 python3-pip \
  uidmap squashfs-tools software-properties-common
```

Install Apptainer on Ubuntu or Linux Mint:

```bash
sudo add-apt-repository -y ppa:apptainer/ppa
sudo apt-get update
sudo apt-get install -y apptainer
```

On Debian AMD64, install the matching `.deb` package from the latest
Apptainer release. For example, on Debian 12/bookworm:

```bash
APPTAINER_VERSION="$(curl -fsSL -o /dev/null -w '%{url_effective}' https://github.com/apptainer/apptainer/releases/latest)"
APPTAINER_VERSION="${APPTAINER_VERSION##*/v}"
curl -fsSLO "https://github.com/apptainer/apptainer/releases/download/v${APPTAINER_VERSION}/apptainer_${APPTAINER_VERSION}_amd64.deb"
sudo apt-get install -y "./apptainer_${APPTAINER_VERSION}_amd64.deb"
```

Install Micromamba and Nextflow:

```bash
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/1.5.7 |
  tar -xj -C /tmp bin/micromamba
install -m 755 /tmp/bin/micromamba "$VIRALFLOW_BIN/micromamba"

curl -fsSL https://get.nextflow.io -o "$VIRALFLOW_BIN/nextflow"
chmod 755 "$VIRALFLOW_BIN/nextflow"
```

Clone ViralFlow and create the environment:

```bash
git clone --branch develop-SIF3-MAC --single-branch \
  https://github.com/camilodotto/ViralFlow.git "$VIRALFLOW_REPO"

MAMBA_ROOT_PREFIX="$MAMBA_ROOT_PREFIX" \
  "$VIRALFLOW_BIN/micromamba" env create \
  -n viralflow -f "$VIRALFLOW_REPO/envs/amd64.yml" -y

MAMBA_ROOT_PREFIX="$MAMBA_ROOT_PREFIX" \
  "$VIRALFLOW_BIN/micromamba" run -n viralflow \
  python -m pip install -e "$VIRALFLOW_REPO"

ln -sfn "$VIRALFLOW_REPO/vfnext" \
  "$MAMBA_ROOT_PREFIX/envs/viralflow/vfnext"
```

Create the launcher:

```bash
cat > "$VIRALFLOW_BIN/viralflow" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export MAMBA_ROOT_PREFIX="$MAMBA_ROOT_PREFIX"
export NXF_VER="$NXF_VER"
export PATH="$VIRALFLOW_BIN:\$PATH"
exec "$VIRALFLOW_BIN/micromamba" run -n viralflow viralflow "\$@"
EOF
chmod 755 "$VIRALFLOW_BIN/viralflow"
```

Configure the `unsquashfs` compatibility link, Apptainer fakeroot and the
SylabsCloud remote:

```bash
sudo ln -sf "$(command -v unsquashfs)" /usr/local/bin/unsquashfs
sudo apptainer config fakeroot --add "$(id -un)"
apptainer remote add --no-login SylabsCloud cloud.sylabs.io || true
apptainer remote use SylabsCloud
```

Build the containers:

```bash
viralflow build-containers --arch amd64
```

If `/tmp` is small or mounted as `tmpfs`, use a staging directory on a larger
disk:

```bash
viralflow build-containers --arch amd64 --staging-dir "$HOME/viralflow-apptainer"
```

### Linux or Raspberry Pi OS on ARM64

Install base packages:

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates curl git bzip2 tar python3 python3-pip \
  uidmap squashfs-tools cpio rpm2cpio
```

Install Apptainer using the official unprivileged installer:

```bash
. /etc/os-release
APPTAINER_VERSION="$(curl -fsSL -o /dev/null -w '%{url_effective}' https://github.com/apptainer/apptainer/releases/latest)"
APPTAINER_VERSION="${APPTAINER_VERSION##*/v}"
INSTALL_ROOT="/opt/apptainer-${APPTAINER_VERSION}"
curl -fsSL \
  "https://raw.githubusercontent.com/apptainer/apptainer/v${APPTAINER_VERSION}/tools/install-unprivileged.sh" \
  -o /tmp/install-apptainer-unprivileged.sh
chmod 755 /tmp/install-apptainer-unprivileged.sh
sudo bash /tmp/install-apptainer-unprivileged.sh \
  -d "debian${VERSION_ID%%.*}" -a aarch64 -v "$APPTAINER_VERSION" "$INSTALL_ROOT"
sudo ln -sf "$INSTALL_ROOT/bin/apptainer" /usr/local/bin/apptainer
```

Install the ARM64 Micromamba binary:

```bash
curl -Ls https://micro.mamba.pm/api/micromamba/linux-aarch64/1.5.7 |
  tar -xj -C /tmp bin/micromamba
install -m 755 /tmp/bin/micromamba "$VIRALFLOW_BIN/micromamba"
```

Install Nextflow and clone ViralFlow:

```bash
curl -fsSL https://get.nextflow.io -o "$VIRALFLOW_BIN/nextflow"
chmod 755 "$VIRALFLOW_BIN/nextflow"

git clone --branch develop-SIF3-MAC --single-branch \
  https://github.com/camilodotto/ViralFlow.git "$VIRALFLOW_REPO"
```

Create the ViralFlow environment from `envs/arm64.yml` and install the wrapper:

```bash
MAMBA_ROOT_PREFIX="$MAMBA_ROOT_PREFIX" \
  "$VIRALFLOW_BIN/micromamba" env create \
  -n viralflow -f "$VIRALFLOW_REPO/envs/arm64.yml" -y

MAMBA_ROOT_PREFIX="$MAMBA_ROOT_PREFIX" \
  "$VIRALFLOW_BIN/micromamba" run -n viralflow \
  python -m pip install -e "$VIRALFLOW_REPO"

ln -sfn "$VIRALFLOW_REPO/vfnext" \
  "$MAMBA_ROOT_PREFIX/envs/viralflow/vfnext"
```

Create the same `viralflow` launcher described for AMD64, configure Apptainer
fakeroot and the SylabsCloud remote, then build the ARM64 containers with:

```bash
viralflow build-containers --arch arm64
```

### Fedora, RHEL, Rocky Linux, AlmaLinux or Oracle Linux

Install the base packages with the system package manager:

```bash
sudo dnf install -y ca-certificates curl git bzip2 tar python3 python3-pip \
  shadow-utils squashfs-tools
```

On Fedora:

```bash
sudo dnf install -y apptainer
```

On RHEL-compatible systems:

```bash
sudo dnf install -y epel-release
sudo dnf install -y apptainer
```

After Apptainer is installed, follow the AMD64 or ARM64 Micromamba, Nextflow,
ViralFlow environment and container build steps according to the machine
architecture.

### macOS through Lima

ViralFlow itself runs in a Linux ARM64 VM. Install Homebrew and Lima on macOS:

```bash
brew install lima
limactl create --name viralflow --tty=false --mount-writable --arch aarch64 template:ubuntu-lts
limactl start viralflow
```

Open a shell inside the VM:

```bash
limactl shell viralflow
```

Inside the Lima shell, keep the ViralFlow checkout in the mounted macOS home
directory, but install Linux-only dependencies in a fixed directory on the
VM's internal filesystem:

```bash
export MACOS_HOME="/Users/your_user"
export VIRALFLOW_REPO="$MACOS_HOME/ViralFlow"
export VIRALFLOW_INSTALL_ROOT="/var/lib/viralflow"
export VIRALFLOW_BIN="$VIRALFLOW_INSTALL_ROOT/bin"
export MAMBA_ROOT_PREFIX="$VIRALFLOW_INSTALL_ROOT/micromamba"
export NXF_VER="22.04.0"

test -d "$MACOS_HOME" && test -w "$MACOS_HOME"
sudo install -d -o "$(id -u)" -g "$(id -g)" \
  "$VIRALFLOW_INSTALL_ROOT" "$VIRALFLOW_BIN"
mkdir -p "$MAMBA_ROOT_PREFIX"
export PATH="$VIRALFLOW_BIN:$PATH"
```

Replace `/Users/your_user` with the value of `echo "$HOME"` on macOS. Then
follow the Linux ARM64 instructions above using these paths. This places
Micromamba, Nextflow and the `viralflow` environment under `/var/lib/viralflow`
inside Lima. Only the repository remains in the macOS home directory.

Create a host-side launcher at `~/.local/bin/viralflow`:

```bash
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/viralflow" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
MACOS_HOME="$HOME"
limactl start viralflow >/dev/null
exec limactl shell viralflow -- /bin/bash -lc '
  set -euo pipefail
  macos_home="$1"
  shift
  export MAMBA_ROOT_PREFIX="/var/lib/viralflow/micromamba"
  export NXF_VER="22.04.0"
  export PATH="/var/lib/viralflow/bin:$PATH"
  cd "${macos_home}/ViralFlow"
  exec "/var/lib/viralflow/bin/micromamba" run -n viralflow viralflow "$@"
' bash "$MACOS_HOME" "$@"
EOF
chmod 755 "$HOME/.local/bin/viralflow"
```
