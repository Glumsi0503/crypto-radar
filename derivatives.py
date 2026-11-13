#!/usr/bin/env python3
"""Derivatives diagnostics (funding/OI snapshots), not a squeeze signal or trade."""
import datetime as dt
import json
import urllib.parse
from pathlib import Path
from enrichment import request_json

UTC=dt.timezone.utc
OUT=Path("docs/derivatives.json")
HISTORY=Path("docs/derivatives_history.json")
COINS=("BTC","ETH","SOL","HYPE","SUI")

def parse_okx(data):
    if not isinstance(data,dict) or data.get("code")!="0" or not data.get("data"):
        raise ValueError("okx_missing_data_or_error")
    return data["data"][0]

def summarize(coin, funding, interest, now):
    inst=coin+"-USDT-SWAP"
    f=parse_okx(funding)
    oi=parse_okx(interest)
    if f.get("instId")!=inst or oi.get("instId")!=inst:
        raise ValueError("instrument_mismatch")
    f_time=int(f["ts"])/1000
    oi_time=int(oi["ts"])/1000
    if now.timestamp()-f_time>1800 or now.timestamp()-oi_time>1800:
        raise ValueError("stale_derivatives_snapshot")
    rate=float(f["fundingRate"])
    oi_value=float(oi["oi"])
    if not (-1 < rate < 1) or oi_value<=0:raise ValueError("invalid_metrics")
    return {"instrument":inst,"funding_rate_percent":round(rate*100,6),
            "oi_contracts":oi_value,
            "funding_timestamp_utc":dt.datetime.fromtimestamp(f_time,UTC).isoformat(),
            "oi_timestamp_utc":dt.datetime.fromtimestamp(oi_time,UTC).isoformat(),
            "funding_interval_unverified":True,"oi_change_4h_percent":None}

def comparison(history, coin, item, now):
    rows=history.setdefault(coin,[])
    old=[r for r in rows if 3.5*3600 <= (now-dt.datetime.fromisoformat(r["timestamp"])).total_seconds() <= 4.5*3600
         and r.get("instrument")==item["instrument"] and r.get("oi_contracts",0)>0]
    if old:
        base=sorted(old,key=lambda x:abs((now-dt.datetime.fromisoformat(x["timestamp"])).total_seconds()-4*3600))[0]
        item["oi_change_4h_percent"]=round(100*(item["oi_contracts"]/base["oi_contracts"]-1),3)
    rows.append({"instrument":item["instrument"],"timestamp":now.isoformat(),
                 "oi_contracts":item["oi_contracts"]})
    history[coin]=[r for r in rows if 0<=(now-dt.datetime.fromisoformat(r["timestamp"])).total_seconds()<=30*3600][-150:]
    return item

def main():
    now=dt.datetime.now(UTC)
    history=json.loads(HISTORY.read_text()) if HISTORY.exists() else {}
    records=[]
    for coin in COINS:
        inst=coin+"-USDT-SWAP"
        a="https://www.okx.com/api/v5/public/funding-rate?"+urllib.parse.urlencode({"instId":inst})
        b="https://www.okx.com/api/v5/public/open-interest?"+urllib.parse.urlencode({"instType":"SWAP","instId":inst})
        row={"coin":coin,"venue":"okx","funding_url":a,"open_interest_url":b,
             "checked_at_utc":now.isoformat(),"status":"error"}
        try:
            item=summarize(coin,request_json(a),request_json(b),now)
            row.update(item)
            row["status"]="ok"
            comparison(history,coin,row,now)
        except Exception as e:
            row["error"]=(type(e).__name__+": "+str(e))[:200]
        records.append(row)
    OUT.write_text(json.dumps({"generated_at_utc":now.isoformat(),"research_only":True,
         "squeeze_signal_verified":False,"records":records,
         "notes":["Funding and current open interest alone do NOT establish a squeeze.",
                  "OI changes only comparable within unchanged swap contracts and sampled history.",
                  "Spot confirmation and funding interval assessment still required."]},indent=2)+"\n")
    HISTORY.write_text(json.dumps(history,indent=2)+"\n")
    print(json.dumps({"derivatives_valid":sum(x["status"]=="ok" for x in records),
                      "attempts":len(records)}))

if __name__=="__main__":
    main()
