#!/usr/bin/env python3
"""Research-only discovery: require two liquid, independently verified SPOT venues.

Gate.io supplies a broad initial shortlist; OKX supplies a second independent
24h ticker check. Final candidates must ALSO pass 21 closed 15m candles on both
venues with matching bar timestamps and agreeing spot prices.
"""
import datetime as dt
import json
import math
import re
import time
from pathlib import Path
from market_data import SYMBOLS, get_json, utc_now, fetch, evaluate

OUT=Path("docs/discovery.json")
CORE=set(SYMBOLS)
GATE_URL="https://api.gateio.ws/api/v4/spot/tickers"
OKX_URL="https://www.okx.com/api/v5/market/tickers?instType=SPOT"
BITGET_URL="https://api.bitget.com/api/v3/market/tickers?category=SPOT"
MIN_GATE_QUOTE_24H=2_000_000
MIN_OKX_QUOTE_24H=1_000_000  # applies to either second SPOT venue
MIN_15M_QUOTE=25_000
MAX_PRICE_DISAGREEMENT=0.02
MAX_NEW=10
MAX_PREFLIGHT=150
MAX_CANDLE_PREFLIGHT=24
CANDLE_MS=900_000
LEVERAGED=re.compile(r"(?:[2357]L|[2357]S|BULL|BEAR|UP|DOWN)$")

def finite_positive(v):
    try:
        n=float(v)
        return n if math.isfinite(n) and n>0 else None
    except (TypeError, ValueError, OverflowError):return None

def select(tickers, existing=CORE, limit=MAX_PREFLIGHT):
    """Rank only sufficiently liquid Gate USDT spot *pre-candidates*."""
    choices=[]
    if not isinstance(tickers,list):return []
    for row in tickers:
        if not isinstance(row,dict):continue
        pair=row.get("currency_pair","")
        if not isinstance(pair,str) or not re.fullmatch(r"[A-Z0-9]{2,18}_USDT",pair):continue
        base=pair[:-5]
        symbol=base+"USDT"
        if LEVERAGED.search(base) or symbol in existing:continue
        volume=finite_positive(row.get("quote_volume"))
        price=finite_positive(row.get("last"))
        try:change=abs(float(row.get("change_percentage",0)))
        except (TypeError,ValueError,OverflowError):continue
        if volume is None or price is None or not math.isfinite(change):continue
        if volume<MIN_GATE_QUOTE_24H or not 0.25<=change<=150:continue
        # Lower sensitivity to large already-completed pumps.
        score=min(change,25)*math.sqrt(volume)
        choices.append((score,symbol,volume,change,price))
    choices.sort(key=lambda x:(-x[0],x[1]))
    return [{"symbol":symbol,"quote_volume_24h_usdt":round(volume,2),
             "abs_change_24h_percent":round(change,3),"gate_last_usdt":price}
            for _,symbol,volume,change,price in choices[:limit]]

def parse_okx_tickers(obj):
    """OKX volCcy24h is quote-currency volume for USDT spot instruments."""
    if not isinstance(obj,dict) or obj.get("code")!="0":raise ValueError("bad_okx_ticker_response")
    data=obj.get("data",[])
    if not isinstance(data,list):raise ValueError("invalid_okx_ticker_list")
    result={}
    for row in data:
        try:
            inst=row["instId"]
            if not isinstance(inst,str) or not inst.endswith("-USDT"):continue
            base=inst[:-5]
            if not re.fullmatch(r"[A-Z0-9]{2,18}",base):continue
            price=finite_positive(row.get("last"))
            volume=finite_positive(row.get("volCcy24h"))
            ts=int(row["ts"])
            if price is None or volume is None or ts<=0:continue
            result[base+"USDT"]={"price":price,"quote_volume":volume,"ts":ts}
        except (KeyError,ValueError,TypeError,OverflowError):continue
    return result

def parse_bitget_tickers(obj):
    """Bitget UTA v3 SPOT turnover24h is quote turnover; never use futures."""
    if not isinstance(obj,dict) or obj.get("code")!="00000":
        raise ValueError("bad_bitget_ticker_response")
    data=obj.get("data",[])
    if not isinstance(data,list):raise ValueError("invalid_bitget_ticker_list")
    result={}
    for row in data:
        try:
            symbol=row["symbol"]
            if row.get("category")!="SPOT" or not isinstance(symbol,str):
                continue
            if not re.fullmatch(r"[A-Z0-9]{2,18}USDT",symbol):continue
            price=finite_positive(row.get("lastPrice"))
            volume=finite_positive(row.get("turnover24h"))
            ts=int(row["ts"])
            if price is None or volume is None or ts<=0:continue
            result[symbol]={"price":price,"quote_volume":volume,"ts":ts}
        except (KeyError,ValueError,TypeError,OverflowError):continue
    return result

