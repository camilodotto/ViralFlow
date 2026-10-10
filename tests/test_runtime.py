"""Runtime failure handling; no biological data or container downloads."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import wrapper

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "container_helpers", ROOT / "vfnext/containers/spython_functions.py"
)
containers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(containers)


class RuntimeTests(unittest.TestCase):
    def test_failed_download_stops_container_build(self):
        failure = subprocess.CalledProcessError(1, "apptainer pull")
        with patch.object(wrapper.subprocess, "check_call", side_effect=failure) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                wrapper.build_containers(str(ROOT), "amd64")
        self.assertEqual(run.call_count, 1)

    def test_failed_pipeline_returns_failure_to_cli(self):
        with patch.object(wrapper, "parse_params", return_value=""), \
                patch.object(wrapper.subprocess, "call", return_value=42):
            with self.assertRaises(SystemExit) as raised:
                wrapper.run_vfnext(str(ROOT), "unused.params")
        self.assertEqual(raised.exception.code, 42)

    def test_pangolin_update_failure_is_reported_and_temporary_files_removed(self):
        for update, option in ((wrapper.update_pangolin, "--update"),
                               (wrapper.update_pangolin_data, "--update-data")):
            with self.subTest(option=option):
                temporary = []

                def fail(command, cwd):
                    temporary.append(Path(command[command.index("--bind") + 1].removesuffix(":/tmp")))
                    self.assertEqual((temporary[0] / "build-constraints.txt").read_text(), "setuptools<81\n")
                    self.assertIn("PIP_BUILD_CONSTRAINT=/tmp/build-constraints.txt", command)
                    self.assertEqual(command[-1], option)
                    self.assertEqual(cwd, "/installation with spaces/vfnext/containers")
                    raise subprocess.CalledProcessError(7, command)

                with patch.object(wrapper.subprocess, "check_call", side_effect=fail):
                    with self.assertRaises(subprocess.CalledProcessError) as raised:
                        update("/installation with spaces")
                self.assertEqual(raised.exception.returncode, 7)
                self.assertFalse(temporary[0].exists())

    def test_snpeff_arguments_with_spaces_and_failure_are_preserved(self):
        failure = subprocess.CalledProcessError(9, "bash")
        with patch.object(wrapper.subprocess, "check_call", side_effect=failure) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                wrapper.add_entries_to_DB("/installation with spaces", "Synthetic test", "TEST", "amd64")
        self.assertEqual(run.call_args.args[0], [
            "bash", "/installation with spaces/vfnext/containers/add_entries_SnpeffDB.sh",
            "Synthetic test", "TEST", "amd64"])

    def test_data_update_does_not_install_tool_dependencies(self):
        with patch.object(wrapper.subprocess, "check_call") as run:
            wrapper.update_pangolin_data("/installation")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][-2:], ["pangolin", "--update-data"])

    def test_full_update_reports_dependency_installation_and_check_failures(self):
        for failed_step in (2, 3):
            with self.subTest(failed_step=failed_step):
                failure = subprocess.CalledProcessError(8, "dependency verification")
                outcomes = [None] * (failed_step - 1) + [failure]
                with patch.object(wrapper.subprocess, "check_call", side_effect=outcomes) as run:
                    with self.assertRaises(subprocess.CalledProcessError) as raised:
                        wrapper.update_pangolin("/installation")
                self.assertEqual(raised.exception.returncode, 8)
                self.assertEqual(run.call_count, failed_step)

    def test_snpeff_failed_download_or_build_does_not_publish_catalog(self):
        for failure in ("download", "build", "missing-output"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "directory with spaces"
                root.mkdir()
                config = root / "snpeff:5.0.sif/opt/conda/share/snpeff-5.0-3/snpEff.config"
                config.parent.mkdir(parents=True)
                config.write_text("# existing configuration\n")
                catalog = root / "snpEff_DB.catalog"
                catalog.write_text("existing catalog\n")
                script = root / "add_entries_SnpeffDB.sh"
                shutil.copy2(ROOT / "vfnext/containers/add_entries_SnpeffDB.sh", script)
                executable = root / "apptainer"
                executable.write_text("""#!/bin/sh
case " $* " in
  *" efetch "*)
    if [ "$TEST_FAILURE" != download ]; then
      printf 'LOCUS       TEST\nORIGIN\n        1 acgt\n//\n'
    fi ;;
  *" snpEff build "*)
    if [ "$TEST_FAILURE" = build ]; then exit 7; fi ;;
  *) printf 'Unexpected catalog publication\n' >&2; exit 99 ;;
esac
""")
                executable.chmod(0o755)
                environment = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}", TEST_FAILURE=failure)
                result = subprocess.run(["bash", str(script), "Synthetic test", "TEST", "amd64"],
                                        env=environment, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(catalog.read_text(), "existing catalog\n")
                if failure == "download":
                    self.assertEqual(config.read_text(), "# existing configuration\n")
                    self.assertFalse((config.parent / "data/TEST").exists())

    def test_pull_does_not_depend_on_default_apptainer_remote(self):
        image = ("test", "example:1", "test/test/example:1")
        with patch.object(containers.subprocess, "check_call") as run:
            containers.container_pull("/tmp/container-test", [image])
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--library") + 1], "https://library.sylabs.io")
        self.assertEqual(run.call_args.kwargs["cwd"], "/tmp/container-test")

    def test_missing_downloads_terminate_instead_of_looping_forever(self):
        missing = [("test", "example:1", "test/test/example:1")]
        with patch.object(containers, "container_pull") as run, \
                patch.object(containers, "check_containers", return_value=missing):
            with self.assertRaises(RuntimeError):
                containers.containers_routine_pull(missing, "/tmp", missing)
        self.assertEqual(run.call_count, 3)


if __name__ == "__main__":
    unittest.main()
