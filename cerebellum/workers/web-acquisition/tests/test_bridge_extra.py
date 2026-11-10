from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cerebellum_web_acquisition.mediacrawler_bridge import (
    MC_TIMEOUT_SECONDS,
    _parse_heat,
    _safe_environment,
    _venv_python,
    compose_detail_text,
    configured_dir,
    kind_for_url,
    read_jsonl,
    run_mediacrawler,
)


def make_mc_dir(root: Path) -> Path:
    mc_dir = root / "mc"
    (mc_dir / ".venv" / "Scripts").mkdir(parents=True)
    (mc_dir / "main.py").write_text("# mediacrawler entry", encoding="utf-8")
    (mc_dir / ".venv" / "Scripts" / "python.exe").write_bytes(b"")
    return mc_dir


class EnvironmentTests(unittest.TestCase):
    def test_safe_environment_keeps_only_allowlisted_names(self) -> None:
        env = {
            "PATH": "/usr/bin",
            "HOME": "/home/x",
            "CEREBELLUM_TOKEN": "secret",
            "TAVILY_API_KEY": "secret2",
            "RANDOM_THING": "nope",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            safe = _safe_environment()
        self.assertEqual(safe, {"PATH": "/usr/bin", "HOME": "/home/x"})

    def test_venv_python_found_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(_venv_python(root))
            mc_dir = make_mc_dir(root)
            self.assertEqual(
                _venv_python(mc_dir), mc_dir / ".venv" / "Scripts" / "python.exe"
            )


class ConfiguredDirTests(unittest.TestCase):
    def test_unset_env_is_unconfigured(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(configured_dir())

    def test_missing_directory_is_unconfigured(self) -> None:
        with mock.patch.dict(
            os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": "E:/definitely/missing"}, clear=True
        ):
            self.assertIsNone(configured_dir())

    def test_missing_main_py_is_unconfigured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": directory}, clear=True
            ):
                self.assertIsNone(configured_dir())

    def test_missing_venv_is_unconfigured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = Path(directory)
            (mc_dir / "main.py").write_text("# entry", encoding="utf-8")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=True
            ):
                self.assertIsNone(configured_dir())

    def test_fully_installed_directory_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = make_mc_dir(Path(directory))
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=True
            ):
                self.assertEqual(configured_dir(), mc_dir)


class KindForUrlExtraTests(unittest.TestCase):
    def test_host_matching_is_case_insensitive_and_subdomain_aware(self) -> None:
        self.assertEqual(kind_for_url("https://WWW.Xiaohongshu.com/explore/n1"), "xhs")
        self.assertEqual(kind_for_url("https://sub.douyin.com/v/1"), "douyin")
        self.assertEqual(kind_for_url("https://b23.tv/abc"), "bilibili")
        self.assertEqual(kind_for_url("https://tieba.baidu.com/p/1"), "tieba")
        self.assertEqual(kind_for_url("https://www.zhihu.com/question/1"), "zhihu")

    def test_non_matching_and_hostless_urls(self) -> None:
        self.assertIsNone(kind_for_url("https://notxiaohongshu.com/"))
        self.assertIsNone(kind_for_url("not a url"))
        self.assertIsNone(kind_for_url(""))


