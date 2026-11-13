#!/usr/bin/env python3
"""Fail-closed data-quality audit. Does not modify strategies, send alerts or trade."""
import datetime as dt
import json
from pathlib import Path

UTC=dt.timezone.utc
MAX_AGE_MIN=40
def parse(s):
    t=dt.datetime.fromisoformat(s.replace("Z","+00:00"))
    if t.tzinfo is None:raise ValueError("timezone_missing")
    return t.astimezone(UTC)
def audit(root=Path("docs"), now=None):
    now=now or dt.datetime.now(UTC)
    details={}
    for name in ("latest","enrichment","strategy_status","signal_feed","discovery","derivatives","five_method_audit","observed_outcomes","radar_inbox"):
        path=root/(name+".json")
        item={"exists":path.exists(),"fresh":False,"valid":False}
        if path.exists():
            try:
                obj=json.loads(path.read_text(encoding="utf-8"))
                age=(now-parse(obj["generated_at_utc"])).total_seconds()/60
                item["age_minutes"]=round(age,2)
                item["fresh"]=0<=age<=MAX_AGE_MIN
                if name=="latest":
                    q=obj.get("quality",{})
                    item["checks"]=q.get("checks",0)
                    item["valid_checks"]=q.get("valid_checks",0)
                    item["valid"]=isinstance(q.get("valid_checks"),int) and q["valid_checks"]>0 and item["fresh"]
                elif name=="enrichment":
                    q=obj.get("quality",{})
                    item["market_valid"]=q.get("market_valid",0)
                    item["fundamental_reachable"]=q.get("fundamental_reachable",0)
                    item["valid"]=isinstance(q.get("market_valid"),int) and q["market_valid"]>0 and item["fresh"]
                elif name=="strategy_status":
                    item["valid"]=item["fresh"] and obj.get("eligible_for_real_trading") is False
                elif name=="signal_feed":
                    source_age=(now-parse(obj["source_generated_at_utc"])).total_seconds()/60
                    item["source_age_minutes"]=round(source_age,2)
                    item["valid"]=item["fresh"] and 0<=source_age<=MAX_AGE_MIN and obj.get("research_only") is True
                    item["new_event_count"]=obj.get("new_event_count",0)
                elif name=="discovery":
                    item["discovered"]=len(obj.get("candidates",[]))
                    item["valid"]=item["fresh"] and obj.get("status")=="ok"
                elif name=="derivatives":
                    item["valid_snapshots"]=sum(x.get("status")=="ok" for x in obj.get("records",[]))
                    item["valid"]=item["fresh"] and item["valid_snapshots"]>0
                elif name=="five_method_audit":
                    item["evaluated"]=obj.get("symbols_evaluated",0)
                    item["valid"]=item["fresh"] and obj.get("research_only") is True and obj.get("trade_alert_authorized") is False
                elif name=="observed_outcomes":
                    item["observations"]=obj.get("observation_count",0)
                    item["valid"]=item["fresh"] and obj.get("no_actual_orders_or_fills") is True
                elif name=="radar_inbox":
                    source_age=(now-parse(obj["feed_generated_at_utc"])).total_seconds()/60
                    audit_age=(now-parse(obj["audit_generated_at_utc"])).total_seconds()/60
                    item["candidate_count"]=obj.get("candidate_count",0)
                    item["valid"]=item["fresh"] and 0<=source_age<=MAX_AGE_MIN and 0<=audit_age<=MAX_AGE_MIN and obj.get("research_only") is True and obj.get("push_service_configured") is False
            except (OSError,ValueError,KeyError,TypeError) as e:
                item["error"]=type(e).__name__+": "+str(e)[:120]
        details[name]=item
    return {"generated_at_utc":now.isoformat(),"data_quality":"USABLE_RESEARCH_ONLY" if details["latest"]["valid"] else "NO_VERIFIED_FRESH_MARKET_DATA",
            "checks":details,"trade_alerts_permitted":False,
            "automated_remediation":"fail-closed; never reuse stale reports; continue independent sources next run",
            "notes":["Enrichment fundamental_reachable does not establish fundamental growth.",
                     "No account-level exchange buying checks or automatic trade execution; research-only diagnostics."]}
if __name__=="__main__":
    root=Path("docs")
    root.mkdir(exist_ok=True)
    result=audit(root)
    (root/"health.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"data_quality":result["data_quality"],"checks":result["checks"]}))
