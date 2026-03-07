#!/bin/bash

set -euo pipefail

# get bash script location
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR"

# user input
organism_name=${1:?Usage: add_entries_SnpeffDB.sh <organism_name> <refseq_code> <arch>}
organism_refseq_code=${2:?Usage: add_entries_SnpeffDB.sh <organism_name> <refseq_code> <arch>}
arch=${3:-unknown}

# hardcoded paths
SNPEFF_CTNR="snpeff:5.0.sif"
EFETCH_CTNR="edirect:1.1.0.sif"

if command -v apptainer >/dev/null 2>&1; then
    CONTAINER_RUNTIME="apptainer"
elif command -v singularity >/dev/null 2>&1; then
    CONTAINER_RUNTIME="singularity"
else
    echo "ERROR: apptainer/singularity executable not found."
    exit 1
fi

if [ ! -e "$SNPEFF_CTNR" ]; then
    echo "ERROR: Container not found: $SNPEFF_CTNR"
    exit 1
fi

if [ ! -e "$EFETCH_CTNR" ]; then
    echo "ERROR: Container not found: $EFETCH_CTNR"
    exit 1
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
TMP_GENBANK="$TMP_DIR/genes.gbk"

SNPEFF_PATH=$("$CONTAINER_RUNTIME" exec "$SNPEFF_CTNR" sh -c '
    for d in \
        /opt/conda/share/snpeff-5.0-3 \
        /opt/conda/share/snpeff-5.0-2 \
        /usr/local/bin/mm/share/snpeff-5.0-3 \
        /usr/local/bin/mm/share/snpeff-5.0-2
    do
        if [ -d "$d" ]; then
            printf "%s\n" "$d"
            exit 0
        fi
    done
    exit 1
') || {
    echo "ERROR: Could not find snpEff installation directory inside $SNPEFF_CTNR (arch=$arch)."
    exit 1
}

echo "Using container runtime: $CONTAINER_RUNTIME"
echo "Using snpEff path: $SNPEFF_PATH"

echo "@ adding new entry..."
"$CONTAINER_RUNTIME" exec --fakeroot --writable "$SNPEFF_CTNR" sh -c '
    set -eu
    snpeff_path=$1
    organism_name=$2
    organism_refseq_code=$3
    config_file="$snpeff_path/snpEff.config"

    mkdir -p "$snpeff_path/data/$organism_refseq_code"

    if ! grep -q "^$organism_refseq_code\\.genome:" "$config_file"; then
        {
            printf "# %s, version %s\n" "$organism_name" "$organism_refseq_code"
            printf "%s.genome: %s\n" "$organism_refseq_code" "$organism_name"
            printf "%s.has_cds: true\n" "$organism_refseq_code"
            printf "%s.codonTable: Standard\n" "$organism_refseq_code"
        } >> "$config_file"
    fi
' sh "$SNPEFF_PATH" "$organism_name" "$organism_refseq_code"

echo "@ downloading fasta..."
"$CONTAINER_RUNTIME" exec "$EFETCH_CTNR" \
    efetch -db nucleotide -id "$organism_refseq_code" -format gb > "$TMP_GENBANK"

echo "@ copying fasta into snpEff container..."
"$CONTAINER_RUNTIME" exec --fakeroot --writable \
    -B "$TMP_DIR:/tmp/vf-snpeff" \
    "$SNPEFF_CTNR" \
    sh -c '
        set -eu
        snpeff_path=$1
        organism_refseq_code=$2
        cp /tmp/vf-snpeff/genes.gbk "$snpeff_path/data/$organism_refseq_code/genes.gbk"
    ' sh "$SNPEFF_PATH" "$organism_refseq_code"

echo "@ rebuild database"
"$CONTAINER_RUNTIME" exec --fakeroot --writable "$SNPEFF_CTNR" \
    snpEff build -genbank -v "$organism_refseq_code"

echo "@ update snpeff database catalog..."
"$CONTAINER_RUNTIME" exec "$SNPEFF_CTNR" snpEff databases > snpEff_DB.catalog
