import unittest

from api_hackathon.ai import FixtureAI
from api_hackathon.artifacts import load_text
from api_hackathon.workshop import diagnose_incident


class MockAI:
    def __init__(self, candidates: list[dict]):
        self.candidates = candidates

    def ask(self, task: str, _context) -> list[dict]:
        return self.candidates


class TestDiagnoseIncident(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load incident.log from the data folder."""
        cls.incident_log = load_text("incident.log")

    def test_incident_log_file_loaded_successfully(self):
        """Ensure the incident.log file in data folder is not empty."""
        self.assertTrue(len(self.incident_log) > 0)
        self.assertIn("deploy version=2.4.1 change=orders-db-pool", self.incident_log)

    def test_diagnose_incident_with_fixture_ai(self):
        """Test diagnose_incident with data/incident.log and FixtureAI."""
        ai = FixtureAI()
        result = diagnose_incident(self.incident_log, ai)

        self.assertIsInstance(result, dict)
        self.assertIn("cause", result)
        self.assertIn("evidence", result)

        # Ensure all evidence items from the selected diagnosis are in the log file
        for evidence in result["evidence"]:
            self.assertIn(evidence, self.incident_log)

        # Verify specific expected incident cause
        self.assertIn("database-pool", result["cause"])

    def test_diagnose_incident_filters_out_unsupported_candidate(self):
        """Test that a candidate with evidence not present in logs is rejected."""
        unsupported_candidate = {
            "cause": "A DNS outage prevented all clients from reaching the API.",
            "evidence": ["dns_resolution_failed", "upstream_host_not_found"],
        }
        supported_candidate = {
            "cause": "The 2.4.1 database-pool change exhausted connections.",
            "evidence": [
                "deploy version=2.4.1 change=orders-db-pool",
                "status=503 error=db_pool_timeout",
            ],
        }
        mock_ai = MockAI([unsupported_candidate, supported_candidate])

        result = diagnose_incident(self.incident_log, mock_ai)
        self.assertEqual(result, supported_candidate)

    def test_diagnose_incident_rejects_partial_evidence(self):
        """Test that candidate with only partial evidence matching the log is rejected."""
        partial_candidate = {
            "cause": "Partial evidence candidate",
            "evidence": [
                "deploy version=2.4.1 change=orders-db-pool",  # exists in log
                "non_existent_error_code_999",  # does not exist in log
            ],
        }
        mock_ai = MockAI([partial_candidate])

        result = diagnose_incident(self.incident_log, mock_ai)
        self.assertEqual(result, {})

    def test_diagnose_incident_returns_empty_when_no_match(self):
        """Test that an empty dict is returned when no candidate evidence matches."""
        no_match_candidate = {
            "cause": "Unrelated hardware failure",
            "evidence": ["disk_failure_sector_0"],
        }
        mock_ai = MockAI([no_match_candidate])

        result = diagnose_incident(self.incident_log, mock_ai)
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
