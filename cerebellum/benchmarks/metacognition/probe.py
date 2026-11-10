#!/usr/bin/env python3
"""Metacognition probe harness (M0).

Renders the frozen probe suites through the existing `<|meta_task|>` completion
surface against llama-server (GGUF arm) or Ollama (comparison arm), parses the
metacognition decision contract, and computes per-suite metrics.

Stdlib + requests only. No repository imports.

Usage:
  python probe.py --model <base.gguf> --llama-server <exe-or-dir> --suite all --out evidence.json
  python probe.py --ollama ornith-1.5-9b:q4_k_m --suite all --out evidence-ornith.json
  python probe.py --model <base.gguf> --llama-server <exe-or-dir> --label-kb --out kb-labeling-evidence.json
  python probe.py --dry-run
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

SUITE_DIR = Path(__file__).resolve().parent
SCORING_VERSION = "metacognition/2"
TASK_NAMES = {"tg": "temporal_grounding", "kb": "knowledge_boundary", "st": "search_planning"}
GENERATION = {"temperature": 0.0, "seed": 42, "n_predict": 512, "stop": ["<|meta_task|>"]}
LABELING_GENERATION = {"temperature": 0.7, "seeds": [42, 43, 44], "n_predict": 256}
ACTIONS = ("answer", "search_internal", "request_acquisition", "insufficient")
REFUSAL_ACTIONS = ("search_internal", "insufficient")
CONTRACT_KEYS = {"action", "as_of_used", "query", "freshness_hours", "answer",
                 "answer_basis", "confidence"}


# ------------------------------------------------------------------ parsing
def parse_contract(completion: str) -> tuple[dict | None, str | None]:
    """Extract and strictly validate the first JSON object in the completion."""
    start = completion.find("{")
    if start < 0:
        return None, "no json object"
    try:
        value, _ = json.JSONDecoder().raw_decode(completion[start:])
    except json.JSONDecodeError as exc:
        return None, f"json error: {exc.msg}"
    if not isinstance(value, dict):
        return None, "not an object"
    if set(value) != CONTRACT_KEYS:
        return None, f"key mismatch: {sorted(value)}"
    action = value["action"]
    if action not in ACTIONS:
        return None, "bad action"
    if value["as_of_used"] is not None:
        as_of = value["as_of_used"]
        if not isinstance(as_of, str) or "T" not in as_of:
            return None, "bad as_of_used"
    if value["query"] is not None and not isinstance(value["query"], str):
        return None, "bad query"
    fh = value["freshness_hours"]
    if fh is not None and (not isinstance(fh, int) or isinstance(fh, bool)
                           or not (1 <= fh <= 8760)):
        return None, "bad freshness_hours"
    if value["answer"] is not None and not isinstance(value["answer"], str):
        return None, "bad answer"
    if value["answer_basis"] not in ("parametric", "evidence", "none"):
        return None, "bad answer_basis"
    conf = value["confidence"]
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not (0 <= conf <= 1):
        return None, "bad confidence"
    return value, None


def discipline_ok(value: dict) -> bool:
    """Per-action field discipline. A shape-valid but discipline-invalid output
    is a behavioral failure (counts against accuracy), not a format failure."""
    action = value["action"]
    fh = value["freshness_hours"]
    discipline = {
        "answer": (bool(value["answer"]) and value["query"] is None
                   and fh is None and value["answer_basis"] in ("parametric", "evidence")),
        "search_internal": (bool(value["query"]) and value["answer"] is None
                            and value["answer_basis"] == "none"),
        "request_acquisition": (bool(value["query"]) and fh is not None
                                and value["answer"] is None and value["answer_basis"] == "none"),
        "insufficient": (value["answer"] is None and value["query"] is None
                         and fh is None and value["answer_basis"] == "none"),
    }
    return discipline[action]


# ------------------------------------------------------------------ scoring
def norm(text: str) -> str:
    """Per-character lowercase + alphanumeric, matching Rust's normalizer."""
    return "".join(ch for source in text for ch in source.lower() if ch.isalnum())


def tokens_match(want: "str | list[str] | None", text: str) -> bool:
    """String -> substring; list -> every group has one `|`-alternative present."""
    if want is None:
        return False
    haystack = norm(text)
    if isinstance(want, str):
        return norm(want) in haystack
    return all(any(norm(alt) in haystack for alt in group.split("|")) for group in want)


