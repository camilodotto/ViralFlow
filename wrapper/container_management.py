"""Installation infrastructure; tool recipes and analysis defaults are unchanged."""

import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

CLAIR3_IMAGE = "docker://hkubal/clair3:v1.2.0"
OVERLAYS = {
    "pangolin:4.4.sif": "pangolin_4.4.overlay",
    "snpeff:5.0.sif": "snpeff_5.0.overlay",
}


def runtime():
    requested = os.environ.get("VIRALFLOW_CONTAINER_RUNTIME")
    candidates = [requested] if requested else ["apptainer", "singularity"]
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    raise RuntimeError("Install Apptainer (or Singularity) before preparing containers")


def exec_prefix(directory, image, writable=False):
    directory = Path(directory)
    prefix = [runtime(), "exec"]
    overlay = directory / OVERLAYS.get(image, "__no_overlay__")
    if overlay.is_file():
        prefix += [
            "--fakeroot",
            "--overlay",
            str(overlay) + ("" if writable else ":ro"),
        ]
    elif writable and (directory / image).is_dir():
        prefix += ["--fakeroot", "--writable"]
    elif writable:
        raise RuntimeError(
            f"Missing writable overlay for {image}; run build-containers"
        )
    return prefix + [str(directory / image)]


def _fingerprint(path):
    stat = path.stat()
    return [stat.st_size, stat.st_mtime_ns]


def _write_receipt(directory, receipt):
    """Publish readiness atomically so interruption cannot leave partial JSON."""
    with tempfile.NamedTemporaryFile(
        mode="w", dir=directory, prefix=".prepared-", delete=False
    ) as output:
        temporary = Path(output.name)
        json.dump(receipt, output, indent=2)
    try:
        os.replace(temporary, Path(directory) / ".prepared-containers.json")
    finally:
        temporary.unlink(missing_ok=True)


def record_overlay_update(directory, names):
    """Refresh fingerprints after a successful, explicit management command."""
    receipt_path = Path(directory) / ".prepared-containers.json"
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        for artifacts in receipt.get("modes", {}).values():
            for name in names:
                if name in artifacts and (Path(directory) / name).is_file():
                    artifacts[name] = _fingerprint(Path(directory) / name)
        _write_receipt(directory, receipt)


def ensure_snpeff_database(root_path, args, mode):
    directory = Path(root_path) / "vfnext" / "containers"
    if not (directory / "snpeff_5.0.overlay").is_file():
        return  # Preserve legacy installations and non-GUI use.
    options = {
        args[i][2:]: args[i + 1]
        for i in range(len(args) - 1)
        if args[i].startswith("--")
    }
    if (
        options.get("mode", mode or "ILLUMINA") != "ILLUMINA"
        or options.get("runSnpEff", "True").lower() == "false"
    ):
        return
    code = (
        "NC_045512.2"
        if options.get("virus", "sars-cov2") == "sars-cov2"
        else options.get("refGenomeCode")
    )
    if not code:
        raise ValueError("Set refGenomeCode before preparing the snpEff database")
    check = 'p=$(dirname "$(readlink -f "$(command -v snpEff)")"); test -f "$p/data/$1/snpEffectPredictor.bin"'
    result = subprocess.run(
        exec_prefix(directory, "snpeff:5.0.sif") + ["bash", "-c", check, "bash", code]
    )
    if result.returncode:
        subprocess.run(
            exec_prefix(directory, "snpeff:5.0.sif", writable=True)
            + ["snpEff", "download", code],
            check=True,
        )
        record_overlay_update(directory, ["snpeff_5.0.overlay"])


