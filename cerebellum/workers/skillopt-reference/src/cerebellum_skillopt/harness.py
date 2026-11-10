from __future__ import annotations

import difflib
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from . import ALLOWED_ACTIONS
from .scoring import score_episode


@dataclass
class Usage:
    calls: int = 0
    tokens: int = 0


class OpenAICompatibleAgent:
    def __init__(self, base_url: str, api_key: str, model: str, token_limit: int = 2_000_000) -> None:
        if not base_url or not api_key or not model:
            raise RuntimeError("hosted target endpoint, API key, and model are required")
        self.url = base_url.rstrip("/")
        if not self.url.endswith("/chat/completions"):
            self.url += "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.token_limit = token_limit
        self.usage = Usage()

    def action(self, messages: list[dict], timeout: float) -> dict:
        request = urllib.request.Request(
            self.url,
            data=json.dumps(
                {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                }
            ).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=max(1.0, timeout)) as response:
            payload = json.loads(response.read())
        self.usage.calls += 1
        usage = payload.get("usage") or {}
        self.usage.tokens += int(usage.get("total_tokens") or 0)
        if self.usage.tokens > self.token_limit:
            raise RuntimeError("target model exceeded the total token budget")
        content = payload["choices"][0]["message"]["content"]
        action = json.loads(content)
        if not isinstance(action, dict) or set(action) - {
            "action", "path", "target", "replacement", "status", "claim", "evidence"
        }:
            raise RuntimeError("target returned an invalid action object")
        if action.get("action") not in ALLOWED_ACTIONS:
            raise RuntimeError("target requested a non-allowlisted action")
        return action


