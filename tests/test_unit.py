import unittest
from starlette.testclient import TestClient

from backend.main import app, calc_threshold, build_aspect_stats
from backend.config import CANONICAL_ASPECTS
from backend.database import get_connection, init_database


class TestAspectLogic(unittest.TestCase):
    def test_threshold_lower_bound(self):
        self.assertEqual(calc_threshold(0), 5.0)
        self.assertEqual(calc_threshold(50), 5.0)
        self.assertEqual(calc_threshold(999), 5.0)

    def test_threshold_dynamic_scaling(self):
        self.assertEqual(calc_threshold(2000), 10.0)
        self.assertEqual(calc_threshold(20000), 100.0)

    def test_build_stats_insufficient_data(self):
        stats = build_aspect_stats(pos=2, neg=1, neu=0, threshold=5.0)
        self.assertEqual(stats["mentions"], 3)
        self.assertIsNone(stats["positive_percent"])
        self.assertIsNone(stats["negative_percent"])

    def test_build_stats_percentages(self):
        stats = build_aspect_stats(pos=80, neg=20, neu=0, threshold=5.0)
        self.assertEqual(stats["mentions"], 100)
        self.assertEqual(stats["positive_percent"], 80.0)
        self.assertEqual(stats["negative_percent"], 20.0)
        self.assertEqual(stats["neutral_percent"], 0.0)

    def test_build_stats_exclude_neutral(self):
        stats = build_aspect_stats(pos=50, neg=50, neu=100, threshold=5.0, exclude_neutral=True)
        self.assertEqual(stats["mentions"], 200)
        self.assertEqual(stats["positive_percent"], 50.0)
        self.assertEqual(stats["negative_percent"], 50.0)
        self.assertEqual(stats["neutral_percent"], 0.0)


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_database()
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("message", data)
        self.assertIn("aspects", data)

    def test_aspects_list(self):
        resp = self.client.get("/aspects")
        self.assertEqual(resp.status_code, 200)
        aspects = resp.json()
        self.assertIsInstance(aspects, list)
        self.assertEqual(len(aspects), len(CANONICAL_ASPECTS))
        self.assertIn("Audio", aspects)

    def test_nonexistent_game_404(self):
        resp = self.client.get("/games/999999999999")
        self.assertEqual(resp.status_code, 404)

    def test_compare_endpoint_empty(self):
        resp = self.client.get("/games/compare")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


class TestDatabasePragmas(unittest.TestCase):
    def test_foreign_keys_enabled(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys;")
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()

