import datetime as dt
import unittest
from discovery import select
from signal_feed import build
UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,13,15,0,tzinfo=UTC)
CANDLE=(NOW-dt.timedelta(minutes=15)).isoformat()

def record(symbol="SOLUSDT",stage=2.0):
    return {"symbol":symbol,"venue":"okx","status":"ok","data":{
        "valid":True,"candle_start_utc":CANDLE,"change_percent":stage,
        "volume_multiplier":3,"spot_quote_volume_usdt":300000,
        "spot_close_usdt":100}}
def report(gain=2.0):
    one=record(stage=gain)
    two=record(stage=gain)
    two["venue"]="gate"
    return {"generated_at_utc":NOW.isoformat(),"quality":{"valid_checks":2},
            "sources":[one,two]}

class DiscoveryAndFeedTests(unittest.TestCase):
    def test_dynamic_liquid_filters(self):
        tickers=[{"currency_pair":"ABC_USDT","quote_volume":"3000000","change_percentage":"8","last":"1"},
                 {"currency_pair":"BAD_USDT","quote_volume":"2","change_percentage":"95","last":"1"},
                 {"currency_pair":"XYZ_BTC","quote_volume":"90000000","change_percentage":"8","last":"1"},
                 {"currency_pair":"ETH5L_USDT","quote_volume":"90000000","change_percentage":"8","last":"1"},
                 {"currency_pair":"ZEC5S_USDT","quote_volume":"90000000","change_percentage":"8","last":"1"}]
        self.assertEqual([x["symbol"] for x in select(tickers,existing=set())],["ABCUSDT"])
    def test_pre_watch_and_dedupe(self):
        feed,hist=build(report(),{"keys":[]},NOW)
        self.assertEqual(feed["new_event_count"],1)
        self.assertEqual(feed["new_events"][0]["stage"],"EARLY_RESEARCH")
        feed2,_=build(report(),hist,NOW)
        self.assertEqual(feed2["new_event_count"],0)
    def test_confirmed_momentum_research(self):
        feed,_=build(report(3.4),{"keys":[]},NOW)
        self.assertEqual(feed["current_candidates"][0]["stage"],"MOMENTUM_RESEARCH")
        self.assertFalse(feed["auto_push_connected"])
    def test_offensive_75_confirmed_at_2_7_percent(self):
        feed,_=build(report(2.7),{"keys":[]},NOW)
        self.assertEqual(feed["new_event_count"],1)
        self.assertEqual(feed["new_events"][0]["stage"],"MOMENTUM_RESEARCH")
        self.assertEqual(feed["signal_profile"]["subjective_strictness_0_100"],75)
        self.assertEqual(feed["signal_profile"]["confirmed_gain_min_percent"],2.5)
    def test_offensive_early_at_1_6_percent(self):
        feed,_=build(report(1.6),{"keys":[]},NOW)
        self.assertEqual(feed["new_event_count"],1)
        self.assertEqual(feed["new_events"][0]["stage"],"EARLY_RESEARCH")
    def test_confirmed_does_not_double_emit_early(self):
        feed,_=build(report(3.4),{"keys":[]},NOW)
        self.assertEqual(feed["new_event_count"],1)
        self.assertEqual(feed["new_events"][0]["stage"],"MOMENTUM_RESEARCH")
    def test_recent_events_survive_next_schedule(self):
        feed,hist=build(report(),{"keys":[]},NOW)
        subsequent=report()
        subsequent["generated_at_utc"]=(NOW+dt.timedelta(minutes=15)).isoformat()
        subsequent["sources"]=[]
        feed2,_=build(subsequent,hist,NOW+dt.timedelta(minutes=15))
        self.assertEqual(feed2["new_event_count"],0)
        self.assertEqual(len(feed2["recent_events_3h"]),1)
    def test_old_input_usable_for_history_only(self):
        old=report(3.4)
        old["generated_at_utc"]=(NOW-dt.timedelta(hours=2)).isoformat()
        feed,_=build(old,{"keys":[]},NOW)
        self.assertEqual(feed["source_data_classification"],"historical_only")
        self.assertEqual(feed["new_event_count"],0)
        self.assertEqual(len(feed["current_candidates"]),0)
        self.assertEqual(len(feed["historical_candidates"]),1)
    def test_older_than_a_day_rejected(self):
        old=report()
        old["generated_at_utc"]=(NOW-dt.timedelta(hours=25)).isoformat()
        with self.assertRaises(ValueError):build(old,{"keys":[]},NOW)
    def test_single_venue_does_not_emit(self):
        single=report()
        single["sources"].pop()
        feed,_=build(single,{"keys":[]},NOW)
        self.assertEqual(feed["new_event_count"],0)
if __name__=="__main__":
    unittest.main()
