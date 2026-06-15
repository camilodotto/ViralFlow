# ViralFlow - Development Documentation

For computing environments with ARM64 architecture the user should inform the `--arch arm64` flag into some commands.

## Installation

### Automated installation

The installer in this branch configures Apptainer, Micromamba, Nextflow,
ViralFlow and the architecture-specific environment:

```bash
curl -fsSLO https://raw.githubusercontent.com/camilodotto/ViralFlow/develop-SIF3-MAC/install.sh
chmod +x install.sh
./install.sh
```

Supported environments:

- Linux and WSL on AMD64;
- Linux and Raspberry Pi OS 64-bit on ARM64;
- macOS through an ARM64 Lima VM.

The default checkout is `~/ViralFlow`, and the command is installed at
`~/.local/bin/viralflow`. Use `./install.sh --help` to change these paths or
skip the initial container build.

### AMD64

```bash
./install.sh --skip-containers
viralflow build-containers --arch amd64
```

### ARM64

```bash
./install.sh --skip-containers
viralflow build-containers --arch arm64
```

### Customizing snpEff catalog

#### AMD64

```bash
viralflow add-entry-to-snpeff --org-name Dengue --genome-code NC_001474.2
```

#### ARM64

```bash
viralflow add-entry-to-snpeff --org-name Dengue --genome-code NC_001474.2 --arch arm64
```

### Updating pangolin

```bash
viralflow update-pangolin

viralflow update-pangolin-data
```

### Running ViralFlow

```bash
viralflow run --params-file test_files/sars-cov-2.params
```

```bash
viralflow run --params-file test_files/denv.params
```
