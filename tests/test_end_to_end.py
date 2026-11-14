"""Integration contract: synthetic data through feed, five-method audit and inbox.

A passing test verifies Python hand-off, not a real ChatGPT push notification.
"""
import datetime as dt
import unittest

from signal_feed import build as make_feed
from five_method_audit import evaluate as audit
from radar_inbox import build as make_inbox

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,13,16,0,tzinfo=UTC)
CANDLE=(NOW-dt.timedelta(minutes=30)).isoformat()

def observation(venue,gain=3.5):
    return {"symbol":"SOLUSDT","venue":venue,"status":"ok",
        "source_url":"https://exchange.example.invalid/"+venue,
        "data":{"valid":True,"spot_close_usdt":100 if venue=="okx" else 100.2,
            "candle_start_utc":CANDLE,"change_percent":gain,
            "volume_multiplier":3.5,"spot_quote_volume_usdt":300000}}

def spot(rows=None):
    return {"generated_at_utc":NOW.isoformat(),"quality":{"valid_checks":2},
            "sources":rows if rows is not None else [observation("okx"),observation("gate")]}

class BridgeIntegrationTests(unittest.TestCase):
    def test_two_venue_event_reaches_research_inbox(self):
        report=spot()
        feed,history=make_feed(report,{"keys":[]},NOW)
        assessment=audit(report,now=NOW)
        inbox=make_inbox(feed,assessment,NOW)
        self.assertEqual(feed["new_event_count"],1)
        self.assertEqual(inbox["candidate_count"],1)
        self.assertEqual(inbox["candidates"][0]["research_stage"],"MOMENTUM_RESEARCH")
        self.assertFalse(inbox["push_service_configured"])
        self.assertTrue(inbox["requires_independent_live_check"])
        self.assertFalse(assessment["trade_alert_authorized"])
        # Same candle next run is not a fresh event.
        again,_=make_feed(report,history,NOW)
        self.assertEqual(again["new_event_count"],0)
    def test_offensive_two_venue_momentum_reaches_inbox(self):
        report=spot([observation("okx",gain=2.7),observation("gate",gain=2.7)])
        for row in report["sources"]:
            row["data"]["volume_multiplier"]=2.7
        feed,_=make_feed(report,{"keys":[]},NOW)
        assessment=audit(report,now=NOW)
        inbox=make_inbox(feed,assessment,NOW)
        self.assertEqual(inbox["candidate_count"],1)
        self.assertEqual(inbox["candidates"][0]["research_stage"],"MOMENTUM_RESEARCH")
        self.assertFalse(inbox["candidates"][0]["not_a_buy_signal"] is False)
    def test_one_exchange_never_reaches_inbox(self):
        report=spot([observation("okx")])
        feed,_=make_feed(report,{"keys":[]},NOW)
        inbox=make_inbox(feed,audit(report,now=NOW),NOW)
        self.assertEqual(inbox["candidate_count"],0)
    def test_old_market_source_reaches_only_history(self):
        report=spot()
        report["generated_at_utc"]=(NOW-dt.timedelta(hours=2)).isoformat()
        feed,_=make_feed(report,{"keys":[]},NOW)
        inbox=make_inbox(feed,audit(report,now=NOW),NOW)
        self.assertEqual(inbox["candidate_count"],0)
        self.assertEqual(inbox["historical_candidate_count"],1)
        self.assertEqual(feed["new_event_count"],0)

if __name__=="__main__":unittest.main()
