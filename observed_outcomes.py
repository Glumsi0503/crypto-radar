#!/usr/bin/env python3
"""Observed signal checkpoints, never invented fills or backtest returns."""
import datetime as dt
import json
from pathlib import Path
from statistics import median
from strategy import market,parse_time

UTC=dt.timezone.utc
CHECKPOINT_HOURS=(0.25,0.5,1,2,4,24,72)
OBSERVATION_WINDOW=dt.timedelta(minutes=90)
MAX_CHECKPOINT_PRICE_OFFSET=dt.timedelta(minutes=20)
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
             "checkpoints":{},"research_only":True,"detection_context":incoming.get("detection_context"),"venues":incoming.get("venues",[])}
        items.append(row)
        indexed[key]=row
    for row in items:
        first=parse_time(row["first_seen_utc"])
        obs=quote(markets,row["symbol"])
        for hours in CHECKPOINT_HOURS:
            k=f"{hours:g}h"
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
            # Never substitute a much later scan price for the scheduled checkpoint.
            target_at=first+dt.timedelta(hours=hours)
            if abs(candle_at-target_at)>MAX_CHECKPOINT_PRICE_OFFSET:continue
            gross=100*(obs["price"]/row["reference_price_usdt"]-1)
            row["checkpoints"][k]={"status":"observed","observed_at_utc":now.isoformat(),
                 "price_reference_usdt":round(obs["price"],9),"candle_start_utc":obs["candle"],
                 "checkpoint_offset_minutes":round((candle_at-target_at).total_seconds()/60,2),
                 "venues":obs["venues"],"gross_change_percent":round(gross,4),
                 "net_after_assumed_fees_percent":round(gross-ASSUMED_FEES_ROUNDTRIP_PERCENT,4)}
    # Only observed checkpoints; small samples never used for optimisation.
    performance={}
    for hours in CHECKPOINT_HOURS:
        k=f"{hours:g}h"
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

def research_audit(spot, journal, now):
    """Forward-only sampled price experiments; never infer intrabar fills."""
    markets=market(spot)
    items=journal["observations"]
    cohorts={}
    for row in items:
        cohort=row["first_seen_utc"][:16]
        cohorts.setdefault(cohort,[]).append(row)
        first=parse_time(row["first_seen_utc"])
        if now-first>dt.timedelta(hours=72):continue
        obs=quote(markets,row["symbol"])
        if not obs:continue
        closed=parse_time(obs["candle"])+dt.timedelta(minutes=15)
        if not first<closed<=now or now-closed>MAX_SOURCE_AGE:continue
        # Archive matching closed bars from independent venues, without inventing gaps.
        archive=row.setdefault("ohlcv_by_venue",{})
        for venue,data in markets.get(row["symbol"],[]):
            dest=archive.setdefault(venue,{})
            for bar in data.get("closed_bars",[]):
                t=dt.datetime.fromtimestamp(bar["ts"]/1000,UTC)
                if first-dt.timedelta(hours=24)<=t and t+dt.timedelta(minutes=15)<=now:
                    dest[str(bar["ts"])]=bar
        path=row.setdefault("sampled_path",{})
        path[closed.isoformat()]=obs["price"]
        row["sampled_path"]=dict(sorted(path.items()))
        if "first_context" not in row:
            row["first_context"]={"captured_at_utc":now.isoformat(),
                "at_detection":False,"btc_eth":{s:[{"venue":v,**d} for v,d in markets.get(s,[])] for s in ("BTCUSDT","ETHUSDT")}}
        prices=list(row["sampled_path"].values())
        ref=row["reference_price_usdt"]
        row["sampled_extrema_percent"]={"max":round(100*(max(prices)/ref-1),4),"min":round(100*(min(prices)/ref-1),4)}
        experiments={}
        for entry_rule in ("reference","first_observed","pullback_1pct"):
            entry=None
            for stamp,price in row["sampled_path"].items():
                if entry is None:
                    if entry_rule=="pullback_1pct" and price>ref*.99:continue
                    entry=ref if entry_rule=="reference" else price
                    entry_stamp=stamp
                    if entry_rule!="reference":continue
                for target in (2,3,5):
                    key=f"{entry_rule}_tp{target}_sl2.5"
                    if key in experiments:continue
                    gross=100*(price/entry-1)
                    if gross>=target or gross<=-2.5:
                        experiments[key]={"entry_price":entry,"entry_sample_utc":entry_stamp,
                            "exit_sample_utc":stamp,"exit_price":price,"net_percent":round(gross-.5,4),
                            "reason":"target_sample" if gross>=target else "stop_sample"}
        row["sampled_experiments"]=experiments
    summary=[]
    for stamp,rows in sorted(cohorts.items()):
        vals=[r["checkpoints"]["4h"]["net_after_assumed_fees_percent"] for r in rows if r["checkpoints"].get("4h",{}).get("status")=="observed"]
        summary.append({"first_seen_minute_utc":stamp,"simultaneous_events":len(rows),
            "observed_4h":len(vals),"positive_4h":sum(x>0 for x in vals),
            "mean_net_4h":round(sum(vals)/len(vals),4) if vals else None})
    return {"cohorts":summary,"research_only":True,"live_rules_changed":False,
        "limitations":["Historical intrabar prices and detection context not reconstructed.",
        "Sampled exits are not actual fills; missing intervals may hide stop or target hits.",
        "Reference entry is retrospective and may not be executable.",
        "No automatic parameter selection; validate on later independent market days."]}

def main():
    spot=json.loads(SOURCE.read_text())
    events=json.loads(EVENTS.read_text()) if EVENTS.exists() else {"events":[]}
    journal=json.loads(JOURNAL.read_text()) if JOURNAL.exists() else {"observations":[]}
    outcome=advance(spot,events,journal,dt.datetime.now(UTC))
    outcome["research_audit"]=research_audit(spot,journal,dt.datetime.now(UTC))
    JOURNAL.write_text(json.dumps(journal,ensure_ascii=False,indent=2)+"\n")
    OUTPUT.write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"observations":outcome["observation_count"],"real_orders":0}))

if __name__=="__main__":main()