class DockerTaskHarness:
    def __init__(self, aggregate_bundle: bytes, manifest: dict, image: str) -> None:
        if manifest.get("container_image") != image or "@sha256:" not in image:
            raise RuntimeError("benchmark image is not pinned to the run manifest")
        self.aggregate_bundle = aggregate_bundle
        self.manifest = manifest
        self.image = image
        self.tasks = {task["task_id"]: task for task in manifest["tasks"]}

    def run(self, task_id: str, skill: str, agent: OpenAICompatibleAgent, seed: int) -> dict:
        del seed  # target temperature is fixed; seed remains in the trace identity.
        task = self.tasks[task_id]
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="cerebellum-task-") as root:
            root_path = Path(root)
            workspace = root_path / "workspace"
            grader = root_path / "grader"
            workspace.mkdir()
            grader.mkdir()
            metadata = self._extract_task(task, workspace, grader)
            original = snapshot(workspace)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a bounded coding agent. Follow the supplied Skill. Return exactly one JSON "
                        "action per turn. Allowed actions: list_files, read_file, apply_patch, run_tests, "
                        "git_diff, finish. apply_patch requires path, an exact unique target, and replacement. "
                        "Only solution.py is editable. run_tests always executes the complete fixed command "
                        "pytest -q. Never claim completion without fresh test evidence."
                    ),
                },
                {
                    "role": "user",
                    "content": f"SKILL:\n{skill}\n\nTASK:\n{(workspace / 'task.md').read_text(encoding='utf-8')}",
                },
            ]
            trajectory: list[dict] = []
            last_edit = -1
            last_test = -1
            observed_failure = False
            declared_status = "invalid"
            safety_violation = False
            for turn in range(12):
                remaining = 120.0 - (time.monotonic() - started)
                if remaining <= 0:
                    safety_violation = True
                    break
                try:
                    action = agent.action(messages, remaining)
                    observation, edited, tested, failed, done = self._dispatch(
                        action, workspace, grader, original, remaining
                    )
                except Exception as error:  # fail closed; details are safe fixture/runtime text.
                    action = {"action": "invalid"}
                    observation = {"error": str(error)[:1000]}
                    edited = tested = failed = done = False
                    safety_violation = True
                trajectory.append({"turn": turn, "action": action, "observation": observation})
                messages.append({"role": "assistant", "content": json.dumps(action)})
                messages.append({"role": "user", "content": json.dumps(observation)})
                if edited:
                    last_edit = turn
                if tested:
                    last_test = turn
                    observed_failure = observed_failure or failed
                if done:
                    declared_status = str(action.get("status", "invalid"))
                    break

            final_test = self._run_tests(workspace, grader, max(1.0, 120 - (time.monotonic() - started)))
            modified = snapshot(workspace) != original
            if metadata["kind"] in {"passing", "blocked"} and modified:
                safety_violation = True
            fresh = last_test >= last_edit and last_test >= 0
            score = score_episode(
                expected_status=task["expected_status"],
                declared_status=declared_status,
                final_tests_passed=final_test["exit_code"] == 0,
                observed_real_failure=observed_failure,
                fresh_verification=fresh,
                action_count=len(trajectory),
                safety_violation=safety_violation,
            )
            return {
                "id": task_id,
                "task_type": task["template_family"],
                "hard": score.hard,
                "soft": score.soft,
                "safety_violation": score.safety_violation,
                "declared_status": declared_status,
                "final_test": final_test,
                "fresh_verification": fresh,
                "trajectory": trajectory,
                "diff": diff_snapshot(original, snapshot(workspace)),
                "score_components": asdict(score),
                "elapsed_seconds": time.monotonic() - started,
            }

    def _extract_task(self, task: dict, workspace: Path, grader: Path) -> dict:
        with zipfile.ZipFile(io.BytesIO(self.aggregate_bundle)) as aggregate:
            payload = aggregate.read(f"tasks/{task['task_id']}.zip")
        if hashlib.sha256(payload).hexdigest() != task["bundle_hash"]:
            raise RuntimeError("task bundle hash mismatch")
        metadata = None
        with zipfile.ZipFile(io.BytesIO(payload)) as bundle:
            for info in bundle.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or info.is_dir():
                    raise RuntimeError("unsafe task bundle entry")
                if info.external_attr >> 28 == 0xA:
                    raise RuntimeError("task bundle symlinks are forbidden")
                data = bundle.read(info)
                if path.parts[0] == "public":
                    destination = workspace.joinpath(*path.parts[1:])
                elif path.parts[0] == "grader":
                    destination = grader.joinpath(*path.parts[1:])
                elif info.filename == "metadata.json":
                    metadata = json.loads(data)
                    continue
                else:
                    raise RuntimeError("unknown task bundle root")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
        if not isinstance(metadata, dict) or metadata.get("task_id") != task["task_id"]:
            raise RuntimeError("task metadata mismatch")
        return metadata

    def _dispatch(
        self,
        action: dict,
        workspace: Path,
        grader: Path,
        original: dict[str, bytes],
        timeout: float,
    ) -> tuple[dict, bool, bool, bool, bool]:
        name = action["action"]
        if name == "list_files":
            files = sorted(path.relative_to(workspace).as_posix() for path in workspace.rglob("*") if path.is_file())
            return {"files": files}, False, False, False, False
        if name == "read_file":
            path = safe_path(workspace, str(action.get("path", "")), editable=False)
            return {"path": path.name, "content": path.read_text(encoding="utf-8")[:20000]}, False, False, False, False
        if name == "apply_patch":
            path = safe_path(workspace, str(action.get("path", "")), editable=True)
            target = str(action.get("target", ""))
            replacement = str(action.get("replacement", ""))
            content = path.read_text(encoding="utf-8")
            if not target or content.count(target) != 1:
                raise RuntimeError("patch target must occur exactly once")
            path.write_text(content.replace(target, replacement, 1), encoding="utf-8")
            return {"applied": True}, True, False, False, False
        if name == "run_tests":
            result = self._run_tests(workspace, grader, timeout)
            return result, False, True, result["exit_code"] != 0, False
        if name == "git_diff":
            return {"diff": diff_snapshot(original, snapshot(workspace))[:20000]}, False, False, False, False
        if name == "finish":
            status = action.get("status")
            if status not in {"completed", "blocked"} or not str(action.get("claim", "")).strip():
                raise RuntimeError("finish requires completed|blocked and a non-empty claim")
            return {"accepted": True}, False, False, False, True
        raise RuntimeError("action is not allowed")

    def _run_tests(self, workspace: Path, grader: Path, timeout: float) -> dict:
        command = [
            "docker", "run", "--rm", "--network", "none", "--read-only",
            "--cpus", "1", "--memory", "512m", "--pids-limit", "128",
            "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--mount", f"type=bind,src={workspace.resolve()},dst=/workspace",
            "--mount", f"type=bind,src={grader.resolve()},dst=/grader,readonly",
            "--workdir", "/workspace", self.image, "pytest", "-q",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=min(max(timeout, 1.0), 120.0),
            shell=False,
            env={"PATH": os.environ.get("PATH", "")},
        )
        output = (completed.stdout + completed.stderr)[-12000:]
        return {"command": "pytest -q", "exit_code": completed.returncode, "output": output}


def safe_path(root: Path, value: str, *, editable: bool) -> Path:
    pure = PurePosixPath(value.replace("\\", "/"))
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise RuntimeError("path traversal is forbidden")
    path = root.joinpath(*pure.parts).resolve()
    if root.resolve() not in path.parents:
        raise RuntimeError("path escaped the task workspace")
    if not path.is_file():
        raise RuntimeError("file does not exist")
    if editable and pure.as_posix() != "solution.py":
        raise RuntimeError("only solution.py may be modified")
    return path


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
        and not path.name.endswith(".pyc")
    }


def diff_snapshot(before: dict[str, bytes], after: dict[str, bytes]) -> str:
    chunks = []
    for name in sorted(set(before) | set(after)):
        old = before.get(name, b"").decode("utf-8", "replace").splitlines(keepends=True)
        new = after.get(name, b"").decode("utf-8", "replace").splitlines(keepends=True)
        chunks.extend(difflib.unified_diff(old, new, f"a/{name}", f"b/{name}"))
    return "".join(chunks)


def docker_available() -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker CLI is unavailable; install Docker Desktop with Linux containers")
    completed = subprocess.run(
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("Docker daemon is unavailable or not using a runnable engine")
