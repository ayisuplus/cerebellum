import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from generate import generate


IMAGE = "python@sha256:" + "a" * 64


class GeneratorTests(unittest.TestCase):
    def test_counts_and_family_isolation(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            manifest_path, bundle_path = generate(Path(first), IMAGE)
            other_manifest, other_bundle = generate(Path(second), IMAGE)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["tasks"]), 60)
            self.assertEqual(
                {split: sum(task["split"] == split for task in manifest["tasks"])
                 for split in ("train", "validation", "holdout")},
                {"train": 30, "validation": 15, "holdout": 15},
            )
            families = {}
            for task in manifest["tasks"]:
                families.setdefault(task["template_family"], set()).add(task["split"])
            self.assertEqual(len(families), 20)
            self.assertTrue(all(len(splits) == 1 for splits in families.values()))
            self.assertEqual(manifest_path.read_bytes(), other_manifest.read_bytes())
            self.assertEqual(bundle_path.read_bytes(), other_bundle.read_bytes())

    def test_aggregate_contains_hash_verified_separate_grader_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest_path, bundle_path = generate(Path(directory), IMAGE)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            with zipfile.ZipFile(bundle_path) as aggregate:
                for task in manifest["tasks"]:
                    payload = aggregate.read(f"tasks/{task['task_id']}.zip")
                    self.assertEqual(hashlib.sha256(payload).hexdigest(), task["bundle_hash"])
                    with zipfile.ZipFile(__import__("io").BytesIO(payload)) as bundle:
                        roots = {name.split("/", 1)[0] for name in bundle.namelist()}
                        self.assertIn("public", roots)
                        self.assertIn("grader", roots)
                        for name in bundle.namelist():
                            if name.endswith(".py"):
                                compile(bundle.read(name), name, "exec")


if __name__ == "__main__":
    unittest.main()
