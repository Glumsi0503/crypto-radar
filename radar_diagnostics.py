#!/usr/bin/env python3
"""Research-only signal funnel: identify where observations fail without inventing entries."""
import collections
import datetime as dt
import json
from pathlib import Path

ROOT = Path("docs")
UTC = dt.timezone.utc

def read(name):
    try:
        obj = json.loads((ROOT / name).read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}

def build(latest, discovery, feed, now=None):
    now = now or dt.datetime.now(UTC)
    rows = latest.get("sources", [])
    counts = collections.Counter()
    by_symbol = collections.defaultdict(list)
    for row in rows:
        counts["checks"] += 1
        data = row.get("data") or {}
        if row.get("status") != "ok" or not data.get("valid"):
            counts["invalid"] += 1
            counts["invalid_" + str(data.get("reason") or row.get("error") or "unknown").split(":")[0][:45]] += 1
            continue
        counts["valid"] += 1
        by_symbol[row.get("symbol")].append((row.get("venue"), data))
        if data.get("change_percent", 0) >= 1.5:
            counts["gain_1_5"] += 1
        if data.get("volume_multiplier", 0) >= 1.8:
            counts["volume_1_8x"] += 1
        if data.get("change_percent", 0) >= 1.5 and data.get("volume_multiplier", 0) >= 1.8:
            counts["single_venue_early"] += 1
        if data.get("change_percent", 0) >= 2.5 and data.get("volume_multiplier", 0) >= 2.5:
            counts["single_venue_momentum"] += 1
    for symbol, observations in by_symbol.items():
        for gain, volume, label in ((1.5, 1.8, "early"), (2.5, 2.5, "momentum")):
            grouped = collections.defaultdict(list)
            for venue, d in observations:
                if (d.get("change_percent", 0) >= gain and
                    d.get("volume_multiplier", 0) >= volume and
                    d.get("spot_quote_volume_usdt", 0) >= 100000):
                    grouped[d.get("candle_start_utc")].append((venue, d))
            if any(len({v for v, _ in group}) >= 2 and
                   max(d["spot_close_usdt"] for _, d in group) /
                   min(d["spot_close_usdt"] for _, d in group) <= 1.01
                   for group in grouped.values()):
                counts["two_venue_" + label] += 1
    stamp = latest.get("generated_at_utc")
    age = None
    try:
        age = round((now - dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))).total_seconds() / 60, 2)
    except (TypeError, ValueError, AttributeError):
        pass
    return {
        "generated_at_utc": now.isoformat(),
        "latest_generated_at_utc": stamp,
        "latest_age_minutes": age,
        "source_classification": "CURRENT_RESEARCH" if age is not None and 0 <= age <= 40 else "HISTORICAL_RESEARCH_ONLY",
        "research_only": True,
        "counts": dict(counts),
        "discovery_status": discovery.get("status", "missing"),
        "discovery_diagnostics": discovery.get("diagnostics", {}),
        "discovery_venue_fetch_errors": discovery.get("venue_fetch_errors", {}),
        "discovery_venues_reached": discovery.get("venues_reached", []),
        "feed_current_candidates": len(feed.get("current_candidates", [])),
        "feed_recent_events_3h": len(feed.get("recent_events_3h", [])),
        "trade_ready": False,
        "auto_push_connected": False,
        "note": "Diagnostic counts only. No independent live validation, fills or trading signals."
    }

def main():
    ROOT.mkdir(exist_ok=True)
    result = build(read("latest.json"), read("discovery.json"), read("signal_feed.json"))
    (ROOT / "radar_diagnostics.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": result["counts"], "discovery": result["discovery_status"]}))

if __name__ == "__main__":
    main()