class RunMediacrawlerTests(unittest.TestCase):
    def test_unconfigured_install_fails_closed(self) -> None:
        with mock.patch(
            "cerebellum_web_acquisition.mediacrawler_bridge.configured_dir",
            return_value=None,
        ):
            with self.assertRaises(RuntimeError):
                run_mediacrawler("xhs", "detail", specified="https://x")

    def test_successful_run_returns_tmp_dir_and_sanitized_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = make_mc_dir(Path(directory))
            completed = subprocess.CompletedProcess([], 0, stdout=b"ok", stderr=b"")
            env = {
                "CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir),
                "CEREBELLUM_TOKEN": "must-not-leak",
                "PATH": "/usr/bin",
            }
            with mock.patch.dict(os.environ, env, clear=True), mock.patch(
                "cerebellum_web_acquisition.mediacrawler_bridge.subprocess.run",
                return_value=completed,
            ) as run:
                tmp = run_mediacrawler(
                    "bili", "detail", specified="https://www.bilibili.com/video/BV1", notes_limit=3
                )
            try:
                command = run.call_args.args[0]
                self.assertEqual(command[1], "main.py")
                self.assertIn("--platform", command)
                self.assertEqual(command[command.index("--platform") + 1], "bili")
                self.assertEqual(command[command.index("--type") + 1], "detail")
                self.assertEqual(
                    command[command.index("--specified_id") + 1],
                    "https://www.bilibili.com/video/BV1",
                )
                self.assertEqual(
                    command[command.index("--crawler_max_notes_count") + 1], "3"
                )
                self.assertNotIn("--keywords", command)
                self.assertEqual(run.call_args.kwargs["cwd"], mc_dir)
                self.assertEqual(run.call_args.kwargs["timeout"], MC_TIMEOUT_SECONDS)
                self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
                self.assertFalse(run.call_args.kwargs["shell"])
                child_env = run.call_args.kwargs["env"]
                self.assertNotIn("CEREBELLUM_TOKEN", child_env)
                self.assertNotIn("CEREBELLUM_MEDIACRAWLER_DIR", child_env)
                self.assertEqual(child_env, {"PATH": "/usr/bin"})
                self.assertTrue(str(tmp).startswith(tempfile.gettempdir()))
            finally:
                for child in Path(tmp).rglob("*"):
                    pass

    def test_search_run_passes_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = make_mc_dir(Path(directory))
            completed = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=True
            ), mock.patch(
                "cerebellum_web_acquisition.mediacrawler_bridge.subprocess.run",
                return_value=completed,
            ) as run:
                run_mediacrawler("xhs", "search", keywords="滑雪 攻略")
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--keywords") + 1], "滑雪 攻略")
            self.assertNotIn("--specified_id", command)

    def test_nonzero_exit_raises_with_stderr_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = make_mc_dir(Path(directory))
            completed = subprocess.CompletedProcess([], 2, stdout=b"", stderr=b"boom details")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=True
            ), mock.patch(
                "cerebellum_web_acquisition.mediacrawler_bridge.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    run_mediacrawler("xhs", "detail", specified="https://x")
            self.assertIn("exited 2", str(ctx.exception))
            self.assertIn("boom details", str(ctx.exception))

    def test_timeout_and_oserror_raise_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = make_mc_dir(Path(directory))
            for failure in (
                subprocess.TimeoutExpired(cmd="mc", timeout=MC_TIMEOUT_SECONDS),
                OSError("spawn failed"),
            ):
                with self.subTest(failure=type(failure).__name__), mock.patch.dict(
                    os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=True
                ), mock.patch(
                    "cerebellum_web_acquisition.mediacrawler_bridge.subprocess.run",
                    side_effect=failure,
                ):
                    with self.assertRaises(RuntimeError):
                        run_mediacrawler("xhs", "detail", specified="https://x")


class ReadJsonlTests(unittest.TestCase):
    def test_missing_directory_yields_no_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(read_jsonl(Path(directory), "xhs", "detail", "contents"), [])

    def test_bad_and_non_dict_lines_are_skipped_and_files_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "xhs" / "jsonl"
            out_dir.mkdir(parents=True)
            first = out_dir / "detail_contents_2026-08-28.jsonl"
            second = out_dir / "detail_contents_2026-08-29.jsonl"
            second.write_text(
                "\n".join(
                    [
                        json.dumps({"note_id": "b"}),
                        "not json at all",
                        json.dumps(["a", "list"]),
                        "",
                        json.dumps({"note_id": "c"}),
                    ]
                ),
                encoding="utf-8",
            )
            first.write_text(json.dumps({"note_id": "a"}) + "\n", encoding="utf-8")
            rows = read_jsonl(Path(directory), "xhs", "detail", "contents")
        self.assertEqual([row["note_id"] for row in rows], ["a", "b", "c"])


class ParseHeatTests(unittest.TestCase):
    def test_numeric_and_garbage_values(self) -> None:
        self.assertEqual(_parse_heat("512"), 512)
        self.assertEqual(_parse_heat(7), 7)
        self.assertEqual(_parse_heat(None), 0)
        self.assertEqual(_parse_heat("abc"), 0)
        self.assertEqual(_parse_heat(""), 0)


class ComposeDetailTextTests(unittest.TestCase):
    def test_empty_contents_yield_empty_pair(self) -> None:
        self.assertEqual(compose_detail_text([], []), ("", ""))

    def test_title_falls_back_to_desc_prefix(self) -> None:
        desc = "很长的一段描述" * 30
        title, text = compose_detail_text([{"desc": desc}], [])
        self.assertEqual(title, desc[:80])
        self.assertEqual(text, f"{title}\n\n{desc}")

    def test_title_only_without_desc(self) -> None:
        title, text = compose_detail_text([{"title": "标题"}], [])
        self.assertEqual((title, text), ("标题", "标题"))

    def test_comments_ranked_by_heat_and_blank_skipped(self) -> None:
        comments = [
            {"content": "中等", "like_count": "5"},
            {"content": "   ", "like_count": 999},
            {"content": "最热", "like_count": 100},
            {"content": "未知热度", "like_count": "abc"},
        ]
        _, text = compose_detail_text([{"title": "T", "desc": "D"}], comments)
        self.assertIn("评论：\n- 最热（赞 100）\n- 中等（赞 5）\n- 未知热度（赞 0）", text)
        self.assertNotIn("999", text)

    def test_comment_cap_is_enforced(self) -> None:
        comments = [{"content": f"评论{i}", "like_count": i} for i in range(25)]
        _, text = compose_detail_text([{"title": "T"}], comments, max_comments=20)
        self.assertEqual(text.count("（赞"), 20)
        self.assertIn("评论24", text)
        self.assertNotIn("评论4（赞 4）", text)


if __name__ == "__main__":
    unittest.main()
