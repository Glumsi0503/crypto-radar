#!/usr/bin/env python3
"""Optional Bitvavo EUR public-market catalog for radar reference, NOT an eligibility gate.

Public GET /markets enumerates EUR markets and statuses. It does not certify
account-specific or German-region tradability. Failures cannot block spot scans.
"""
import datetime as dt
import json
import re
import urllib.request
from pathlib import Path
from market_data import SYMBOLS

UTC=dt.timezone.utc
MARKETS_URL="https://api.bitvavo.com/v2/markets"
ASSETS_URL="https://api.bitvavo.com/v2/assets"
OUTPUT=Path("docs/bitvavo_catalog.json")
VALID_SYMBOL=re.compile(r"^[A-Z0-9]{2,35}$")

def request_json(url, timeout=12):
    request=urllib.request.Request(url,headers={"Accept":"application/json",
        "User-Agent":"CryptoRadarResearch/1.0"})
    with urllib.request.urlopen(request,timeout=timeout) as resp:
        body=resp.read(8_000_001)
    if len(body)>8_000_000:raise ValueError("bitvavo_response_too_large")
    return json.loads(body)

def catalog(markets, assets, generated_at_utc):
    if not isinstance(markets,list) or not markets:
        raise ValueError("Bitvavo markets must be a nonempty array")
    # Exclude assets without a EUR market and markets that are not actively trading.
    names={}
    if isinstance(assets,list):
        for a in assets:
            if not isinstance(a,dict):continue
            symbol=a.get("symbol")
            if isinstance(symbol,str) and VALID_SYMBOL.fullmatch(symbol):
                names[symbol]=a.get("name") if isinstance(a.get("name"),str) else None
    eur={}
    for m in markets:
        if not isinstance(m,dict):continue
        base,quote,status=m.get("base"),m.get("quote"),m.get("status")
        label=m.get("market")
        if quote!="EUR" or not isinstance(base,str) or not VALID_SYMBOL.fullmatch(base):
            continue
        if not isinstance(label,str) or label!=base+"-EUR":continue
        if status not in ("trading","halted","auction","auctionMatching","cancelOnly"):
            continue
        # If repeated, prefer a valid actively trading entry.
        if base not in eur or status=="trading":
            eur[base]={"symbol":base,"name":names.get(base),"market":label,
                       "public_market_status":status}
    if not eur:raise ValueError("No valid EUR markets found")
    trading={sym for sym,item in eur.items() if item["public_market_status"]=="trading"}
    current={s[:-4] for s in SYMBOLS if s.endswith("USDT")}
    return {"generated_at_utc":generated_at_utc,"source_urls":{"markets":MARKETS_URL,
        "assets":ASSETS_URL},"status":"ok","reference_only":True,
        "bitvavo_germany_eligibility_verified":False,
        "user_account_buyability_verified":False,
        "mandatory_trade_filter":False,
        "universe_source":"Public Bitvavo EUR market metadata, not German account entitlements",
        "counts":{"eur_markets":len(eur),"public_trading_eur_markets":len(trading),
                  "core_radar_coins":len(current),
                  "core_radar_with_public_trading_eur_market":len(current & trading)},
        "core_radar_public_trading_symbols":sorted(current & trading),
        "core_radar_not_publicly_trading_symbols":sorted(current-trading),
        "markets":sorted(eur.values(),key=lambda x:x["symbol"]),
        "notes":["A public trading EUR market does not prove availability for any particular account in Germany.",
                 "This catalog does NOT gate spot data collection, signals or papertrades.",
                 "Metadata refresh may fail due to regional restrictions; absence is unknown, not a delisting."]}

def main():
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    now=dt.datetime.now(UTC).isoformat()
    try:
        markets=request_json(MARKETS_URL)
        try:
            assets=request_json(ASSETS_URL)
        except Exception:
            assets=[]
        result=catalog(markets,assets,now)
    except Exception as exc:
        # Never convert a failed request to a false claim of zero Bitvavo listings.
        result={"generated_at_utc":now,"status":"unavailable","reference_only":True,
                "mandatory_trade_filter":False,
                "bitvavo_germany_eligibility_verified":False,
                "user_account_buyability_verified":False,
                "source_urls":{"markets":MARKETS_URL,"assets":ASSETS_URL},
                "counts":None,"markets":None,
                "error":(type(exc).__name__+": "+str(exc))[:240],
                "notes":["Unknown public market list on this run, not zero listed markets.",
                         "Spot research and strategy scanning are unaffected."]}
    OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    print(json.dumps({"status":result["status"],
                      "public_trading_eur_markets":(result["counts"] or {}).get("public_trading_eur_markets"),
                      "spot_scans_blocked":False}))

if __name__=="__main__":main()
