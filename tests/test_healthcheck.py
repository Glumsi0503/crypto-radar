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
            self.assertEqual(r["data_quality"],"NO_VERIFIED_FRESH_MARKET_DATA")
            self.assertFalse(r["trade_alerts_permitted"])
    def test_fresh_report_usable_research_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"latest.json").write_text(json.dumps({"generated_at_utc":NOW.isoformat(),"quality":{"valid_checks":2,"checks":3}}))
            r=audit(p,NOW)
            self.assertEqual(r["data_quality"],"USABLE_RESEARCH_ONLY")
            self.assertFalse(r["trade_alerts_permitted"])
    def test_stale_report_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"latest.json").write_text(json.dumps({"generated_at_utc":(NOW-dt.timedelta(minutes=41)).isoformat(),"quality":{"valid_checks":2}}))
            self.assertFalse(audit(p,NOW)["checks"]["latest"]["valid"])
if __name__=="__main__":
    unittest.main()
