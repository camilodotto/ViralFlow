#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def cleanup_dir(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)


def remove_path(p: Path) -> bool:
    if p.is_dir():
        shutil.rmtree(p)
        print(f"Removed directory: {p}")
        return True
    if p.exists():
        p.unlink()
        print(f"Removed file: {p}")
        return True
    return False


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


def ensure_overlay(overlay_path: Path, *, cwd: Path, env: Dict[str, str], size_mb: int = 2048) -> None:
    if overlay_path.exists():
        return

    run(
        [
            "apptainer", "overlay", "create",
            "--fakeroot",
            "--size", str(size_mb),
            str(overlay_path),
        ],
        cwd=cwd,
        env=env,
    )


def clean_generated_artifacts(containers_dir: Path, specs: List[Tuple[str, str]]) -> None:
    patterns = [
        "pangolin_*.overlay",
        "snpeff_*.overlay",
        "snpEff_DB.catalog",
    ]

    removed = 0
    print("Cleaning generated build-container artifacts:")

    for image_name, _def_rel in specs:
        if remove_path(containers_dir / image_name):
            removed += 1

    for pattern in patterns:
        for path in sorted(containers_dir.glob(pattern)):
            if remove_path(path):
                removed += 1

    if removed == 0:
        print("No generated build-container artifacts found to remove.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build ViralFlow containers that are generated locally."
    )
    parser.add_argument(
        "arch",
        choices=["amd64", "arm64"],
        help="Architecture to build containers",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previously generated containers and overlays before rebuilding",
    )
    parser.add_argument(
        "--mksquashfs-processors",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Number of processors used to create SIF files (default: 1; "
            "avoids crashes in recent bundled mksquashfs versions)"
        ),
    )
    args = parser.parse_args()

    arch = args.arch.strip()
    if args.mksquashfs_processors < 1:
        parser.error("--mksquashfs-processors must be at least 1")

    containers_dir = Path(__file__).resolve().parent  # .../vfnext/containers (pode ser /Users/... no Lima)
    vm_home = Path.home().resolve()                  # usado apenas em fallback legado abaixo

    # Staging sempre em /tmp para evitar builds em mounts compartilhados do macOS,
    # mesmo quando o HOME da VM Lima estiver configurado como /Users/<usuario>.
    base = Path("/tmp") / "viralflow-apptainer"
    tmpdir = base / "tmp"
    cachedir = base / "cache"
    workdir = base / "work" / f"build_{arch}"

    ensure_dir(tmpdir)
    ensure_dir(cachedir)
    ensure_dir(workdir)

    # Força tmp/cache para dentro do staging local da VM.
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
        ("pangolin:4.4.sif", f"def_files/{arch}/Singularity_pangolin"),
        ("snpeff:5.0.sif",   f"def_files/{arch}/Singularity_snpEff"),
    ]

    if args.clean:
        clean_generated_artifacts(containers_dir, specs)

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
            "--mksquashfs-args",
            f"-processors {args.mksquashfs_processors}",
            # "--sandbox",
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

    pangolin_img = containers_dir / "pangolin:4.4.sif"
    pangolin_overlay = containers_dir / "pangolin_4.4.overlay"
    if path_exists_as_container(pangolin_img):
        print("\nPreparing writable pangolin overlay:")
        try:
            ensure_overlay(pangolin_overlay, cwd=containers_dir, env=env)
            print(f" > Ready: {pangolin_overlay.name}")
        except subprocess.CalledProcessError as e:
            print(" > Failed <")
            eprint(f"Error: {e}")
            return 1

    snpeff_img = containers_dir / "snpeff:5.0.sif"
    snpeff_overlay = containers_dir / "snpeff_5.0.overlay"
    if path_exists_as_container(snpeff_img):
        print("\nPreparing writable snpEff overlay:")
        try:
            ensure_overlay(snpeff_overlay, cwd=containers_dir, env=env, size_mb=1024)
            print(f" > Ready: {snpeff_overlay.name}")
        except subprocess.CalledProcessError as e:
            print(" > Failed <")
            eprint(f"Error: {e}")
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
    if path_exists_as_container(snpeff_img):
        print(" > Downloading snpeff database catalog...")
        snpeff_command = [
            "apptainer", "exec",
            "--fakeroot",
            "--overlay", str(snpeff_overlay),
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
        print(" > After creating the link, rerun 'viralflow build-containers' to finish setup.")
        return 1

    cleanup_dir(tmpdir)
    cleanup_dir(workdir)

    print("\nAll steps from 'build-containers' completed successfully.")
    print("You can test ViralFlow using the following command:")
    print(" > viralflow run --params-file test_files/sars-cov-2.params")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
