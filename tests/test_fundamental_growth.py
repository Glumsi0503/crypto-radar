import datetime as dt
import unittest
from enrichment import verified_weekly_growth

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,13,12,tzinfo=UTC)
TODAY=int(NOW.timestamp())//86400

def daily_series(prev=10,latest=15,missing=None):
    return {"totalDataChart":[[(TODAY-14+i)*86400, prev if i<7 else latest]
        for i in range(14) if i!=missing]}

class FundamentalGrowthTest(unittest.TestCase):
    def test_7day_change(self):
        x=verified_weekly_growth(daily_series(),NOW)
        self.assertTrue(x["growth_verified"])
        self.assertEqual(x["previous_7d"],70)
        self.assertEqual(x["latest_7d"],105)
        self.assertEqual(x["growth_percent"],50)
    def test_missing_day_is_not_verified(self):
        self.assertFalse(verified_weekly_growth(daily_series(missing=3),NOW)["growth_verified"])
    def test_zero_baseline_is_not_verified(self):
        self.assertFalse(verified_weekly_growth(daily_series(prev=0),NOW)["growth_verified"])
    def test_missing_series_is_not_verified(self):
        self.assertFalse(verified_weekly_growth({},NOW)["growth_verified"])

if __name__=="__main__":
    unittest.main()
