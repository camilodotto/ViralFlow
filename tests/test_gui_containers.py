import json
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

with patch("importlib.metadata.version", return_value="2.0.0a1"):
    from wrapper.cli import cli
from wrapper import container_management as management


class GuiContainerTests(unittest.TestCase):
    def test_versioned_marker_declares_real_cli_commands_and_runtime_version(self):
        from wrapper import NEXTFLOW_VERSION

        marker = json.loads((Path(__file__).parents[1] / ".viralflow-gui").read_text())
        self.assertEqual(marker["schemaVersion"], 1)
        self.assertEqual(marker["requirements"]["nextflow"], NEXTFLOW_VERSION)
        self.assertEqual(set(marker["modes"]), {"ILLUMINA", "NANOPORE"})
        for command in marker["viralFlowCmdParams"].values():
            self.assertIn(command, cli.commands)

    @staticmethod
    def fake_engine(args, **kwargs):
        if args[1] in ("pull", "build"):
            Path(args[-2]).write_bytes(b"SIF")
        if args[1:3] == ["overlay", "create"]:
            Path(args[-1]).write_bytes(b"overlay")
        return subprocess.CompletedProcess(args, 0, stdout="apptainer version 1.5")

    def test_migration_preserves_legacy_sandbox_content_and_existing_overlay(self):
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as staging,
        ):
            directory = Path(root) / "vfnext" / "containers"
            (directory / "repositories").mkdir(parents=True)
            (directory / "repositories" / "repositories_amd64.txt").write_text(
                "org/project/nextclade:3.18\n"
            )
            sandbox = directory / "pangolin:4.4.sif"
            sandbox.mkdir()
            (sandbox / "custom-database").write_text("preserved")
            overlay = directory / "pangolin_4.4.overlay"
            overlay.write_bytes(b"existing overlay")
            unrelated = Path(staging) / "user-owned-file"
            unrelated.write_text("keep")
            with (
                patch.object(management, "runtime", return_value="apptainer"),
                patch.object(
                    management.subprocess, "run", side_effect=self.fake_engine
                ) as run,
            ):
                management.prepare_containers(root, "amd64", staging_dir=staging)
            self.assertTrue(sandbox.is_file())
            self.assertEqual(
                next(
                    directory.glob("backup-*/pangolin:4.4.sif/custom-database")
                ).read_text(),
                "preserved",
            )
            self.assertEqual(overlay.read_bytes(), b"existing overlay")
            self.assertEqual(unrelated.read_text(), "keep")
            self.assertTrue(
                any(
                    call.args[0][-1] == str(sandbox) and call.args[0][1] == "build"
                    for call in run.call_args_list
                )
            )

    def test_clean_backs_up_mutable_data_instead_of_deleting_it(self):
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as staging,
        ):
            directory = Path(root) / "vfnext" / "containers"
            (directory / "repositories").mkdir(parents=True)
            (directory / "repositories" / "repositories_amd64.txt").write_text(
                "org/project/nextclade:3.18\n"
            )
            (directory / "snpeff_5.0.overlay").write_bytes(b"custom data")
            with (
                patch.object(management, "runtime", return_value="apptainer"),
                patch.object(
                    management.subprocess, "run", side_effect=self.fake_engine
                ),
            ):
                management.prepare_containers(
                    root, "amd64", clean=True, staging_dir=staging
                )
            self.assertEqual(
                next(directory.glob("backup-*/snpeff_5.0.overlay")).read_bytes(),
                b"custom data",
            )

    def test_snpeff_preflight_does_not_run_for_nanopore_or_disabled_annotation(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "vfnext" / "containers"
            directory.mkdir(parents=True)
            (directory / "snpeff_5.0.overlay").touch()
            with patch.object(management.subprocess, "run") as run:
                management.ensure_snpeff_database(root, ["--mode", "NANOPORE"], None)
                management.ensure_snpeff_database(
                    root, ["--runSnpEff", "False"], "ILLUMINA"
                )
            run.assert_not_called()

    def test_snpeff_preflight_checks_readonly_and_downloads_into_writable_overlay(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "vfnext" / "containers"
            directory.mkdir(parents=True)
            overlay = directory / "snpeff_5.0.overlay"
            overlay.touch()
            with (
                patch.object(management, "runtime", return_value="apptainer"),
                patch.object(
                    management.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 1),
                ) as run,
            ):
                management.ensure_snpeff_database(
                    root,
                    ["--virus", "custom", "--refGenomeCode", "NC_001474.2"],
                    "ILLUMINA",
                )
            self.assertIn(str(overlay) + ":ro", run.call_args_list[0].args[0])
            self.assertIn(str(overlay), run.call_args_list[1].args[0])
            self.assertEqual(
                run.call_args_list[1].args[0][-3:],
                ["snpEff", "download", "NC_001474.2"],
            )
            self.assertTrue(run.call_args_list[1].kwargs["check"])

    def test_build_options_are_forwarded_without_shell_interpolation(self):
        with patch("wrapper.cli._build_containers") as build:
            result = CliRunner().invoke(
                cli,
                [
                    "build-containers",
                    "--arch",
                    "arm64",
                    "--clean",
                    "--staging-dir",
                    "/var/tmp/with spaces",
                ],
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
            build.call_args.args[1:], ("arm64", True, "/var/tmp/with spaces")
        )

    def test_no_receipt_means_neither_mode_is_ready(self):
        with tempfile.TemporaryDirectory() as root:
            status = management.container_status(root)
        self.assertFalse(status["modes"]["ILLUMINA"]["ready"])
        self.assertFalse(status["modes"]["NANOPORE"]["ready"])

    def test_readiness_requires_same_arch_runtime_and_unchanged_files(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "vfnext" / "containers"
            directory.mkdir(parents=True)
            image = directory / "baseContainer.sif"
            image.write_bytes(b"test image")
            receipt = {
                "architecture": platform.machine(),
                "runtime": "apptainer version 1.5",
                "modes": {"NANOPORE": {image.name: management._fingerprint(image)}},
            }
            (directory / ".prepared-containers.json").write_text(json.dumps(receipt))
            with (
                patch.object(management, "runtime", return_value="apptainer"),
                patch.object(
                    management.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(
                        [], 0, stdout=receipt["runtime"]
                    ),
                ),
            ):
                self.assertTrue(
                    management.container_status(root)["modes"]["NANOPORE"]["ready"]
                )
                image.write_bytes(b"changed image")
                self.assertFalse(
                    management.container_status(root)["modes"]["NANOPORE"]["ready"]
                )
                receipt["architecture"] = "wrong"
                (directory / ".prepared-containers.json").write_text(
                    json.dumps(receipt)
                )
                self.assertFalse(
                    management.container_status(root)["modes"]["NANOPORE"]["ready"]
                )

    def test_shared_staging_is_rejected_before_any_build(self):
        with (
            patch.object(management, "runtime", return_value="apptainer"),
            patch.object(management.subprocess, "run") as run,
        ):
            with self.assertRaisesRegex(ValueError, "local Linux"):
                management.prepare_containers(
                    "/repo", "arm64", staging_dir="/Users/test/staging"
                )
        run.assert_not_called()

    def test_overlay_is_readonly_for_execution_writable_for_management(self):
        with (
            tempfile.TemporaryDirectory() as root,
            patch.object(management, "runtime", return_value="apptainer"),
        ):
            (Path(root) / "pangolin_4.4.overlay").touch()
            self.assertIn(
                str(Path(root) / "pangolin_4.4.overlay") + ":ro",
                management.exec_prefix(root, "pangolin:4.4.sif"),
            )
            self.assertIn(
                str(Path(root) / "pangolin_4.4.overlay"),
                management.exec_prefix(root, "pangolin:4.4.sif", writable=True),
            )

    def test_build_preserves_recipes_and_records_only_successful_modes(self):
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as staging,
        ):
            directory = Path(root) / "vfnext" / "containers"
            (directory / "repositories").mkdir(parents=True)
            (directory / "repositories" / "repositories_arm64.txt").write_text(
                "org/project/nextclade:3.18\n"
            )
            commands = []

            def run(args, **kwargs):
                commands.append(args)
                if args[1] in ("pull", "build"):
                    Path(args[-2]).write_bytes(b"SIF")
                if args[1:3] == ["overlay", "create"]:
                    Path(args[-1]).write_bytes(b"overlay")
                if args[-2:] == ["/opt/bin/run_clair3.sh", "--version"]:
                    raise subprocess.CalledProcessError(1, args)
                return subprocess.CompletedProcess(
                    args, 0, stdout="apptainer version 1.5"
                )

            with (
                patch.object(management, "runtime", return_value="apptainer"),
                patch.object(management.subprocess, "run", side_effect=run),
            ):
                with self.assertRaisesRegex(RuntimeError, "amd64 emulation"):
                    management.prepare_containers(root, "arm64", staging_dir=staging)
            receipt = json.loads((directory / ".prepared-containers.json").read_text())
            self.assertIn("ILLUMINA", receipt["modes"])
            self.assertNotIn("NANOPORE", receipt["modes"])
            self.assertTrue(
                any(
                    args[-1] == management.CLAIR3_IMAGE and "amd64" in args
                    for args in commands
                )
            )
            self.assertTrue(
                any(
                    args[-1].endswith("Nanopore_baseContainer.sing")
                    for args in commands
                )
            )
