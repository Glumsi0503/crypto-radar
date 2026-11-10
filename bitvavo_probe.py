#!/usr/bin/env python3
"""Probe Bitvavo PUBLIC data. A trading market status is NOT proof of Germany-specific eligibility."""
import datetime as dt
import json
from pathlib import Path
import urllib.request

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"CryptoRadarDiagnostics/0.1","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=15) as res:
        return res.status, json.loads(res.read(1200000))

def main():
    ts=dt.datetime.now(dt.timezone.utc).isoformat()
    endpoints={
        "market":"https://api.bitvavo.com/v2/markets?market=BTC-EUR",
        "candles":"https://api.bitvavo.com/v2/BTC-EUR/candles?interval=15m&limit=25",
        "ticker":"https://api.bitvavo.com/v2/ticker/24h?market=BTC-EUR",
    }
    checks={}
    for name,url in endpoints.items():
        try:
            status,data=fetch(url)
            if name=="candles":
                rows=data if isinstance(data,list) else []
                checks[name]={"ok":status==200 and len(rows)>=21,"http_status":status,"rows":len(rows),
                              "latest_timestamp_ms":max(int(x[0]) for x in rows if isinstance(x,list) and len(x)==6) if rows else None,
                              "row_shape_valid":all(isinstance(x,list) and len(x)==6 for x in rows)}
            elif name=="market":
                items=data if isinstance(data,list) else [data]
                checks[name]={"ok":status==200 and len(items)>0,"http_status":status,
                              "markets":[{"market":i.get("market"),"status":i.get("status"),
                                          "base":i.get("base"),"quote":i.get("quote")} for i in items[:3] if isinstance(i,dict)]}
            else:
                items=data if isinstance(data,list) else [data]
                checks[name]={"ok":status==200 and bool(items),"http_status":status,
                              "tickers":[{"market":i.get("market"),"timestamp":i.get("timestamp"),"bid":i.get("bid"),
                                          "ask":i.get("ask"),"volumeQuote":i.get("volumeQuote")} for i in items[:3] if isinstance(i,dict)]}
        except Exception as e:
            checks[name]={"ok":False,"error":str(e)[:180]}
    out={"generated_at_utc":ts,"provider":"Bitvavo public exchange API",
         "scope":"BTC-EUR PUBLIC DATA DIAGNOSTIC ONLY","checks":checks,
         "german_customer_spot_eligibility_verified":False,
         "reason":"Public market status cannot prove individual German-account regional availability",
         "use_in_trade_signals":False}
    p=Path("docs/bitvavo_probe.json")
    p.parent.mkdir(exist_ok=True,parents=True)
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"checks":{k:v["ok"] for k,v in checks.items()},"german_eligibility_verified":False}))

if __name__=="__main__":
    main()
