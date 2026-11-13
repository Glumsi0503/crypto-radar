import unittest
from backtest import backtest,PERIOD

def bars(n=360):
    out=[]
    for i in range(n):
        out.append({"ts":1700000000+i*PERIOD,"open":100.0,"close":100.0,
                    "high":101.0,"low":99.0,"volume":1000.0})
    out[20].update({"open":100,"close":103.5,"high":200,"low":100,"volume":500000})
    for i in range(21,n):
        out[i].update({"open":103.5,"close":103.5,"high":104.0,"low":103.0,"volume":1000})
    return out

class BacktestTests(unittest.TestCase):
    def test_next_open_and_target(self):
        sample=bars()
        sample[22]["high"]=110
        rows=backtest(sample)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["exit_model"],"target_assumed")
        self.assertEqual(rows[0]["entry_candle_utc"],"2023-11-15T03:28:20+00:00")
    def test_both_hit_stop_first(self):
        sample=bars()
        sample[21]["high"]=110
        sample[21]["low"]=95
        result=backtest(sample)
        self.assertEqual(result[0]["exit_model"],"stop_assumed")
        self.assertLess(result[0]["net_percent"],0)
    def test_right_censored_not_invented(self):
        self.assertEqual(backtest(bars(40)),[])
    def test_no_low_liquidity_signals(self):
        sample=bars()
        sample[20]["volume"]=2000
        self.assertEqual(backtest(sample),[])
    def test_gap_rejected(self):
        sample=bars()
        sample[10]["ts"]+=100
        # Gap invalidates the first candidate's lookback.
        self.assertEqual(backtest(sample),[])

if __name__=="__main__":unittest.main()
