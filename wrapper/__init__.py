import os
import subprocess
import shlex
import tempfile
import re
from pathlib import Path


NEXTFLOW_VERSION = "26.04.6"


def add_entries_to_DB(root_path, org_name, refseq_code, arch):
    """
    add entries provided to snpeff database
    """
    if any(ord(character) < 32 or ord(character) == 127 for character in org_name):
        raise ValueError("Organism name cannot contain control characters")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", refseq_code):
        raise ValueError(
            "Genome code must start with a letter or number and contain only letters, numbers, dots, underscores, and hyphens"
        )
    containers_dir = Path(root_path) / "vfnext" / "containers"
    script = (
        "add_entries_SnpeffOverlay.sh"
        if (containers_dir / "snpeff_5.0.overlay").is_file()
        else "add_entries_SnpeffDB.sh"
    )
    command = [
        "bash",
        str(containers_dir / script),
        org_name,
        refseq_code,
        arch,
    ]
    print(shlex.join(command))
    subprocess.run(command, cwd=containers_dir, check=True)
    from .container_management import record_overlay_update

    record_overlay_update(containers_dir, ["snpeff_5.0.overlay", "snpEff_DB.catalog"])


def parse_csv(csv_flpath):
    with open(csv_flpath, "r") as csv_fl:
        first_line = True
        entries_lst = []
        for line in csv_fl:
            # skip header
            if first_line:
                first_line = False
                continue
            ln_data = line.split(",")
            entry = [ln_data[0], ln_data[1].replace("\n", "")]
            entries_lst.append(entry)
    return entries_lst


def build_containers(root_path, arch: str, clean=False, staging_dir=None):
    """
    run script to build container for vfnext
    """
    from .container_management import prepare_containers

    prepare_containers(root_path, arch, clean, staging_dir)


# Parameters that only NANOPORE mode reads, by their nextflow.config names. The
# params-file parser accepts them and the CLI exposes one option for each
# (wrapper.cli.NANOPORE_OPTIONS); tests/test_wrapper_nanopore.py keeps the two
# in step. Their defaults live in nextflow.config alone: the wrapper forwards a
# value only when the user gave one.
NANOPORE_PARAMS = (
    "clair3_model",
    "clair3_qual",
    "clair3_chunk_size",
    "af_threshold",
    "np_min_depth",
    "base_container",
    "clair3_container",
    "porechop_cpus",
    "porechop_memory",
    "minimap_cpus",
    "minimap_memory",
    "clair3_cpus",
    "clair3_memory",
)

# The two NANOPORE images may be a local SIF or a registry reference.
CONTAINER_PARAMS = ("base_container", "clair3_container")
MEMORY_PARAMS = ("porechop_memory", "minimap_memory", "clair3_memory")


def container_reference(value):
    """A container value as Nextflow should receive it.

    An existing local file (a SIF) is made absolute, as path parameters are:
    Nextflow would otherwise resolve it against a task's work directory. Anything
    else - `viralflow/nanopore-base:2.0.0a1`, `docker://…` - is an image
    reference for the engine to resolve, and a path lookup would corrupt it.
    """
    value = str(value)
    return os.path.abspath(value) if os.path.isfile(value) else value


