import datetime as dt
import time
import unittest
from market_data import CANDLE_MS, evaluate, collect

def fixture(change=3.5, multiple=4, gap=False):
    now=int(time.time()*1000)
    end=(now//CANDLE_MS-1)*CANDLE_MS
    bars=[]
    for n in range(21):
        ts=end-(20-n)*CANDLE_MS
        if gap and n==10:ts+=60000
        bars.append({"ts":ts,"open":100.0,"close":103.5 if n==20 and change==3.5 else (100*(1+change/100) if n==20 else 100),
                     "volume":1000*multiple if n==20 else 1000,"confirmed":True})
    return bars

class MarketDataTest(unittest.TestCase):
    def test_positive_pattern(self):
        result=evaluate(fixture(),int(time.time()*1000))
        self.assertTrue(result["valid"])
        self.assertTrue(result["pattern_met"])
    def test_missing_volume(self):
        result=evaluate(fixture(multiple=2),int(time.time()*1000))
        self.assertFalse(result["pattern_met"])
    def test_gap_rejected(self):
        result=evaluate(fixture(gap=True),int(time.time()*1000))
        self.assertFalse(result["valid"])
    def test_two_venues_required(self):
        def fetcher(venue,symbol):
            return "fixture://"+venue,fixture(multiple=4 if venue=="binance" else 1)
        result=collect(("BTCUSDT",),("binance","bybit"),fetcher)
        self.assertEqual(result["research_only"],[])
        self.assertFalse(result["alerts_permitted"])
    def test_corroboration_still_not_trade(self):
        def fetcher(venue,symbol):return "fixture://"+venue,fixture()
        result=collect(("BTCUSDT",),("binance","bybit"),fetcher)
        self.assertEqual(len(result["research_only"]),1)
        self.assertFalse(result["alerts_permitted"])
        self.assertFalse(result["research_only"][0]["trade_alert"])

if __name__=="__main__":
    unittest.main()
