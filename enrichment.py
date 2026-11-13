#!/usr/bin/env python3
"""Independent public-data enrichment; research only, never an entry signal."""
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

UTC = dt.timezone.utc
SYMBOLS = ("BTC","ETH","SOL","LINK","AAVE","UNI","AVAX","NEAR","ATOM","INJ","ARB","OP","SUI","SEI","APT","TIA","FET","RENDER","ONDO","HYPE","ADA","XRP","DOGE","TAO")
VENUES = ("okx","gate")  # proven 1h/1d OHLCV; Bitget v3 intervals failed HTTP 400
INTERVAL_MS = {"1h":3600000,"1d":86400000}

def now_utc():
    return dt.datetime.now(UTC).isoformat(timespec="seconds")

def request_json(url, limit=1500000):
    req=urllib.request.Request(url,headers={"User-Agent":"CryptoRadarResearch/0.2","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=10) as response:
        payload=response.read(limit+1)
        if len(payload)>limit: raise ValueError("response_too_large")
        return json.loads(payload)

def endpoint(venue,coin,interval):
    if venue=="okx":
        bar={"1h":"1H","1d":"1Dutc"}[interval]
        return "https://www.okx.com/api/v5/market/history-candles?"+urllib.parse.urlencode({"instId":coin+"-USDT","bar":bar,"limit":40})
    if venue=="gate":
        bar={"1h":"1h","1d":"1d"}[interval]
        return "https://api.gateio.ws/api/v4/spot/candlesticks?"+urllib.parse.urlencode({"currency_pair":coin+"_USDT","interval":bar,"limit":40})
    if venue=="bitget":
        bar={"1h":"1h","1d":"1day"}[interval]
        return "https://api.bitget.com/api/v3/market/candles?"+urllib.parse.urlencode({"category":"SPOT","symbol":coin+"USDT","interval":bar,"limit":40})
    raise ValueError("unknown venue")

def parse_bars(venue,obj):
    if venue=="okx":
        if obj.get("code")!="0":raise ValueError(str(obj.get("msg")))
        return [{"ts":int(x[0]),"open":float(x[1]),"close":float(x[4]),"quote_volume":float(x[7]),"confirmed":x[8]=="1"} for x in obj["data"]]
    if venue=="gate":
        return [{"ts":int(x[0])*1000,"open":float(x[5]),"close":float(x[2]),"quote_volume":float(x[1]),"confirmed":True} for x in obj]
    if obj.get("code")!="00000":raise ValueError(str(obj.get("msg")))
    return [{"ts":int(x[0]),"open":float(x[1]),"close":float(x[4]),"quote_volume":float(x[6]),"confirmed":True} for x in obj["data"]]

def validate(bars, interval, now_ms):
    period=INTERVAL_MS[interval]
    closed=sorted((b for b in bars if b["ts"]+period<=now_ms and b.get("confirmed",True)),key=lambda b:b["ts"])
    if len(closed)<2:return {"valid":False,"reason":"too_few_closed_bars"}
    last=closed[-1]
    if now_ms-last["ts"]-period>2*period:return {"valid":False,"reason":"stale"}
    if any(b["open"]<=0 or b["close"]<=0 or b["quote_volume"]<0 for b in closed):
        return {"valid":False,"reason":"invalid_values"}
    if any(closed[i+1]["ts"]-closed[i]["ts"]!=period for i in range(len(closed)-1)):
        return {"valid":False,"reason":"gaps"}
    return {"valid":True,"latest_closed_start_utc":dt.datetime.fromtimestamp(last["ts"]/1000,UTC).isoformat(),
            "closed_bars":len(closed),"latest_close_usdt":last["close"],
            "last_bar_change_percent":round(100*(last["close"]/last["open"]-1),5),
            "last_bar_quote_volume_usdt":round(last["quote_volume"],2),
            "observed_period_change_percent":round(100*(last["close"]/closed[0]["open"]-1),5)}

def verified_weekly_growth(obj, queried_at):
    """Seven complete UTC days versus the seven days before that."""
    if not isinstance(obj, dict):
        return {"growth_verified": False, "reason": "non_object_payload"}
    series=obj.get("totalDataChart")
    if not isinstance(series, list):
        return {"growth_verified": False, "reason": "missing_daily_chart"}
    today=int(queried_at.timestamp())//86400
    daily={}
    for p in series:
        if not isinstance(p, (tuple,list)) or len(p)<2: continue
        try:
            ts=int(p[0])
            value=float(p[1])
            day=ts//86400
            if ts%86400 != 0 or not (0<=value<float("inf")): continue
            if day < today: daily[day]=value
        except (ValueError,TypeError,OverflowError): continue
    days=list(range(today-14,today))
    if any(day not in daily for day in days):
        return {"growth_verified": False, "reason": "missing_14_complete_utc_days"}
    previous=sum(daily[d] for d in days[:7])
    latest=sum(daily[d] for d in days[7:])
    if previous<=0:
        return {"growth_verified": False, "reason": "zero_previous_week"}
    return {"growth_verified": True, "previous_7d": round(previous,2),
            "latest_7d": round(latest,2),
            "growth_percent": round(100*(latest/previous-1),3),
            "window_end_utc": dt.datetime.fromtimestamp(today*86400,UTC).isoformat()}

def collect():
    records=[]
    now_ms=int(time.time()*1000)
    # Only known functioning providers; no repeated blocked Binance/Bybit probes.
    for coin in SYMBOLS:
        for interval in ("1h","1d"):
            for venue in VENUES:
                url=endpoint(venue,coin,interval)
                item={"coin":coin,"interval":interval,"venue":venue,"url":url,"queried_at_utc":now_utc()}
                try:
                    result=validate(parse_bars(venue,request_json(url)),interval,now_ms)
                    item.update({"status":"ok" if result["valid"] else "invalid","data":result})
                except Exception as e:
                    item.update({"status":"error","error":(type(e).__name__+": "+str(e))[:180]})
                records.append(item)
                time.sleep(0.08)
    # Targeted protocol-specific fundamental endpoints; absence is not a negative signal.
    protocols={"AAVE":"aave","UNI":"uniswap","LINK":"chainlink","ARB":"arbitrum","OP":"optimism"}
    fundamentals=[]
    for coin,slug in protocols.items():
        for kind,url in (("protocol","https://api.llama.fi/protocol/"+slug),
                         ("fees","https://api.llama.fi/summary/fees/"+slug+"?dataType=dailyFees"),
                         ("dex","https://api.llama.fi/summary/dexs/"+slug+"?dataType=dailyVolume")):
            item={"coin":coin,"protocol_slug":slug,"kind":kind,"url":url,"queried_at_utc":now_utc()}
            try:
                obj=request_json(url,1500000)
                # Endpoint reachability alone is not proof of growth or value capture.
                growth=verified_weekly_growth(obj,dt.datetime.now(UTC)) if kind in ("fees","dex") else {"growth_verified":False,"reason":"not_a_daily_metric"}
                item.update({"status":"reachable","data_keys":list(obj)[:20] if isinstance(obj,dict) else [],
                             **growth,"token_value_capture_verified":False})
            except Exception as e:
                item.update({"status":"error","error":(type(e).__name__+": "+str(e))[:180]})
            fundamentals.append(item)
            time.sleep(0.1)
    return {"schema_version":1,"generated_at_utc":now_utc(),"research_only":True,
            "exchange_availability_status":"NOT_CHECKED","alerts_permitted":False,
            "scope":"24-coin enrichment subset of 50-coin 15m universe; 1h and daily history, targeted DefiLlama endpoint health only",
            "market_checks":records,"fundamental_checks":fundamentals,
            "quality":{"market_valid":sum(x["status"]=="ok" for x in records),
                       "market_attempts":len(records),
                       "fundamental_reachable":sum(x["status"]=="reachable" for x in fundamentals),
                       "fundamental_attempts":len(fundamentals)},
            "limits":["No exchange-specific buyability verification","No independent wallet-purchase verification",
                      "No funding/OI verification","Growth needs 14 complete UTC days; token value capture still requires independent evidence",
                      "No trade alerts or orders"]}

if __name__=="__main__":
    report=collect()
    path=Path("docs/enrichment.json")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(report["quality"]))
