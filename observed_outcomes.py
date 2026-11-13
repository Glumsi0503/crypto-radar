#!/usr/bin/env python3
"""Observed signal checkpoints, never invented fills or backtest returns."""
import datetime as dt
import json
from pathlib import Path
from statistics import median
from strategy import market,parse_time

UTC=dt.timezone.utc
CHECKPOINT_HOURS=(1,4,24,72)
OBSERVATION_WINDOW=dt.timedelta(minutes=35)
MAX_SOURCE_AGE=dt.timedelta(minutes=40)
ASSUMED_FEES_ROUNDTRIP_PERCENT=0.50
SOURCE=Path("docs/latest.json")
EVENTS=Path("docs/signal_history.json")
JOURNAL=Path("docs/observed_outcomes_journal.json")
OUTPUT=Path("docs/observed_outcomes.json")

def quote(markets,symbol):
    entries=markets.get(symbol,[])
    by_candle={}
    for venue,d in entries:
        try:
            price=float(d["spot_close_usdt"])
            if not 0<price<float("inf"):continue
            by_candle.setdefault(d["candle_start_utc"],[]).append((venue,price))
        except (ValueError,TypeError,KeyError):continue
    if not by_candle:return None
    candle=max(by_candle)
    rows=by_candle[candle]
    if len({venue for venue,_ in rows})<2:return None
    prices=[price for _,price in rows]
    if max(prices)/min(prices)-1>0.01:return None
    return {"price":median(prices),"candle":candle,
            "venues":sorted({venue for venue,_ in rows})}

def advance(spot, events, journal, now):
    source_at=parse_time(spot["generated_at_utc"])
    if source_at.tzinfo is None or not dt.timedelta(0)<=now-source_at<=MAX_SOURCE_AGE:
        raise ValueError("stale_market_source")
    markets=market(spot)
    items=journal.setdefault("observations",[])
    indexed={e["event_id"]:e for e in items}
    for incoming in events.get("events",[]):
        if not isinstance(incoming,dict):continue
        key=incoming.get("event_id")
        entry=incoming.get("reference_price_usdt")
        if not key or key in indexed or not isinstance(entry,(float,int)) or entry<=0:continue
        try:
            first=parse_time(incoming["first_seen_utc"])
            if first.tzinfo is None or not dt.timedelta(0)<=now-first<=dt.timedelta(hours=3):continue
        except (ValueError,KeyError,TypeError):continue
        row={"event_id":key,"symbol":incoming["symbol"],"stage":incoming["stage"],
             "first_seen_utc":first.isoformat(),"reference_price_usdt":entry,
             "checkpoints":{},"research_only":True}
        items.append(row)
        indexed[key]=row
    for row in items:
        first=parse_time(row["first_seen_utc"])
        obs=quote(markets,row["symbol"])
        for hours in CHECKPOINT_HOURS:
            k=str(hours)+"h"
            if k in row["checkpoints"]:continue
            age=now-first-dt.timedelta(hours=hours)
            if age < dt.timedelta(0):continue
            if age>OBSERVATION_WINDOW:
                row["checkpoints"][k]={"status":"missed_window","reason":"no_verifiable_checkpoint_in_window"}
                continue
            if obs is None:continue
            # Price only if candle closed after first seen and before this checkpoint run.
            candle_at=parse_time(obs["candle"])+dt.timedelta(minutes=15)
            if candle_at<=first or candle_at>now:continue
            gross=100*(obs["price"]/row["reference_price_usdt"]-1)
            row["checkpoints"][k]={"status":"observed","observed_at_utc":now.isoformat(),
                 "price_reference_usdt":round(obs["price"],9),"candle_start_utc":obs["candle"],
                 "venues":obs["venues"],"gross_change_percent":round(gross,4),
                 "net_after_assumed_fees_percent":round(gross-ASSUMED_FEES_ROUNDTRIP_PERCENT,4)}
    # Only observed checkpoints; small samples never used for optimisation.
    performance={}
    for hours in CHECKPOINT_HOURS:
        k=str(hours)+"h"
        values=[r["checkpoints"][k]["net_after_assumed_fees_percent"] for r in items
                if r["checkpoints"].get(k,{}).get("status")=="observed"]
        missing=sum(r["checkpoints"].get(k,{}).get("status")=="missed_window" for r in items)
        performance[k]={"observed":len(values),"missed":missing,
                        "median_net_percent":round(median(values),4) if values else None,
                        "positive_fraction":round(sum(x>0 for x in values)/len(values),4) if values else None,
                        "sufficient_sample":len(values)>=30}
    return {"generated_at_utc":now.isoformat(),"research_only":True,
            "no_actual_orders_or_fills":True,"fee_assumption_roundtrip_percent":ASSUMED_FEES_ROUNDTRIP_PERCENT,
            "slippage_modelled":False,"observation_count":len(items),
            "checkpoint_summary":performance,
            "warnings":["Checkpoint prices are scheduled observations, not real stop/target fills.",
                        "Missed checkpoints remain missing, never interpolated.",
                        "No strategy tuning without adequate out-of-sample results."]}

def main():
    spot=json.loads(SOURCE.read_text())
    events=json.loads(EVENTS.read_text()) if EVENTS.exists() else {"events":[]}
    journal=json.loads(JOURNAL.read_text()) if JOURNAL.exists() else {"observations":[]}
    outcome=advance(spot,events,journal,dt.datetime.now(UTC))
    JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2)+"\n")
    OUTPUT.write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"observations":outcome["observation_count"],"real_orders":0}))

if __name__=="__main__":main()
