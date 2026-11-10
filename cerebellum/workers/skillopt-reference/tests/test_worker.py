from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from cerebellum_skillopt.driver import body_replacement_patch, bootstrap_low
from cerebellum_skillopt.adapter import objective_gate
from cerebellum_skillopt.harness import DockerTaskHarness, OpenAICompatibleAgent, safe_path
from cerebellum_skillopt.scoring import score_episode


class WorkerSafetyTests(unittest.TestCase):
    def test_scoring_formula_is_objective(self):
        score = score_episode(
            expected_status="completed",
            declared_status="completed",
            final_tests_passed=True,
            observed_real_failure=False,
            fresh_verification=True,
            action_count=1,
            safety_violation=False,
        )
        self.assertEqual(score.hard, 1.0)
        self.assertAlmostEqual(score.soft, 1.0)

    def test_path_traversal_and_test_mutation_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "solution.py").write_text("x = 1\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_x.py").write_text("", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                safe_path(root, "../secret", editable=False)
            with self.assertRaises(RuntimeError):
                safe_path(root, "tests/test_x.py", editable=True)

    def test_docker_test_command_has_all_hard_limits(self):
        harness = DockerTaskHarness(
            b"unused",
            {"container_image": "python@sha256:" + "a" * 64, "tasks": []},
            "python@sha256:" + "a" * 64,
        )
        completed = type("Completed", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as grader:
            with patch("subprocess.run", return_value=completed) as run:
                result = harness._run_tests(Path(workspace), Path(grader), 10)
            command = run.call_args.args[0]
            self.assertEqual(command[-2:], ["pytest", "-q"])
            self.assertIn("none", command)
            self.assertIn("--read-only", command)
            self.assertIn("512m", command)
            self.assertIn("ALL", command)
            self.assertEqual(result["command"], "pytest -q")

    def test_frontmatter_cannot_be_changed_by_candidate_patch(self):
        baseline = "---\nname: verify\n---\nOld body\n"
        candidate = "---\nname: attacker\n---\nNew body\n"
        self.assertIsNone(
            body_replacement_patch(
                "11111111-1111-4111-8111-111111111111", 1, baseline, candidate, "optimizer", "a" * 64
            )
        )

    def test_bootstrap_matches_positive_paired_gain(self):
        scores = [{"baseline_hard": 0.0, "candidate_hard": 1.0} for _ in range(30)]
        self.assertEqual(bootstrap_low(scores), 1.0)

    def test_objective_gate_denies_a_single_regression(self):
        baseline = {
            "a": {"hard": 1.0, "soft": 0.5},
            "b": {"hard": 0.0, "soft": 0.5},
        }
        candidate = {
            "a": {"hard": 0.0, "soft": 1.0, "safety_violation": False},
            "b": {"hard": 1.0, "soft": 1.0, "safety_violation": False},
        }
        self.assertFalse(objective_gate(baseline, candidate))


class FakeOpenAITests(unittest.TestCase):
    def test_json_action_and_usage_from_compatible_service(self):
        seen = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen["authorization"] = self.headers.get("Authorization")
                length = int(self.headers["Content-Length"])
                json.loads(self.rfile.read(length))
                payload = json.dumps(
                    {
                        "choices": [{"message": {"content": '{"action":"list_files"}'}}],
                        "usage": {"total_tokens": 7},
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            agent = OpenAICompatibleAgent(f"http://127.0.0.1:{server.server_port}/v1", "secret", "fake")
            action = agent.action([{"role": "user", "content": "task"}], 10)
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(action, {"action": "list_files"})
        self.assertEqual(agent.usage.tokens, 7)
        self.assertEqual(seen["authorization"], "Bearer secret")


if __name__ == "__main__":
    unittest.main()
