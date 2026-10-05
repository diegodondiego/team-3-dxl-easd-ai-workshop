"""Participant file -- improve these working-but-unreliable baselines.

Quick start
-----------
1. Run  python demo.py          to see the raw AI output for all four levels.
2. Edit the functions below one at a time.
3. Run  python score.py --team "Your Team" --open   to see your score and a
   visual report in the browser.

The API being reviewed has three endpoints (see http://localhost:8081/api/v1):

    GET  /orders               list orders, optional ?limit=<int>
    POST /orders               create an order  (Bearer auth required)
    GET  /orders/{orderId}     fetch one order  (Bearer auth required)

The AI assistant (ai.ask(...)) always returns a list of dicts. The shapes are
shown in the comments below. Your job is to filter that list so only items
that are verifiable against real evidence survive.
"""

dont_look_at_spec = True

def check_if_endpoint_exists(spec: dict, path: str, method: str) -> bool:
    """Check if the endpoint exists in the OpenAPI spec."""
    return path in spec.get("paths", {}) and method.lower() in spec["paths"][path]

def get_parameter(spec: dict, path: str, method: str, param_name: str) -> dict | None:
    """Find a parameter definition by name for a given endpoint in the OpenAPI spec."""
    path_item = spec.get("paths", {}).get(path, {})
    if not isinstance(path_item, dict):
        return None
    operation = path_item.get(method.lower(), {})
    if isinstance(operation, dict):
        for param in operation.get("parameters", []):
            if isinstance(param, dict) and param.get("name") == param_name:
                return param
    for param in path_item.get("parameters", []):
        if isinstance(param, dict) and param.get("name") == param_name:
            return param
    return None

