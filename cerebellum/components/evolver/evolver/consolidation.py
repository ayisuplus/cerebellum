"""Versioned, storage-independent Cerebellum consolidation protocol.

Evolver receives complete JSON values and returns proposals. It never opens the
Cerebellum Registry or relies on its SQLite schema.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "cerebellum/v1"
ALLOWED_ACTIONS = {
    "ignore", "store", "merge", "distill", "propose_skill",
    "propose_workflow", "schedule_eval", "training_candidate",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_consolidation_request(request: dict) -> None:
    """Reject malformed or unsafe cross-process requests."""
    if request.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    for field in ("request_id", "experience", "feedback", "decision"):
        if field not in request:
            raise ValueError(f"missing required field: {field}")
    experience = request["experience"]
    decision = request["decision"]
    if not isinstance(experience, dict) or not isinstance(decision, dict):
        raise ValueError("experience and decision must be objects")
    if experience.get("experience_id") != decision.get("experience_id"):
        raise ValueError("decision does not belong to experience")
    if not str(experience.get("task", "")).strip():
        raise ValueError("experience task must not be empty")
    actions = decision.get("actions", [])
    if not isinstance(actions, list) or any(action not in ALLOWED_ACTIONS for action in actions):
        raise ValueError("decision contains an unknown learning action")


def consolidate_request(request: dict, *, producer: str = "evolver/2.3.0") -> dict:
    """Convert one immutable experience into non-executable memory proposals."""
    validate_consolidation_request(request)
    experience = request["experience"]
    decision = request["decision"]
    outcome = experience.get("outcome", {})
    success = bool(outcome.get("success"))
    summary = str(outcome.get("summary", "")).strip()
    family = str(experience.get("task_family", "unknown")).strip() or "unknown"
    experience_id = experience["experience_id"]
    actions = set(decision.get("actions", []))
    created_at = _now()
    evidence = {
        "request_id": request["request_id"],
        "decision_id": decision.get("decision_id"),
        "scores": decision.get("scores", {}),
        "producer": producer,
    }

    proposals = [_proposal(
        experience_id,
        "episodic" if success else "failure",
        f"{family}: {'success' if success else 'failure'}",
        summary or str(experience.get("task", "")),
        evidence,
        created_at,
    )]
    if success:
        proposals.append(_proposal(
            experience_id, "fact", f"fact::{family}",
            f"Observed successful outcome for: {experience.get('task', '')}. {summary}",
            evidence, created_at,
        ))
    else:
        failure_class = outcome.get("failure_class") or "unknown"
        proposals.append(_proposal(
            experience_id, "anti_skill", f"avoid::{family}",
            f"Avoid repeating this approach without new evidence. "
            f"Failure class: {failure_class}. {summary}",
            evidence, created_at,
        ))
    if "propose_skill" in actions:
        proposals.append(_proposal(
            experience_id, "skill_proposal", f"candidate-skill::{family}",
            f"Draft a versioned procedure from this evidence: {summary}",
            {**evidence, "requires_paired_eval": True}, created_at,
        ))
    if "propose_workflow" in actions:
        proposals.append(_proposal(
            experience_id, "workflow_proposal", f"candidate-workflow::{family}",
            "Draft a DAG with explicit failure recovery and hard gates; keep quarantined.",
            {**evidence, "requires_human_publication": True}, created_at,
        ))
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request["request_id"],
        "producer": producer,
        "proposals": proposals,
        "created_at": created_at,
    }


def _proposal(experience_id: str, kind: str, title: str, content: str,
              evidence: dict, created_at: str) -> dict:
    return {
        "proposal_id": str(uuid.uuid4()),
        "experience_id": experience_id,
        "kind": kind,
        "title": title,
        "content": content,
        "evidence": evidence,
        "executable": False,
        "created_at": created_at,
    }


def write_consolidation_response(response: dict, path: str | Path) -> Path:
    """Atomically write a ConsolidationResponse v1 document."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(response, ensure_ascii=False, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return target
