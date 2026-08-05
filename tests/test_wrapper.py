import unittest
from unittest.mock import patch

from wrapper import NEXTFLOW_VERSION, run_vfnext


class RunVfnextTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
