from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cerebellum_social_acquisition.mediacrawler import (
    MC_TIMEOUT_SECONDS,
    _iso_from_epoch,
    _parse_heat,
    _safe_environment,
    _venv_python,
    compose_detail_text,
    configured_dir,
    content_to_board_item,
    read_jsonl,
    run_mediacrawler,
)


def make_install(root: Path) -> Path:
    """Materialize a minimal fake MediaCrawler install (main.py + .venv python)."""
    mc_dir = root / "MediaCrawler"
    mc_dir.mkdir(parents=True)
    (mc_dir / "main.py").write_text("# fake", encoding="utf-8")
    venv = mc_dir / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    venv.mkdir(parents=True)
    (venv / ("python.exe" if sys.platform == "win32" else "python")).write_text(
        "# fake", encoding="utf-8"
    )
    return mc_dir


class SafeEnvironmentTests(unittest.TestCase):
    def test_only_allowlisted_variables_pass_through(self) -> None:
        env = {"PATH": "/usr/bin", "HOME": "/home/x", "CEREBELLUM_TOKEN": "secret", "AWS_KEY": "x"}
        with mock.patch.dict(os.environ, env, clear=True):
            safe = _safe_environment()
        self.assertEqual(set(safe), {"PATH", "HOME"})
        self.assertNotIn("secret", json.dumps(safe))


class VenvPythonTests(unittest.TestCase):
    def test_missing_venv_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(_venv_python(Path(directory)))

    def test_finds_platform_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = make_install(Path(directory))
            found = _venv_python(mc_dir)
        self.assertIsNotNone(found)
        assert found is not None
        self.assertIn("python", found.name)


class ConfiguredDirTests(unittest.TestCase):
    def test_unset_returns_none(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(configured_dir())

    def test_missing_directory_returns_none(self) -> None:
        with mock.patch.dict(
            os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": "E:/no/such/mc"}, clear=False
        ):
            self.assertIsNone(configured_dir())

    def test_missing_main_py_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": directory}, clear=False
            ):
                self.assertIsNone(configured_dir())

    def test_missing_venv_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "main.py").write_text("# fake", encoding="utf-8")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": directory}, clear=False
            ):
                self.assertIsNone(configured_dir())

    def test_complete_install_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = make_install(Path(directory))
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=False
            ):
                self.assertEqual(configured_dir(), mc_dir)