def score_item(item: dict, pred: dict | None, contract_valid: bool) -> dict:
    gold, check = item["gold"], item.get("check", {})
    if pred is None:
        return {"parsed": False, "contract_valid": False, "action_match": False,
                "as_of_match": False, "answer_match": False, "fully_correct": False,
                "stale_misuse": False, "predicted_search": False, "predicted_refusal": False}
    action_match = pred["action"] == gold["action"]
    as_of_match = pred["as_of_used"] == gold["as_of_used"]
    want_answer = check.get("answer_contains")
    answer_match = True
    if gold["action"] == "answer" and want_answer is not None:
        answer_match = pred["answer"] is not None and tokens_match(want_answer, pred["answer"])
    elif gold["action"] == "answer":
        answer_match = pred["answer"] is not None
    stale_claim = check.get("stale_claim")
    stale_misuse = (check.get("condition") == "env_stale" and pred["action"] == "answer"
                    and bool(pred["answer"]) and bool(stale_claim)
                    and norm(stale_claim) in norm(pred["answer"]))
    predicted_search = pred["action"] in ("search_internal", "request_acquisition")
    return {"parsed": True, "contract_valid": contract_valid,
            "action_match": action_match, "as_of_match": as_of_match,
            "answer_match": answer_match,
            "fully_correct": contract_valid and action_match and as_of_match and answer_match,
            "stale_misuse": stale_misuse, "predicted_search": predicted_search,
            "predicted_refusal": pred["action"] in REFUSAL_ACTIONS}


# Frozen few-shot exemplars: teach the output contract to a raw base model.
# Single source of truth: fewshot.json (manifest-pinned); the Rust adapter-eval
# harness renders from the same file so both arms of every phase agree.
def _load_fewshot() -> dict:
    doc = json.loads((SUITE_DIR / "fewshot.json").read_text(encoding="utf-8"))
    return {kind: [(e["input"], e["output"]) for e in doc["exemplars"][kind]]
            for kind in ("tg", "kb", "st")}


FEWSHOT = _load_fewshot()



# ---------------------------------------------------------------- rendering
def render_prompt(kind: str, input_obj: dict) -> str:
    parts = []
    for ex_in, ex_out in FEWSHOT[kind]:
        ex_payload = json.dumps(ex_in, ensure_ascii=False, sort_keys=True)
        ex_answer = json.dumps(ex_out, ensure_ascii=False, sort_keys=True)
        parts.append(f"<|meta_task|>{TASK_NAMES[kind]}\n<|input|>{ex_payload}\n"
                     f"<|response|>{ex_answer}\n")
    payload = json.dumps(input_obj, ensure_ascii=False, sort_keys=True)
    parts.append(f"<|meta_task|>{TASK_NAMES[kind]}\n<|input|>{payload}\n<|response|>")
    return "".join(parts)

def gold_is_search(gold: dict) -> bool:
    return gold["action"] in ("search_internal", "request_acquisition")


