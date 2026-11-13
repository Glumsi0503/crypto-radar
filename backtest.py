#!/usr/bin/env python3
"""Bounded, historical, one-venue research backtest with strict no-lookahead fills.

Not a five-method backtest, not an execution simulation or proof of profitability.
"""
import datetime as dt
import json
from pathlib import Path
from statistics import median
from urllib.parse import urlencode
from enrichment import request_json

PERIOD=900
UTC=dt.timezone.utc
COINS=("BTC","ETH","SOL","LINK","AAVE","SUI","INJ","ONDO","HYPE","AVAX","UNI","NEAR")
FEE=.0025
SLIPPAGE=.001
STOP=.025
TARGET=.05
MAX_BARS=288
MIN_15M_QUOTE_VOLUME=100000

def gate_bars(payload,now=None):
    now=now or dt.datetime.now(UTC)
    if not isinstance(payload,list):raise ValueError("non_list")
    bars=[]
    for r in payload:
        if not isinstance(r,list) or len(r)<6:continue
        try:
            ts=int(r[0])
            bar={"ts":ts,"open":float(r[5]),"close":float(r[2]),
                 "high":float(r[3]),"low":float(r[4]),"volume":float(r[1])}
            if ts+PERIOD>now.timestamp():continue
            if not all(0<x<float("inf") for x in (bar["open"],bar["close"],bar["high"],bar["low"])):continue
            if not 0<=bar["volume"]<float("inf"):continue
            if not (bar["low"]<=min(bar["open"],bar["close"])<=bar["high"] and
                    bar["low"]<=max(bar["open"],bar["close"])<=bar["high"]):continue
            bars.append(bar)
        except (TypeError,ValueError,OverflowError):continue
    return sorted({b["ts"]:b for b in bars}.values(),key=lambda x:x["ts"])

def backtest(bars):
    """Signal from CLOSED bar i, fill no earlier than next bar OPEN; conservative collision."""
    trades=[]
    idx=20
    while idx<len(bars)-1:
        sample=bars[idx-20:idx+1]
        if any(sample[k+1]["ts"]-sample[k]["ts"]!=PERIOD for k in range(20)):
            idx+=1;continue
        base=sum(x["volume"] for x in sample[:-1])/20
        signal=sample[-1]
        gain=100*(signal["close"]/signal["open"]-1)
        if base<=0 or not (3<=gain<=8 and signal["volume"]>=3*base and signal["volume"]>=MIN_15M_QUOTE_VOLUME):
            idx+=1;continue
        if bars[idx+1]["ts"]-signal["ts"]!=PERIOD:idx+=1;continue
        entry=bars[idx+1]["open"]*(1+SLIPPAGE)
        sl=entry*(1-STOP)
        tp=entry*(1+TARGET)
        ended=False
        for exit_idx in range(idx+1,min(idx+MAX_BARS+1,len(bars))):
            bar=bars[exit_idx]
            if exit_idx>idx+1 and bar["ts"]-bars[exit_idx-1]["ts"]!=PERIOD:break
            stop_hit=bar["low"]<=sl
            target_hit=bar["high"]>=tp
            if stop_hit or target_hit:
                # If both targets hit inside one bar, adverse stop first to avoid optimism.
                exit_px=sl if stop_hit else tp
                outcome="stop_assumed" if stop_hit else "target_assumed"
                ended=True
                break
            if exit_idx==idx+MAX_BARS:
                exit_px=bar["close"]
                outcome="time_exit_72h"
                ended=True
                break
        if not ended:
            # Right-censored trades are excluded rather than assumed to close profitably.
            idx+=1;continue
        exit_net=exit_px*(1-SLIPPAGE)
        net_pct=100*((exit_net*(1-FEE))/(entry*(1+FEE))-1)
        trades.append({"signal_candle_utc":dt.datetime.fromtimestamp(signal["ts"],UTC).isoformat(),
                       "entry_candle_utc":dt.datetime.fromtimestamp(bars[idx+1]["ts"],UTC).isoformat(),
                       "exit_candle_utc":dt.datetime.fromtimestamp(bars[exit_idx]["ts"],UTC).isoformat(),
                       "net_percent":round(net_pct,4),"exit_model":outcome})
        idx=exit_idx+1
    return trades

def main():
    result={"generated_at_utc":dt.datetime.now(UTC).isoformat(),
        "research_only":True,"source":"Gate.io spot 15m historical candles",
        "model":"Single-venue historical, forward walk; signal on closed bar, next-open entry.",
        "assumed_fee_per_side":FEE,"assumed_slippage_per_side":SLIPPAGE,
        "stop_pct":STOP,"target_pct":TARGET,"max_hold_15m_bars":MAX_BARS,
        "selection":"Fixed universe, no ex-post winner selection",
        "limitations":["Limited OHLCV window and one venue; no cross-venue confirmation",
                       "Intrabar stop/target collision assigned to stop; real spread/liquidity unknown",
                       "Delisting and broader survivorship bias unresolved",
                       "Not a five-strategy validation or predictive performance proof"],
        "coins":[]}
    for coin in COINS:
        url="https://api.gateio.ws/api/v4/spot/candlesticks?"+urlencode(
            {"currency_pair":coin+"_USDT","interval":"15m","limit":1000})
        row={"symbol":coin+"USDT","url":url,"status":"error"}
        try:
            raw=request_json(url,3000000)
            bars=gate_bars(raw)
            if len(bars)<310:raise ValueError("insufficient_closed_history")
            trades=backtest(bars)
            changes=[x["net_percent"] for x in trades]
            row.update({"status":"ok","bars":len(bars),
                "start_utc":dt.datetime.fromtimestamp(bars[0]["ts"],UTC).isoformat(),
                "end_utc":dt.datetime.fromtimestamp(bars[-1]["ts"],UTC).isoformat(),
                "completed_trades":len(trades),
                "median_net_percent":round(median(changes),4) if changes else None,
                "mean_net_percent":round(sum(changes)/len(changes),4) if changes else None,
                "sufficient_sample":len(changes)>=30,"trades":trades})
        except Exception as e:
            row["error"]=(type(e).__name__+": "+str(e))[:180]
        result["coins"].append(row)
    all_returns=[t["net_percent"] for row in result["coins"] for t in row.get("trades",[])]
    result["summary"]={"valid_markets":sum(x["status"]=="ok" for x in result["coins"]),
        "completed_trades":len(all_returns),
        "median_net_percent":round(median(all_returns),4) if all_returns else None,
        "sufficient_sample":len(all_returns)>=100,
        "statistically_valid_strategy":False}
    output=Path("docs/backtest.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result["summary"]))

if __name__=="__main__":main()
