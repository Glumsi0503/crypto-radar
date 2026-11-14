import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from healthcheck import audit

NOW=dt.datetime(2026,11,11,0,0,tzinfo=dt.timezone.utc)
class HealthTest(unittest.TestCase):
    def test_missing_reports_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            r=audit(Path(d),NOW)
            self.assertEqual(r["data_quality"],"NO_VERIFIED_RESEARCH_DATA")
            self.assertFalse(r["trade_alerts_permitted"])
    def test_fresh_report_usable_research_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"latest.json").write_text(json.dumps({"generated_at_utc":NOW.isoformat(),"quality":{"valid_checks":2,"checks":3}}))
            r=audit(p,NOW)
            self.assertEqual(r["data_quality"],"USABLE_RESEARCH_ONLY")
            self.assertFalse(r["trade_alerts_permitted"])
    def test_signal_feed_must_have_fresh_source(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"latest.json").write_text(json.dumps({"generated_at_utc":NOW.isoformat(),"quality":{"valid_checks":2}}))
            (p/"signal_feed.json").write_text(json.dumps({
                "generated_at_utc":NOW.isoformat(),
                "source_generated_at_utc":(NOW-dt.timedelta(minutes=70)).isoformat(),
                "research_only":True,"new_event_count":1}))
            r=audit(p,NOW)
            self.assertFalse(r["checks"]["signal_feed"]["valid"])
    def test_empty_but_checked_dynamic_universe_is_healthy(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"discovery.json").write_text(json.dumps({
                "generated_at_utc":NOW.isoformat(),
                "status":"no_correlated_candidates","candidates":[]}))
            result=audit(root,NOW)
            self.assertTrue(result["checks"]["discovery"]["valid"])
    def test_old_report_is_historical_not_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"latest.json").write_text(json.dumps({"generated_at_utc":(NOW-dt.timedelta(minutes=70)).isoformat(),"quality":{"valid_checks":2}}))
            output=audit(p,NOW)
            self.assertTrue(output["checks"]["latest"]["valid"])
            self.assertFalse(output["checks"]["latest"]["fresh"])
            self.assertEqual(output["data_quality"],"HISTORICAL_RESEARCH_ONLY")
    def test_older_than_day_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"latest.json").write_text(json.dumps({"generated_at_utc":(NOW-dt.timedelta(hours=25)).isoformat(),"quality":{"valid_checks":2}}))
            self.assertFalse(audit(p,NOW)["checks"]["latest"]["valid"])
if __name__=="__main__":
    unittest.main()