def corroborate(shortlist,okx,current_ms,bitget=None):
    """Require fresh independent 24h spot tickers; prefer OKX, else Bitget."""
    out=[]
    options=(("okx",okx),("bitget",bitget or {}))
    for entry in shortlist:
        a=entry["gate_last_usdt"]
        for venue,index in options:
            second=index.get(entry["symbol"])
            if not second:continue
            age=current_ms-second["ts"]
            if not 0<=age<=10*60_000:continue
            if second["quote_volume"]<MIN_OKX_QUOTE_24H:continue
            b=second["price"]
            if max(a,b)/min(a,b)-1>MAX_PRICE_DISAGREEMENT:continue
            out.append({**entry,"second_venue":venue,
                "second_venue_quote_volume_24h_usdt":round(second["quote_volume"],2),
                "second_venue_last_usdt":b,
                "ticker_price_disagreement_percent":round(
                    100*(max(a,b)/min(a,b)-1),3)})
            break
    return out

def verify_candles(candidate,now_ms,fetcher=fetch):
    """A candidate enters the added universe only after both 15m feeds validate."""
    observations=[]
    for venue in ("gate",candidate["second_venue"]):
        url,bars=fetcher(venue,candidate["symbol"])
        check=evaluate(bars,now_ms)
        if not check.get("valid"):raise ValueError(venue+":"+check.get("reason","invalid_candles"))
        if check["spot_quote_volume_usdt"]<MIN_15M_QUOTE:
            raise ValueError(venue+":insufficient_closed_15m_quote_volume")
        observations.append((venue,url,check))
    c1=observations[0][2]
    c2=observations[1][2]
    if c1["candle_start_utc"]!=c2["candle_start_utc"]:
        raise ValueError("different_closed_candle")
    a,b=c1["spot_close_usdt"],c2["spot_close_usdt"]
    if max(a,b)/min(a,b)-1>MAX_PRICE_DISAGREEMENT:
        raise ValueError("closed_candle_price_disagreement")
    return {**candidate,"validated_spot_venues":["gate",candidate["second_venue"]],
        "verified_same_closed_15m_candle_utc":c1["candle_start_utc"],
        "closed_15m_quote_volume_usdt":{"gate":c1["spot_quote_volume_usdt"],
                                         candidate["second_venue"]:c2["spot_quote_volume_usdt"]},
        "closed_15m_price_disagreement_percent":round(
            100*(max(a,b)/min(a,b)-1),3),
        "source_urls":{venue:url for venue,url,_ in observations},
        "two_venue_ohlcv_verified":True}

def run(gate_tickers,okx_tickers,current_ms,fetcher=fetch,limit=MAX_NEW,bitget_tickers=None):
    shortlist=select(gate_tickers,limit=MAX_PREFLIGHT)
    available=corroborate(shortlist,parse_okx_tickers(okx_tickers),current_ms,
                          parse_bitget_tickers(bitget_tickers) if bitget_tickers is not None else None)
    confirmed=[]
    rejected=[]
    attempted=0
    for row in available[:MAX_CANDLE_PREFLIGHT]:
        attempted+=1
        try:
            confirmed.append(verify_candles(row,current_ms,fetcher))
            if len(confirmed)>=limit:break
        except Exception as exc:
            rejected.append({"symbol":row["symbol"],
                             "reason":(type(exc).__name__+": "+str(exc))[:150]})
    return confirmed,{"gate_shortlist":len(shortlist),"ticker_correlated":len(available),
                      "candle_checked":attempted,"candle_rejected":rejected[:24],"validated":len(confirmed)}

def main():
    OUT.parent.mkdir(exist_ok=True)
    report={"generated_at_utc":utc_now(),"source_urls":{"gate":GATE_URL,"okx":OKX_URL,"bitget":BITGET_URL},
            "status":"unavailable","research_only":True,"candidates":[],
            "selection_rules":{"independent_venues":2,"min_gate_quote_24h_usdt":MIN_GATE_QUOTE_24H,
                "min_okx_quote_24h_usdt":MIN_OKX_QUOTE_24H,
                "min_each_venue_closed_15m_quote_usdt":MIN_15M_QUOTE,
                "max_price_disagreement_fraction":MAX_PRICE_DISAGREEMENT,
                "closed_candles_per_venue_min":21,
                "exclude_leveraged_tokens":True}}
    try:
        now_ms=int(time.time()*1000)
        gate=get_json(GATE_URL)
        okx=get_json(OKX_URL)
        try:
            bitget=get_json(BITGET_URL)
        except Exception as exc:
            bitget=None
            report["bitget_fallback_error"]=(type(exc).__name__+": "+str(exc))[:180]
        chosen,diagnostics=run(gate,okx,now_ms,bitget_tickers=bitget)
        report.update({"candidates":chosen,"diagnostics":diagnostics,
                       "status":"ok" if chosen else "no_correlated_candidates"})
    except Exception as exc:
        report["error"]=(type(exc).__name__+": "+str(exc))[:220]
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":report["status"],"validated":len(report["candidates"]),
                      "diagnostics":report.get("diagnostics")}))
if __name__=="__main__":main()
