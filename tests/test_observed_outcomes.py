import datetime as dt
import unittest
from observed_outcomes import advance

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,13,16,tzinfo=UTC)
FIRST=NOW-dt.timedelta(hours=1,minutes=10)
CANDLE=(NOW-dt.timedelta(minutes=15)).isoformat()

def spot(venues=2):
    return {"generated_at_utc":NOW.isoformat(),"sources":[
        {"symbol":"SOLUSDT","venue":v,"status":"ok","data":{
            "valid":True,"candle_start_utc":CANDLE,
            "spot_close_usdt":105 if v=="okx" else 105.1,
            "change_percent":0,"volume_multiplier":1,"spot_quote_volume_usdt":200000}}
        for v in ("okx","gate")[:venues]]}

def events():
    return {"events":[{"event_id":"SOL|early","symbol":"SOLUSDT",
             "stage":"EARLY_RESEARCH","first_seen_utc":FIRST.isoformat(),
             "reference_price_usdt":100.0}]}

class OutcomeTest(unittest.TestCase):
    def test_one_hour_observation_and_idempotence(self):
        journal={}
        r=advance(spot(),events(),journal,NOW)
        self.assertEqual(r["observation_count"],1)
        self.assertEqual(r["checkpoint_summary"]["1h"]["observed"],1)
        self.assertFalse(r["checkpoint_summary"]["1h"]["sufficient_sample"])
        advance(spot(),events(),journal,NOW)
        self.assertEqual(len(journal["observations"]),1)
    def test_single_venue_does_not_invent_price(self):
        journal={}
        r=advance(spot(1),events(),journal,NOW)
        self.assertEqual(r["checkpoint_summary"]["1h"]["observed"],0)
    def test_missed_is_not_backfilled(self):
        far=NOW+dt.timedelta(hours=4)
        market=spot()
        market["generated_at_utc"]=far.isoformat()
        journal={}
        advance(spot(1),events(),journal,NOW)
        result=advance(market,{"events":[]},journal,far)
        self.assertEqual(result["checkpoint_summary"]["1h"]["missed"],1)
        self.assertEqual(result["checkpoint_summary"]["1h"]["observed"],0)
    def test_stale_market_fails(self):
        market=spot()
        market["generated_at_utc"]=(NOW-dt.timedelta(hours=2)).isoformat()
        with self.assertRaises(ValueError):advance(market,events(),{},NOW)
if __name__=="__main__":unittest.main()
