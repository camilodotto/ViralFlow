import unittest
from pathlib import Path


INTRAHOST_SCRIPT_CONTAINER = (
    "community.wave.seqera.io/library/"
    "pip_bio_numpy_pandas:76453d2622855f06"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ContainerInventoryTests(unittest.TestCase):
    def test_intrahost_script_container_matches_runtime_configuration(self):
        runtime_config = (
            REPOSITORY_ROOT / "vfnext/configs/containers.config"
        ).read_text()
        metadata_helper = (
            REPOSITORY_ROOT / "vfnext/lib/MetadataHelper.groovy"
        ).read_text()

        self.assertIn(INTRAHOST_SCRIPT_CONTAINER, runtime_config)
        self.assertIn(INTRAHOST_SCRIPT_CONTAINER, metadata_helper)
        self.assertIn(
            'remoteContainer("intrahost_script", INTRAHOST_SCRIPT_CONTAINER)',
            metadata_helper,
        )


if __name__ == "__main__":
    unittest.main()
