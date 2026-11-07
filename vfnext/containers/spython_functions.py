import os
import subprocess


def get_repository(repository_list):
    containers_name_list = []
    with open(repository_list, "r") as containers:
        for line_number, container in enumerate(containers, start=1):
            container = container.strip()
            if not container:
                continue
            # Keep the complete ORAS URI, but preserve the local image:tag.sif name.
            parts = container.removeprefix("oras://").split("/")
            if (not container.startswith("oras://") or len(parts) < 3
                    or not all(parts) or ":" not in parts[-1]
                    or any(char.isspace() for char in container)):
                raise ValueError(
                    f"{repository_list}:{line_number}: expected "
                    "oras://registry/namespace/image:tag"
                )
            container_version = parts[-1]
            if not all(container_version.split(":", 1)):
                raise ValueError(f"{repository_list}:{line_number}: missing image name or tag")
            containers_name_list.append((parts[-2], container_version, container))
    return containers_name_list


def container_pull(containers_dir, containers_name_list):
    for container in containers_name_list:
        container_version = container[1]
        full_repo = container[2]
        print(f"Downloading container {container_version} from {full_repo}. Please wait ...", flush=True)
        subprocess.check_call([
            "singularity", "pull", "-F", f"{container_version}.sif", full_repo
        ], cwd=containers_dir)



def check_containers(containers_name_list, downloaded_list):
    download_list = os.scandir(downloaded_list)
    container_download_list = [container.name for container in download_list]
    missing_containers = []
    for cont in containers_name_list:
        # cont is (project, container_version, full_repo)
        expected_file = f"{cont[1]}.sif"
        if expected_file not in container_download_list:
            missing_containers.append(cont)
    return missing_containers


def containers_routine_pull(missing_containers_list, containers_dir, containers_names_list):
    lost_containers = missing_containers_list
    attempts = len(lost_containers) * 3
    while len(lost_containers) > 0 and attempts > 0:
        container_pull(containers_dir, lost_containers)
        lost_containers = check_containers(containers_names_list, containers_dir)
        attempts -= 1
        if len(lost_containers) == 0:
            break
    if lost_containers:
        raise RuntimeError("Required containers are missing after download.")

