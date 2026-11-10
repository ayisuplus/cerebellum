"""MediaCrawler (NanmiCoder) bridge for login-walled detail+comment deep fetch.

与 social-acquisition/mediacrawler.py 同源，改动须同步 —— this is the trimmed
copy for the web-acquisition worker (detail ladder rung): it carries only
configured_dir / run_mediacrawler / read_jsonl / compose_detail_text /
MC_HOST_TO_KIND (+ kind_for_url and the two private helpers they need). The
BoardItem mapper and search provider live in the social worker's copy only.

MediaCrawler is NOT vendored; operators bootstrap the pinned commit via
workers/social-acquisition/scripts/setup_mediacrawler.py and point both
workers at it with CEREBELLUM_MEDIACRAWLER_DIR. Fail-closed everywhere.

License note: MediaCrawler is NON-COMMERCIAL LEARNING LICENSE 1.1; this bridge
is original code that only shells out to its CLI and copies none of its source.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

MC_PROVIDER_VERSION = "2026.08.14"

# domain -> social-worker kind; matched with `host == d or host.endswith("." + d)`
MC_HOST_TO_KIND = {
    "xiaohongshu.com": "xhs",
    "douyin.com": "douyin",
    "kuaishou.com": "kuaishou",
    "bilibili.com": "bilibili",
    "b23.tv": "bilibili",
    "weibo.com": "weibo",
    "tieba.baidu.com": "tieba",
    "zhihu.com": "zhihu",
}

# kind -> MediaCrawler platform code (main.py CrawlerFactory)
MC_PLATFORM_CODES = {
    "xhs": "xhs",
    "douyin": "dy",
    "kuaishou": "ks",
    "bilibili": "bili",
    "weibo": "wb",
    "tieba": "tieba",
    "zhihu": "zhihu",
}

MC_TIMEOUT_SECONDS = 600


def _safe_environment() -> dict:
    # verbatim copy of OpenCLIProvider's env allowlist (providers.py)
    return {
        name: os.environ[name]
        for name in ("PATH", "SYSTEMROOT", "WINDIR", "LOCALAPPDATA", "APPDATA", "HOME")
        if name in os.environ
    }


def _venv_python(mc_dir: Path) -> Path | None:
    candidates = (
        [mc_dir / ".venv" / "Scripts" / "python.exe"]
        if sys.platform == "win32"
        else [mc_dir / ".venv" / "bin" / "python"]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def configured_dir() -> Path | None:
    """MediaCrawler install dir from CEREBELLUM_MEDIACRAWLER_DIR, or None when
    unset / missing main.py / missing .venv interpreter."""
    value = os.environ.get("CEREBELLUM_MEDIACRAWLER_DIR", "").strip()
    if not value:
        return None
    mc_dir = Path(value)
    if not mc_dir.is_dir() or not (mc_dir / "main.py").is_file():
        return None
    if _venv_python(mc_dir) is None:
        return None
    return mc_dir


def kind_for_url(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    for domain, kind in MC_HOST_TO_KIND.items():
        if host == domain or host.endswith("." + domain):
            return kind
    return None


def run_mediacrawler(
    code: str,
    crawler_type: str,
    *,
    keywords: str | None = None,
    specified: str | None = None,
    notes_limit: int = 15,
) -> Path:
    """Run MediaCrawler main.py as a sanitized subprocess; returns the temp
    output directory holding {code}/jsonl/{type}_{item_type}_{date}.jsonl.

    Raises RuntimeError on non-zero exit or timeout; the caller maps outcomes.
    """
    mc_dir = configured_dir()
    if mc_dir is None:
        raise RuntimeError("mediacrawler is not configured")
    venv_python = _venv_python(mc_dir)
    if venv_python is None:
        raise RuntimeError("mediacrawler venv is missing")
    tmp = Path(tempfile.mkdtemp(prefix="cerebellum-mc-"))
    command = [
        str(venv_python),
        "main.py",
        "--platform",
        code,
        "--lt",
        "cookie",
        "--type",
        crawler_type,
        "--save_data_option",
        "jsonl",
        "--save_data_path",
        str(tmp),
        "--headless",
        "yes",
        "--get_comment",
        "yes",
        "--max_comments_count_singlenotes",
        "20",
        "--crawler_max_notes_count",
        str(notes_limit),
    ]
    if crawler_type == "search" and keywords:
        command += ["--keywords", keywords]
    if crawler_type == "detail" and specified:
        command += ["--specified_id", specified]
    try:
        completed = subprocess.run(
            command,
            cwd=mc_dir,  # login-state user_data_dir persists next to main.py
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=MC_TIMEOUT_SECONDS,
            check=False,
            shell=False,
            env=_safe_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"mediacrawler subprocess failed: {error}") from error
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or b"")[-400:].decode("utf-8", "replace")
        raise RuntimeError(f"mediacrawler exited {completed.returncode}: {tail}")
    return tmp


def read_jsonl(tmp: Path, code: str, crawler_type: str, item_type: str) -> list[dict]:
    """Parse {tmp}/{code}/jsonl/{crawler_type}_{item_type}_*.jsonl; bad lines skipped."""
    pattern = str(tmp / code / "jsonl" / f"{crawler_type}_{item_type}_*.jsonl")
    rows: list[dict] = []
    for path in sorted(glob.glob(pattern)):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def _parse_heat(value: object) -> int:
    try:
        return int(str(value or 0))
    except (TypeError, ValueError):
        return 0


def compose_detail_text(
    contents: list[dict],
    comments: list[dict],
    *,
    max_comments: int = 20,
) -> tuple[str, str]:
    """(title, markdown text) from detail contents + comments rows."""
    row = contents[0] if contents else {}
    title = str(row.get("title") or "") or str(row.get("desc") or "")[:80]
    desc = str(row.get("desc") or "")
    text = f"{title}\n\n{desc}" if desc else title
    ranked = sorted(
        (comment for comment in comments if str(comment.get("content") or "").strip()),
        key=lambda comment: _parse_heat(comment.get("like_count")),
        reverse=True,
    )[:max_comments]
    if ranked:
        lines = [f"- {str(comment.get('content')).strip()}（赞 {_parse_heat(comment.get('like_count'))}）" for comment in ranked]
        text += "\n\n评论：\n" + "\n".join(lines)
    return title, text