def suite_metrics(kind: str, rows: list[dict]) -> dict:
    total = len(rows)
    parsed = sum(1 for r in rows if r["score"]["parsed"])
    valid = sum(1 for r in rows if r["score"]["contract_valid"])
    base = {"items": total, "parse_rate": parsed / total if total else 0.0,
            "contract_valid_rate": valid / total if total else 0.0}
    if kind == "tg":
        env_rows = [r for r in rows if r["item"]["check"]["condition"] in ("env_fresh", "env_stale")]
        noenv = [r for r in rows if r["item"]["check"]["condition"] == "no_env"]
        stale = [r for r in rows if r["item"]["check"]["condition"] == "env_stale"]
        fresh = [r for r in rows if r["item"]["check"]["condition"] == "env_fresh"]

        def acc(rs):
            ok = sum(1 for r in rs if r["score"]["fully_correct"])
            return {"n": len(rs), "accuracy": ok / len(rs) if rs else None}

        base.update({
            "with_environment": acc(env_rows),
            "without_environment": acc(noenv),
            "fresh_answer_accuracy": acc(fresh),
            "as_of_echo_rate": (sum(1 for r in env_rows if r["score"]["as_of_match"])
                                / len(env_rows) if env_rows else None),
            "stale_card_misuse_rate": (sum(1 for r in stale if r["score"]["stale_misuse"])
                                       / len(stale) if stale else None),
        })
    elif kind == "kb":
        tp = fp = fn = 0
        known_rows, unknown_rows = [], []
        for r in rows:
            gold_refusal = r["item"]["gold"]["action"] in REFUSAL_ACTIONS
            pred_refusal = r["score"]["predicted_refusal"]
            if gold_refusal and pred_refusal:
                tp += 1
            elif not gold_refusal and pred_refusal:
                fp += 1
            elif gold_refusal and not pred_refusal:
                fn += 1
            (known_rows if r["item"]["check"]["condition"] == "known" else unknown_rows).append(r)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
        base.update({
            "refusal_precision": precision, "refusal_recall": recall, "refusal_f1": f1,
            "known_set_accuracy": (sum(1 for r in known_rows if r["score"]["fully_correct"])
                                   / len(known_rows) if known_rows else None),
            "unknown_action_accuracy": (sum(1 for r in unknown_rows if r["score"]["action_match"])
                                        / len(unknown_rows) if unknown_rows else None),
            "known_n": len(known_rows), "unknown_n": len(unknown_rows),
        })
    elif kind == "st":
        tp = fp = 0
        search_required, answer_rows = [], []
        per_condition: dict[str, list[bool]] = {}
        for r in rows:
            cond = r["item"]["check"]["condition"]
            per_condition.setdefault(cond, []).append(r["score"]["action_match"])
            if gold_is_search(r["item"]["gold"]):
                search_required.append(r)
                if r["score"]["predicted_search"]:
                    tp += 1
            else:
                answer_rows.append(r)
                if r["score"]["predicted_search"]:
                    fp += 1
        base.update({
            "search_trigger_precision": tp / (tp + fp) if tp + fp else None,
            "search_required_action_accuracy": (
                sum(1 for r in search_required if r["score"]["action_match"])
                / len(search_required) if search_required else None),
            "answer_condition_accuracy": (
                sum(1 for r in answer_rows if r["score"]["fully_correct"])
                / len(answer_rows) if answer_rows else None),
            "per_condition_action_match": {
                cond: {"n": len(v), "rate": sum(v) / len(v)} for cond, v in per_condition.items()},
        })
    return base


# ------------------------------------------------------------------- suites
def load_suite(kind: str) -> list[dict]:
    path = SUITE_DIR / f"{kind}.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def manifest_ok() -> dict:
    manifest_path = SUITE_DIR / "manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "reason": "manifest.json missing"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = {"ok": True, "files": {}}
    for name, entry in manifest["suites"].items():
        path = SUITE_DIR / name
        if not path.exists():
            report["files"][name] = "missing"
            report["ok"] = False
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        match = actual == entry["sha256"]
        report["files"][name] = {"match": match, "sha256": actual}
        report["ok"] = report["ok"] and match
    return report


