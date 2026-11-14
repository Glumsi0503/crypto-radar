#!/usr/bin/env python3
"""Durable research signal feed for ChatGPT scheduled readers; NOT a push service."""
import datetime as dt
import json
from pathlib import Path
from strategy import market, consensus, parse_time
from data_freshness import classification, RESEARCH_MAX_AGE_MIN, ACTIONABLE_MAX_AGE_MIN

SOURCE=Path("docs/latest.json")
OUT=Path("docs/signal_feed.json")
HISTORY=Path("docs/signal_history.json")
UTC=dt.timezone.utc
# Research heuristic ~75/100 subjective strictness (not measured trading risk).
EARLY_GAIN_MIN=1.5
EARLY_VOLUME_MIN=1.8
CONFIRMED_GAIN_MIN=2.5
CONFIRMED_VOLUME_MIN=2.5

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
                   EARLY_GAIN_MIN<=x.get("change_percent",-999)<=8 and
                   x.get("volume_multiplier",0)>=EARLY_VOLUME_MIN and
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
    source_mode=classification(report["generated_at_utc"],now)
    if source_mode=="expired":
        raise ValueError("source_older_than_research_window")
    markets=market(report)
    # Paper strategy uses a deliberately wider 2%/2x research heuristic.
    # The higher-stage momentum event needs >=2.5% AND >=2.5x on two venues.
    confirmed=[{"symbol":x["symbol"],"candle_start_utc":x["candle_start_utc"],
                "reference_price_usdt":x["price_reference_usdt"],
                "venues":x["venues"],"stage":"MOMENTUM_RESEARCH",
                "not_a_buy_signal":True} for x in consensus(markets)
               if sum(1 for venue,d in markets.get(x["symbol"],[])
                      if venue in x["venues"] and d["candle_start_utc"]==x["candle_start_utc"]
                      and d["change_percent"]>=CONFIRMED_GAIN_MIN
                      and d["volume_multiplier"]>=CONFIRMED_VOLUME_MIN)>=2]
    confirmed_candles={(x["symbol"],x["candle_start_utc"]) for x in confirmed}
    early=[x for x in prewatch(markets)
           if (x["symbol"],x["candle_start_utc"]) not in confirmed_candles]
    research=early+confirmed
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
    # Backfilled data is historical research, not a newly discovered time-sensitive event.
    if source_mode!="current":
        new=[]
    previously=history.get("events",[])
    event_log={row["event_id"]:row for row in previously if isinstance(row,dict) and "event_id" in row}
    for item in new:
        event_log[item["event_id"]]={**item,"first_seen_utc":now.isoformat()}
    archived_window=[row for row in event_log.values()
                     if "first_seen_utc" in row and
                     0 <= (now-parse_time(row["first_seen_utc"])).total_seconds() <= 24*3600]
    history["events"]=sorted(archived_window,key=lambda x:x["first_seen_utc"])[-1200:]
    recent=[row for row in history["events"]
            if (now-parse_time(row["first_seen_utc"])).total_seconds() <= 3*3600]
    older=[row for row in history["events"]
           if (now-parse_time(row["first_seen_utc"])).total_seconds() > 3*3600]
    history["updated_at_utc"]=now.isoformat()
    feed={"generated_at_utc":now.isoformat(),"source_generated_at_utc":created.isoformat(),
          "research_only":True,"auto_push_connected":False,"venue_buyability_checked":False,
          "market_regime_15m":market_regime(markets),
          "source_data_classification":source_mode,
          "historical_research_max_age_minutes":RESEARCH_MAX_AGE_MIN,
          "actionable_research_max_age_minutes":ACTIONABLE_MAX_AGE_MIN,
          "new_alerts_permitted_from_source":source_mode=="current",
          "signal_profile":{"name":"offensive_research_v75",
              "subjective_strictness_0_100":75,
              "early_gain_min_percent":EARLY_GAIN_MIN,
              "early_volume_multiplier_min":EARLY_VOLUME_MIN,
              "confirmed_gain_min_percent":CONFIRMED_GAIN_MIN,
              "early_gain_max_percent":8,
              "confirmed_volume_multiplier_min":CONFIRMED_VOLUME_MIN,
              "min_independent_spot_venues":2,
              "min_quote_volume_per_venue_usdt":100000,
              "max_spot_price_disagreement_percent":1.0,
              "classification":"subjective_not_statistically_calibrated"},
          "current_candidates":research if source_mode=="current" else [],
          "historical_candidates":research if source_mode=="historical_only" else [],
          "new_events":new,
          "recent_events_3h":recent,
          "historical_events_24h":older,
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
