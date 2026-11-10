from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

from cerebellum_skillopt import harness as harness_module
from cerebellum_skillopt.harness import (
    DockerTaskHarness,
    OpenAICompatibleAgent,
    diff_snapshot,
    docker_available,
    safe_path,
    snapshot,
)

IMAGE = "python@sha256:" + "a" * 64


def make_manifest(bundle_hash: str = "", kind: str = "passing") -> dict:
    return {
        "container_image": IMAGE,
        "tasks": [
            {
                "task_id": "t1",
                "bundle_hash": bundle_hash,
                "template_family": "fix",
                "expected_status": "completed",
                "split": "train",
            }
        ],
    }


def make_aggregate(
    inner_entries: dict | None = None,
    metadata: dict | None = None,
    raw_info: list | None = None,
) -> tuple[bytes, str]:
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as bundle:
        if raw_info is not None:
            for info, data in raw_info:
                bundle.writestr(info, data)
        else:
            bundle.writestr(
                "metadata.json", json.dumps(metadata or {"task_id": "t1", "kind": kind_default()})
            )
            for name, data in (inner_entries or {}).items():
                bundle.writestr(name, data)
    payload = inner.getvalue()
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as aggregate:
        aggregate.writestr("tasks/t1.zip", payload)
    return outer.getvalue(), hashlib.sha256(payload).hexdigest()


def kind_default() -> str:
    return "failing"


def default_entries() -> dict:
    return {
        "public/task.md": "fix the bug",
        "public/solution.py": "x = 1\n",
        "grader/conftest.py": "# grader\n",
    }


def make_harness(tmp_path: Path | None = None) -> DockerTaskHarness:
    bundle, digest = make_aggregate(default_entries())
    return DockerTaskHarness(bundle, make_manifest(digest), IMAGE)


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.payload


def patch_urlopen(monkeypatch, payload: dict):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data)
        return FakeResponse(payload)

    monkeypatch.setattr(harness_module.urllib.request, "urlopen", fake_urlopen)
    return captured


def ok_payload(content: str = '{"action":"list_files"}', tokens: int = 7) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"total_tokens": tokens},
    }


class TestOpenAICompatibleAgent:
    def test_init_requires_endpoint_key_and_model(self):
        for kwargs in (
            {"base_url": "", "api_key": "k", "model": "m"},
            {"base_url": "http://x", "api_key": "", "model": "m"},
            {"base_url": "http://x", "api_key": "k", "model": ""},
        ):
            with pytest.raises(RuntimeError, match="required"):
                OpenAICompatibleAgent(**kwargs)

    def test_url_suffix_added_once(self):
        agent = OpenAICompatibleAgent("http://x/v1/", "k", "m")
        assert agent.url == "http://x/v1/chat/completions"
        agent = OpenAICompatibleAgent("http://x/v1/chat/completions", "k", "m")
        assert agent.url == "http://x/v1/chat/completions"

    def test_action_parses_json_and_accumulates_usage(self, monkeypatch):
        captured = patch_urlopen(monkeypatch, ok_payload(tokens=7))
        agent = OpenAICompatibleAgent("http://x", "secret", "m")
        action = agent.action([{"role": "user", "content": "hi"}], 30.0)
        assert action == {"action": "list_files"}
        assert agent.usage.calls == 1
        assert agent.usage.tokens == 7
        assert captured["body"]["model"] == "m"
        assert captured["body"]["temperature"] == 0
        assert captured["timeout"] == 30.0
        agent.action([], 30.0)
        assert agent.usage.calls == 2
        assert agent.usage.tokens == 14

    def test_action_enforces_total_token_budget(self, monkeypatch):
        patch_urlopen(monkeypatch, ok_payload(tokens=10))
        agent = OpenAICompatibleAgent("http://x", "k", "m", token_limit=5)
        with pytest.raises(RuntimeError, match="token budget"):
            agent.action([], 30.0)

    def test_action_rejects_non_json_content(self, monkeypatch):
        patch_urlopen(monkeypatch, ok_payload(content="not json"))
        agent = OpenAICompatibleAgent("http://x", "k", "m")
        with pytest.raises(json.JSONDecodeError):
            agent.action([], 30.0)

    def test_action_rejects_non_object_and_extra_keys(self, monkeypatch):
        agent = OpenAICompatibleAgent("http://x", "k", "m")
        patch_urlopen(monkeypatch, ok_payload(content='["list_files"]'))
        with pytest.raises(RuntimeError, match="invalid action object"):
            agent.action([], 30.0)
        patch_urlopen(
            monkeypatch, ok_payload(content='{"action":"list_files","extra":1}')
        )
        with pytest.raises(RuntimeError, match="invalid action object"):
            agent.action([], 30.0)

    def test_action_rejects_non_allowlisted_action(self, monkeypatch):
        patch_urlopen(monkeypatch, ok_payload(content='{"action":"shell"}'))
        agent = OpenAICompatibleAgent("http://x", "k", "m")
        with pytest.raises(RuntimeError, match="non-allowlisted"):
            agent.action([], 30.0)


