#!/bin/bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"
organism_name=$1
organism_refseq_code=$2
runtime=${VIRALFLOW_CONTAINER_RUNTIME:-}
if [ -z "$runtime" ]; then
    if command -v apptainer >/dev/null; then runtime=apptainer; else runtime=singularity; fi
fi
snpeff=("$runtime" exec --fakeroot --overlay "$SCRIPT_DIR/snpeff_5.0.overlay")
genbank=$(mktemp "${TMPDIR:-/tmp}/viralflow-snpeff.XXXXXX")
trap 'rm -f "$genbank"' EXIT
"$runtime" exec "$SCRIPT_DIR/edirect:1.1.0.sif" efetch -db nucleotide -id "$organism_refseq_code" -format gb > "$genbank"
# Pass user inputs as positional arguments, never interpolate them into code.
"${snpeff[@]}" --bind "$genbank:/tmp/viralflow-snpeff.gbk:ro" "$SCRIPT_DIR/snpeff:5.0.sif" bash -c '
set -euo pipefail
snpeff_path=$(dirname "$(readlink -f "$(command -v snpEff)")")
test -f "$snpeff_path/snpEff.config"
code=$2
if ! grep -Fq "$code.genome:" "$snpeff_path/snpEff.config"; then
    printf "# %s, version %s\n%s.genome: %s\n%s.has_cds: true\n%s.codonTable: Standard\n" "$1" "$code" "$code" "$1" "$code" "$code" >> "$snpeff_path/snpEff.config"
fi
mkdir -p "$snpeff_path/data/$code"
cp "$3" "$snpeff_path/data/$code/genes.gbk"
snpEff build -genbank -v "$code"
' bash "$organism_name" "$organism_refseq_code" /tmp/viralflow-snpeff.gbk
"${snpeff[@]}" "$SCRIPT_DIR/snpeff:5.0.sif" snpEff databases > snpEff_DB.catalog
