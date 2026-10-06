"""Regression coverage for recovery between Apptainer builds."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "vfnext/containers/build_containers.py"
spec = importlib.util.spec_from_file_location("build_containers", SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildRecoveryTest(unittest.TestCase):
    def test_next_build_has_temp_directory_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            script = base / "containers/build_containers.py"
            definitions = script.parent / "def_files/amd64"
            definitions.mkdir(parents=True)
            for name in ("Singularity_pangolin", "Singularity_snpEff"):
                (definitions / name).touch()
            attempts = []

            def run_build(command, *, cwd, env):
                self.assertTrue(Path(env["APPTAINER_TMPDIR"]).is_dir())
                attempts.append(command)
                if len(attempts) == 1:
                    # Simulate partial temporary files left by a failed build.
                    (Path(env["APPTAINER_TMPDIR"]) / "partial").touch()
                    raise subprocess.CalledProcessError(255, command)
                self.assertFalse((Path(env["APPTAINER_TMPDIR"]) / "partial").exists())
                Path(command[-2]).write_text("successful snpEff build")

            with patch.object(builder, "__file__", str(script)), \
                 patch.object(builder.shutil, "which", return_value="/usr/bin/apptainer"), \
                 patch.object(builder, "run", side_effect=run_build), \
                 patch("sys.argv", [str(script), "amd64", "--staging-dir", str(base / "staging")]):
                self.assertEqual(builder.main(), 1)
            self.assertEqual(len(attempts), 2)
            self.assertEqual((script.parent / "snpeff:5.0.sif").read_text(), "successful snpEff build")


if __name__ == "__main__":
    unittest.main()
