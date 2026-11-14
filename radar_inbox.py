#!/usr/bin/env python3
"""Reader-friendly research inbox. Never an automatic buy signal or push service."""
import datetime as dt
import json
from pathlib import Path
from five_method_audit import moment, fresh
from data_freshness import classification, RESEARCH_MAX_AGE_MIN

UTC=dt.timezone.utc
SOURCE_MAX_MIN=40
RECENT_EVENT_MAX_MIN=60

def build(feed, audit, now):
    if not fresh(feed,now) or not fresh(audit,now):
        raise ValueError("stale_or_missing_research_sources")
    source_mode=classification(feed["source_generated_at_utc"],now)
    if source_mode=="expired":
        raise ValueError("underlying_candles_outside_historical_window")
    by_symbol={row["symbol"]:row for row in audit.get("coins",[])}
    rows=[]
    seen=set()
    for event in (feed.get("recent_events_3h",[]) if source_mode=="current" else []):
        if not isinstance(event,dict):continue
        try:
            key=event["event_id"]
            coin=event["symbol"]
            age_min=(now-moment(event["first_seen_utc"])).total_seconds()/60
            candle_age=(now-(moment(event["candle_start_utc"])+dt.timedelta(minutes=15))).total_seconds()/60
            if not (0<=age_min<=RECENT_EVENT_MAX_MIN and 0<=candle_age<=SOURCE_MAX_MIN):
                continue
            if key in seen:continue
            audit_row=by_symbol.get(coin)
            if not audit_row:continue
            mom=audit_row.get("methods",{}).get("momentum",{})
            stage=event.get("stage")
            if stage=="MOMENTUM_RESEARCH" and mom.get("status")!="supported":continue
            if stage not in ("MOMENTUM_RESEARCH","EARLY_RESEARCH"):continue
            venues=event.get("venues",[])
            if len(set(venues))<2:continue
            price=float(event["reference_price_usdt"])
            if not 0<price<float("inf"):continue
            statuses={k:v.get("status","not_evaluable") for k,v in audit_row.get("methods",{}).items()}
            seen.add(key)
            rows.append({"event_id":key,"symbol":coin,"research_stage":stage,
                "first_seen_utc":event["first_seen_utc"],
                "candle_start_utc":event["candle_start_utc"],
                "reference_price_usdt":price,"venues":sorted(set(venues)),
                "methods":statuses,"coin_exchange_buyability_checked":False,
                "must_recheck_live_price":True,"not_a_buy_signal":True,
                "priority":"higher" if stage=="MOMENTUM_RESEARCH" else "watch"})
        except (KeyError,ValueError,TypeError):continue
    rows.sort(key=lambda x:(x["priority"]!="higher",x["first_seen_utc"]))
    # Research-only older signals appear separately. Never re-label as actionable.
    archived=[]
    if source_mode=="historical_only":
        for entry in feed.get("historical_candidates",[]):
            if not isinstance(entry,dict):continue
            sym=entry.get("symbol")
            if sym not in by_symbol:continue
            stage=entry.get("stage")
            if stage not in ("EARLY_RESEARCH","MOMENTUM_RESEARCH"):continue
            if stage=="MOMENTUM_RESEARCH" and by_symbol[sym].get("methods",{}).get("momentum",{}).get("status")!="supported":continue
            archived.append({"symbol":sym,"research_stage":stage,
                             "candle_start_utc":entry.get("candle_start_utc"),
                             "classification":"historical_only",
                             "not_a_buy_signal":True})
    return {"generated_at_utc":now.isoformat(),
        "feed_generated_at_utc":feed["generated_at_utc"],
        "audit_generated_at_utc":audit["generated_at_utc"],
        "research_only":True,"push_service_configured":False,
        "reliable_user_delivery_tested":False,
        "requires_independent_live_check":True,
        "candidate_count":len(rows),"candidates":rows,
        "historical_candidate_count":len(archived),
        "historical_candidates":archived,
        "underlying_source_classification":source_mode,
        "historical_research_max_age_minutes":RESEARCH_MAX_AGE_MIN,
        "status":"RESEARCH_CANDIDATES" if rows else "NO_CURRENT_VALIDATED_CANDIDATES",
        "notice":"Reader inbox only; ChatGPT tasks must fetch and independently validate. No direct push or trading permission."}

def main():
    doc=json.loads(Path("docs/signal_feed.json").read_text())
    audit=json.loads(Path("docs/five_method_audit.json").read_text())
    result=build(doc,audit,dt.datetime.now(UTC))
    output=Path("docs/radar_inbox.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"candidate_count":result["candidate_count"],
                      "push_configured":False}))

if __name__=="__main__":main()
