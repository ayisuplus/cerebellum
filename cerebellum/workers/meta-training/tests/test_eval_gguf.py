from __future__ import annotations

import hashlib
import io
import stat
import sys
import tarfile
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from cerebellum_meta_training import eval_gguf

MODULE = "cerebellum_meta_training.eval_gguf"

GGUF_BYTES = b"fake-gguf-output"


def build_base_tree(root: Path) -> tuple[Path, str]:
    base_dir = root / "base-model"
    base_dir.mkdir(parents=True)
    (base_dir / "config.json").write_text("{}", encoding="utf-8")
    (base_dir / "model.safetensors").write_bytes(b"weights")
    return base_dir, eval_gguf.tree_sha256(base_dir)


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    return output.getvalue()


def build_adapter_tar(root: Path, expert_id: str, blob: bytes) -> tuple[Path, str]:
    tar_path = root / "adapters.tar"
    with tarfile.open(tar_path, "w:") as archive:
        info = tarfile.TarInfo(f"adapters/{expert_id}.zip")
        info.size = len(blob)
        archive.addfile(info, io.BytesIO(blob))
    return tar_path, hashlib.sha256(blob).hexdigest()


def build_fake_merge_stack(capture: dict) -> dict:
    """Fake torch/transformers/peft for _merge_adapter (CPU-only path)."""

    torch_module = types.ModuleType("torch")
    torch_module.float16 = "float16"

    transformers_module = types.ModuleType("transformers")

    class AutoModelForCausalLM:
        @staticmethod
        def from_pretrained(model, **kwargs):
            capture["model_from_pretrained"] = (model, kwargs)
            return types.SimpleNamespace(kind="base")

    transformers_module.AutoModelForCausalLM = AutoModelForCausalLM

    peft_module = types.ModuleType("peft")

    class FakePeftModel:
        def merge_and_unload(self):
            capture.setdefault("order", []).append("merge_and_unload")

            class Merged:
                def save_pretrained(self, directory):
                    capture["order"].append("save_pretrained")
                    Path(directory).mkdir(parents=True, exist_ok=True)
                    Path(directory, "model.safetensors").write_bytes(b"merged")

            return Merged()

    class PeftModel:
        @staticmethod
        def from_pretrained(model, adapter_dir, **kwargs):
            capture["peft_from_pretrained"] = (model, adapter_dir, kwargs)
            return FakePeftModel()

    peft_module.PeftModel = PeftModel

    return {
        "peft": peft_module,
        "torch": torch_module,
        "transformers": transformers_module,
    }


def write_outfile(argv, **kwargs):
    Path(argv[argv.index("--outfile") + 1]).write_bytes(GGUF_BYTES)
    return types.SimpleNamespace(returncode=0)


def base_args(directory: str, tree_hash: str, llama_cpp: str, out: str) -> list[str]:
    return [
        "base",
        "--base-dir",
        directory,
        "--expect-tree-sha256",
        tree_hash,
        "--llama-cpp",
        llama_cpp,
        "--out",
        out,
    ]


class BaseCommandTests(unittest.TestCase):
    def test_tree_hash_mismatch_refuses_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_dir, _ = build_base_tree(root)
            out = root / "out.gguf"
            with mock.patch(f"{MODULE}.subprocess.run") as run_mock:
                with self.assertRaisesRegex(RuntimeError, "does not match"):
                    eval_gguf.main(
                        base_args(str(base_dir), "0" * 64, str(root), str(out))
                    )
            run_mock.assert_not_called()

    def test_success_runs_fixed_argv_and_prints_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_dir, tree_hash = build_base_tree(root)
            out = root / "out.gguf"
            with mock.patch(
                f"{MODULE}.subprocess.run", side_effect=write_outfile
            ) as run_mock:
                stdout = io.StringIO()
                with mock.patch.object(sys, "stdout", stdout):
                    result = eval_gguf.main(
                        base_args(str(base_dir), tree_hash, str(root), str(out))
                    )
            self.assertEqual(result, 0)
            expected_argv = [
                sys.executable,
                str(root / "convert_hf_to_gguf.py"),
                str(base_dir),
                "--outfile",
                str(out),
                "--outtype",
                "q8_0",
            ]
            run_mock.assert_called_once_with(expected_argv, check=True)
            self.assertEqual(
                stdout.getvalue().strip(), hashlib.sha256(GGUF_BYTES).hexdigest()
            )


