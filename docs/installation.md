# Installation

## Ubuntu 26.04 with Apptainer

This branch uses Apptainer on the Ubuntu host. The installer was adapted from
`develop-SIF3-MAC`, keeping the Linux installation path:

```bash
git clone -b feat/develop/ubuntu26.04 https://github.com/camilodotto/ViralFlow.git
cd ViralFlow
bash install.sh --repo-dir "$PWD"
export PATH="$HOME/.local/bin:$PATH"
viralflow --version
```

It installs the wrapper in a Micromamba environment, Java 17 and the compact
Nextflow 23.10.1 launcher, which resolves dependencies on first use.
Apptainer is reused when already installed;
otherwise it is installed from its Ubuntu PPA. System packages and missing
fakeroot mappings use `sudo`. Images keep their original versions; pangolin
and snpEff remain **sandbox directories**, even though their names end in `.sif`.
The other images remain SIF files. Docker Engine is not needed.

To use an existing checkout and system dependencies:

```bash
bash install.sh --repo-dir "$PWD" --no-update --skip-system-packages
```

Use `--dry-run` to preview, `--skip-containers` to install only the runtime,
and `--no-path-update` to leave shell startup files untouched. `--install-root`
and `--bin-dir` select separate installation directories. Existing local
changes are preserved. No `/usr/local/bin/unsquashfs` symlink is required;
`unsquashfs` only needs to be available in `PATH`.

The generated `viralflow` launcher selects Java through Micromamba and keeps
Nextflow's cache under the installation root. Direct Nextflow invocation
requires Nextflow >=23.10.1 and Java 17. ARM64 environment definitions remain
available; the host validation recorded for this branch is AMD64.

See [the migration record](../UBUNTU26.04-CHANGES.md) for validation results and
the complete file-by-file change list. The manual instructions below describe
the older Ubuntu installations; prefer this installer for the current branch.

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
