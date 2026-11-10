#!/usr/bin/env python3
"""Research-only consensus momentum paper journal. No orders, no real-money alerts."""
import datetime as dt
import json
from pathlib import Path

DATA=Path("docs/latest.json")
STATE=Path("docs/paper_journal.json")
OUT=Path("docs/strategy_status.json")
MAX_AGE_MIN=40
FEE_RATE=0.0025 # assumed per side, intentionally conservative simulation
STOP_PCT=0.025
TARGET_PCT=0.05
MAX_HOURS=72

def parse_time(s):
    return dt.datetime.fromisoformat(s.replace("Z","+00:00"))

def market(report):
    m={}
    for x in report.get("sources",[]):
        d=x.get("data",{})
        if x.get("status")!="ok" or not d.get("valid"):continue
        m.setdefault(x["symbol"],[]).append((x["venue"],d))
    return m

def consensus(reports):
    candidates=[]
    for symbol, entries in reports.items():
        qualifying=[(v,d) for v,d in entries if
            2<=d["change_percent"]<=8 and d["volume_multiplier"]>=2 and
            d["spot_quote_volume_usdt"]>=100000]
        by_candle={}
        for venue,data in qualifying:
            by_candle.setdefault(data["candle_start_utc"],[]).append((venue,data))
        for candle, group in by_candle.items():
            if len(set(v for v,_ in group))<2:continue
            price=[d["spot_close_usdt"] for _,d in group]
            mid=sum(price)/len(price)
            if max(price)/min(price)-1>0.01:continue
            candidates.append({"symbol":symbol,"candle_start_utc":candle,
              "price_reference_usdt":round(mid,8),"venues":[v for v,_ in group],
              "min_quote_volume_usdt":round(min(d["spot_quote_volume_usdt"] for _,d in group),2),
              "min_volume_multiplier":min(d["volume_multiplier"] for _,d in group),
              "label":"RESEARCH_PAPER_ONLY","bitvavo_de_eligibility_verified":False})
    return candidates

def update(report, journal, now):
    if now-parse_time(report["generated_at_utc"])>dt.timedelta(minutes=MAX_AGE_MIN):
        raise ValueError("stale market data")
    if report.get("quality",{}).get("valid_checks",0)<2:
        raise ValueError("insufficient market data")
    markets=market(report)
    findings=consensus(markets)
    trades=journal.setdefault("trades",[])
    for trade in trades:
        if trade.get("state")!="open":continue
        quotes=[d["spot_close_usdt"] for _,d in markets.get(trade["symbol"],[]) if d.get("spot_close_usdt")]
        if not quotes:continue
        price=sorted(quotes)[len(quotes)//2]
        trade["last_price_usdt"]=price
        trade["last_seen_utc"]=now.isoformat()
        trade["best_return_percent"]=max(trade.get("best_return_percent",-100),100*(price/trade["reference_entry_usdt"]-1))
        trade["worst_return_percent"]=min(trade.get("worst_return_percent",100),100*(price/trade["reference_entry_usdt"]-1))
        held_hours=(now-parse_time(trade["opened_at_utc"])).total_seconds()/3600
        gross=price/trade["reference_entry_usdt"]-1
        trigger="stop_observed" if gross<=-STOP_PCT else ("target_observed" if gross>=TARGET_PCT else ("time_exit" if held_hours>=MAX_HOURS else None))
        if trigger:
            trade.update({"state":"closed","closed_at_utc":now.isoformat(),"close_reference_usdt":price,
                          "exit_reason":trigger,"net_pnl_percent":round(gross*100-FEE_RATE*200,5),
                          "note":"Observed checkpoint price, not true intrabar stop/target execution; may overstate realizable fills."})
    # One concurrent paper position per symbol, no hindsight insertion.
    for f in findings:
        if any(t["symbol"]==f["symbol"] and (t["state"]=="open" or
           (t["candle_start_utc"]==f["candle_start_utc"])) for t in trades):
            continue
        if len([t for t in trades if t["state"]=="open"])>=3:break
        trades.append({"symbol":f["symbol"],"candle_start_utc":f["candle_start_utc"],
                       "opened_at_utc":now.isoformat(),"reference_entry_usdt":f["price_reference_usdt"],
                       "venue_confirmations":f["venues"],"state":"open",
                       "last_price_usdt":f["price_reference_usdt"],"best_return_percent":0,
                       "worst_return_percent":0,"eligible_for_real_trade":False})
    closed=[t for t in trades if t["state"]=="closed"]
    good=sum(t["net_pnl_percent"]>0 for t in closed)
    performance={"closed":len(closed),"winners":good,
                 "win_rate_percent":round(100*good/len(closed),2) if closed else None,
                 "avg_net_return_percent":round(sum(t["net_pnl_percent"] for t in closed)/len(closed),3) if closed else None,
                 "notes":"Observation-only simulation; fees approximated at 0.25% per side; excludes slippage, intrabar execution, tax and survivorship effects."}
    return {"generated_at_utc":now.isoformat(),"status":"RESEARCH_ONLY","eligible_for_real_trading":False,
            "candidates":findings,"paper_open":sum(t["state"]=="open" for t in trades),
            "paper_performance":performance,
            "strategy_rules":{"min_two_spot_venues":True,"price_spread_max_percent":1.0,
            "candle_gain_min_percent":2,"candle_gain_max_percent":8,"volume_multiple_min":2,
            "min_quote_volume_per_venue_usdt":100000,"max_simultaneous_paper_positions":3,
            "stop_observation_percent":-2.5,"target_observation_percent":5,"max_holding_hours":72,
            "estimated_fee_per_side_percent":0.25},
            "limits":["Pilot watchlist only, no Germany Bitvavo eligibility or account-level buyability checks",
                      "Prices from independent USDT venues do not equal Bitvavo EUR execution prices",
                      "Paper checkpoints are not proof of actual stop or target fills",
                      "No risk-adjusted or statistically validated profitability yet"]}

def main():
    report=json.loads(DATA.read_text())
    journal=json.loads(STATE.read_text()) if STATE.exists() else {"schema_version":1,"trades":[]}
    now=dt.datetime.now(dt.timezone.utc)
    outcome=update(report,journal,now)
    STATE.write_text(json.dumps(journal,indent=2,ensure_ascii=False)+"\n")
    OUT.write_text(json.dumps(outcome,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"candidates":len(outcome["candidates"]),"open_paper":outcome["paper_open"],
      "completed_paper":outcome["paper_performance"]["closed"],"real_trade_alert":False}))

if __name__=="__main__":
    main()
