#!/usr/bin/env python3
"""Five-method evidence audit. Fail closed; not trade or push authorization."""
import datetime as dt
import json
from pathlib import Path
from data_freshness import classification, RESEARCH_MAX_AGE_MIN

UTC=dt.timezone.utc
MAX_AGE=dt.timedelta(minutes=RESEARCH_MAX_AGE_MIN)
STRATEGIES=("momentum","smart_money","short_squeeze","fundamental_divergence","catalyst")
MAX_SPOT_SPREAD=.01
MOMENTUM_GAIN_MIN=2.5
MOMENTUM_VOLUME_MIN=2.5

def moment(value):
    x=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if x.tzinfo is None: raise ValueError("naive_timestamp")
    return x.astimezone(UTC)

def fresh(document, now):
    if not isinstance(document,dict): return False
    try: return dt.timedelta(0)<=now-moment(document["generated_at_utc"])<=MAX_AGE
    except (TypeError,ValueError,KeyError):return False

def state(status,reason,evidence=None):
    return {"status":status,"reason":reason,"evidence":evidence or []}

def spot_groups(report):
    groups={}
    for row in report.get("sources",[]):
        data=row.get("data") or {}
        if row.get("status")!="ok" or not data.get("valid"):continue
        try:
            price=float(data["spot_close_usdt"])
            gain=float(data["change_percent"])
            multiple=float(data["volume_multiplier"])
            volume=float(data["spot_quote_volume_usdt"])
            stamp=data["candle_start_utc"]
            if not 0<price<float("inf") or not 0<=volume<float("inf"):continue
            moment(stamp)
        except (TypeError,ValueError,KeyError):continue
        groups.setdefault((row["symbol"],stamp),[]).append(
            (row["venue"],price,gain,multiple,volume,row.get("source_url")))
    return groups

def momentum(report):
    outcomes={}
    by_coin={}
    for (coin,candle),rows in spot_groups(report).items():
        by_coin.setdefault(coin,[]).append((candle,rows))
    for coin, entries in by_coin.items():
        confirmed=[]
        for candle, rows in entries:
            q=[x for x in rows if MOMENTUM_GAIN_MIN<=x[2]<=8 and x[3]>=MOMENTUM_VOLUME_MIN and x[4]>=100000]
            if len(set(x[0] for x in q))<2:continue
            prices=[x[1] for x in q]
            if min(prices)<=0 or max(prices)/min(prices)-1>MAX_SPOT_SPREAD:continue
            confirmed.append({"candle_start_utc":candle,"venues":sorted(set(x[0] for x in q)),
                              "spot_usdt_reference":round(sum(prices)/len(prices),8),
                              "gain_percent_min":round(min(x[2] for x in q),3),
                              "volume_multiple_min":round(min(x[3] for x in q),3),
                              "source_urls":[x[5] for x in q if x[5]]})
        if confirmed:
            outcomes[coin]=state("supported","Two independent spot venues confirmed momentum",confirmed)
        else:
            outcomes[coin]=state("not_confirmed","No matching two-venue momentum pattern")
    return outcomes

def evaluate(spot, enrichment=None, derivatives=None, now=None):
    now=now or dt.datetime.now(UTC)
    source_mode=classification(spot.get("generated_at_utc") if isinstance(spot,dict) else None,now)
    if source_mode=="expired":raise ValueError("Spot source absent or outside research window")
    if not isinstance(spot.get("sources"),list):raise ValueError("Missing spot source rows")
    coins=sorted({row.get("symbol","")[:-4] for row in spot["sources"]
                  if str(row.get("symbol","")).endswith("USDT")})
    mom=momentum(spot)
    fundamental_ok=fresh(enrichment,now)
    derivative_ok=fresh(derivatives,now)
    metrics={}
    if fundamental_ok:
        for row in enrichment.get("fundamental_checks",[]):
            if row.get("status")=="reachable" and row.get("growth_verified") is True:
                metrics.setdefault(row.get("coin"),[]).append(row)
    deriv={row.get("coin"):row for row in derivatives.get("records",[])} if derivative_ok else {}
    results=[]
    for coin in coins:
        label=coin+"USDT"
        m=mom.get(label,state("not_evaluable","No verified spot candles for this symbol"))
        frows=metrics.get(coin,[])
        f_evidence=[{"metric":r.get("kind"),"growth_7d_percent":r.get("growth_percent"),
                     "window_end_utc":r.get("window_end_utc"),"source":r.get("url")}
                    for r in frows]
        if len({r.get("kind") for r in frows if r.get("growth_percent",-999)>=40})>=2 and all(r.get("token_value_capture_verified") for r in frows):
            f=state("supported","Two independent improving usage metrics with token capture",f_evidence)
        elif f_evidence:
            f=state("not_confirmed","Growth or token value capture criteria not established",f_evidence)
        else:
            f=state("not_evaluable","No verified comparable 7-day fundamental metrics")
        d=deriv.get(coin)
        if d and d.get("status")=="ok":
            details=[{"funding_percent":d.get("funding_rate_percent"),
                      "oi_change_4h_percent":d.get("oi_change_4h_percent"),
                      "funding_interval_unverified":d.get("funding_interval_unverified"),
                      "funding_url":d.get("funding_url"),"oi_url":d.get("open_interest_url")}]
            s=state("not_evaluable","Funding interval and 4h OI plus spot confirmation not yet complete",details)
        else:
            s=state("not_evaluable","No fresh and verified funding/OI pair")
        methods={"momentum":m,"smart_money":state("not_evaluable","No independently verified wallet purchases"),
                 "short_squeeze":s,"fundamental_divergence":f,
                 "catalyst":state("not_evaluable","No dated official catalyst events ingested")}
        results.append({"symbol":label,"methods":methods,
                        "supported_methods":[k for k,v in methods.items() if v["status"]=="supported"],
                        "trade_ready":False,"exchange_buyability_checked":False})
    return {"generated_at_utc":now.isoformat(),"spot_source_at_utc":spot["generated_at_utc"],
            "enrichment_fresh":fundamental_ok,"derivatives_fresh":derivative_ok,
            "research_only":True,"auto_push_connected":False,"trade_alert_authorized":False,
            "spot_source_classification":source_mode,
            "historical_research_max_age_minutes":RESEARCH_MAX_AGE_MIN,
            "method_names":STRATEGIES,"symbols_evaluated":len(results),"coins":results,
            "interpretation":"Each strategy needs its own evidence; absence is never a confirming signal."}

def load(path):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError):return None

def main():
    result=evaluate(load("docs/latest.json"),load("docs/enrichment.json"),load("docs/derivatives.json"))
    path=Path("docs/five_method_audit.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"coins":result["symbols_evaluated"],
                      "momentum_supported":sum("momentum" in x["supported_methods"] for x in result["coins"]),
                      "trade_alert_authorized":False}))

if __name__=="__main__":main()
