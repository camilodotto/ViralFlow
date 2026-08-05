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

The same existing Nanopore parameters can be passed through the ViralFlow
wrapper:

```bash
viralflow run --mode NANOPORE \
  --in-dir /path/to/np_input_dir/ \
  --reference-genome /path/to/reference.fna \
  --np-min-depth 20 \
  --af-threshold 0.51 \
  --clair3-qual 10 \
  --clair3-model r941_prom_sup_g5014 \
  --clair3-chunk-size 10000 \
  --base-container /path/to/baseContainer.sif
```

In a params file, use the original Nextflow names: `np_min_depth`,
`af_threshold`, `clair3_qual`, `clair3_model`, `clair3_chunk_size`, and
`base_container`. Omitting these options leaves the defaults from
`nextflow.config` unchanged.

## Current threshold behavior

The current threshold logic is as follows:

- Clair3 receives `--qual` from `clair3_qual` and `--min_mq` from
  `mapping_quality`.
- BCFtools retains variants when `FORMAT/AF >= af_threshold`. No additional
  variant depth or `FILTER=PASS` condition is applied.
- Consensus coverage is calculated with `samtools depth -J -a` without
  additional mapping-quality or base-quality filters.
- Consensus positions with depth less than or equal to `np_min_depth` are
  masked.

Consequently, a low-depth variant can remain in the filtered VCF while the same
position is masked in the consensus. Each sample directory contains a
`<sample>.nanopore_qc.tsv` file that reports the configured thresholds, variant
counts, depth summary, masked bases, and callable consensus percentage. This
file is descriptive and does not affect pipeline success or filtering.

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

## Truth integration test

The deterministic FASTQ-to-consensus truth test is intentionally separate from
the regular unit-test suite because it runs Porechop, Minimap2, Clair3,
BCFtools, consensus generation, and Nanopore QC:

```bash
cd vfnext
NXF_VER=25.04.6 nf-test test integration_tests/nanopore-truth.nf.test
```
