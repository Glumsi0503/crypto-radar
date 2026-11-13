import datetime as dt
import unittest
from five_method_audit import evaluate

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,13,16,0,tzinfo=UTC)
STAMP=(NOW-dt.timedelta(minutes=15)).isoformat()

def source(venue,gain=3.4,volume=300000,multiple=3.3):
    return {"symbol":"SOLUSDT","venue":venue,"status":"ok",
            "source_url":"https://example.invalid/"+venue,
            "data":{"valid":True,"spot_close_usdt":100 if venue=="okx" else 100.2,
                    "change_percent":gain,"volume_multiplier":multiple,
                    "spot_quote_volume_usdt":volume,"candle_start_utc":STAMP}}

def report(rows=None):
    return {"generated_at_utc":NOW.isoformat(),
            "sources":rows if rows is not None else [source("okx"),source("gate")]}

class AuditTests(unittest.TestCase):
    def test_confirmed_spot_is_research_not_trade(self):
        result=evaluate(report(),now=NOW)
        item=result["coins"][0]
        self.assertEqual(item["methods"]["momentum"]["status"],"supported")
        self.assertFalse(item["trade_ready"])
        self.assertFalse(result["auto_push_connected"])
    def test_single_venue_not_confirmed(self):
        item=evaluate(report([source("okx")]),now=NOW)["coins"][0]
        self.assertEqual(item["methods"]["momentum"]["status"],"not_confirmed")
    def test_missing_other_methods_are_not_positive(self):
        item=evaluate(report(),now=NOW)["coins"][0]
        for key in ("smart_money","short_squeeze","catalyst"):
            self.assertEqual(item["methods"][key]["status"],"not_evaluable")
    def test_derivative_snapshot_does_not_equal_squeeze(self):
        d={"generated_at_utc":NOW.isoformat(),"records":[
           {"coin":"SOL","status":"ok","funding_rate_percent":-0.04,
            "oi_change_4h_percent":12,"funding_interval_unverified":True}]}
        item=evaluate(report(),derivatives=d,now=NOW)["coins"][0]
        self.assertEqual(item["methods"]["short_squeeze"]["status"],"not_evaluable")
    def test_fees_growth_alone_no_fundamental_signal(self):
        e={"generated_at_utc":NOW.isoformat(),"fundamental_checks":[
           {"coin":"SOL","kind":"fees","growth_verified":True,"growth_percent":110,
            "token_value_capture_verified":False,"status":"reachable",
            "window_end_utc":STAMP}]}
        item=evaluate(report(),enrichment=e,now=NOW)["coins"][0]
        self.assertEqual(item["methods"]["fundamental_divergence"]["status"],"not_confirmed")
    def test_stale_input_rejected(self):
        doc=report()
        doc["generated_at_utc"]=(NOW-dt.timedelta(hours=1)).isoformat()
        with self.assertRaises(ValueError):evaluate(doc,now=NOW)

if __name__=="__main__":unittest.main()