def find_nested_keys(spec: dict, target_key: str):
    """Return {target_key: [val1, val2, ...]}."""
    def _search(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == target_key:
                    yield v
                yield from _search(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from _search(item)
    return {target_key: list(_search(spec))}

def review_contract(spec: dict, ai) -> list[dict]:
    """Level 1 -- return only findings supported by the OpenAPI contract.

    ai.ask("contract_review", spec) returns a list like:
        [
          {
            "id": "AUTH-001",
            "claim": "GET /orders has no authentication requirement.",
            "path": "/orders",
            "method": "get",
            "evidence_pointer": "/paths/~1orders/get"
          },
          ...
          {
            "id": "SEC-001",
            "claim": "DELETE /customers is publicly accessible.",
            "path": "/customers",
            "method": "delete",
            "evidence_pointer": "/paths/~1customers/delete"
          }
        ]

    Compare each finding against the OpenAPI v1 document in
    data/openapi-v1.json (same spec as http://localhost:8081/api/v1).

    Tip: check two things for each finding before keeping it.
      1. Does spec["paths"][finding["path"]][finding["method"]] exist?
      2. Does the evidence_pointer resolve to a real location inside spec?
         JSON Pointer: split on "/" first, then decode ~1 to "/" inside a key.
         "/paths/~1orders/get" is spec["paths"]["/orders"]["get"].
         It is not "//orders" -- the slash belongs to the key name "/orders".
    """
    findings = ai.ask("contract_review", spec)

    valid_findings = []
    for finding in findings:
        path = finding.get("path")
        method = (finding.get("method") or "").lower()

        # Check if endpoint exists in spec
        if check_if_endpoint_exists(spec, path, method):
            valid_findings.append(finding)

    return valid_findings


def design_negative_tests(spec: dict, ai) -> list[dict]:
    """Level 2 -- return runnable test ideas for operations that really exist.

    ai.ask("negative_tests", spec) returns a list like:
        [
          {
            "name": "zero limit",
            "method": "get",
            "path": "/orders",
            "input": {"limit": 0},
            "expected_status": 400
          },
          ...
          {
            "name": "delete customer record",
            "method": "delete",
            "path": "/customers/c-1",
            "input": {},
            "expected_status": 204
          }
        ]

    Compare each test case against the OpenAPI v1 document in
    data/openapi-v1.json (same spec as http://localhost:8081/api/v1).

    Tip: keep a test case only if ALL of these are true.
      1. spec["paths"][case["path"]][case["method"]] exists.
      2. expected_status is one of 400, 401, 403, 404, 409, or 422.
         A 204 from a non-existent endpoint is a red flag.
      3. The case has all required fields: name, method, path, input,
         expected_status.
    """

    findings = ai.ask("negative_tests", spec)

    # remove inexistent paths
    for finding in findings.copy():
        if not check_if_endpoint_exists(spec, finding["path"], finding["method"]):
            findings.remove(finding)

    # get all the valid status from the spec
    spec_available_status = find_nested_keys(spec, "responses")

    if dont_look_at_spec:
        unique_available_status = [400, 401, 403, 404, 409, 422]
    else:
        unique_available_status = list(dict.fromkeys(int(k) for d in spec_available_status["responses"] for k in d if str(k).isdigit()))

    for finding in findings.copy():
        if int(finding["expected_status"]) not in unique_available_status:
            findings.remove(finding)

    return findings


def diagnose_incident(logs: str, ai) -> dict:
    """Level 3 -- select a diagnosis whose evidence appears in the logs.

    ai.ask("incident_diagnosis", logs) returns a list of candidates:
        [
          {
            "cause": "A DNS outage prevented all clients from reaching the API.",
            "evidence": ["dns_resolution_failed", "upstream_host_not_found"]
          },
          {
            "cause": "The 2.4.1 database-pool change exhausted connections.",
            "evidence": [
              "deploy version=2.4.1 change=orders-db-pool",
              "db_pool_wait_ms=1850 active=20 max=20",
              "status=503 error=db_pool_timeout"
            ]
          }
        ]

    Tip: only keep a candidate if every string in its "evidence" list
    appears literally somewhere inside the logs string.
    The log file is at  data/incident.log  -- open it to see what is there.
    """
    candidates = ai.ask("incident_diagnosis", logs)

    for candidate in candidates:
        evidence_list = candidate.get("evidence", [])
        if evidence_list and all(evidence in logs for evidence in evidence_list):
            return candidate

    return {}


def review_migration(v1: dict, v2: dict, ai) -> list[dict]:
    """Level 4 -- return only breaking changes proven by the two contracts.

    ai.ask("migration_review", {...}) returns a list like:
        [
          {
            "id": "BREAK-POST",
            "claim": "POST /orders was removed in v2.",
            "kind": "operation_removed",
            "path": "/orders",
            "method": "post"
          },
          {
            "id": "BREAK-LIMIT",
            "claim": "The limit query parameter became required.",
            "kind": "parameter_became_required",
            "path": "/orders",
            "method": "get",
            "parameter": "limit"
          },
          {
            "id": "BREAK-003",
            "claim": "orderId changed from integer to string.",
            "kind": "schema_changed",
            "path": "/orders/{orderId}",
            "method": "get",
            "parameter": "orderId"
          }
        ]

    Compare each claim against data/openapi-v1.json and data/openapi-v2.json
    (Swagger: http://localhost:8081/api/v1 and http://localhost:8081/api/v2).

    Verify each change by comparing v1 and v2 directly.
      "operation_removed"       -- operation exists in v1 but not in v2.
      "parameter_became_required" -- parameter.required is False in v1
                                     and True in v2.
      "schema_changed"          -- parameter["schema"] differs between v1 and v2.
                                   If the schemas are identical the claim is false.
    """

    findings = ai.ask("migration_review", {"v1": v1, "v2": v2})
    valid_findings = []

    for finding in findings:
        kind = finding.get("kind")
        path = finding.get("path")
        method = (finding.get("method") or "").lower()
        param_name = finding.get("parameter")

        if kind == "operation_removed":
            if check_if_endpoint_exists(v1, path, method) and not check_if_endpoint_exists(v2, path, method):
                valid_findings.append(finding)
        elif kind == "parameter_became_required":
            param_v1 = get_parameter(v1, path, method, param_name)
            param_v2 = get_parameter(v2, path, method, param_name)
            if param_v1 is not None and param_v2 is not None:
                req_v1 = bool(param_v1.get("required", False))
                req_v2 = bool(param_v2.get("required", False))
                if not req_v1 and req_v2:
                    valid_findings.append(finding)
        elif kind == "schema_changed":
            param_v1 = get_parameter(v1, path, method, param_name)
            param_v2 = get_parameter(v2, path, method, param_name)
            if param_v1 is not None and param_v2 is not None:
                schema_v1 = param_v1.get("schema")
                schema_v2 = param_v2.get("schema")
                if schema_v1 is not None and schema_v2 is not None and schema_v1 != schema_v2:
                    valid_findings.append(finding)

    return valid_findings
