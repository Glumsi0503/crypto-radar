import datetime as dt
import unittest
from radar_diagnostics import build

UTC = dt.timezone.utc

class FunnelTests(unittest.TestCase):
    def test_missing_data_never_promoted(self):
        now = dt.datetime(2026, 11, 16, 9, tzinfo=UTC)
        result = build({}, {}, {}, now)
        self.assertEqual(result["source_classification"], "HISTORICAL_RESEARCH_ONLY")
        self.assertEqual(result["feed_current_candidates"], 0)
        self.assertFalse(result["trade_ready"])

    def test_single_venue_is_not_consensus(self):
        now = dt.datetime(2026, 11, 16, 9, tzinfo=UTC)
        d = {"valid": True, "change_percent": 3, "volume_multiplier": 3,
             "spot_quote_volume_usdt": 200000, "spot_close_usdt": 10,
             "candle_start_utc": "2026-11-16T08:30:00+00:00"}
        report = {"generated_at_utc": now.isoformat(),
                  "sources": [{"symbol": "ABCUSDT", "venue": "okx", "status": "ok", "data": d}]}
        result = build(report, {}, {}, now)
        self.assertEqual(result["counts"]["single_venue_momentum"], 1)
        self.assertEqual(result["counts"].get("two_venue_momentum", 0), 0)

if __name__ == "__main__":
    unittest.main()
