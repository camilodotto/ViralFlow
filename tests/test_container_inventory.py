import unittest
from pathlib import Path


INTRAHOST_SCRIPT_CONTAINER = "intrahost_analysis:1.1.0.sif"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ContainerInventoryTests(unittest.TestCase):
    def test_intrahost_script_container_matches_runtime_configuration(self):
        runtime_config = (
            REPOSITORY_ROOT / "vfnext/configs/containers.config"
        ).read_text()
        metadata_helper = (
            REPOSITORY_ROOT / "vfnext/modules/metadata_helpers.nf"
        ).read_text()

        self.assertIn(INTRAHOST_SCRIPT_CONTAINER, runtime_config)
        # Both intrahost processes now share the declared local image.
        self.assertIn(
            "'intrahost_analysis'",
            metadata_helper,
        )
        self.assertIn("illuminaContainerSpec(params, name)", metadata_helper)
        self.assertRegex(
            runtime_config,
            r"withName:\s*runIntraHostScript \{\s*container = \{ "
            r"params.getOrDefault\('illumina_containers', \[:\]\).intrahost_analysis \}",
        )


if __name__ == "__main__":
    unittest.main()
