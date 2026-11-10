import time
import unittest
from enrichment import endpoint, validate, INTERVAL_MS

class EnrichmentTest(unittest.TestCase):
    def sample(self,interval):
        now=int(time.time()*1000)
        period=INTERVAL_MS[interval]
        last=(now//period-1)*period
        return [{"ts":last-period,"open":100,"close":101,"quote_volume":1000,"confirmed":True},
                {"ts":last,"open":101,"close":102,"quote_volume":1200,"confirmed":True}]
    def test_valid_closed_history(self):
        self.assertTrue(validate(self.sample("1h"),"1h",int(time.time()*1000))["valid"])
    def test_reject_gap(self):
        bars=self.sample("1h")
        bars[0]["ts"]-=INTERVAL_MS["1h"]
        self.assertFalse(validate(bars,"1h",int(time.time()*1000))["valid"])
    def test_reject_future(self):
        bars=self.sample("1h")
        bars[-1]["ts"]+=INTERVAL_MS["1h"]
        self.assertFalse(validate(bars,"1h",int(time.time()*1000))["valid"])
    def test_endpoint(self):
        self.assertIn("BTC-USDT",endpoint("okx","BTC","1h"))
        self.assertIn("interval=1h",endpoint("gate","BTC","1h"))

if __name__=="__main__":
    unittest.main()
