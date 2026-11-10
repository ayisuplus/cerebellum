import json
import uuid

import pytest

from evolver.consolidation import (
    consolidate_request,
    validate_consolidation_request,
    write_consolidation_response,
)


def request(success=False):
    experience_id = str(uuid.uuid4())
    return {
        "schema_version": "cerebellum/v1",
        "request_id": str(uuid.uuid4()),
        "experience": {
            "experience_id": experience_id,
            "task": "repair parser",
            "task_family": "bugfix",
            "outcome": {
                "success": success,
                "summary": "parser regression",
                "failure_class": None if success else "test_failure",
            },
        },
        "feedback": [],
        "decision": {
            "decision_id": str(uuid.uuid4()),
            "experience_id": experience_id,
            "actions": ["store", "distill", "propose_skill"],
            "scores": {"correctness": float(success)},
        },
    }


def test_failure_consolidates_to_anti_skill_and_quarantined_skill_proposal(tmp_path):
    response = consolidate_request(request(False), producer="evolver/test")

    kinds = {proposal["kind"] for proposal in response["proposals"]}
    assert {"failure", "anti_skill", "skill_proposal"} <= kinds
    assert all(proposal["executable"] is False for proposal in response["proposals"])
    output = write_consolidation_response(response, tmp_path / "nested" / "response.json")
    assert json.loads(output.read_text(encoding="utf-8"))["request_id"] == response["request_id"]


def test_request_rejects_unknown_learning_action():
    value = request(True)
    value["decision"]["actions"].append("publish_trusted")

    with pytest.raises(ValueError, match="unknown learning action"):
        validate_consolidation_request(value)
