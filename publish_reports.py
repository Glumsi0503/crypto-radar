#!/usr/bin/env python3
"""Publish generated research reports without overwriting newer completed scans."""
import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path

REPORTS = ("docs/latest.json", "docs/enrichment.json", "docs/health.json",
           "docs/strategy_status.json", "docs/paper_journal.json",
           "docs/discovery.json", "docs/signal_feed.json", "docs/signal_history.json",
           "docs/derivatives.json", "docs/derivatives_history.json",
           "docs/five_method_audit.json", "docs/observed_outcomes.json",
           "docs/observed_outcomes_journal.json", "docs/radar_inbox.json")

def git(*args, check=True):
    return subprocess.run(["git", *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def stamp(text):
    try:
        obj=json.loads(text)
        value=obj.get("generated_at_utc")
        if not value: return None
        parsed=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        if parsed.tzinfo is None: return None
        return parsed.astimezone(dt.timezone.utc)
    except (ValueError, TypeError, AttributeError): return None

def remote_newer():
    local=Path("docs/latest.json")
    if not local.exists(): return True
    local_time=stamp(local.read_text())
    if local_time is None: raise RuntimeError("Local latest.json lacks valid timestamp")
    result=git("show","origin/main:docs/latest.json",check=False)
    remote_time=stamp(result.stdout) if result.returncode==0 else None
    return remote_time is not None and remote_time >= local_time

def publish():
    git("config","user.name","github-actions[bot]")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    for attempt in range(1,5):
        git("fetch","origin","main")
        if remote_newer():
            print("SKIPPED_STALE: remote report is as new or newer")
            return
        # Reset the *index only* to latest upstream. Keep freshly generated docs
        # in working tree, then stage only these explicit data files, never old code.
        git("reset","--mixed","origin/main")
        existing=[p for p in REPORTS if Path(p).exists()]
        if not existing:
            raise RuntimeError("No generated report available")
        git("add","--",*existing)
        if git("diff","--cached","--quiet",check=False).returncode==0:
            print("NO_CHANGES")
            return
        git("commit","-m","Refresh validated research diagnostics")
        result=git("push","origin","HEAD:main",check=False)
        if result.returncode==0:
            print("PUBLISHED_OK")
            return
        if attempt==4:
            raise RuntimeError("Could not publish after retries: "+result.stderr[-500:])
        print("PUSH_CONFLICT_RETRY",attempt)
        time.sleep(attempt)
    raise RuntimeError("Unreachable")

if __name__=="__main__":
    publish()