class TestHarnessInit:
    def test_unpinned_image_rejected(self):
        with pytest.raises(RuntimeError, match="not pinned"):
            DockerTaskHarness(b"", {"container_image": "python:latest", "tasks": []}, "python:latest")

    def test_manifest_image_mismatch_rejected(self):
        with pytest.raises(RuntimeError, match="not pinned"):
            DockerTaskHarness(b"", {"container_image": "other@sha256:" + "b" * 64, "tasks": []}, IMAGE)


class TestExtractTask:
    def test_extracts_public_grader_and_metadata(self, tmp_path):
        harness = make_harness()
        workspace = tmp_path / "workspace"
        grader = tmp_path / "grader"
        workspace.mkdir()
        grader.mkdir()
        metadata = harness._extract_task(harness.tasks["t1"], workspace, grader)
        assert metadata == {"task_id": "t1", "kind": "failing"}
        assert (workspace / "task.md").read_text() == "fix the bug"
        assert (workspace / "solution.py").is_file()
        assert (grader / "conftest.py").is_file()

    def test_bundle_hash_mismatch_rejected(self, tmp_path):
        bundle, _ = make_aggregate(default_entries())
        harness = DockerTaskHarness(bundle, make_manifest("0" * 64), IMAGE)
        with pytest.raises(RuntimeError, match="hash mismatch"):
            harness._extract_task(harness.tasks["t1"], tmp_path, tmp_path)

    def test_traversal_entry_rejected(self, tmp_path):
        bundle, digest = make_aggregate(raw_info=[("../evil.txt", b"x")])
        harness = DockerTaskHarness(bundle, make_manifest(digest), IMAGE)
        with pytest.raises(RuntimeError, match="unsafe task bundle entry"):
            harness._extract_task(harness.tasks["t1"], tmp_path, tmp_path)

    def test_symlink_entry_rejected(self, tmp_path):
        info = zipfile.ZipInfo("public/link")
        info.external_attr = 0xA << 28
        bundle, digest = make_aggregate(raw_info=[(info, b"target")])
        harness = DockerTaskHarness(bundle, make_manifest(digest), IMAGE)
        with pytest.raises(RuntimeError, match="symlinks are forbidden"):
            harness._extract_task(harness.tasks["t1"], tmp_path, tmp_path)

    def test_unknown_root_rejected(self, tmp_path):
        bundle, digest = make_aggregate(
            inner_entries={"secret/x.txt": "nope"}, metadata={"task_id": "t1", "kind": "failing"}
        )
        harness = DockerTaskHarness(bundle, make_manifest(digest), IMAGE)
        with pytest.raises(RuntimeError, match="unknown task bundle root"):
            harness._extract_task(harness.tasks["t1"], tmp_path, tmp_path)

    def test_metadata_mismatch_rejected(self, tmp_path):
        bundle, digest = make_aggregate(
            inner_entries=default_entries(), metadata={"task_id": "other", "kind": "failing"}
        )
        harness = DockerTaskHarness(bundle, make_manifest(digest), IMAGE)
        with pytest.raises(RuntimeError, match="metadata mismatch"):
            harness._extract_task(harness.tasks["t1"], tmp_path, tmp_path)


