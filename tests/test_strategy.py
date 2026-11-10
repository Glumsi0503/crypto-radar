import datetime as dt
import unittest
from strategy import consensus, update

NOW=dt.datetime.now(dt.timezone.utc)
STAMP=NOW.isoformat()
CANDLE=NOW.replace(second=0,microsecond=0).isoformat()
def point(p=105,gain=3,mult=3,vol=200000):
    return {"valid":True,"candle_start_utc":CANDLE,"change_percent":gain,"volume_multiplier":mult,
            "spot_quote_volume_usdt":vol,"spot_close_usdt":p}
def record(venues=("okx","gate"), price=(105,105.1)):
    return {"generated_at_utc":STAMP,"quality":{"valid_checks":len(venues)},
            "sources":[{"symbol":"SOLUSDT","venue":v,"status":"ok","data":point(p=price[i])}
                for i,v in enumerate(venues)]}
class StrategyTest(unittest.TestCase):
    def test_two_venues_required(self):
        self.assertFalse(consensus({"SOLUSDT":[("okx",point())]}))
    def test_two_venue_agreement(self):
        self.assertEqual(len(consensus({"SOLUSDT":[("okx",point()),("gate",point(p=105.3))]})),1)
    def test_price_disagreement_blocks(self):
        self.assertFalse(consensus({"SOLUSDT":[("okx",point()),("gate",point(p=107))]}))
    def test_weak_volume_blocks(self):
        self.assertFalse(consensus({"SOLUSDT":[("okx",point(vol=50000)),("gate",point())]}))
    def test_not_actionable(self):
        journal={"trades":[]}
        result=update(record(),journal,NOW)
        self.assertFalse(result["eligible_for_real_trading"])
        self.assertEqual(len(journal["trades"]),1)
        self.assertFalse(journal["trades"][0]["eligible_for_real_trade"])
    def test_no_duplicate_paper_entry(self):
        journal={"trades":[]}
        update(record(),journal,NOW)
        update(record(),journal,NOW)
        self.assertEqual(len(journal["trades"]),1)
    def test_stale_data_rejected(self):
        r=record()
        r["generated_at_utc"]=(NOW-dt.timedelta(hours=1)).isoformat()
        with self.assertRaises(ValueError):update(r,{"trades":[]},NOW)
    def test_paper_target_fees(self):
        journal={"trades":[]}
        update(record(),journal,NOW)
        second=record(price=(111.1,111.2))
        for s in second["sources"]:s["data"].update(change_percent=0.1,volume_multiplier=1.0)
        outcome=update(second,journal,NOW+dt.timedelta(minutes=15))
        self.assertEqual(outcome["paper_performance"]["closed"],1)
        self.assertEqual(journal["trades"][0]["exit_reason"],"target_observed")
        self.assertLess(journal["trades"][0]["net_pnl_percent"],6)
if __name__=="__main__":
    unittest.main()
