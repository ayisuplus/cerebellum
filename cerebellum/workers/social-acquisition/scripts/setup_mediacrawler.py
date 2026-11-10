#!/usr/bin/env python3
"""Bootstrap the pinned MediaCrawler checkout under .external/.

Reads providers.lock.json, downloads the pinned commit tarball from GitHub
codeload, verifies its sha256, unpacks (stripping the top-level directory),
then creates a .venv inside it and installs requirements + playwright chromium.

Pure stdlib for the fetch/unpack phase; the venv phase shells out to the
freshly created interpreter. Safe to re-run: an existing complete install is
left untouched unless --force is passed.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

WORKER_DIR = Path(__file__).resolve().parent.parent
LOCK_PATH = WORKER_DIR / "providers.lock.json"
TARGET_DIR = WORKER_DIR / ".external" / "mediacrawler"
CODLOAD_URL = "https://codeload.github.com/NanmiCoder/MediaCrawler/tar.gz/{commit}"

VENV_PYTHON = ".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python"


def load_provider() -> dict:
    with LOCK_PATH.open("r", encoding="utf-8") as handle:
        lock = json.load(handle)
    providers = [p for p in lock.get("providers", []) if p.get("name") == "mediacrawler"]
    if len(providers) != 1:
        raise SystemExit(f"error: expected exactly one mediacrawler entry in {LOCK_PATH}")
    return providers[0]

def _closed_tempname(prefix: str, suffix: str) -> str:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)  # close so the file is re-openable/unlinkable on Windows
    return name


def download_and_verify(commit: str, expected_sha256: str) -> Path:
    url = CODLOAD_URL.format(commit=commit)
    digest = hashlib.sha256()
    tmp = Path(_closed_tempname("mediacrawler-", ".tar.gz"))
    try:
        print(f"downloading {url}")
        with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as out:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                digest.update(chunk)
                out.write(chunk)
        actual = digest.hexdigest()
        if actual != expected_sha256:
            print(f"error: sha256 mismatch for {url}")
            print(f"  expected: {expected_sha256}")
            print(f"  actual:   {actual}")
            print("If the commit is unchanged and GitHub re-generated the archive,")
            print("update source_archive_sha256 in providers.lock.json to the actual value.")
            raise SystemExit(2)
        return tmp
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def unpack(archive: Path, target: Path) -> None:
    staging = target.parent / (target.name + ".staging")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = []
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if len(parts) < 2:  # strip the top-level MediaCrawler-<commit>/ directory
                    continue
                member.name = str(Path(*parts[1:]))
                members.append(member)
            tar.extractall(staging, members=members, filter="data")
        shutil.rmtree(target, ignore_errors=True)
        staging.rename(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def create_venv(target: Path) -> Path:
    venv_python = target / VENV_PYTHON
    if not venv_python.is_file():
        print("creating .venv")
        subprocess.run([sys.executable, "-m", "venv", str(target / ".venv")], check=True)
    print("installing requirements.txt")
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=target,
        check=True,
    )
    print("installing playwright chromium")
    subprocess.run([str(venv_python), "-m", "playwright", "install", "chromium"], cwd=target, check=True)
    return venv_python


def print_login_guidance(venv_python: Path) -> None:
    print()
    print("MediaCrawler installed.")
    print()
    print("One-time login (manual, per platform you intend to use):")
    print("  MediaCrawler persists login state via SAVE_LOGIN_STATE=True into")
    print("  <platform>_user_data_dir/ next to main.py. Run once, headed, and scan")
    print("  the QR code:")
    for code in ("xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"):
        print(f'    cd {TARGET_DIR} && "{venv_python}" main.py --platform {code} --lt qrcode --type search --keywords 测试')
    print()
    print(f"Then point workers at it via: CEREBELLUM_MEDIACRAWLER_DIR={TARGET_DIR}")


def main() -> None:
    force = "--force" in sys.argv[1:]
    provider = load_provider()
    commit = provider["commit"]
    expected_sha256 = provider["source_archive_sha256"]

    already = (TARGET_DIR / "main.py").is_file() and (TARGET_DIR / VENV_PYTHON).is_file()
    if already and not force:
        print(f"mediacrawler already installed at {TARGET_DIR} (use --force to reinstall)")
        print_login_guidance(TARGET_DIR / VENV_PYTHON)
        return

    archive = download_and_verify(commit, expected_sha256)
    try:
        unpack(archive, TARGET_DIR)
    finally:
        archive.unlink(missing_ok=True)
    venv_python = create_venv(TARGET_DIR)
    print_login_guidance(venv_python)


if __name__ == "__main__":
    main()