def container_status(root_path):
    """Only report images successfully smoke-tested on this machine as ready."""
    directory = Path(root_path) / "vfnext" / "containers"
    try:
        receipt = json.loads((directory / ".prepared-containers.json").read_text())
        engine = runtime()
        engine_version = subprocess.run(
            [engine, "--version"], check=True, capture_output=True, text=True
        ).stdout.strip()
        valid = (
            isinstance(receipt, dict)
            and receipt.get("architecture") == platform.machine()
            and receipt.get("runtime") == engine_version
        )
    except (
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        RuntimeError,
        subprocess.CalledProcessError,
    ):
        receipt, valid = {}, False
    if not isinstance(receipt, dict) or not isinstance(receipt.get("modes", {}), dict):
        receipt, valid = {}, False
    modes = {}
    for mode in ("ILLUMINA", "NANOPORE"):
        artifacts = receipt.get("modes", {}).get(mode, {})
        if not isinstance(artifacts, dict):
            artifacts = {}
        missing = [
            name
            for name, stamp in artifacts.items()
            if not (directory / name).is_file()
            or _fingerprint(directory / name) != stamp
        ]
        modes[mode] = {
            "ready": bool(valid and artifacts and not missing),
            "missingOrChanged": missing,
        }
    return {"schemaVersion": 1, "architecture": platform.machine(), "modes": modes}


