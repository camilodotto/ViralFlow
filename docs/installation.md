# Installation

## Ubuntu 26.04

This branch uses Micromamba 1.5.7, Nextflow 22.04.0 and Java 17.
ViralFlow invokes `singularity` for container build, download, maintenance and
execution, as in the upstream branch. The GUI installs Apptainer and provides
the `singularity` compatibility command. Pangolin and snpEff remain
**sandbox directories**, despite their `.sif` suffix; the other images are SIF.

The ViralFlow GUI manages the installation in separate steps: Micromamba,
Nextflow, Apptainer, ViralFlow and containers. Its default paths are
`~/ViralFlowGUI/bin`, `~/ViralFlowGUI/micromamba` and `~/ViralFlowGUI/ViralFlow`.
This branch does not provide `install.sh`.

### Container distribution (GHCR)

`viralflow build-containers` downloads the 11 prebuilt SIF images from
`oras://ghcr.io/camilodotto/viralflow-amd64/<image>:<tag>` using the host's
`singularity` compatibility command. Public images need no login, token or
Sylabs remote configuration. The repository lists in
`vfnext/containers/repositories/` contain complete ORAS URIs. Local filenames
remain `<image>:<tag>.sif`, so existing images are reused and Nextflow paths
are unchanged. Pangolin and snpEff are still built locally as writable sandboxes.

The AMD64 snpEff recipe uses Debian 12 and Micromamba 1.5.7, with
`snpeff=5.0=hdfd78af_3` and Java 17 installed under `/opt/conda`. This avoids
upgrading Conda inside the old Miniconda 4.7.12 base (glibc 2.28), which can
fail dependency resolution against current channels. The database maintenance
path `/opt/conda/share/snpeff-5.0-3` is preserved, and the build verifies the
downloaded `NC_045512.2` database before completing. Existing snpEff sandboxes
are reused; this recipe applies to new builds.

Validated on 2026-11-07: a clean AMD64 sandbox build, snpEff 5.0e/Java 17,
annotation of a test VCF using `NC_045512.2` (including the HTML summary and
gene report), and the complete `viralflow build-containers` command in the
GUI installation. The command completed with exit code 0, including the
Nextclade dataset and snpEff database catalog. The 14 Python runtime tests passed.

ARM64 uses the separate `viralflow-arm64` prefix. As of 2026-11-07, anonymous
manifest requests for the 11 AMD64 images succeeded; all ARM64 requests returned
403. ARM64 installation requires those images to be published and made public;
never substitute AMD64 images for them.

To test an anonymous download, use a clean user environment without registry
credentials and a temporary output directory:

```bash
singularity pull edirect:1.1.0.sif \
  oras://ghcr.io/camilodotto/viralflow-amd64/edirect:1.1.0
```

Existing GUI installations must update their ViralFlow checkout to
`feat/dev/ubuntu26.04-ghcr.io` before running `build-containers` again.


For manual installation, provide Micromamba and a working `singularity` command
on the host (Singularity or Apptainer's compatibility command), put them in
`PATH`, then create the environment from the appropriate YAML:

```bash
git clone -b feat/dev/ubuntu26.04-ghcr.io https://github.com/camilodotto/ViralFlow.git
cd ViralFlow
micromamba env create -n viralflow -f envs/amd64.yml -y
micromamba run -n viralflow python -m pip install -e .
NXF_VER=22.04.0 micromamba run -n viralflow nextflow -version
micromamba run -n viralflow viralflow --version
```

Java 17 and Nextflow 22.04.0 come from the YAML, matching the upstream
environment. The GUI also installs its own Nextflow launcher in `bin` and
selects that absolute path. The container runtime is provided by the host;
the YAML does not install a second runtime in the Conda environment.
For an existing environment, use
`micromamba update -n viralflow -f envs/amd64.yml --prune -y`.
The GUI pins its own Nextflow binary and keeps its cache under the installation
root. See [the migration record](../UBUNTU26.04-CHANGES.md) for changes and
validation. The remaining instructions describe the older installation paths.

## MacOS Installation

Due to the limitation of using singularity on MacOS, to run ViralFlow on this type of system, we suggest using a Linux virtualization software called [Lima](https://github.com/lima-vm/lima).

### Installing Lima

Install Lima using the Homebrew package manager:

```bash
brew install lima
```

### Installing the Ubuntu instance

Follow the step by step installation of an Ubuntu instance:

```bash
limactl start
```

### Start Ubuntu

When the virtual machine is installed, use the command below to start Ubuntu and follow the ViralFlow installation steps as usual:

```bash
lima
```

## Ubuntu Installation

To install ViralFlow, four steps are necessary:
1. Install system dependencies
2. Install Conda
3. Install ViralFlow  
4. Build the containers for analyses

This process is performed only once.

ViralFlow was developed and tested for the following operational systems:
- Ubuntu 20.04 LTS
- Ubuntu 22.04 LTS

### Installing System Dependencies

If you don't have the pip dependency installer, the git version control system, and the uidmap package, install them with:

```bash
sudo apt update -y && \
  sudo apt upgrade -y && \
  sudo apt install curl git python3-pip uidmap -y
```

### Installing and Configuring Micromamba

We recommend managing micromamba environments due to their parallelization when downloading and installing dependencies. If you use another environment manager (conda, miniconda, mamba), you can skip this step, however, conflicts during installation may occur.

If you don't have micromamba installed:

```bash
cd $HOME
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/1.5.7 | tar -xvj bin/micromamba
./bin/micromamba shell init -s bash -p ~/micromamba
source ~/.bashrc
micromamba activate
```

### Installing ViralFlow

If you already have the aforementioned dependencies and conda installed, you can install ViralFlow with 5 lines of code:

```bash
git clone https://github.com/WallauBioinfo/ViralFlow
cd ViralFlow/
micromamba env create -f envs/env.yml
micromamba activate viralflow
pip install -e .
```

### Building the Containers

All steps of ViralFlow are performed in controlled environments. ViralFlow has its own method to carry out all this construction of environments, running just one line of code.

For the building of containers, ViralFlow requires that the tool "unsquashfs" be available in the directory `/usr/local/bin/`. To ensure this, create a symbolic link:

```bash
sudo ln -s /usr/bin/unsquashfs /usr/local/bin/unsquashfs
```

After ensuring that "unsquashfs" is in the appropriate location, run the command to build the containers:

```bash
viralflow build_containers
```

```{note}
This process will download approximately 4.4GB of container images. Ensure you have sufficient disk space and a stable internet connection.
```
