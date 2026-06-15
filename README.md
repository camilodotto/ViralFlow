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
