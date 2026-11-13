import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from discovery import select,parse_okx_tickers,parse_bitget_tickers,corroborate,verify_candles,run
from market_data import CANDLE_MS,dynamic_symbols

NOW_MS=int(dt.datetime(2026,11,13,16,0,tzinfo=dt.timezone.utc).timestamp()*1000)
LAST=NOW_MS-CANDLE_MS

def gate(symbol="XYZ",volume=8000000,price="10"):
    return {"currency_pair":symbol+"_USDT","quote_volume":str(volume),
            "change_percentage":"10","last":price}

def okx(symbol="XYZ",volume=7000000,price="10.03",stamp=NOW_MS):
    return {"instId":symbol+"-USDT","volCcy24h":str(volume),
            "last":price,"ts":str(stamp)}

def rows(price=10,vol=100000):
    return [{"ts":LAST-(20-i)*CANDLE_MS,"open":price,
             "close":price,"volume":vol,"confirmed":True} for i in range(21)]

def fetcher(venue,symbol):
    return "test://"+venue+"/"+symbol,rows(10 if venue=="gate" else 10.03)

class DiscoveryLiquidityTests(unittest.TestCase):
    def test_two_venues_and_matching_closed_candles(self):
        chosen,report=run([gate()],{"code":"0","data":[okx()]},NOW_MS,fetcher)
        self.assertEqual(len(chosen),1)
        self.assertTrue(chosen[0]["two_venue_ohlcv_verified"])
        self.assertEqual(chosen[0]["validated_spot_venues"],["gate","okx"])
        self.assertEqual(report["ticker_correlated"],1)
    def test_bitget_spot_fallback(self):
        bitget={"code":"00000","data":[{"symbol":"XYZUSDT",
            "category":"SPOT","lastPrice":"10.02","turnover24h":"8000000",
            "ts":str(NOW_MS)}]}
        chosen,report=run([gate()],{"code":"0","data":[]},NOW_MS,
                          fetcher,bitget_tickers=bitget)
        self.assertEqual(len(chosen),1)
        self.assertEqual(chosen[0]["validated_spot_venues"],["gate","bitget"])
    def test_bitget_futures_never_count_as_second_spot(self):
        bitget={"code":"00000","data":[{"symbol":"XYZUSDT",
            "category":"USDT-FUTURES","lastPrice":"10","turnover24h":"8000000",
            "ts":str(NOW_MS)}]}
        chosen,_=run([gate()],{"code":"0","data":[]},NOW_MS,
                     fetcher,bitget_tickers=bitget)
        self.assertEqual(chosen,[])
    def test_bitget_spot_low_turnover_rejected(self):
        bitget={"code":"00000","data":[{"symbol":"XYZUSDT",
            "category":"SPOT","lastPrice":"10","turnover24h":"100",
            "ts":str(NOW_MS)}]}
        chosen,_=run([gate()],{"code":"0","data":[]},NOW_MS,
                     fetcher,bitget_tickers=bitget)
        self.assertEqual(chosen,[])
    def test_gate_only_rejected(self):
        chosen,report=run([gate()],{"code":"0","data":[]},NOW_MS,fetcher)
        self.assertEqual(chosen,[])
        self.assertEqual(report["ticker_correlated"],0)
    def test_too_little_okx_liquidity_rejected(self):
        chosen,_=run([gate()],{"code":"0","data":[okx(volume=300000)]},NOW_MS,fetcher)
        self.assertEqual(chosen,[])
    def test_stale_ticker_rejected(self):
        chosen,_=run([gate()],{"code":"0","data":[okx(stamp=NOW_MS-60*60*1000)]},NOW_MS,fetcher)
        self.assertEqual(chosen,[])
    def test_exchange_price_disagreement_rejected(self):
        chosen,_=run([gate()],{"code":"0","data":[okx(price="11")]},NOW_MS,fetcher)
        self.assertEqual(chosen,[])
    def test_mismatched_close_candle_rejected(self):
        def bad(venue,symbol):
            bars=rows()
            if venue=="okx":
                for bar in bars:bar["ts"]-=CANDLE_MS
            return "test://"+venue,bars
        chosen,report=run([gate()],{"code":"0","data":[okx()]},NOW_MS,bad)
        self.assertEqual(chosen,[])
        self.assertEqual(report["candle_rejected"][0]["symbol"],"XYZUSDT")
    def test_missing_15m_quote_liquidity_rejected(self):
        def thin(venue,symbol):
            return "test://"+venue,rows(vol=1000 if venue=="okx" else 100000)
        chosen,_=run([gate()],{"code":"0","data":[okx()]},NOW_MS,thin)
        self.assertEqual(chosen,[])
    def test_leveraged_and_nonfinite_tickers_rejected(self):
        items=[gate("ETH5L"),gate("XYZ",volume=float("inf")),gate("GOOD")]
        self.assertEqual([x["symbol"] for x in select(items,existing=set())],["GOODUSDT"])
    def test_fail_closed_without_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"discovery.json"
            f.write_text(json.dumps({"status":"ok",
                "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                "candidates":[{"symbol":"XYZUSDT"}]}))
            self.assertEqual(dynamic_symbols(f),())
            f.write_text(json.dumps({"status":"ok",
                "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
                "candidates":[{"symbol":"XYZUSDT","two_venue_ohlcv_verified":True,
                               "validated_spot_venues":["gate","okx"]}]}))
            self.assertEqual(dynamic_symbols(f),("XYZUSDT",))

if __name__=="__main__":
    unittest.main()
