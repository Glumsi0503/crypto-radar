import datetime as dt
import unittest
from radar_inbox import build

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,13,16,0,tzinfo=UTC)
CANDLE=(NOW-dt.timedelta(minutes=30)).isoformat()
FIRST=(NOW-dt.timedelta(minutes=12)).isoformat()
def feed(stage="MOMENTUM_RESEARCH"):
    return {"generated_at_utc":NOW.isoformat(),
        "source_generated_at_utc":NOW.isoformat(),
        "recent_events_3h":[{"event_id":"SOL|"+CANDLE+"|"+stage,
            "symbol":"SOLUSDT","first_seen_utc":FIRST,"candle_start_utc":CANDLE,
            "stage":stage,"venues":["okx","gate"],"reference_price_usdt":100.0}]}
def audit(status="supported"):
    return {"generated_at_utc":NOW.isoformat(),"coins":[{"symbol":"SOLUSDT",
        "methods":{"momentum":{"status":status},
                   "smart_money":{"status":"not_evaluable"}}}]}

class ReaderInboxTests(unittest.TestCase):
    def test_positive_momentum_research(self):
        x=build(feed(),audit(),NOW)
        self.assertEqual(x["candidate_count"],1)
        self.assertFalse(x["push_service_configured"])
        self.assertFalse(x["candidates"][0]["not_a_buy_signal"] is False)
    def test_no_false_momentum_confirmation(self):
        self.assertEqual(build(feed(),audit("not_confirmed"),NOW)["candidate_count"],0)
    def test_early_watch_is_not_purchase_signal(self):
        x=build(feed("EARLY_RESEARCH"),audit("not_confirmed"),NOW)
        self.assertEqual(x["candidates"][0]["priority"],"watch")
    def test_stale_candle_is_rejected(self):
        x=feed()
        x["recent_events_3h"][0]["candle_start_utc"]=(NOW-dt.timedelta(minutes=70)).isoformat()
        self.assertEqual(build(x,audit(),NOW)["candidate_count"],0)
    def test_stale_feed_is_rejected(self):
        x=feed()
        x["source_generated_at_utc"]=(NOW-dt.timedelta(hours=2)).isoformat()
        with self.assertRaises(ValueError):build(x,audit(),NOW)
    def test_deduplicated(self):
        x=feed()
        x["recent_events_3h"]*=2
        self.assertEqual(build(x,audit(),NOW)["candidate_count"],1)

if __name__=="__main__":unittest.main()
