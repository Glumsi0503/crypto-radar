import datetime as dt
import unittest
from derivatives import summarize, comparison

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,13,15,tzinfo=UTC)

def fixtures():
    ts=str(int(NOW.timestamp()*1000))
    return ({"code":"0","data":[{"instId":"BTC-USDT-SWAP","ts":ts,"fundingRate":"-0.0004"}]},
            {"code":"0","data":[{"instId":"BTC-USDT-SWAP","ts":ts,"oi":"1500"}]})

class DerivativeTests(unittest.TestCase):
    def test_parse_funding_and_oi(self):
        f,o=fixtures()
        row=summarize("BTC",f,o,NOW)
        self.assertEqual(row["funding_rate_percent"],-0.04)
        self.assertIsNone(row["oi_change_4h_percent"])
    def test_four_hour_comparison(self):
        f,o=fixtures()
        row=summarize("BTC",f,o,NOW)
        history={"BTC":[{"instrument":"BTC-USDT-SWAP",
              "timestamp":(NOW-dt.timedelta(hours=4)).isoformat(),"oi_contracts":1000}]}
        comparison(history,"BTC",row,NOW)
        self.assertEqual(row["oi_change_4h_percent"],50)
    def test_no_comparison_without_history(self):
        f,o=fixtures()
        row=summarize("BTC",f,o,NOW)
        comparison({},"BTC",row,NOW)
        self.assertIsNone(row["oi_change_4h_percent"])
    def test_wrong_instrument_fails(self):
        f,o=fixtures()
        o["data"][0]["instId"]="ETH-USDT-SWAP"
        with self.assertRaises(ValueError):summarize("BTC",f,o,NOW)
if __name__=="__main__":
    unittest.main()
