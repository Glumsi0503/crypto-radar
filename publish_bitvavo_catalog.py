#!/usr/bin/env python3
"""Publish Bitvavo public catalog only, with retries and freshness guard."""
import subprocess
import time
from pathlib import Path
from publish_reports import stamp

PATH="docs/bitvavo_catalog.json"

def git(*args,check=True):
    return subprocess.run(["git",*args],text=True,capture_output=True,check=check)

def main():
    p=Path(PATH)
    local=stamp(p.read_text())
    if local is None:raise ValueError("Invalid local public catalog timestamp")
    git("config","user.name","github-actions[bot]")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    for attempt in range(4):
        git("fetch","origin","main")
        remote=git("show","origin/main:"+PATH,check=False)
        prev=stamp(remote.stdout) if remote.returncode==0 else None
        if prev and prev>=local:
            print("SKIP_OLDER_CATALOG")
            return
        git("reset","--mixed","origin/main")
        git("add","--",PATH)
        if git("diff","--cached","--quiet",check=False).returncode==0:
            print("NO_CHANGES");return
        git("commit","-m","Refresh optional Bitvavo EUR market reference")
        result=git("push","origin","HEAD:main",check=False)
        if result.returncode==0:
            print("PUBLISHED_CATALOG");return
        print("CATALOG_PUSH_CONFLICT",attempt+1)
        time.sleep(attempt+1)
    raise RuntimeError("Catalog publishing conflict after retries")

if __name__=="__main__":
    main()
