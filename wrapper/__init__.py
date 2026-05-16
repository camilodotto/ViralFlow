from distutils.command.build_scripts import first_line_re
from logging import root
import os
import shutil
import subprocess
from pathlib import Path


def _get_container_runtime():
    for runtime in ("apptainer", "singularity"):
        if shutil.which(runtime):
            return runtime
    raise RuntimeError("apptainer/singularity executable not found.")


def _run(command, cwd=None):
    subprocess.check_call(command, cwd=str(cwd) if cwd else None)


def _ensure_overlay(runtime, overlay_path: Path, size_mb: int = 2048):
    if overlay_path.exists():
        return

    _run(
        [runtime, "overlay", "create", "--fakeroot", "--size", str(size_mb), str(overlay_path)],
        cwd=overlay_path.parent,
    )


def _overlay_path(containers_dir: Path, image_name: str) -> Path:
    safe_name = image_name.replace(":", "_")
    return containers_dir / f"{safe_name}.overlay"


def _pangolin_exec_prefix(runtime: str, overlay_path: Path, container_path: Path):
    return [
        runtime,
        "exec",
        "--fakeroot",
        "--overlay",
        str(overlay_path),
        str(container_path),
    ]


def add_entries_to_DB(root_path, org_name, refseq_code, arch):
    """
    add entries provided to snpeff database
    """
    run_bash = ["bash", f"{root_path}/vfnext/containers/add_entries_SnpeffDB.sh", org_name, refseq_code, arch]
    print(" ".join(run_bash))
    subprocess.check_call(run_bash)


def _container_names_from_repository_file(repository_file: Path):
    if not repository_file.exists():
        return []

    names = []
    for line in repository_file.read_text(encoding="utf-8").splitlines():
        container = line.strip()
        if not container:
            continue
        parts = container.split("/")
        if len(parts) >= 3:
            names.append(f"{parts[2]}.sif")
    return names


def _remove_path(path: Path):
    if path.is_dir():
        shutil.rmtree(path)
        print(f"Removed directory: {path}")
    elif path.exists():
        path.unlink()
        print(f"Removed file: {path}")


def clean_containers(root_path, arch: str):
    containers_dir = Path(root_path) / "vfnext" / "containers"
    repositories = {
        "arm64": "repositories_arm64.txt",
        "amd64": "repositories_amd64.txt",
    }
    repository_file = containers_dir / "repositories" / repositories.get(arch, "repositories_amd64.txt")

    names = set(_container_names_from_repository_file(repository_file))
    patterns = [
        "pangolin:*.sif",
        "pangolin_*.overlay",
        "snpeff:*.sif",
        "snpeff_*.overlay",
        "snpEff_DB.catalog",
    ]

    print("Cleaning generated ViralFlow container artifacts...")
    removed = 0

    for name in sorted(names):
        path = containers_dir / name
        if path.exists():
            _remove_path(path)
            removed += 1

    for pattern in patterns:
        for path in sorted(containers_dir.glob(pattern)):
            if path.exists():
                _remove_path(path)
                removed += 1

    if removed == 0:
        print("No generated container artifacts found to remove.")

def parse_csv(csv_flpath):
    with open(csv_flpath, "r") as csv_fl:
        first_line = True
        entries_lst = []
        for line in csv_fl:
            # skip header
            if first_line == True:
                first_line = False
                continue
            ln_data = line.split(",")
            entry = [ln_data[0], ln_data[1].replace("\n","")]
            entries_lst.append(entry)
    return entries_lst

def build_containers(root_path, arch: str, clean: bool = False):
    """
    run script to build container for vfnext
    """
    if clean:
        clean_containers(root_path, arch)

    # build containers
    cd_to_dir= f"cd {root_path}/vfnext/containers/" 
    build_sandbox = f"python ./build_containers.py {arch}"
    if clean:
        build_sandbox += " --clean"
    pull_containers = f"python ./pull_containers.py {arch}"
    os.system(cd_to_dir+';'+pull_containers) 
    print(cd_to_dir+';'+build_sandbox)
    os.system(cd_to_dir+';'+build_sandbox)
    