class MergeCommandTests(unittest.TestCase):
    def run_merge(
        self,
        root: Path,
        tar_path: Path,
        artifact_sha: str,
        expert_id: str = "e1",
        stack: dict | None = None,
    ):
        base_dir, tree_hash = build_base_tree(root)
        out = root / "merged.gguf"
        argv = [
            "merge",
            "--base-dir",
            str(base_dir),
            "--expect-tree-sha256",
            tree_hash,
            "--adapter-tar",
            str(tar_path),
            "--expert-id",
            expert_id,
            "--expect-artifact-sha256",
            artifact_sha,
            "--llama-cpp",
            str(root),
            "--out",
            str(out),
        ]
        with mock.patch.dict(sys.modules, stack or {}), mock.patch(
            f"{MODULE}.subprocess.run", side_effect=write_outfile
        ) as run_mock:
            stdout = io.StringIO()
            with mock.patch.object(sys, "stdout", stdout):
                result = eval_gguf.main(argv)
        return result, run_mock, stdout, base_dir, out

    def test_artifact_sha_mismatch_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar_path, _ = build_adapter_tar(
                root, "e1", zip_bytes({"adapter_config.json": b"{}"})
            )
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                self.run_merge(root, tar_path, "0" * 64)

    def test_zip_dotdot_entry_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar_path, sha = build_adapter_tar(
                root, "e1", zip_bytes({"../evil": b"x"})
            )
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                self.run_merge(root, tar_path, sha)

    def test_zip_symlink_entry_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as archive:
                info = zipfile.ZipInfo("link", date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, "target")
            tar_path, sha = build_adapter_tar(root, "e1", output.getvalue())
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                self.run_merge(root, tar_path, sha)

    def test_member_of_other_expert_is_not_picked_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar_path, sha = build_adapter_tar(
                root, "e1", zip_bytes({"adapter_config.json": b"{}"})
            )
            with self.assertRaisesRegex(RuntimeError, "adapters/e2.zip"):
                self.run_merge(root, tar_path, sha, expert_id="e2")

    def test_success_merges_on_cpu_then_converts(self) -> None:
        capture: dict = {}
        stack = build_fake_merge_stack(capture)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar_path, sha = build_adapter_tar(
                root, "e1", zip_bytes({"adapter_config.json": b"{}"})
            )
            result, run_mock, stdout, base_dir, out = self.run_merge(
                root, tar_path, sha, stack=stack
            )
        self.assertEqual(result, 0)

        model_path, model_kwargs = capture["model_from_pretrained"]
        self.assertEqual(model_path, str(base_dir))
        self.assertEqual(model_kwargs["torch_dtype"], "float16")
        self.assertEqual(model_kwargs["device_map"], "cpu")
        self.assertEqual(capture["order"], ["merge_and_unload", "save_pretrained"])

        convert_argv = run_mock.call_args.args[0]
        self.assertEqual(convert_argv[0], sys.executable)
        self.assertEqual(convert_argv[1], str(root / "convert_hf_to_gguf.py"))
        self.assertTrue(convert_argv[2].endswith("merged"))
        self.assertEqual(convert_argv[3:], ["--outfile", str(out), "--outtype", "q8_0"])
        run_mock.assert_called_once_with(convert_argv, check=True)
        self.assertEqual(
            stdout.getvalue().strip(), hashlib.sha256(GGUF_BYTES).hexdigest()
        )


if __name__ == "__main__":
    unittest.main()
