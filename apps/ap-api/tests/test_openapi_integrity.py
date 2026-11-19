from collections import Counter

from asaa_ap.main import app


def test_operation_ids_are_unique_and_compensation_decision_has_one_route():
    schema = app.openapi()
    ids = [op["operationId"] for path in schema["paths"].values() for op in path.values() if isinstance(op, dict) and "operationId" in op]
    assert [k for k, v in Counter(ids).items() if v > 1] == []
    decision = schema["paths"]["/api/v1/payroll/compensation/{record_id}/decision"]
    assert list(decision) == ["post"]
    assert decision["post"]["operationId"] == "decide_compensation_api_v1_payroll_compensation__record_id__decision_post"