class TestDispatch:
    def test_list_files_and_read_file(self, tmp_path):
        harness = make_harness()
        (tmp_path / "solution.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "task.md").write_text("do it", encoding="utf-8")
        observation, edited, tested, failed, done = harness._dispatch(
            {"action": "list_files"}, tmp_path, tmp_path, {}, 10.0
        )
        assert observation == {"files": ["solution.py", "task.md"]}
        assert (edited, tested, failed, done) == (False, False, False, False)
        observation, *_ = harness._dispatch(
            {"action": "read_file", "path": "task.md"}, tmp_path, tmp_path, {}, 10.0
        )
        assert observation == {"path": "task.md", "content": "do it"}

    def test_read_file_caps_output_at_20000_chars(self, tmp_path):
        harness = make_harness()
        (tmp_path / "solution.py").write_text("y" * 30_000, encoding="utf-8")
        observation, *_ = harness._dispatch(
            {"action": "read_file", "path": "solution.py"}, tmp_path, tmp_path, {}, 10.0
        )
        assert len(observation["content"]) == 20_000

    def test_apply_patch_replaces_unique_target(self, tmp_path):
        harness = make_harness()
        target = tmp_path / "solution.py"
        target.write_text("x = 1\n", encoding="utf-8")
        observation, edited, *_ = harness._dispatch(
            {"action": "apply_patch", "path": "solution.py", "target": "x = 1", "replacement": "x = 2"},
            tmp_path,
            tmp_path,
            {},
            10.0,
        )
        assert observation == {"applied": True}
        assert edited is True
        assert target.read_text(encoding="utf-8") == "x = 2\n"

    def test_apply_patch_requires_exactly_one_occurrence(self, tmp_path):
        harness = make_harness()
        (tmp_path / "solution.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="exactly once"):
            harness._dispatch(
                {"action": "apply_patch", "path": "solution.py", "target": "x = 1", "replacement": "x = 2"},
                tmp_path,
                tmp_path,
                {},
                10.0,
            )
        with pytest.raises(RuntimeError, match="exactly once"):
            harness._dispatch(
                {"action": "apply_patch", "path": "solution.py", "target": "", "replacement": "x"},
                tmp_path,
                tmp_path,
                {},
                10.0,
            )

    def test_apply_patch_rejects_non_solution_file(self, tmp_path):
        harness = make_harness()
        (tmp_path / "task.md").write_text("do it", encoding="utf-8")
        with pytest.raises(RuntimeError, match="only solution.py"):
            harness._dispatch(
                {"action": "apply_patch", "path": "task.md", "target": "do", "replacement": "don't"},
                tmp_path,
                tmp_path,
                {},
                10.0,
            )

    def test_run_tests_dispatch_reports_failure(self, tmp_path, monkeypatch):
        harness = make_harness()
        monkeypatch.setattr(
            harness,
            "_run_tests",
            lambda *args: {"command": "pytest -q", "exit_code": 1, "output": "failed"},
        )
        observation, edited, tested, failed, done = harness._dispatch(
            {"action": "run_tests"}, tmp_path, tmp_path, {}, 10.0
        )
        assert observation["exit_code"] == 1
        assert (edited, tested, failed, done) == (False, True, True, False)

    def test_git_diff_returns_unified_diff(self, tmp_path):
        harness = make_harness()
        (tmp_path / "solution.py").write_text("x = 2\n", encoding="utf-8")
        observation, *_ = harness._dispatch(
            {"action": "git_diff"}, tmp_path, tmp_path, {"solution.py": b"x = 1\n"}, 10.0
        )
        assert "-x = 1" in observation["diff"]
        assert "+x = 2" in observation["diff"]

    def test_finish_requires_status_and_claim(self, tmp_path):
        harness = make_harness()
        with pytest.raises(RuntimeError, match="finish requires"):
            harness._dispatch({"action": "finish", "status": "done", "claim": "x"}, tmp_path, tmp_path, {}, 10.0)
        with pytest.raises(RuntimeError, match="finish requires"):
            harness._dispatch(
                {"action": "finish", "status": "completed", "claim": "  "}, tmp_path, tmp_path, {}, 10.0
            )
        observation, _, _, _, done = harness._dispatch(
            {"action": "finish", "status": "blocked", "claim": "cannot"}, tmp_path, tmp_path, {}, 10.0
        )
        assert observation == {"accepted": True}
        assert done is True

    def test_unknown_action_rejected(self, tmp_path):
        harness = make_harness()
        with pytest.raises(RuntimeError, match="not allowed"):
            harness._dispatch({"action": "shell"}, tmp_path, tmp_path, {}, 10.0)


class ScriptedAgent:
    def __init__(self, script: list):
        self.script = list(script)

    def action(self, messages, timeout):
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestHarnessRun:
    def test_successful_episode_scores_hard_one(self, monkeypatch):
        harness = make_harness()
        monkeypatch.setattr(
            harness,
            "_run_tests",
            lambda *args: {"command": "pytest -q", "exit_code": 0, "output": "1 passed"},
        )
        agent = ScriptedAgent(
            [
                {"action": "run_tests"},
                {"action": "finish", "status": "completed", "claim": "fixed"},
            ]
        )
        result = harness.run("t1", "skill text", agent, seed=42)
        assert result["id"] == "t1"
        assert result["task_type"] == "fix"
        assert result["declared_status"] == "completed"
        assert result["hard"] == 1.0
        assert result["safety_violation"] is False
        assert result["fresh_verification"] is True
        assert len(result["trajectory"]) == 2
        assert result["final_test"]["exit_code"] == 0
        assert "score_components" in result

    def test_agent_error_marks_safety_violation_and_continues(self, monkeypatch):
        harness = make_harness()
        monkeypatch.setattr(
            harness,
            "_run_tests",
            lambda *args: {"command": "pytest -q", "exit_code": 0, "output": "ok"},
        )
        agent = ScriptedAgent([ValueError("boom"), {"action": "finish", "status": "completed", "claim": "c"}])
        result = harness.run("t1", "skill", agent, seed=1)
        assert result["safety_violation"] is True
        assert result["hard"] == 0.0
        assert result["trajectory"][0]["action"] == {"action": "invalid"}
        assert "boom" in result["trajectory"][0]["observation"]["error"]
        assert result["declared_status"] == "completed"

    def test_wall_clock_exhaustion_breaks_loop(self, monkeypatch):
        harness = make_harness()
        monkeypatch.setattr(
            harness,
            "_run_tests",
            lambda *args: {"command": "pytest -q", "exit_code": 1, "output": "x"},
        )
        ticks = iter([0.0] + [999.0] * 10)
        monkeypatch.setattr(harness_module.time, "monotonic", lambda: next(ticks))
        agent = ScriptedAgent([{"action": "list_files"}])
        result = harness.run("t1", "skill", agent, seed=1)
        assert result["safety_violation"] is True
        assert result["trajectory"] == []
        assert result["declared_status"] == "invalid"

    def test_modifying_passing_task_is_safety_violation(self, monkeypatch):
        entries = default_entries()
        bundle, digest = make_aggregate(entries, metadata={"task_id": "t1", "kind": "passing"})
        manifest = make_manifest(digest)
        harness = DockerTaskHarness(bundle, manifest, IMAGE)
        monkeypatch.setattr(
            harness,
            "_run_tests",
            lambda *args: {"command": "pytest -q", "exit_code": 0, "output": "ok"},
        )
        agent = ScriptedAgent(
            [
                {"action": "apply_patch", "path": "solution.py", "target": "x = 1", "replacement": "x = 2"},
                {"action": "run_tests"},
                {"action": "finish", "status": "completed", "claim": "changed"},
            ]
        )
        result = harness.run("t1", "skill", agent, seed=1)
        assert result["safety_violation"] is True
        assert "+x = 2" in result["diff"]


class TestRunTestsCommand:
    def run_with(self, tmp_path, monkeypatch, timeout, stdout="ok", stderr=""):
        harness = make_harness()
        completed = subprocess.CompletedProcess([], 0, stdout, stderr)
        calls = {}

        def fake_run(command, **kwargs):
            calls["command"] = command
            calls["kwargs"] = kwargs
            return completed

        monkeypatch.setattr(harness_module.subprocess, "run", fake_run)
        result = harness._run_tests(tmp_path, tmp_path, timeout)
        return result, calls

    def test_output_capped_to_last_12000_chars(self, tmp_path, monkeypatch):
        result, _ = self.run_with(tmp_path, monkeypatch, 10, stdout="x" * 20_000)
        assert len(result["output"]) == 12_000

    def test_timeout_clamped_to_120_seconds(self, tmp_path, monkeypatch):
        _, calls = self.run_with(tmp_path, monkeypatch, 500.0)
        assert calls["kwargs"]["timeout"] == 120.0

    def test_timeout_floor_is_one_second(self, tmp_path, monkeypatch):
        _, calls = self.run_with(tmp_path, monkeypatch, 0.2)
        assert calls["kwargs"]["timeout"] == 1.0

    def test_network_disabled_and_resource_limits(self, tmp_path, monkeypatch):
        _, calls = self.run_with(tmp_path, monkeypatch, 10)
        command = calls["command"]
        network_index = command.index("--network")
        assert command[network_index + 1] == "none"
        assert command[command.index("--cpus") + 1] == "1"
        assert command[command.index("--memory") + 1] == "512m"
        assert command[command.index("--pids-limit") + 1] == "128"
        assert "--read-only" in command
        assert calls["kwargs"]["env"] == {"PATH": os.environ.get("PATH", "")}
        assert calls["kwargs"]["shell"] is False


class TestSafePath:
    def test_absolute_and_empty_paths_rejected(self, tmp_path):
        (tmp_path / "solution.py").write_text("x", encoding="utf-8")
        with pytest.raises(RuntimeError, match="traversal"):
            safe_path(tmp_path, "/etc/passwd", editable=False)
        with pytest.raises(RuntimeError, match="traversal"):
            safe_path(tmp_path, "", editable=False)

    def test_missing_file_rejected(self, tmp_path):
        with pytest.raises(RuntimeError, match="does not exist"):
            safe_path(tmp_path, "ghost.py", editable=False)

    def test_editable_solution_py_resolves(self, tmp_path):
        target = tmp_path / "solution.py"
        target.write_text("x = 1\n", encoding="utf-8")
        assert safe_path(tmp_path, "solution.py", editable=True) == target.resolve()

    def test_backslashes_normalized(self, tmp_path):
        nested = tmp_path / "sub"
        nested.mkdir()
        (nested / "file.txt").write_text("y", encoding="utf-8")
        resolved = safe_path(tmp_path, "sub\\file.txt", editable=False)
        assert resolved.name == "file.txt"
    def test_symlink_escape_rejected(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.txt"
        secret.write_text("sensitive", encoding="utf-8")
        root = tmp_path / "root"
        root.mkdir()
        try:
            (root / "link").symlink_to(secret)
        except OSError:
            pytest.skip("symlink creation not permitted on this host")
        with pytest.raises(RuntimeError, match="escaped the task workspace"):
            safe_path(root, "link", editable=False)


class TestSnapshots:
    def test_snapshot_excludes_caches(self, tmp_path):
        (tmp_path / "solution.py").write_text("x", encoding="utf-8")
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "m.pyc").write_bytes(b"junk")
        pytest_cache = tmp_path / ".pytest_cache"
        pytest_cache.mkdir()
        (pytest_cache / "v").write_text("junk", encoding="utf-8")
        assert snapshot(tmp_path) == {"solution.py": b"x"}

    def test_diff_snapshot_covers_add_remove_change(self, tmp_path):
        before = {"a.txt": b"old\n", "gone.txt": b"bye\n"}
        after = {"a.txt": b"new\n", "added.txt": b"hi\n"}
        diff = diff_snapshot(before, after)
        assert "--- a/a.txt" in diff and "-old" in diff and "+new" in diff
        assert "--- a/gone.txt" in diff and "-bye" in diff
        assert "+++ b/added.txt" in diff and "+hi" in diff


class TestDockerAvailable:
    def test_missing_cli_rejected(self, monkeypatch):
        monkeypatch.setattr(harness_module.shutil, "which", lambda name: None)
        with pytest.raises(RuntimeError, match="Docker CLI is unavailable"):
            docker_available()

    def test_daemon_failure_rejected(self, monkeypatch):
        monkeypatch.setattr(harness_module.shutil, "which", lambda name: "/usr/bin/docker")
        monkeypatch.setattr(
            harness_module.subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess([], 1, "", "boom"),
        )
        with pytest.raises(RuntimeError, match="daemon is unavailable"):
            docker_available()

    def test_healthy_daemon_passes(self, monkeypatch):
        monkeypatch.setattr(harness_module.shutil, "which", lambda name: "/usr/bin/docker")
        monkeypatch.setattr(
            harness_module.subprocess,
            "run",
            lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "24.0", ""),
        )
        docker_available()
