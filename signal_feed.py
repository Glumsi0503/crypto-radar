#!/usr/bin/env python3
"""Durable research signal feed for ChatGPT scheduled readers; NOT a push service."""
import datetime as dt
import json
from pathlib import Path
from strategy import market, consensus, parse_time

SOURCE=Path("docs/latest.json")
OUT=Path("docs/signal_feed.json")
HISTORY=Path("docs/signal_history.json")
UTC=dt.timezone.utc

def market_regime(markets):
    changes={}
    for symbol in ("BTCUSDT","ETHUSDT"):
        rows=markets.get(symbol,[])
        observations=sorted(x["change_percent"] for _,x in rows
                            if x.get("valid") and x.get("change_percent") is not None)
        if len(observations)<2:
            return "unknown"
        changes[symbol]=observations[len(observations)//2]
    if all(x>=0.5 for x in changes.values()):return "short_term_risk_on"
    if all(x<=-0.5 for x in changes.values()):return "short_term_risk_off"
    return "neutral_or_mixed"

def prewatch(markets):
    result=[]
    for symbol,rows in markets.items():
        qualified=[(venue,x) for venue,x in rows if
                   2<=x.get("change_percent",-999)<3.0 and
                   x.get("volume_multiplier",0)>=2 and
                   x.get("spot_quote_volume_usdt",0)>=100000]
        by_candle={}
        for venue,x in qualified:
            by_candle.setdefault(x["candle_start_utc"],[]).append((venue,x))
        for candle,group in by_candle.items():
            if len({v for v,_ in group})<2:continue
            prices=[x["spot_close_usdt"] for _,x in group]
            if min(prices)<=0 or max(prices)/min(prices)>1.01:continue
            result.append({"symbol":symbol,"candle_start_utc":candle,
                "reference_price_usdt":round(sum(prices)/len(prices),8),
                "venues":sorted({v for v,_ in group}),
                "stage":"EARLY_RESEARCH","not_a_buy_signal":True})
    return result

def build(report, history, now):
    created=parse_time(report["generated_at_utc"])
    if created.tzinfo is None or not dt.timedelta(0)<=now-created<=dt.timedelta(minutes=40):
        raise ValueError("stale_source")
    markets=market(report)
    # Paper strategy uses a deliberately wider 2%/2x research heuristic.
    # The higher-stage momentum event needs >=3% AND >=3x on two venues.
    confirmed=[{"symbol":x["symbol"],"candle_start_utc":x["candle_start_utc"],
                "reference_price_usdt":x["price_reference_usdt"],
                "venues":x["venues"],"stage":"MOMENTUM_RESEARCH",
                "not_a_buy_signal":True} for x in consensus(markets)
               if sum(1 for venue,d in markets.get(x["symbol"],[])
                      if venue in x["venues"] and d["candle_start_utc"]==x["candle_start_utc"]
                      and d["change_percent"]>=3 and d["volume_multiplier"]>=3)>=2]
    research=prewatch(markets)+confirmed
    seen=set(history.get("keys",[]))
    new=[]
    for item in research:
        key=item["symbol"]+"|"+item["candle_start_utc"]+"|"+item["stage"]
        item["event_id"]=key
        if key not in seen:
            seen.add(key)
            new.append(item)
    # Persist deduplication so repeated scheduled scans cannot manufacture fresh events.
    history["keys"]=sorted(seen)[-3000:]
    history["updated_at_utc"]=now.isoformat()
    feed={"generated_at_utc":now.isoformat(),"source_generated_at_utc":created.isoformat(),
          "research_only":True,"auto_push_connected":False,"venue_buyability_checked":False,
          "market_regime_15m":market_regime(markets),
          "current_candidates":research,"new_events":new,
          "new_event_count":len(new),"notice":"Research observations only. No automatic external push, no order, no verified exchange availability."}
    return feed,history

def main():
    report=json.loads(SOURCE.read_text())
    history=json.loads(HISTORY.read_text()) if HISTORY.exists() else {"keys":[]}
    feed,history=build(report,history,dt.datetime.now(UTC))
    OUT.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+"\n")
    HISTORY.write_text(json.dumps(history,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"research_events":len(feed["current_candidates"]),
                      "new_events":feed["new_event_count"],"auto_push_connected":False}))

if __name__=="__main__":
    main()
