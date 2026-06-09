# Nanopore 

This document provides guidelines and instructions on how to run nanopore data on ViralFlow.

> this is a provisory documentation for development purpose, the oficial documentation should be included on the regular ViralFlow documentation.

---

## Build container

```
cd /.../ViralFlow/vfnext/containers/
singularity build baseContainer.sif Nanopore_baseContainer.sing
# or
apptainer build baseContainer.sif Nanopore_baseContainer.sing
```
### Apptainer setup

Unfortunately, apptainer does not support `library://` protocol. To make it work on this protocol run the following commands:

```bash
apptainer remote add --no-login SylabsCloud cloud.sycloud.io
apptainer remote use SylabsCloud
apptainer remote list
```

---

## Run pipeline 

To run the nanopore mode of the viral pipeline simply run:

```bash
nextflow run /../ViralFlow/vfnext/main.nf \
        --mode NANOPORE \
        --inDir /path/to/np_input_dir/ \
        --referenceGenome /path/to/reference.fna \
        -resume
```

to run it using apptainer, just add `-profile apptainer` to your nextflow command.

## Reproducibility metadata

Every run writes reproducibility records under `RUN_METADATA` inside the output
directory:

- `run_manifest.json`: pipeline revision, parameters, runtime context, and final status.
- `input_checksums.tsv`: SHA-256 checksums for reads and reference inputs.
- `software_versions.tsv`: versions of the core tools used by the selected mode.
- `container_manifest.tsv`: container identities and local SIF checksums.
- `execution_trace.tsv`: per-task status and resource usage.
- `execution_report.html` and `execution_timeline.html`: Nextflow execution reports.

Metadata collection is part of the workflow. Missing tools, unreadable inputs, or
an invalid local container path cause the run to fail rather than recording
incomplete provenance.
