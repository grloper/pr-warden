"""Tests for the local insights ledger: record -> query -> summarize -> outputs."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import insights  # noqa: E402


def _temp_db(self) -> Path:
    d = Path(tempfile.mkdtemp(prefix="warden-ins-"))
    self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
    return d / "warden.db"


class InsightsTest(unittest.TestCase):
    def test_record_and_query_roundtrip(self):
        db = _temp_db(self)
        insights.record("cli", "review", repo="acme/app", pr="https://x/pull/1",
                        model="local-fast", rc=0, latency_ms=1200, db=db)
        insights.record("server", "webhook", repo="acme/app", rc=403, latency_ms=5,
                        detail="pull_request opened", db=db)
        rows = insights.query(db=db)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["kind"], "review")
        self.assertEqual(rows[0]["repo"], "acme/app")

    def test_query_since_days_filters(self):
        db = _temp_db(self)
        insights.record("cli", "review", repo="a/b", db=db)  # ts = now
        rows = insights.query(since_days=7, db=db)
        self.assertEqual(len(rows), 1)

    def test_summarize_counts_and_latency(self):
        db = _temp_db(self)
        for i in range(3):
            insights.record("cli", "review", repo="a/b", rc=0, latency_ms=100 * (i + 1), db=db)
        insights.record("cli", "ask", repo="a/c", rc=1, db=db)
        s = insights.summarize(insights.query(db=db))
        self.assertEqual(s["total_events"], 4)
        self.assertEqual(s["ok_runs"], 3)
        self.assertEqual(s["by_kind"], {"review": 3, "ask": 1})
        self.assertEqual(s["avg_latency_ms"], 200)
        self.assertEqual(s["by_repo"]["a/b"], 3)
        self.assertGreater(s["est_coderabbit_dollars"], 0)

    def test_digest_markdown_has_headings_and_numbers(self):
        db = _temp_db(self)
        insights.record("cli", "review", repo="a/b", rc=0, db=db)
        md = insights.digest_markdown(insights.query(db=db), since_days=7)
        self.assertIn("# PR-Warden weekly digest", md)
        self.assertIn("Events recorded:** 1", md)

    def test_badge_svg_embeds_value(self):
        db = _temp_db(self)
        insights.record("cli", "review", repo="a/b", rc=0, db=db)
        svg = insights.badge_svg(insights.summarize(insights.query(db=db)))
        self.assertIn("<svg", svg)
        self.assertIn("1 reviews", svg)


if __name__ == "__main__":
    unittest.main()