# input args file load
def parse_params(in_flpath, overrides=None):
    """
    Load a legacy parameter file as a subprocess argument list.

    Path parameters consume the entire remainder of their line so unquoted paths
    containing spaces remain a single argument. All other parameters are scalar.
    Explicit CLI overrides replace file values before mode validation.
    """
    valid_args = {*NANOPORE_PARAMS} | {
        "mode",
        "virus",
        "primersBED",
        "outDir",
        "inDir",
        "samplesheet",
        "runSnpEff",
        "writeMappedReads",
        "minLen",
        "depth",
        "minDpIntrahost",
        "trimLen",
        "refGenomeCode",
        "referenceGFF",
        "referenceGenome",
        "nextflowSimCalls",
        "fastp_threads",
        "bwa_threads",
        "mafft_threads",
        "nxtclade_jobs",
        "mapping_quality",
        "base_quality",
        "dedup",
        "ndedup",
    }
    path_params = {
        "inDir",
        "samplesheet",
        "outDir",
        "referenceGFF",
        "referenceGenome",
        "primersBED",
    }
    parsed = {}

    with open(in_flpath, "r") as in_file:
        for line_number, raw_line in enumerate(in_file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            fields = line.split(maxsplit=1)
            key = fields[0]
            if key not in valid_args:
                raise ValueError(f"Line {line_number}: {key} is not a valid argument")

            value = fields[1].strip() if len(fields) == 2 else ""
            if not value or value == "null":
                continue
            # The CLI already accepts Nextflow memory literals with spaces.
            # Forward the same literal from a params file as one argv value.
            if key in MEMORY_PARAMS and not re.fullmatch(
                r"\d+(\.\d+)?\s*\.?\s*[KMGTP]?B", value, flags=re.IGNORECASE
            ):
                raise ValueError(f"Line {line_number}: {key} is not a valid memory size")
            if (
                key not in path_params
                and key not in CONTAINER_PARAMS
                and key not in MEMORY_PARAMS
                and len(value.split()) > 1
            ):
                raise ValueError(f"Line {line_number}: {key} accepts a single value")

            if key in path_params:
                value = os.path.abspath(value)
            elif key in CONTAINER_PARAMS:
                value = container_reference(value)
            parsed[key] = value

    if overrides:
        parsed.update(
            {key: str(value) for key, value in overrides.items() if value is not None}
        )

    nanopore_only = [key for key in NANOPORE_PARAMS if key in parsed]
    if nanopore_only and parsed.get("mode") != "NANOPORE":
        mode = parsed.get("mode", "unset, so ILLUMINA")
        raise ValueError(
            f"{', '.join(nanopore_only)} only apply to mode NANOPORE; "
            f"this file's mode is {mode}"
        )

    args = []
    for key, value in parsed.items():
        option = f"--{key}"
        args.extend([option, value])
    args.append("-resume")
    return args


def update_pangolin(root_path):
    from .container_management import exec_prefix

    containers_dir = Path(root_path) / "vfnext" / "containers"
    subprocess.run(
        exec_prefix(containers_dir, "pangolin:4.4.sif", writable=True)
        + ["pangolin", "--update"],
        cwd=containers_dir,
        check=True,
    )
    from .container_management import record_overlay_update

    record_overlay_update(containers_dir, ["pangolin_4.4.overlay"])


def update_pangolin_data(root_path):
    from .container_management import exec_prefix

    containers_dir = Path(root_path) / "vfnext" / "containers"
    subprocess.run(
        exec_prefix(containers_dir, "pangolin:4.4.sif", writable=True)
        + ["pangolin", "--update-data"],
        cwd=containers_dir,
        check=True,
    )
    from .container_management import record_overlay_update

    record_overlay_update(containers_dir, ["pangolin_4.4.overlay"])


def run_vfnext(root_path, params_fl, mode, cli_params=None, profile=None):
    """
    Run the vfnext pipeline.

    Explicit CLI parameters override file values; CLI defaults do not.
    Without a file or explicit mode, mode defaults to ILLUMINA.
    """
    path_params = [
        "inDir",
        "samplesheet",
        "outDir",
        "referenceGFF",
        "referenceGenome",
        "primersBED",
    ]

    cli_params = dict(cli_params or {})
    for key in path_params:
        if key in cli_params:
            cli_params[key] = os.path.abspath(str(cli_params[key]))
    for key in CONTAINER_PARAMS:
        if key in cli_params:
            cli_params[key] = container_reference(cli_params[key])

    if params_fl:
        overrides = dict(cli_params)
        if mode is not None:
            overrides["mode"] = mode
        args = (
            parse_params(params_fl, overrides=overrides)
            if overrides
            else parse_params(params_fl)
        )
    else:
        # No file provided — use CLI params
        if cli_params:
            args = []
            for key, value in cli_params.items():
                option = f"--{key}"
                args.extend([option, str(value)])
        else:
            raise ValueError(
                "No parameters provided. Use --params-file or individual CLI options."
            )

    if "-resume" not in args:
        args.append("-resume")

    nxtflw_ver = os.environ.get("NXF_VER", NEXTFLOW_VERSION)
    resolved_mode = None if params_fl else (mode or "ILLUMINA")
    run_env = os.environ.copy()
    run_env["NXF_VER"] = nxtflw_ver
    command = ["nextflow", "run", f"{root_path}/vfnext/main.nf"]
    command.extend(args)
    if resolved_mode:
        command.extend(["--mode", resolved_mode])
    if profile:
        command.extend(["-profile", profile])
    if profile in ("apptainer", "singularity"):
        from .container_management import ensure_snpeff_database

        ensure_snpeff_database(root_path, args, resolved_mode)
    print(f"NXF_VER={shlex.quote(nxtflw_ver)} {shlex.join(command)}")
    subprocess.run(command, env=run_env, check=True)


def concat_fastqs(path, prefix, extension, min_len, max_len):
    """
    Concatenate and filter fastq files from barcode directories.

    For each directory matching {prefix}* (e.g. barcode01, barcode02, ...),
    concatenates all fastq files and filters reads by min/max length using seqkit.
    A max_len of None sets no maximum.
    """
    if max_len is not None and max_len < min_len:
        raise ValueError(
            f"--max-len {max_len} is below --min-len {min_len}, so every read "
            "would be dropped."
        )
    read_dir = Path(path).resolve()
    output_dir = read_dir / "filtered"
    output_dir.mkdir(exist_ok=True)

    def matching_directories(parent):
        return sorted(
            entry
            for entry in parent.iterdir()
            if entry.is_dir() and entry.name.startswith(prefix)
        )

    barcode_dirs = matching_directories(read_dir)
    if not barcode_dirs:
        barcode_dirs = sorted(
            barcode
            for parent in read_dir.iterdir()
            if parent.is_dir()
            for barcode in matching_directories(parent)
        )
    if not barcode_dirs:
        raise FileNotFoundError(
            f"No files matching '{prefix}*/*{extension}' found in '{read_dir}' or its subdirectories."
        )

    failures = []
    for barcode_path in barcode_dirs:
        barcode_id = barcode_path.name
        fastq_files = sorted(
            entry
            for entry in barcode_path.iterdir()
            if entry.is_file() and entry.name.endswith(extension)
        )
        if not fastq_files:
            print(f"Skipping {barcode_id}: no {extension} files found")
            continue

        output_file = output_dir / f"{barcode_id}.concat.fastq.gz"
        temporary_path = None
        print(f"Processing {barcode_id}...")
        processes = []
        try:
            with tempfile.NamedTemporaryFile(
                dir=output_dir, prefix=f".{barcode_id}.", suffix=".tmp", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                reader = (
                    ["gzip", "-cd", "--", *map(str, fastq_files)]
                    if extension.endswith(".gz")
                    else ["cat", "--", *map(str, fastq_files)]
                )
                source = subprocess.Popen(reader, stdout=subprocess.PIPE)
                processes.append(source)
                seqkit_command = [
                    "seqkit",
                    "seq",
                    "-w",
                    "0",
                    "-g",
                    "--min-len",
                    str(min_len),
                ]
                if max_len is not None:
                    seqkit_command += ["--max-len", str(max_len)]
                seqkit = subprocess.Popen(
                    seqkit_command,
                    stdin=source.stdout,
                    stdout=subprocess.PIPE,
                )
                processes.append(seqkit)
                source.stdout.close()
                compressor = subprocess.Popen(
                    ["gzip", "-c"], stdin=seqkit.stdout, stdout=temporary
                )
                processes.append(compressor)
                seqkit.stdout.close()
                compressor_status = compressor.wait()
                seqkit_status = seqkit.wait()
                source_status = source.wait()
            statuses = {
                "reader": source_status,
                "seqkit": seqkit_status,
                "gzip": compressor_status,
            }
            failed_stages = [name for name, status in statuses.items() if status != 0]
            if failed_stages:
                raise RuntimeError(
                    f"failed pipeline stages: {', '.join(failed_stages)}"
                )
            os.replace(temporary_path, output_file)
            print(f"   The reads were written in {output_file}")
        except (OSError, RuntimeError) as error:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                if process.poll() is None:
                    process.wait()
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            failures.append(f"{barcode_id}: {error}")

    if failures:
        raise RuntimeError("FASTQ concatenation failed:\n - " + "\n - ".join(failures))