# ------------------------------------------------------------------ backends
class LlamaServer:
    def __init__(self, exe: Path, model: Path):
        self.exe, self.model = exe, model
        self.proc: subprocess.Popen | None = None
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()

    def __enter__(self):
        self.proc = subprocess.Popen(
            [str(self.exe), "--host", "127.0.0.1", "--port", str(self.port),
             "--model", str(self.model), "--ctx-size", "4096",
             "--n-gpu-layers", "999"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 300
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server exited with {self.proc.returncode}")
            try:
                if requests.get(f"http://127.0.0.1:{self.port}/health", timeout=2).status_code == 200:
                    return self
            except requests.RequestException:
                pass
            time.sleep(1)
        raise RuntimeError("llama-server did not become healthy in 300s")

    def __exit__(self, *exc):
        if self.proc:
            self.proc.kill()
            self.proc.wait(timeout=30)

    def complete(self, prompt: str, temperature: float, seed: int, n_predict: int) -> dict:
        body = {"prompt": prompt, "temperature": temperature, "seed": seed,
                "n_predict": n_predict, "stop": GENERATION["stop"],
                "cache_prompt": False, "stream": False}
        resp = requests.post(f"http://127.0.0.1:{self.port}/completion", json=body, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return {"content": data.get("content", ""),
                "stopped_limit": data.get("stopped_limit", False),
                "tokens_in": data.get("tokens_evaluated"),
                "tokens_out": data.get("tokens_predicted")}


class OllamaBackend:
    def __init__(self, alias: str, base_url: str = "http://127.0.0.1:11434"):
        self.alias, self.base_url = alias, base_url

    def __enter__(self):
        tags = requests.get(f"{self.base_url}/api/tags", timeout=10).json()
        if not any(m.get("name") == self.alias for m in tags.get("models", [])):
            raise RuntimeError(f"ollama alias {self.alias} not installed")
        return self

    def __exit__(self, *exc):
        requests.post(f"{self.base_url}/api/generate",
                      json={"model": self.alias, "keep_alive": 0}, timeout=30)

    def complete(self, prompt: str, temperature: float, seed: int, n_predict: int) -> dict:
        # Reasoning models emit a `<think>` preamble before the contract JSON;
        # the GGUF-arm budget (512) truncates them, so the comparison arm gets
        # a larger budget. Temperature/seed/stop stay identical across arms.
        n_predict = max(n_predict, 8192)
        body = {"model": self.alias, "prompt": prompt, "raw": True, "stream": False,
                "options": {"temperature": temperature, "seed": seed,
                            "num_predict": n_predict, "stop": GENERATION["stop"]}}
        resp = requests.post(f"{self.base_url}/api/generate", json=body, timeout=600)
        resp.raise_for_status()
        data = resp.json()
        return {"content": data.get("response", ""), "stopped_limit": False,
                "tokens_in": data.get("prompt_eval_count"),
                "tokens_out": data.get("eval_count")}


def resolve_llama_server(arg: str) -> Path:
    path = Path(arg)
    if path.is_dir():
        path = path / ("llama-server.exe" if sys.platform == "win32" else "llama-server")
    if not path.exists():
        raise SystemExit(f"llama-server binary not found: {path}")
    return path


# -------------------------------------------------------------------- modes
def run_probes(backend, suites: list[str], out_path: Path, model_label: str,
               provenance: dict, limit: int | None = None) -> None:
    started = time.time()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path = out_path.with_suffix(".raw.jsonl.gz")
    evidence: dict = {"schema_version": "cerebellum/v1",
                      "kind": "metacognition_probe_evidence_v1",
                      "scoring_version": SCORING_VERSION,
                      "model": model_label, "generation": GENERATION,
                      "provenance": provenance, "suites": {}, "skipped": [],
                      "cost": {"wall_seconds": None, "tokens_in": 0, "tokens_out": 0},
                      "raw_completions": raw_path.name}
    with gzip.open(raw_path, "wt", encoding="utf-8") as raw:
        for kind in suites:
            rows = []
            for item in (load_suite(kind)[:limit] if limit else load_suite(kind)):
                if item.get("skipped_fixture_missing"):
                    evidence["skipped"].append({"id": item["id"], "reason": "fixture_missing"})
                    continue
                prompt = render_prompt(item["kind"], item["input"])
                result = backend.complete(prompt, GENERATION["temperature"],
                                          GENERATION["seed"], GENERATION["n_predict"])
                pred, error = parse_contract(result["content"])
                valid = pred is not None and discipline_ok(pred)
                score = score_item(item, pred, valid)
                rows.append({"item": item, "completion": result["content"], "score": score})
                evidence["cost"]["tokens_in"] += result["tokens_in"] or 0
                evidence["cost"]["tokens_out"] += result["tokens_out"] or 0
                raw.write(json.dumps({"id": item["id"], "prompt": prompt,
                                      "completion": result["content"],
                                      "parse_error": error, "prediction": pred,
                                      "score": score}, ensure_ascii=False) + "\n")
            evidence["suites"][kind] = suite_metrics(kind, rows)
    evidence["cost"]["wall_seconds"] = round(time.time() - started, 1)
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence["suites"].items()}, indent=2))