def prepare_containers(root_path, arch, clean=False, staging_dir=None):
    directory = Path(root_path) / "vfnext" / "containers"
    engine = runtime()
    # Images may live on a shared macOS mount, but builds/overlays must be made
    # on the Linux VM filesystem. Never clear a caller-supplied staging root.
    staging = Path(staging_dir or "/var/tmp")
    if str(staging.resolve()).startswith(("/Users/", "/mnt/", "/media/")):
        raise ValueError(
            "Use a local Linux filesystem for --staging-dir (for example /var/tmp)"
        )
    staging.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="viralflow-build-", dir=staging
    ) as temporary:
        work = Path(temporary)
        env = dict(os.environ, VIRALFLOW_CONTAINER_RUNTIME=engine)
        for name in ("APPTAINER", "SINGULARITY"):
            env[f"{name}_TMPDIR"] = str(work)
            env[f"{name}_CACHEDIR"] = str(work / "cache")
        repositories = directory / "repositories" / f"repositories_{arch}.txt"
        images = []
        for source in repositories.read_text().splitlines():
            if source.strip():
                images.append(
                    (
                        source.strip().split("/")[-1] + ".sif",
                        "library://" + source.strip(),
                    )
                )
        recipes = {
            "pangolin:4.4.sif": directory / "def_files" / arch / "Singularity_pangolin",
            "snpeff:5.0.sif": directory / "def_files" / arch / "Singularity_snpEff",
            "baseContainer.sif": directory / "Nanopore_baseContainer.sing",
        }
        # --clean is recoverable: retain existing images AND mutable overlays.
        managed = (
            [name for name, _ in images]
            + list(recipes)
            + ["clair3_v1.2.0.sif"]
            + list(OVERLAYS.values())
        )
        if clean:
            backup = directory / ("backup-" + str(time.time_ns()))
            backup.mkdir()
            for name in managed + [".prepared-containers.json", "snpEff_DB.catalog"]:
                if (directory / name).exists():
                    shutil.move(str(directory / name), backup / name)
            print(f"Previous containers and overlays preserved in {backup}")

        def execute(args, **kwargs):
            subprocess.run(args, cwd=directory, env=env, check=True, **kwargs)

        for name, source in images + [("clair3_v1.2.0.sif", CLAIR3_IMAGE)]:
            target = directory / name
            if not target.is_file():
                if target.exists():
                    # Convert the existing sandbox itself, not a fresh recipe:
                    # this keeps installed databases and user customizations.
                    built = work / name
                    execute([engine, "build", "--fakeroot", str(built), str(target)])
                    backup = directory / ("backup-" + str(time.time_ns()))
                    backup.mkdir()
                    shutil.move(str(target), backup / name)
                    shutil.move(str(built), target)
                    print(f"Legacy sandbox preserved in {backup}")
                    continue
                built = work / name
                options = ["--arch", "amd64"] if name == "clair3_v1.2.0.sif" else []
                execute([engine, "pull", *options, str(built), source])
                shutil.move(str(built), target)
        for name, recipe in recipes.items():
            target = directory / name
            if not target.is_file():
                if target.exists():
                    built = work / name
                    execute([engine, "build", "--fakeroot", str(built), str(target)])
                    backup = directory / ("backup-" + str(time.time_ns()))
                    backup.mkdir()
                    shutil.move(str(target), backup / name)
                    shutil.move(str(built), target)
                    print(f"Legacy sandbox preserved in {backup}")
                    continue
                built = work / name
                execute([engine, "build", "--fakeroot", str(built), str(recipe)])
                shutil.move(str(built), target)
        for name in OVERLAYS.values():
            if not (directory / name).exists():
                overlay = work / name
                execute(
                    [
                        engine,
                        "overlay",
                        "create",
                        "--fakeroot",
                        "--size",
                        "2048",
                        str(overlay),
                    ]
                )
                shutil.move(str(overlay), directory / name)
        dataset = directory / "nextclade_dataset" / "sars-cov-2"
        dataset.mkdir(parents=True, exist_ok=True)
        if not (dataset / "reference.fasta").is_file():
            execute(
                [
                    engine,
                    "exec",
                    "-B",
                    f"{dataset}:/tmp",
                    str(directory / "nextclade:3.18.sif"),
                    "nextclade",
                    "dataset",
                    "get",
                    "--name",
                    "sars-cov-2",
                    "--output-dir",
                    "/tmp",
                ]
            )
        with (work / "snpEff_DB.catalog").open("w") as catalog:
            execute(
                exec_prefix(directory, "snpeff:5.0.sif") + ["snpEff", "databases"],
                stdout=catalog,
            )
        shutil.move(str(work / "snpEff_DB.catalog"), directory / "snpEff_DB.catalog")
        # Clair3 is amd64. On ARM this is also the emulation check: never
        # claim NANOPORE ready merely because an amd64 image was downloaded.
        probes = {
            "ILLUMINA": [
                ("pangolin:4.4.sif", ["pangolin", "--version"]),
                ("snpeff:5.0.sif", ["snpEff", "-version"]),
            ],
            "NANOPORE": [
                ("baseContainer.sif", ["samtools", "--version"]),
                # An actual ELF executable, not just a version-reporting
                # shell script: ARM must be able to execute amd64 binaries.
                ("clair3_v1.2.0.sif", ["/bin/uname", "-m"]),
                ("clair3_v1.2.0.sif", ["/opt/bin/run_clair3.sh", "--version"]),
            ],
        }
        receipt = {
            "architecture": platform.machine(),
            "runtime": subprocess.run(
                [engine, "--version"], check=True, capture_output=True, text=True
            ).stdout.strip(),
            "modes": {},
        }
        failures = []
        for mode, commands in probes.items():
            try:
                if mode == "ILLUMINA":
                    for name, _ in images:
                        execute([engine, "inspect", str(directory / name)])
                for image, command in commands:
                    execute(exec_prefix(directory, image) + command)
                names = (
                    (
                        [name for name, _ in images]
                        + list(OVERLAYS.values())
                        + ["pangolin:4.4.sif", "snpeff:5.0.sif", "snpEff_DB.catalog"]
                    )
                    if mode == "ILLUMINA"
                    else ["baseContainer.sif", "clair3_v1.2.0.sif"]
                )
                if mode == "ILLUMINA":
                    names += [
                        str(path.relative_to(directory))
                        for path in dataset.rglob("*")
                        if path.is_file()
                    ]
                receipt["modes"][mode] = {
                    name: _fingerprint(directory / name) for name in names
                }
            except subprocess.CalledProcessError:
                failures.append(mode)
        _write_receipt(directory, receipt)
        if failures:
            raise RuntimeError(
                f"Container execution checks failed for {', '.join(failures)}. On ARM, Clair3 v1.2.0 requires working amd64 emulation."
            )