class RunMediacrawlerTests(unittest.TestCase):
    def test_unconfigured_raises(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.mediacrawler.configured_dir", return_value=None
        ):
            with self.assertRaisesRegex(RuntimeError, "not configured"):
                run_mediacrawler("xhs", "search", keywords="滑雪")
    def test_venv_missing_raises(self) -> None:
        with mock.patch(
            "cerebellum_social_acquisition.mediacrawler.configured_dir",
            return_value=Path("E:/fake/mc"),
        ), mock.patch(
            "cerebellum_social_acquisition.mediacrawler._venv_python", return_value=None
        ):
            with self.assertRaisesRegex(RuntimeError, "venv is missing"):
                run_mediacrawler("xhs", "search", keywords="滑雪")

    def _install(self, directory: str) -> Path:
        return make_install(Path(directory))

    def test_nonzero_exit_raises_with_stderr_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = self._install(directory)
            completed = subprocess.CompletedProcess(
                args=[], returncode=2, stdout=b"", stderr=b"traceback tail here"
            )
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=False
            ), mock.patch(
                "cerebellum_social_acquisition.mediacrawler.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaisesRegex(RuntimeError, "exited 2: traceback tail here"):
                    run_mediacrawler("xhs", "search", keywords="滑雪")

    def test_timeout_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = self._install(directory)
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=False
            ), mock.patch(
                "cerebellum_social_acquisition.mediacrawler.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="main.py", timeout=MC_TIMEOUT_SECONDS),
            ):
                with self.assertRaisesRegex(RuntimeError, "subprocess failed"):
                    run_mediacrawler("xhs", "search", keywords="滑雪")

    def test_oserror_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = self._install(directory)
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=False
            ), mock.patch(
                "cerebellum_social_acquisition.mediacrawler.subprocess.run",
                side_effect=OSError("spawn failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "subprocess failed"):
                    run_mediacrawler("dy", "detail", specified="7331")

    def test_command_shape_and_sanitized_env(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = self._install(directory)
            completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            captured: dict = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                captured["kwargs"] = kwargs
                return completed

            with mock.patch.dict(
                os.environ,
                {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir), "LEAK_ME": "should-not-pass"},
                clear=False,
            ), mock.patch(
                "cerebellum_social_acquisition.mediacrawler.subprocess.run",
                side_effect=fake_run,
            ):
                tmp = run_mediacrawler("bili", "detail", specified="BV1", notes_limit=7)
        self.assertTrue(tmp.name.startswith("cerebellum-mc-"))
        command = captured["command"]
        self.assertEqual(command[1], "main.py")
        joined = " ".join(command)
        self.assertIn("--platform bili", joined)
        self.assertIn("--type detail", joined)
        self.assertIn("--specified_id BV1", joined)
        self.assertNotIn("--keywords", joined)
        self.assertIn("--crawler_max_notes_count 7", joined)
        self.assertEqual(captured["kwargs"]["cwd"], mc_dir)
        self.assertEqual(captured["kwargs"]["timeout"], MC_TIMEOUT_SECONDS)
        self.assertFalse(captured["kwargs"]["shell"])
        self.assertNotIn("LEAK_ME", captured["kwargs"]["env"])

    def test_search_command_includes_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            mc_dir = self._install(directory)
            completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            with mock.patch.dict(
                os.environ, {"CEREBELLUM_MEDIACRAWLER_DIR": str(mc_dir)}, clear=False
            ), mock.patch(
                "cerebellum_social_acquisition.mediacrawler.subprocess.run",
                return_value=completed,
            ) as run_mock:
                run_mediacrawler("xhs", "search", keywords="滑雪 装备", notes_limit=15)
        command = run_mock.call_args.args[0]
        joined = " ".join(command)
        self.assertIn("--keywords 滑雪 装备", joined)
        self.assertNotIn("--specified_id", joined)


class ReadJsonlEdgeTests(unittest.TestCase):
    def test_skips_blank_lines_and_non_dict_rows(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mc-jsonl-extra-"))
        out_dir = tmp / "xhs" / "jsonl"
        out_dir.mkdir(parents=True)
        with open(out_dir / "search_contents_2026-08-30.jsonl", "w", encoding="utf-8") as handle:
            handle.write("\n")
            handle.write("   \n")
            handle.write('["list", "row"]\n')
            handle.write('"plain string"\n')
            handle.write(json.dumps({"note_id": "ok"}) + "\n")
        rows = read_jsonl(tmp, "xhs", "search", "contents")
        self.assertEqual(rows, [{"note_id": "ok"}])

    def test_multiple_files_concatenated_in_order(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="mc-jsonl-multi-"))
        out_dir = tmp / "dy" / "jsonl"
        out_dir.mkdir(parents=True)
        for day, aweme_id in (("2026-08-28", "a1"), ("2026-08-29", "a2")):
            with open(out_dir / f"search_contents_{day}.jsonl", "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"aweme_id": aweme_id}) + "\n")
        rows = read_jsonl(tmp, "dy", "search", "contents")
        self.assertEqual([row["aweme_id"] for row in rows], ["a1", "a2"])


class TimeAndHeatTests(unittest.TestCase):
    def test_iso_from_epoch_edges(self) -> None:
        self.assertIsNone(_iso_from_epoch(None))
        self.assertIsNone(_iso_from_epoch(0))
        self.assertIsNone(_iso_from_epoch(-5))
        self.assertIsNone(_iso_from_epoch("not-a-number"))
        self.assertIsNone(_iso_from_epoch(1e30))  # overflow -> None, not crash
        seconds = _iso_from_epoch(1_700_000_000)
        self.assertTrue(seconds and seconds.endswith("Z") and seconds.startswith("2023"))
        millis = _iso_from_epoch(1_700_000_000_000)
        self.assertEqual(millis, seconds)

    def test_parse_heat_edges(self) -> None:
        self.assertEqual(_parse_heat(None), 0)
        self.assertEqual(_parse_heat(""), 0)
        self.assertEqual(_parse_heat("12.9"), 0)  # not int-parseable -> 0
        self.assertEqual(_parse_heat(88), 88)
        self.assertEqual(_parse_heat("42"), 42)


class BoardItemMappingEdgeTests(unittest.TestCase):
    def test_bilibili_style_row_uses_video_keys(self) -> None:
        row = {
            "video_id": "BV1xx",
            "video_url": "https://www.bilibili.com/video/BV1xx",
            "title": "视频标题",
            "liked_count": 66,
        }
        item = content_to_board_item(row, "bilibili", 3)
        assert item is not None
        self.assertEqual(item.external_id, "BV1xx")
        self.assertEqual(item.platform, "bilibili")
        self.assertEqual(item.heat, 66)

    def test_empty_nickname_and_desc_become_none(self) -> None:
        row = {"note_id": "n1", "note_url": "https://x", "nickname": "", "desc": ""}
        item = content_to_board_item(row, "xhs", 1)
        assert item is not None
        self.assertIsNone(item.author)
        self.assertIsNone(item.summary)
        self.assertEqual(item.title, "")


class ComposeDetailEdgeTests(unittest.TestCase):
    def test_empty_contents_no_comments(self) -> None:
        title, text = compose_detail_text([], [])
        self.assertEqual(title, "")
        self.assertEqual(text, "")
        self.assertNotIn("评论", text)

    def test_title_falls_back_to_desc_prefix(self) -> None:
        long_desc = "描" * 100
        title, text = compose_detail_text([{"title": "", "desc": long_desc}], [])
        self.assertEqual(title, long_desc[:80])
        self.assertIn(long_desc, text)

    def test_max_comments_truncates_to_top_liked(self) -> None:
        comments = [{"content": f"评论{i}", "like_count": i} for i in range(5)]
        title, text = compose_detail_text([{"title": "T", "desc": ""}], comments, max_comments=2)
        self.assertIn("评论4（赞 4）", text)
        self.assertIn("评论3（赞 3）", text)
        self.assertNotIn("评论2", text)

    def test_bad_like_count_treated_as_zero(self) -> None:
        comments = [
            {"content": "坏赞", "like_count": "N/A"},
            {"content": "好赞", "like_count": 5},
        ]
        _, text = compose_detail_text([{"title": "T"}], comments)
        self.assertLess(text.index("好赞"), text.index("坏赞"))


if __name__ == "__main__":
    unittest.main()