# input args file load
def parse_params(in_flpath):
    """
    load text file containing viralflow arguments
    """
    valid_args = [
        "virus",
        "primersBED",
        "outDir",
        "inDir",
        "runSnpEff",
        "writeMappedReads",
        "minLen",
        "depth",
        "minDpIntrahost",
        "trimLen",
        "runSnpEff",
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
        "ndedup"
    ]
    path_params = ["inDir", "outDir", "referenceGFF", "referenceGenome", "primersBED"]
    in_file = open(in_flpath, "r")
    dct = {}
    for l in in_file:
        # skip lines
        if (l in ["", " ", "\n"]) or l.startswith("#"):
            continue

        # get line data
        l_dt = l.replace("\n", "").split(" ")
        
        # get content
        key = l_dt[0]
        if (key not in valid_args):
            raise Exception(f"ERROR: {key} not a valid argument")
        # fill dict
        if key in valid_args:
        
            vls_1 = l_dt[1 : len(l_dt)]
            vls = []
        
            for v in vls_1:
                if v in [""]:
                    continue
                vls.append(v)
            # if single value
            if len(vls) == 1:
                # skip null values
                if vls[0] == "null":
                    continue
                # be sure paths are absolute
                if key in path_params:
                    dct[key] = os.path.abspath(vls[0])
                    continue
                dct[key] = vls[0]
            # if a list of values
            if len(vls) > 1:
                dct[key] = vls
            continue
    # get arguments for nextflow
    
    args_str = ""
    for key in dct:
        args_str += f"--{key} {dct[key]} "
    args_str += "-resume"
    return args_str

def update_pangolin(root_path):
    runtime = _get_container_runtime()
    containers_dir = Path(root_path) / "vfnext" / "containers"
    container_path = containers_dir / "pangolin:4.4.sif"
    overlay_path = _overlay_path(containers_dir, "pangolin:4.4")

    _ensure_overlay(runtime, overlay_path)
    exec_prefix = _pangolin_exec_prefix(runtime, overlay_path, container_path)

    # Pangolin major/minor upgrades can require environment changes that
    # `pangolin --update` does not apply by itself.
    _run(
        exec_prefix
        + [
            "env",
            "MAMBA_ROOT_PREFIX=/usr/local/bin/mm",
            "/usr/local/bin/micromamba",
            "install",
            "-y",
            "--prefix",
            "/usr/local/bin/mm",
            "-c",
            "bioconda",
            "-c",
            "conda-forge",
            "snakemake>=8",
        ],
        cwd=containers_dir,
    )
    _run(
        exec_prefix
        + [
            "/usr/local/bin/mm/bin/python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "setuptools<81",
            "wheel",
        ],
        cwd=containers_dir,
    )

    dependencies = [
        "git+https://github.com/cov-lineages/pangolin.git",
        "git+https://github.com/cov-lineages/pangolin-data.git",
        "git+https://github.com/cov-lineages/scorpio.git",
        "git+https://github.com/cov-lineages/constellations.git",
    ]
    _run(
        exec_prefix
        + [
            "/usr/local/bin/mm/bin/python",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--no-build-isolation",
            *dependencies,
        ],
        cwd=containers_dir,
    )
    try:
        _run(
            exec_prefix
            + [
                "/usr/local/bin/mm/bin/python",
                "-m",
                "pip",
                "check",
            ],
            cwd=containers_dir,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Pangolin update finished with incompatible Python dependencies. "
            "The environment was not left in a reliable state; please rerun the "
            "update after checking for upstream package compatibility changes."
        ) from exc

def update_pangolin_data(root_path):
    runtime = _get_container_runtime()
    containers_dir = Path(root_path) / "vfnext" / "containers"
    container_path = containers_dir / "pangolin:4.4.sif"
    overlay_path = _overlay_path(containers_dir, "pangolin:4.4")

    _ensure_overlay(runtime, overlay_path)
    _run(
        _pangolin_exec_prefix(runtime, overlay_path, container_path)
        + [
            "pangolin",
            "--update-data",
        ],
        cwd=containers_dir,
    )

def run_vfnext(root_path, params_fl):
    # get nextflow arguments
    args_str = parse_params(params_fl)
    nxtflw_ver="22.04.0"
    run_nxtfl_cmd = f"NXF_VER={nxtflw_ver} nextflow run {root_path}/vfnext/main.nf {args_str}"
    print(run_nxtfl_cmd)
    os.system(run_nxtfl_cmd)
