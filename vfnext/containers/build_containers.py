#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def path_exists_as_container(p: Path) -> bool:
    # Pode ser sandbox (diretório) ou sif (arquivo)
    return p.is_dir() or p.is_file()


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def copy_container(src: Path, dst: Path) -> None:
    """
    Copia container sandbox (dir) ou sif (file) do workdir interno da VM
    para o diretório do repo (que pode estar em /Users/... montado do macOS).
    """
    if dst.exists():
        # mantém comportamento original (não sobrescreve)
        return

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)


def run(cmd: List[str], *, cwd: Path, env: Dict[str, str]) -> None:
    subprocess.check_call(cmd, cwd=str(cwd), env=env)


def main() -> int:
    if len(sys.argv) < 2:
        eprint("Usage: build_containers.py <arch>\nExample: build_containers.py arm64")
        return 2

    arch = sys.argv[1].strip()

    containers_dir = Path(__file__).resolve().parent  # .../vfnext/containers (pode ser /Users/... no Lima)
    vm_home = Path.home().resolve()                  # HOME real da VM (ex.: /home/usuario)

    # Base interna (no Linux real da VM)
    base = vm_home / ".viralflow" / "apptainer"
    tmpdir = base / "tmp"
    cachedir = base / "cache"
    workdir = base / "work" / f"build_{arch}"

    ensure_dir(tmpdir)
    ensure_dir(cachedir)
    ensure_dir(workdir)

    # Força tmp/cache para dentro do HOME real da VM
    # (Apptainer usa /tmp por default, mas TMPDIR e APPTAINER_TMPDIR sobrescrevem isso)
    env = os.environ.copy()
    env.update({
        "TMPDIR": str(tmpdir),
        "APPTAINER_TMPDIR": str(tmpdir),
        "APPTAINER_CACHEDIR": str(cachedir),
        # compat (caso exista alguma chamada antiga)
        "SINGULARITY_TMPDIR": str(tmpdir),
        "SINGULARITY_CACHEDIR": str(cachedir),
    })

    # Containers que o script já construía
    specs: List[Tuple[str, str]] = [
        ("pangolin:4.3.sif", f"def_files/{arch}/Singularity_pangolin"),
        ("snpeff:5.0.sif",   f"def_files/{arch}/Singularity_snpEff"),
    ]

    failed: List[Tuple[str, str]] = []
    already_built: List[str] = []

    print("Building containers:")
    for image_name, def_rel in specs:
        dst = containers_dir / image_name
        src = workdir / image_name  # build sempre no Linux local, depois copia para o repo

        def_path = (containers_dir / def_rel).resolve()
        if not def_path.exists():
            msg = f"Definition file not found: {def_path}"
            eprint(msg)
            failed.append((image_name, msg))
            continue

        print(f"@ Building {image_name}...")

        if path_exists_as_container(dst):
            print(" > Container already exists.")
            print("If you desire to rebuild it, delete it first and rerun build-containers.")
            already_built.append(image_name)
            continue

        # Apptainer build (mantendo sandbox como no script original)
        # Obs: build ocorre em workdir (Linux real), evitando build-temp-* no /Users/...
        cmd = [
            "apptainer", "build",
            "-F",
            "--fakeroot",
            "--sandbox",
            str(src),
            str(def_path),
        ]

        try:
            run(cmd, cwd=workdir, env=env)
            # Copia o resultado para o repo montado
            copy_container(src, dst)
            print(" > Done <")
        except subprocess.CalledProcessError as e:
            print(" > Failed <")
            failed.append((image_name, " ".join(cmd)))
            eprint(f"Error: {e}")

    print("\nSummary:")
    success = (len(failed) == 0)

    if failed:
        print("\nSome containers failed to build.")
        print("Try to build again. Details:")
        for image, cmd in failed:
            print(f"\nContainer {image} failed.")
            print(f"Command: {cmd}")

    if success:
        print("\nAll containers were successfully built.")
    else:
        print("\nSome containers failed to build. Please check messages above.")
        return 1

    # --- Additional steps (mantém lógica do original, só trocando singularity -> apptainer) ---
    print("\nExecuting additional steps:\n")

    # 1) nextclade dataset (se o container existir)
    nextclade_img = containers_dir / "nextclade:3.18.sif"
    if path_exists_as_container(nextclade_img):
        print(" > Loading sars-cov2 nextclade dataset...\n")
        nextclade_command = [
            "apptainer", "exec",
            "-B", str((containers_dir / "nextclade_dataset/sars-cov-2").resolve()) + ":/tmp",
            str(nextclade_img),
            "nextclade", "dataset", "get",
            "--name", "sars-cov-2",
            "--output-dir", "/tmp",
        ]
        try:
            run(nextclade_command, cwd=containers_dir, env=env)
            print(" > Done <\n")
        except subprocess.CalledProcessError as e:
            print(" > Failed <")
            eprint(f"Error: {e}")
            return 1
    else:
        print(" > Skipping nextclade dataset: nextclade:3.18.sif not found.\n")

    # 2) snpEff catalog
    snpeff_img = containers_dir / "snpeff:5.0.sif"
    if path_exists_as_container(snpeff_img):
        print(" > Downloading snpeff database catalog...")
        snpeff_command = [
            "apptainer", "exec",
            str(snpeff_img),
            "snpEff", "databases",
        ]
        try:
            # captura saída para arquivo como no original
            result = subprocess.check_output(snpeff_command, cwd=str(containers_dir), env=env, text=True)
            (containers_dir / "snpEff_DB.catalog").write_text(result, encoding="utf-8")
            print(" > Done <")
        except subprocess.CalledProcessError as e:
            print(" > Failed <")
            eprint(f"Error: {e}")
            return 1
    else:
        print(" > Skipping snpEff catalog: snpeff:5.0.sif not found.\n")

    # 3) unsquashfs check (mantém aviso do original)
    unsquashfs_desired_location = "/usr/local/bin/unsquashfs"
    if not os.path.exists(unsquashfs_desired_location):
        print("\n\033[91mError:\n > unsquashfs executable not found at expected location.")
        print("You should create a symbolic link using one of the following commands:\033[0m")
        unsquashfs_location = os.path.join(os.environ.get("HOME", str(vm_home)), "miniconda3/envs/viralflow/bin/unsquashfs")
        print(f" > sudo ln -s {unsquashfs_location} /usr/local/bin/unsquashfs\n")
        print(" > If that does not solve it, try:")
        print(" > sudo ln -s /usr/bin/unsquashfs /usr/local/bin/unsquashfs\n")
        print(f" > unsquashfs expected at {unsquashfs_desired_location}\n")
        print(" > After creating the link, rerun 'viralflow -build_containers' to finish setup.")
        return 1

    print("\nAll steps from '-build_containers' completed successfully.")
    print("You can test ViralFlow using the following command:")
    print(" > viralflow -run --params_file test_files/sars-cov-2.params")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
