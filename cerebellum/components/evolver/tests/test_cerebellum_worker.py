import json
from unittest.mock import MagicMock

from evolver.cerebellum_worker import process_once


def test_worker_uses_json_and_cas_boundary_only():
    experience_id = "00000000-0000-0000-0000-000000000001"
    request = {
        "schema_version": "cerebellum/v1",
        "request_id": "00000000-0000-0000-0000-000000000002",
        "experience": {"experience_id": experience_id},
        "feedback": [],
        "decision": {"experience_id": experience_id},
    }
    client = MagicMock()
    client.json.side_effect = [
        {
            "job_id": "00000000-0000-0000-0000-000000000003",
            "payload": {"request_hash": "a" * 64},
        },
        {"imported": 1},
        {"status": "completed"},
    ]
    client.object.return_value = json.dumps(request).encode("utf-8")
    evolver = MagicMock()
    evolver.consolidate_experience.return_value = {
        "schema_version": "cerebellum/v1",
        "proposals": [],
    }

    assert process_once(evolver, client, "worker-test") is True
    client.object.assert_called_once_with("a" * 64)
    evolver.consolidate_experience.assert_called_once_with(request, store=True)
    assert client.json.call_args_list[0].args[1] == "/v1/learning/jobs:claim"
    assert client.json.call_args_list[-1].args[1].endswith(":complete")
