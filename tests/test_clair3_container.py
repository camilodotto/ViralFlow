import unittest
from pathlib import Path


CLAIR3_V1_2_0_CONTAINER = "docker://hkubal/clair3:v1.2.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class Clair3ContainerTests(unittest.TestCase):
    def test_runtime_and_test_configs_use_same_v1_2_0_tag(self):
        source_files = (
            "vfnext/modules/runClair3.nf",
            "vfnext/nextflow.config",
            "vfnext/lib/MetadataHelper.groovy",
            "vfnext/tests/nextflow.config",
            "vfnext/tests/integration/data/nanopore_truth/expected_containers.tsv",
        )

        for relative_path in source_files:
            contents = (REPOSITORY_ROOT / relative_path).read_text()
            with self.subTest(path=relative_path):
                self.assertIn(CLAIR3_V1_2_0_CONTAINER, contents)
                self.assertNotIn("docker://hkubal/clair3:v1.1.0", contents)
                self.assertNotIn("docker://hkubal/clair3@sha256:", contents)


if __name__ == "__main__":
    unittest.main()
