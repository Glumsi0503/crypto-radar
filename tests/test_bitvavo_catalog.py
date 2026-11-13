import unittest
from bitvavo_catalog import catalog

TS="2026-11-13T16:00:00+00:00"

class CatalogTests(unittest.TestCase):
    def test_eur_trading_and_nontrading_are_distinct(self):
        markets=[
            {"market":"BTC-EUR","base":"BTC","quote":"EUR","status":"trading"},
            {"market":"BTC-USDT","base":"BTC","quote":"USDT","status":"trading"},
            {"market":"SOL-EUR","base":"SOL","quote":"EUR","status":"halted"},
            {"market":"ETH-EUR","base":"ETH","quote":"EUR","status":"trading"}]
        assets=[{"symbol":"BTC","name":"Bitcoin"},{"symbol":"SOL","name":"Solana"}]
        item=catalog(markets,assets,TS)
        self.assertEqual(item["counts"]["public_trading_eur_markets"],2)
        self.assertEqual(item["counts"]["eur_markets"],3)
        self.assertFalse(item["mandatory_trade_filter"])
        self.assertFalse(item["bitvavo_germany_eligibility_verified"])
        self.assertEqual(item["markets"][0]["name"],"Bitcoin")
        self.assertIn("BTC",item["core_radar_public_trading_symbols"])
        self.assertNotIn("SOL",item["core_radar_public_trading_symbols"])

    def test_missing_name_does_not_drop_market(self):
        item=catalog([{"market":"BTC-EUR","base":"BTC","quote":"EUR","status":"trading"}],[],TS)
        self.assertEqual(item["markets"][0]["name"],None)
        self.assertEqual(item["counts"]["public_trading_eur_markets"],1)

    def test_incomplete_market_payload_not_counted(self):
        with self.assertRaises(ValueError):
            catalog([{"market":"BTC-EUR","base":"BTC","quote":"EUR"}],[],TS)
        with self.assertRaises(ValueError):
            catalog([],[],TS)

    def test_unknown_market_status_not_assumed_trading(self):
        with self.assertRaises(ValueError):
            catalog([{"market":"DOGE-EUR","base":"DOGE","quote":"EUR",
                      "status":"strange-new-status"}],[],TS)

    def test_duplicate_market_not_double_counted(self):
        item=catalog([
            {"market":"BTC-EUR","base":"BTC","quote":"EUR","status":"halted"},
            {"market":"BTC-EUR","base":"BTC","quote":"EUR","status":"trading"}],[],TS)
        self.assertEqual(item["counts"]["public_trading_eur_markets"],1)

if __name__=="__main__":
    unittest.main()
