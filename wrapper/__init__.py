from distutils.command.build_scripts import first_line_re
from logging import root
import json
import os
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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

def _remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
        print(f"Removed directory: {path}")
        return True
    if os.path.exists(path):
        os.remove(path)
        print(f"Removed file: {path}")
        return True
    return False

def clean_containers(root_path):
    """
    remove locally generated sandbox containers and build artifacts
    """
    containers_dir = os.path.join(root_path, "vfnext", "containers")
    artifacts = [
        "pangolin:4.4.sif",
        "snpeff:5.0.sif",
        "snpEff_DB.catalog",
    ]

    print("Cleaning generated ViralFlow container artifacts...")
    removed = 0
    for artifact in artifacts:
        if _remove_path(os.path.join(containers_dir, artifact)):
            removed += 1

    if removed == 0:
        print("No generated container artifacts found to remove.")

def build_containers(root_path, arch: str, clean: bool = False):
    """
    run script to build container for vfnext
    """
    if clean:
        clean_containers(root_path)

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
    containers_dir = f"{root_path}/vfnext/containers/"
    container = "./pangolin:4.4.sif"

    # Pangolin major/minor upgrades can require environment changes that
    # `pangolin --update` does not apply by itself.
    subprocess.check_call(
        [
            "singularity",
            "exec",
            "--writable",
            container,
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
    subprocess.check_call(
        [
            "singularity",
            "exec",
            "--writable",
            container,
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
        subprocess.check_call(
            [
                "singularity",
                "exec",
                "--writable",
                container,
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
        subprocess.check_call(
            [
                "singularity",
                "exec",
                "--writable",
                container,
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
    containers_dir = f"{root_path}/vfnext/containers/"
    run_update_data = ["singularity", "exec", "--writable", "./pangolin:4.4.sif", "pangolin", "--update-data"]
    subprocess.check_call(run_update_data, cwd=containers_dir)

def run_vfnext(root_path, params_fl):
    # get nextflow arguments
    args_str = parse_params(params_fl)
    nxtflw_ver="22.04.0"
    run_nxtfl_cmd = f"NXF_VER={nxtflw_ver} nextflow run {root_path}/vfnext/main.nf {args_str}"
    print(run_nxtfl_cmd)
    os.system(run_nxtfl_cmd)
