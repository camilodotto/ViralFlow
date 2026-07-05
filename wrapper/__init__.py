from distutils.command.build_scripts import first_line_re
from logging import root
import os
import shlex
import json
import re
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path


def _get_container_runtime():
    if shutil.which("apptainer"):
        return "apptainer"
    raise RuntimeError("apptainer executable not found.")


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


_PANGOLIN_REPO_API = "https://api.github.com/repos/cov-lineages/pangolin"
_STABLE_TAG_PATTERN = re.compile(r"^v(\d+)\.(\d+)(?:\.(\d+))?$")


def _github_json(url: str):
    request = Request(url, headers={"Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def _stable_tag_sort_key(tag: str):
    match = _STABLE_TAG_PATTERN.fullmatch(tag)
    if not match:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def _get_latest_stable_pangolin_tag():
    try:
        latest_release = _github_json(f"{_PANGOLIN_REPO_API}/releases/latest")
        release_tag = latest_release.get("tag_name", "")
        if _stable_tag_sort_key(release_tag) is not None:
            return release_tag
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        pass

    tags = []
    page = 1
    try:
        while True:
            page_tags = _github_json(f"{_PANGOLIN_REPO_API}/tags?per_page=100&page={page}")
            if not page_tags:
                break
            tags.extend(page_tags)
            page += 1
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Unable to determine the latest stable Pangolin version from GitHub."
        ) from exc

    stable_tags = [
        tag["name"]
        for tag in tags
        if isinstance(tag, dict) and _stable_tag_sort_key(tag.get("name", "")) is not None
    ]
    if not stable_tags:
        raise RuntimeError("No stable Pangolin tags were found on GitHub.")

    return max(stable_tags, key=_stable_tag_sort_key)


def add_entries_to_DB(root_path, org_name, refseq_code, arch):
    """
    add entries provided to snpeff database
    """
    run_bash = ["bash", f"{root_path}/vfnext/containers/add_entries_SnpeffDB.sh", org_name, refseq_code, arch]
    print(" ".join(run_bash))
    subprocess.check_call(run_bash)


def _snpeff_paths(root_path):
    containers_dir = Path(root_path) / "vfnext" / "containers"
    return {
        "containers_dir": containers_dir,
        "container": containers_dir / "snpeff:5.0.sif",
        "overlay": containers_dir / "snpeff_5.0.overlay",
        "catalog": containers_dir / "snpEff_DB.catalog",
    }


def _snpeff_catalog_entries(catalog_path: Path, genome_code: str):
    if not catalog_path.exists():
        return []

    entries = []
    for line in catalog_path.read_text(encoding="utf-8").splitlines():
        fields = line.replace(" ", "").split("\t")
        if len(fields) < 5:
            continue
        if genome_code in fields[0]:
            entries.append(fields)
    return entries


def _snpeff_db_is_installed(root_path, genome_code: str):
    runtime = _get_container_runtime()
    paths = _snpeff_paths(root_path)

    if not paths["container"].exists():
        raise RuntimeError(f"snpEff container not found: {paths['container']}")
    if not paths["overlay"].exists():
        raise RuntimeError(f"snpEff overlay not found: {paths['overlay']}")

    check_script = """
for d in \
    /opt/conda/share/snpeff-5.0-3/data \
    /opt/conda/share/snpeff-5.0-2/data \
    /opt/conda/share/snpeff/data \
    /usr/local/bin/mm/share/snpeff-5.0-3/data \
    /usr/local/bin/mm/share/snpeff-5.0-2/data \
    /usr/local/bin/mm/share/snpeff/data
do
    if [ -d "$d/$1" ]; then
        exit 0
    fi
done
exit 1
"""
    result = subprocess.run(
        [
            runtime,
            "exec",
            "--overlay",
            f"{paths['overlay']}:ro",
            str(paths["container"]),
            "sh",
            "-c",
            check_script,
            "sh",
            genome_code,
        ],
        cwd=str(paths["containers_dir"]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _bool_param(value):
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _snpeff_genome_code_from_params(params):
    if not _bool_param(params.get("runSnpEff", "false")):
        return None

    if params.get("virus") == "sars-cov2":
        return "NC_045512.2"

    return params.get("refGenomeCode")


def ensure_snpeff_db_for_run(root_path, params, arch: str = "amd64"):
    genome_code = _snpeff_genome_code_from_params(params)
    if not genome_code:
        return

    paths = _snpeff_paths(root_path)
    catalog_entries = _snpeff_catalog_entries(paths["catalog"], genome_code)
    installed = _snpeff_db_is_installed(root_path, genome_code)

    if catalog_entries and installed:
        return

    if catalog_entries:
        organism_name = catalog_entries[0][1] or genome_code
        print(
            f"snpEff genome {genome_code} is cataloged but not installed; "
            "preparing database in the writable overlay."
        )
    else:
        organism_name = genome_code
        print(
            f"snpEff genome {genome_code} was not found in the local catalog; "
            "adding it to the writable overlay before running ViralFlow."
        )

    add_entries_to_DB(root_path, organism_name, genome_code, arch)


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

def build_containers(root_path, arch: str, clean: bool = False, staging_dir=None):
    """
    run script to build container for vfnext
    """
    if clean:
        clean_containers(root_path, arch)

    containers_dir = Path(root_path) / "vfnext" / "containers"
    build_sandbox = [sys.executable, "./build_containers.py", arch]
    if clean:
        build_sandbox.append("--clean")
    if staging_dir:
        build_sandbox.extend(["--staging-dir", staging_dir])
    pull_containers = [sys.executable, "./pull_containers.py", arch]
    subprocess.check_call(pull_containers, cwd=str(containers_dir))
    print(" ".join(shlex.quote(arg) for arg in build_sandbox))
    subprocess.check_call(build_sandbox, cwd=str(containers_dir))
    

# input args file load
def load_params(in_flpath):
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
    return dct


def parse_params(in_flpath):
    dct = load_params(in_flpath)

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
    pangolin_tag = _get_latest_stable_pangolin_tag()
    print(f"Using latest stable Pangolin tag: {pangolin_tag}")

    for dependency in [
        f"git+https://github.com/cov-lineages/pangolin.git@{pangolin_tag}",
        "git+https://github.com/cov-lineages/pangolin-data.git",
        "git+https://github.com/cov-lineages/scorpio.git",
        "git+https://github.com/cov-lineages/constellations.git",
    ]:
        _run(
            exec_prefix
            + [
                "/usr/local/bin/mm/bin/python",
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--no-build-isolation",
                dependency,
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

def run_vfnext(root_path, params_fl, arch: str = "amd64"):
    # get nextflow arguments
    params = load_params(params_fl)
    ensure_snpeff_db_for_run(root_path, params, arch)
    args_str = parse_params(params_fl)
    nxtflw_ver = os.environ.get("NXF_VER", "22.04.0")
    run_nxtfl_cmd = f"NXF_VER={nxtflw_ver} nextflow run {root_path}/vfnext/main.nf {args_str}"
    print(run_nxtfl_cmd)
    os.system(run_nxtfl_cmd)
