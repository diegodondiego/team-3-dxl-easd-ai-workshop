import unittest
from api_hackathon.ai import FixtureAI
from api_hackathon.artifacts import load_json
from api_hackathon.workshop import review_migration, get_parameter, check_if_endpoint_exists


class MockAI:
    def __init__(self, findings: list[dict]):
        self.findings = findings

    def ask(self, task: str, _context) -> list[dict]:
        return self.findings


class TestReviewMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load openapi-v1.json and openapi-v2.json specs from data directory."""
        cls.v1 = load_json("openapi-v1.json")
        cls.v2 = load_json("openapi-v2.json")

    def test_specs_loaded_correctly(self):
        """Verify both OpenAPI specification documents load and have expected structures."""
        self.assertIn("paths", self.v1)
        self.assertIn("paths", self.v2)
        self.assertEqual(self.v1.get("info", {}).get("version"), "1.0")
        self.assertEqual(self.v2.get("info", {}).get("version"), "2.0")

    def test_review_migration_with_fixture_ai(self):
        """Test review_migration with actual v1/v2 specs and FixtureAI."""
        ai = FixtureAI()
        results = review_migration(self.v1, self.v2, ai)

        result_ids = {item.get("id") for item in results}

        # Proven breaking changes should be retained
        self.assertIn("BREAK-POST", result_ids)
        self.assertIn("BREAK-LIMIT", result_ids)

        # Unverified claim (orderId schema did not change) must be filtered out
        self.assertNotIn("BREAK-003", result_ids)

        # Validate structure of retained findings
        for item in results:
            self.assertIn("id", item)
            self.assertIn("kind", item)
            self.assertIn("path", item)
            self.assertIn("method", item)

    def test_operation_removed_verified_and_unverified(self):
        """Test operation_removed logic: keep removed operations, drop non-removed ones."""
        valid_removed = {
            "id": "OP-REM-1",
            "claim": "POST /orders was removed in v2.",
            "kind": "operation_removed",
            "path": "/orders",
            "method": "post",
        }
        invalid_removed = {
            "id": "OP-REM-2",
            "claim": "GET /orders was removed in v2.",
            "kind": "operation_removed",
            "path": "/orders",
            "method": "get",
        }
        nonexistent_removed = {
            "id": "OP-REM-3",
            "claim": "DELETE /orders was removed in v2.",
            "kind": "operation_removed",
            "path": "/orders",
            "method": "delete",
        }
        mock_ai = MockAI([valid_removed, invalid_removed, nonexistent_removed])

        results = review_migration(self.v1, self.v2, mock_ai)
        self.assertEqual(results, [valid_removed])

    def test_parameter_became_required_verified_and_unverified(self):
        """Test parameter_became_required logic: keep when optional in v1 and required in v2."""
        valid_req = {
            "id": "PARAM-REQ-1",
            "claim": "The limit query parameter became required.",
            "kind": "parameter_became_required",
            "path": "/orders",
            "method": "get",
            "parameter": "limit",
        }
        already_req = {
            "id": "PARAM-REQ-2",
            "claim": "The orderId path parameter became required.",
            "kind": "parameter_became_required",
            "path": "/orders/{orderId}",
            "method": "get",
            "parameter": "orderId",
        }
        nonexistent_param = {
            "id": "PARAM-REQ-3",
            "claim": "The nonExistent param became required.",
            "kind": "parameter_became_required",
            "path": "/orders",
            "method": "get",
            "parameter": "nonExistent",
        }
        mock_ai = MockAI([valid_req, already_req, nonexistent_param])

        results = review_migration(self.v1, self.v2, mock_ai)
        self.assertEqual(results, [valid_req])

    def test_schema_changed_verified_and_unverified(self):
        """Test schema_changed logic: keep only when schema actually differs."""
        # limit schema differs: v1 has minimum 1, v2 adds maximum 100
        valid_schema_change = {
            "id": "SCHEMA-DIFF",
            "claim": "limit parameter schema changed (added maximum).",
            "kind": "schema_changed",
            "path": "/orders",
            "method": "get",
            "parameter": "limit",
        }
        # orderId schema is identical in v1 and v2 ({"type": "string"})
        identical_schema = {
            "id": "SCHEMA-SAME",
            "claim": "orderId schema changed.",
            "kind": "schema_changed",
            "path": "/orders/{orderId}",
            "method": "get",
            "parameter": "orderId",
        }
        mock_ai = MockAI([valid_schema_change, identical_schema])

        results = review_migration(self.v1, self.v2, mock_ai)
        self.assertEqual(results, [valid_schema_change])

    def test_get_parameter_helper(self):
        """Test get_parameter helper for finding operation and path-level parameters."""
        limit_param = get_parameter(self.v1, "/orders", "get", "limit")
        self.assertIsNotNone(limit_param)
        self.assertEqual(limit_param.get("name"), "limit")
        self.assertEqual(limit_param.get("in"), "query")

        missing_param = get_parameter(self.v1, "/orders", "get", "unknown")
        self.assertIsNone(missing_param)


if __name__ == "__main__":
    unittest.main()
