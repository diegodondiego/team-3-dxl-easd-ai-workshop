import unittest
import yaml  # Added for reading YAML files.

from api_hackathon import workshop
from score import calculate


class HackathonKitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load OpenAPI spec for tests."""
        with open("data/openapi-v1.json", "r", encoding="utf-8") as file:
            cls.openapi_spec = yaml.safe_load(file)

    def test_starter_has_room_to_improve(self):
        score, levels, _ = calculate(workshop)
        self.assertLess(score, 100)
        self.assertGreater(score, 0)
        self.assertEqual(levels["L3 Incident diagnosis"], 0)

    def test_loads_path_from_openapi(self):
        """Test accessing a specific dictionary path from the OpenAPI spec."""
        paths = self.openapi_spec.get("paths", {})
        self.assertIn("/orders", paths)  # Example: Check if "/orders" exists in the spec.
        self.assertIn("get", paths.get("/orders", {}))  # Check if "get" method exists on "/orders".


if __name__ == "__main__":
    unittest.main()