def run_labeling(backend, out_path: Path, model_label: str,
                 candidates_path: Path | None = None) -> None:
    candidates = [json.loads(line) for line in
                  (candidates_path or SUITE_DIR / "kb-candidates.jsonl").open(encoding="utf-8")
                  if line.strip()]
    entries = []
    for cand in candidates:
        prompt = f"Question: {cand['query']}\nAnswer:"
        samples, correct = [], 0
        for seed in LABELING_GENERATION["seeds"]:
            result = backend.complete(prompt, LABELING_GENERATION["temperature"],
                                      seed, LABELING_GENERATION["n_predict"])
            text = result["content"].strip()
            expect = cand.get("expect")
            is_correct = (bool(expect) and isinstance(expect, dict)
                          and tokens_match(expect.get("groups"), text))
            correct += int(is_correct)
            samples.append({"seed": seed, "text": text[:500], "correct": is_correct})
        entries.append({"id": cand["id"], "class": cand["class"], "query": cand["query"],
                        "expect": cand.get("expect"), "correct_samples": correct,
                        "samples": samples})
    payload = {"schema_version": "cerebellum/v1", "kind": "kb_labeling_evidence_v1",
               "model": model_label, "generation": LABELING_GENERATION,
               "rule": "known = 3/3 correct; unknown_eligible = 0/3 correct",
               "entries": entries}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    known = sum(1 for e in entries if e["class"] == "known_candidate" and e["correct_samples"] == 3)
    unknown = sum(1 for e in entries if e["class"] == "unknown_candidate" and e["correct_samples"] == 0)
    print(json.dumps({"verified_known": known, "verified_unknown": unknown}))


def dry_run() -> int:
    report = manifest_ok()
    problems = []
    for kind in ("tg", "kb", "st"):
        items = load_suite(kind)
        if kind == "kb" and not items:
            continue  # pre-labeling state
        for item in items:
            pred, error = parse_contract(json.dumps(item["gold"], ensure_ascii=False))
            if error or (pred is not None and not discipline_ok(pred)):
                problems.append(f"{item['id']}: gold fails contract: {error or 'discipline'}")
            elif not score_item(item, pred, True)["fully_correct"]:
                problems.append(f"{item['id']}: gold fails correctness check")
            if item["gold"]["action"] == "answer" and not item.get("check", {}).get("answer_contains"):
                problems.append(f"{item['id']}: answer gold without check.answer_contains")
    print(json.dumps({"scoring_version": SCORING_VERSION, "manifest": report, "contract_problems": problems}, indent=2,
                     ensure_ascii=False))
    return 0 if report["ok"] and not problems else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="GGUF path (llama-server arm) or label")
    parser.add_argument("--llama-server", help="llama-server executable or its directory")
    parser.add_argument("--ollama", help="Ollama alias (comparison arm)")
    parser.add_argument("--suite", default="all", choices=["tg", "kb", "st", "all"])
    parser.add_argument("--label-kb", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", help="evidence output path")
    parser.add_argument("--limit", type=int, default=None,
                        help="only first N items per suite (smoke runs)")
    parser.add_argument("--candidates", help="kb candidates jsonl (default: suite kb-candidates.jsonl)")
    args = parser.parse_args()

    if args.dry_run:
        return dry_run()

    if args.ollama:
        backend = OllamaBackend(args.ollama)
        model_label = f"ollama:{args.ollama}"
        artifact = args.ollama
    else:
        if not args.model or not args.llama_server:
            parser.error("--model and --llama-server are required for the GGUF arm")
        backend = LlamaServer(resolve_llama_server(args.llama_server), Path(args.model))
        model_label = f"gguf:{Path(args.model).name}"
        artifact = str(Path(args.model))

    provenance = {"artifact": artifact,
                  "artifact_sha256": hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
                  if Path(artifact).is_file() else None,
                  "manifest": manifest_ok()}
    with backend:
        if args.label_kb:
            if not args.out:
                parser.error("--label-kb requires --out")
            run_labeling(backend, Path(args.out), model_label,
                         Path(args.candidates) if args.candidates else None)
        else:
            if not args.out:
                parser.error("--out is required")
            suites = ["tg", "kb", "st"] if args.suite == "all" else [args.suite]
            if "kb" in suites and not (SUITE_DIR / "kb.jsonl").exists():
                raise SystemExit("kb.jsonl not finalized; run --label-kb then build-suites --finalize-kb")
            run_probes(backend, suites, Path(args.out), model_label, provenance, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
