import unittest
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from click.testing import CliRunner

from wrapper import NEXTFLOW_VERSION, parse_params, run_vfnext

with patch("importlib.metadata.version", return_value="1.5.0"):
    cli_module = import_module("wrapper.cli")


class RunVfnextTests(unittest.TestCase):
    def run_with_params_file(self, contents, mode):
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        params_file = Path(temporary_directory.name) / "params.txt"
        params_file.write_text(contents)

        with patch("wrapper.os.system") as system_mock:
            run_vfnext(
                "/opt/ViralFlow",
                params_fl=str(params_file),
                mode=mode,
            )

        return system_mock.call_args.args[0]

    @patch("wrapper.os.system")
    def test_uses_pipeline_compatible_nextflow_version(self, system_mock):
        run_vfnext(
            "/opt/ViralFlow",
            params_fl=None,
            mode="NANOPORE",
            cli_params={"virus": "sars-cov2"},
            profile="apptainer",
        )

        self.assertEqual(NEXTFLOW_VERSION, "24.10.3")
        system_mock.assert_called_once_with(
            "NXF_VER=24.10.3 nextflow run /opt/ViralFlow/vfnext/main.nf "
            "--virus sars-cov2 -resume --mode NANOPORE -profile apptainer"
        )

    def test_uses_pipeline_default_when_no_mode_is_specified(self):
        command = self.run_with_params_file("virus sars-cov2\n", mode=None)

        self.assertNotIn("--mode", command)

    def test_preserves_mode_specified_only_in_params_file(self):
        command = self.run_with_params_file("mode NANOPORE\n", mode=None)

        self.assertIn("--mode NANOPORE", command)
        self.assertEqual(command.count("--mode"), 1)

    @patch("wrapper.os.system")
    def test_uses_mode_specified_explicitly_through_cli(self, system_mock):
        run_vfnext(
            "/opt/ViralFlow",
            params_fl=None,
            mode="NANOPORE",
            cli_params={"virus": "sars-cov2"},
        )

        command = system_mock.call_args.args[0]
        self.assertIn("--mode NANOPORE", command)
        self.assertEqual(command.count("--mode"), 1)

    def test_explicit_cli_mode_wins_conflict_without_duplicate_argument(self):
        command = self.run_with_params_file("mode NANOPORE\n", mode="ILLUMINA")

        self.assertIn("--mode ILLUMINA", command)
        self.assertNotIn("--mode NANOPORE", command)
        self.assertEqual(command.count("--mode"), 1)

    @patch("wrapper.cli._run_vfnext")
    def test_cli_default_mode_is_not_an_explicit_file_override(self, run_mock):
        with TemporaryDirectory() as temporary_directory:
            params_file = Path(temporary_directory) / "params.txt"
            params_file.write_text("mode NANOPORE\n")

            result = CliRunner().invoke(
                cli_module.cli,
                ["run", "--params-file", str(params_file)],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIsNone(run_mock.call_args.args[2])

    @patch("wrapper.cli._run_vfnext")
    def test_cli_marks_command_line_mode_as_explicit(self, run_mock):
        with TemporaryDirectory() as temporary_directory:
            params_file = Path(temporary_directory) / "params.txt"
            params_file.write_text("mode NANOPORE\n")

            result = CliRunner().invoke(
                cli_module.cli,
                [
                    "run",
                    "--params-file",
                    str(params_file),
                    "--mode",
                    "ILLUMINA",
                ],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(run_mock.call_args.args[2], "ILLUMINA")

    def test_parse_params_accepts_existing_nanopore_parameters(self):
        with TemporaryDirectory() as temporary_directory:
            base_container = Path(temporary_directory) / "baseContainer.sif"
            params_file = Path(temporary_directory) / "params.txt"
            params_file.write_text(
                "np_min_depth 30\n"
                "af_threshold 0.60\n"
                "clair3_qual 12.5\n"
                "clair3_model r1041_e82_400bps_sup_v500\n"
                "clair3_chunk_size 20000\n"
                f"base_container {base_container}\n"
            )

            arguments = parse_params(str(params_file))

        self.assertIn("--np_min_depth 30", arguments)
        self.assertIn("--af_threshold 0.60", arguments)
        self.assertIn("--clair3_qual 12.5", arguments)
        self.assertIn("--clair3_model r1041_e82_400bps_sup_v500", arguments)
        self.assertIn("--clair3_chunk_size 20000", arguments)
        self.assertIn(f"--base_container {base_container}", arguments)

    @patch("wrapper.os.system")
    def test_constructs_command_with_existing_nanopore_parameters(self, system_mock):
        run_vfnext(
            "/opt/ViralFlow",
            params_fl=None,
            mode="NANOPORE",
            cli_params={
                "np_min_depth": 30,
                "af_threshold": 0.6,
                "clair3_qual": 12.5,
                "clair3_model": "r1041_e82_400bps_sup_v500",
                "clair3_chunk_size": 20000,
                "base_container": "/containers/baseContainer.sif",
            },
        )

        command = system_mock.call_args.args[0]
        self.assertIn("--np_min_depth 30", command)
        self.assertIn("--af_threshold 0.6", command)
        self.assertIn("--clair3_qual 12.5", command)
        self.assertIn("--clair3_model r1041_e82_400bps_sup_v500", command)
        self.assertIn("--clair3_chunk_size 20000", command)
        self.assertIn("--base_container /containers/baseContainer.sif", command)

    @patch("wrapper.cli._run_vfnext")
    def test_explicit_nanopore_cli_option_overrides_params_file(self, run_mock):
        with TemporaryDirectory() as temporary_directory:
            params_file = Path(temporary_directory) / "params.txt"
            params_file.write_text("np_min_depth 20\n")

            result = CliRunner().invoke(
                cli_module.cli,
                [
                    "run",
                    "--params-file",
                    str(params_file),
                    "--np-min-depth",
                    "30",
                ],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(run_mock.call_args.args[3], {"np_min_depth": 30})

    def test_run_help_lists_existing_nanopore_parameters(self):
        result = CliRunner().invoke(cli_module.cli, ["run", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        for option in (
            "--np-min-depth",
            "--af-threshold",
            "--clair3-qual",
            "--clair3-model",
            "--clair3-chunk-size",
            "--base-container",
        ):
            self.assertIn(option, result.output)

    @patch("wrapper.cli._run_vfnext")
    def test_cli_defaults_match_nextflow_boolean_defaults(self, run_mock):
        with TemporaryDirectory() as input_directory:
            result = CliRunner().invoke(
                cli_module.cli,
                ["run", "--in-dir", input_directory],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        cli_params = run_mock.call_args.args[3]
        self.assertEqual(cli_params["runSnpEff"], "true")
        self.assertEqual(cli_params["writeMappedReads"], "true")


if __name__ == "__main__":
    unittest.main()
