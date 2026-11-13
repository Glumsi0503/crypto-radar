#!/usr/bin/env python3
"""Find additional research symbols from liquid Gate.io USDT spot markets.
Candidate discovery is not a buy recommendation; collector validates candles next.
"""
import json
import re
from pathlib import Path
from market_data import SYMBOLS, get_json, utc_now

OUT=Path("docs/discovery.json")
CORE=set(SYMBOLS)
MIN_QUOTE_VOLUME=2_000_000
MAX_NEW=10

def select(tickers, existing=CORE, limit=MAX_NEW):
    choices=[]
    if not isinstance(tickers,list): return []
    for row in tickers:
        try:
            pair=row.get("currency_pair","")
            if not re.fullmatch(r"[A-Z0-9]{2,18}_USDT",pair): continue
            symbol=pair.replace("_","")
            base=pair[:-5]
            # Exclude exchange-issued leveraged tokens (e.g. ETH5L, ZEC5S,
            # BTC3S, BTCBULL, ETHBEAR, BTCUP); these are not ordinary spot coins.
            if re.search(r"(?:[2357]L|[2357]S|BULL|BEAR|UP|DOWN)$",base):continue
            if symbol in existing: continue
            volume=float(row.get("quote_volume",0))
            change=abs(float(row.get("change_percentage",0)))
            if volume < MIN_QUOTE_VOLUME or change>150 or change<1: continue
            if not (0 < float(row.get("last",0)) < float("inf")): continue
            choices.append((min(change,35)*volume**0.3,symbol,volume,change))
        except (TypeError,ValueError,OverflowError): continue
    choices.sort(reverse=True)
    return [{"symbol":symbol,"quote_volume_24h_usdt":round(volume,2),
             "abs_change_24h_percent":round(change,3)}
            for _,symbol,volume,change in choices[:limit]]

def main():
    OUT.parent.mkdir(exist_ok=True)
    url="https://api.gateio.ws/api/v4/spot/tickers"
    doc={"generated_at_utc":utc_now(),"source":url,
         "min_24h_quote_volume_usdt":MIN_QUOTE_VOLUME,
         "status":"unavailable","research_only":True,"candidates":[]}
    try:
        doc["candidates"]=select(get_json(url))
        doc["status"]="ok" if doc["candidates"] else "no_candidates"
    except Exception as e:
        doc["error"]=(type(e).__name__+": "+str(e))[:200]
    OUT.write_text(json.dumps(doc,indent=2)+"\n")
    print(json.dumps({"status":doc["status"],"new":len(doc["candidates"])}))

if __name__=="__main__":
    main()
