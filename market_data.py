#!/usr/bin/env python3
"""Public spot-market OHLCV diagnostics; NEVER an order or trading signal."""
import datetime as dt
import json
import time
import urllib.request
from pathlib import Path

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "LINKUSDT", "AAVEUSDT", "UNIUSDT", "AVAXUSDT", "NEARUSDT", "ATOMUSDT", "INJUSDT", "ARBUSDT", "OPUSDT", "OSMOUSDT", "SUIUSDT", "SEIUSDT", "APTUSDT", "TIAUSDT", "FETUSDT", "RENDERUSDT", "ONDOUSDT", "PEPEUSDT", "WIFUSDT", "BONKUSDT", "HYPEUSDT", "INITUSDT", "LSKUSDT", "STORJUSDT", "ZORAUSDT", "MORPHOUSDT", "ADAUSDT", "XRPUSDT", "DOGEUSDT", "LTCUSDT", "BCHUSDT", "TRXUSDT", "TONUSDT", "TAOUSDT", "PENGUUSDT", "PUMPUSDT", "JUPUSDT", "ENAUSDT", "CRVUSDT", "LDOUSDT", "IMXUSDT", "GRTUSDT", "RUNEUSDT", "KASUSDT", "ZECUSDT", "XLMUSDT", "PYTHUSDT")
EXCHANGES = ("okx", "gate", "bitget")  # empirically accessible sources; preserve alternatives in fetch() for future reassessment
CANDLE_MS = 900_000

def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent":"CryptoRadarResearch/0.1", "Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=12) as response:
        return json.loads(response.read(2_000_000))

def fetch(exchange, symbol):
    if exchange == "binance":
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=30"
        rows = get_json(url)
        bars = [{"ts":int(x[0]),"open":float(x[1]),"close":float(x[4]),"volume":float(x[7])} for x in rows]
    elif exchange == "bybit":
        url = f"https://api.bybit.com/v5/market/kline?category=spot&symbol={symbol}&interval=15&limit=30"
        obj = get_json(url)
        if obj.get("retCode") != 0: raise ValueError(str(obj.get("retMsg")))
        bars = [{"ts":int(x[0]),"open":float(x[1]),"close":float(x[4]),"volume":float(x[6])} for x in obj["result"]["list"]]
    elif exchange == "okx":
        url = f"https://www.okx.com/api/v5/market/candles?instId={symbol[:-4]}-USDT&bar=15m&limit=30"
        obj = get_json(url)
        if obj.get("code") != "0": raise ValueError(str(obj.get("msg")))
        bars = [{"ts":int(x[0]),"open":float(x[1]),"close":float(x[4]),"volume":float(x[7]),"confirmed":x[8]=="1"} for x in obj["data"]]
    elif exchange == "gate":
        url = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={symbol[:-4]}_USDT&interval=15m&limit=30"
        rows = get_json(url)
        bars = [{"ts":int(x[0])*1000,"open":float(x[5]),"close":float(x[2]),"volume":float(x[1]),"confirmed":bool(x[7]) if len(x)>7 else True} for x in rows]
    elif exchange == "bitget":
        url = f"https://api.bitget.com/api/v3/market/candles?category=SPOT&symbol={symbol}&interval=15m&limit=30"
        obj = get_json(url)
        if obj.get("code") != "00000": raise ValueError(str(obj.get("msg")))
        bars = [{"ts":int(x[0]),"open":float(x[1]),"close":float(x[4]),"volume":float(x[6])} for x in obj["data"]]
    else:
        raise ValueError("unknown exchange")
    return url, sorted(bars, key=lambda b:b["ts"])

def evaluate(bars, now_ms):
    closed = sorted([b for b in bars if b["ts"]+CANDLE_MS<=now_ms and b.get("confirmed",True)],key=lambda b:b["ts"])
    if len(closed)<21: return {"valid":False,"reason":"less_than_21_closed_candles"}
    sample=closed[-21:]
    if any(sample[i+1]["ts"]-sample[i]["ts"] != CANDLE_MS for i in range(20)):
        return {"valid":False,"reason":"discontinuous_candles"}
    last=sample[-1]
    if now_ms-(last["ts"]+CANDLE_MS)>CANDLE_MS*2:
        return {"valid":False,"reason":"stale_candle"}
    if last["open"]<=0 or any(b["volume"]<0 for b in sample):
        return {"valid":False,"reason":"invalid_ohlcv"}
    base=sum(b["volume"] for b in sample[:-1])/20
    if base<=0:return {"valid":False,"reason":"zero_baseline_volume"}
    change=(last["close"]/last["open"]-1)*100
    ratio=last["volume"]/base
    return {"valid":True,"candle_start_utc":dt.datetime.fromtimestamp(last["ts"]/1000,dt.timezone.utc).isoformat(),
            "change_percent":round(change,5),"volume_multiplier":round(ratio,4),
            "spot_quote_volume_usdt":round(last["volume"],2),"baseline_quote_volume_usdt":round(base,2),
            "spot_close_usdt":last["close"],"pattern_met":change>=3 and ratio>=3}

def collect(symbols=SYMBOLS, venues=EXCHANGES, fetcher=fetch, current_ms=None):
    now_ms=current_ms if current_ms is not None else int(time.time()*1000)
    observations=[]
    research=[]
    for symbol in symbols:
        positives=[]
        for venue in venues:
            began=utc_now()
            url=None
            try:
                url, candles=fetcher(venue,symbol)
                check=evaluate(candles,now_ms)
                observations.append({"symbol":symbol,"venue":venue,"queried_at_utc":began,
                                     "source_url":url,"status":"ok" if check["valid"] else "invalid",
                                     "data":check})
                if check["valid"] and check["pattern_met"]:
                    positives.append({"venue":venue,**check})
            except Exception as e:
                observations.append({"symbol":symbol,"venue":venue,"queried_at_utc":began,
                                     "source_url":url,"status":"error","error":(type(e).__name__+": "+str(e))[:200]})
            if fetcher is fetch:time.sleep(.15)
        confirmed=[p for p in positives if sum(x["candle_start_utc"]==p["candle_start_utc"] for x in positives)>=2]
        if confirmed:
            research.append({"symbol":symbol,"status":"RESEARCH_ONLY","venues":confirmed,
                             "bitvavo_de_spot_verified":False,"trade_alert":False})
    good=sum(x["status"]=="ok" for x in observations)
    return {"schema_version":1,"generated_at_utc":utc_now(),
            "quality":{"status":"LIVE_DATA_OBTAINED" if good else "NO_VALID_DATA","checks":len(observations),
                       "valid_checks":good,"full_market_coverage":False},
            "research_only":research,"sources":observations,
            "bitvavo_de_spot_status":"NOT_VERIFIED","alerts_permitted":False,
            "disclaimer":"No Bitvavo DE verification, no 5-method cross-check, no liquidity test, no ChatGPT automation integration."}

if __name__=="__main__":
    report=collect()
    path=Path("docs/latest.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"valid_checks":report["quality"]["valid_checks"],"checks":report["quality"]["checks"],
                      "research_patterns":len(report["research_only"]),"alerts_permitted":False}))
    if report["quality"]["valid_checks"]==0: raise SystemExit(2)
