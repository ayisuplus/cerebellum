from __future__ import annotations

import argparse
import hashlib
import io
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
import json
import shutil
from cerebellum_meta_training.remote_worker import tree_sha256

OUTTYPE = "q8_0"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_tree_hash(base_dir: Path, expect: str) -> None:
    actual = tree_sha256(base_dir)
    if actual.lower() != expect.lower():
        raise RuntimeError(
            f"base-model tree sha256 {actual} does not match expected {expect.lower()}"
        )


def _convert(llama_cpp: Path, model_dir: Path, outfile: Path) -> None:
    argv = [
        sys.executable,
        str(llama_cpp / "convert_hf_to_gguf.py"),
        str(model_dir),
        "--outfile",
        str(outfile),
        "--outtype",
        OUTTYPE,
    ]
    subprocess.run(argv, check=True)
    print(_file_sha256(outfile))


def _load_adapter_zip(adapter_tar: Path, expert_id: str, expect_sha256: str) -> bytes:
    name = f"adapters/{expert_id}.zip"
    with tarfile.open(adapter_tar, "r:*") as archive:
        member = next(
            (item for item in archive.getmembers() if item.name == name), None
        )
        if member is None:
            raise RuntimeError(f"adapter tar does not contain {name}")
        if not member.isfile():
            raise RuntimeError(f"adapter tar member {name} is not a regular file")
        source = archive.extractfile(member)
        if source is None:
            raise RuntimeError(f"adapter tar member {name} is unreadable")
        blob = source.read()
    actual = hashlib.sha256(blob).hexdigest()
    if actual != expect_sha256.lower():
        raise RuntimeError(
            f"adapter artifact sha256 {actual} does not match expected {expect_sha256.lower()}"
        )
    return blob


def _safe_adapter_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or ":" in name
        or any(part in ("", ".", "..") for part in name.split("/"))
        or ".." in path.parts
    ):
        raise RuntimeError("adapter zip member path is unsafe")
    return path


def _extract_adapter_zip(blob: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for info in archive.infolist():
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) == stat.S_IFLNK:
                raise RuntimeError("adapter zip member must not be a symlink")
            relative = _safe_adapter_name(info.filename)
            if info.is_dir():
                continue
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))


def _merge_adapter(base_dir: Path, adapter_dir: Path, merged_dir: Path) -> None:
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM
    except ImportError as error:
        raise RuntimeError("pinned merge dependencies are not installed") from error
    model = AutoModelForCausalLM.from_pretrained(
        str(base_dir), torch_dtype=torch.float16, device_map="cpu"
    )
    merged = PeftModel.from_pretrained(model, str(adapter_dir)).merge_and_unload()
    merged.save_pretrained(str(merged_dir))
    # save_pretrained writes weights/config only; the GGUF converter also
    # needs the pinned base model's tokenizer files.
    for name in (
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
        "special_tokens_map.json",
        "generation_config.json",
    ):
        source = base_dir / name
        if source.exists():
            shutil.copyfile(source, merged_dir / name)


def _run_base(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir)
    _require_tree_hash(base_dir, args.expect_tree_sha256)
    _convert(Path(args.llama_cpp), base_dir, Path(args.out))
    return 0


def _run_merge(args: argparse.Namespace) -> int:
    base_dir = Path(args.base_dir)
    _require_tree_hash(base_dir, args.expect_tree_sha256)
    blob = _load_adapter_zip(
        Path(args.adapter_tar), args.expert_id, args.expect_artifact_sha256
    )
    with tempfile.TemporaryDirectory() as scratch:
        adapter_dir = Path(scratch) / "adapter"
        _extract_adapter_zip(blob, adapter_dir)
        merged_dir = Path(scratch) / "merged"
        _merge_adapter(base_dir, adapter_dir, merged_dir)
        _convert(Path(args.llama_cpp), merged_dir, Path(args.out))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert/merge pinned base models to GGUF for adapter evaluation"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    base = subcommands.add_parser("base", help="convert a pinned base-model tree")
    base.add_argument("--base-dir", required=True)
    base.add_argument("--expect-tree-sha256", required=True)
    base.add_argument("--llama-cpp", required=True)
    base.add_argument("--out", required=True)
    base.set_defaults(handler=_run_base)

    merge = subcommands.add_parser("merge", help="merge a routed adapter then convert")
    merge.add_argument("--base-dir", required=True)
    merge.add_argument("--expect-tree-sha256", required=True)
    merge.add_argument("--adapter-tar", required=True)
    merge.add_argument("--expert-id", required=True)
    merge.add_argument("--expect-artifact-sha256", required=True)
    merge.add_argument("--llama-cpp", required=True)
    merge.add_argument("--out", required=True)
    merge.set_defaults(handler=_run_merge)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
