"""MediaCrawler (NanmiCoder) bridge: pinned external CLI subprocess.

Social search acquisition for login-walled platforms. MediaCrawler is NOT
vendored into this repo; operators run scripts/setup_mediacrawler.py once to
materialize the pinned commit (providers.lock.json) under .external/ with its
own .venv, then perform a one-time QR login per platform. This module locates
that install, invokes main.py as a sanitized subprocess, and maps the JSONL
output into BoardItem rows.

Fail-closed everywhere: unconfigured install, non-zero exit, timeout, or
unparseable rows never fabricate data.

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
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from .platforms.base import BoardItem, BoardResult

MC_PROVIDER_VERSION = "2026.08.14"

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

# domain -> kind; matched with `host == d or host.endswith("." + d)` (subdomain
# semantics aligned with acquisition.rs:102)
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

# canonical search-page URLs for search documents; query must be urlencoded
MC_SEARCH_URLS = {
    "xhs": "https://www.xiaohongshu.com/search_result?keyword={q}",
    "douyin": "https://www.douyin.com/search/{q}",
    "kuaishou": "https://www.kuaishou.com/search/video?searchKey={q}",
    "bilibili": "https://search.bilibili.com/all?keyword={q}",
    "weibo": "https://s.weibo.com/weibo?q={q}",
    "tieba": "https://tieba.baidu.com/f/search/res?qw={q}",
    "zhihu": "https://www.zhihu.com/search?type=content&q={q}",
}

MC_TIMEOUT_SECONDS = 600


def _safe_environment() -> dict:
    # verbatim copy of OpenCLIProvider.safe_environment (web-acquisition
    # providers.py:565-625): only the variables a browser subprocess needs
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


def _iso_from_epoch(value: object) -> str | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    if number > 1e12:  # epoch milliseconds
        number /= 1000.0
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError):
        return None


def _parse_heat(value: object) -> int:
    try:
        return int(str(value or 0))
    except (TypeError, ValueError):
        return 0


def content_to_board_item(row: dict, kind: str, rank: int) -> BoardItem | None:
    """Map one MC contents row to a BoardItem; None when id or url missing."""
    external_id = row.get("note_id") or row.get("aweme_id") or row.get("video_id")
    url = row.get("note_url") or row.get("aweme_url") or row.get("video_url")
    if not external_id or not url:
        return None
    desc = str(row.get("desc") or "")
    title = str(row.get("title") or "") or desc[:80]
    return BoardItem(
        external_id=str(external_id),
        title=title,
        url=str(url),
        author=str(row.get("nickname") or "") or None,
        published_at=_iso_from_epoch(row.get("create_time") if row.get("create_time") is not None else row.get("time")),
        summary=desc or None,
        heat=_parse_heat(row.get("liked_count")),
        rank=rank,
        platform=kind,
        extra={"source_keyword": str(row.get("source_keyword") or "")},
    )


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


class MediaCrawlerSearchProvider:
    """Platform keyword search via MediaCrawler CLI (social worker dispatch)."""

    def __init__(self, kind: str):
        self.kind = kind
        self.code = MC_PLATFORM_CODES[kind]

    def discover(self, payload: dict) -> BoardResult:
        policy = payload["source_policy"]
        base_url = str(policy.get("base_url") or "https://invalid.example/")
        if policy.get("access_mode") != "authenticated_local":
            return BoardResult("api", "policy_denied", base_url, error_code="local_auth_not_allowed")
        if configured_dir() is None:
            return BoardResult("api", "policy_denied", base_url, error_code="mediacrawler_not_configured")
        query = str(payload.get("query") or "").strip()
        if not query:
            return BoardResult("api", "policy_denied", base_url, error_code="empty_query")
        search_url = MC_SEARCH_URLS[self.kind].format(q=quote_plus(query))
        notes_limit = min(int(policy.get("max_pages_per_run") or 50), 30)
        try:
            tmp = run_mediacrawler(self.code, "search", keywords=query, notes_limit=notes_limit)
        except RuntimeError:
            return BoardResult("mediacrawler", "parse_failed", search_url, error_code="mediacrawler_failed")
        rows = read_jsonl(tmp, self.code, "search", "contents")
        items = [
            item
            for rank, row in enumerate(rows, 1)
            if (item := content_to_board_item(row, self.kind, rank)) is not None
        ]
        return BoardResult("mediacrawler", "success", search_url, items=items)
