"""Publish only the nightly backtest report without overwriting newer research runs."""
import subprocess
import time
from pathlib import Path
from publish_reports import stamp

def git(*args,check=True):
    return subprocess.run(["git",*args],check=check,text=True,
                          capture_output=True)

def main():
    path=Path("docs/backtest.json")
    if not path.exists():raise RuntimeError("Missing backtest report")
    local=stamp(path.read_text())
    if local is None:raise ValueError("Invalid backtest timestamp")
    git("config","user.name","github-actions[bot]")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    for attempt in range(4):
        git("fetch","origin","main")
        remote=git("show","origin/main:docs/backtest.json",check=False)
        remote_time=stamp(remote.stdout) if remote.returncode==0 else None
        if remote_time and remote_time>=local:
            print("SKIP_OLDER_BACKTEST")
            return
        git("reset","--mixed","origin/main")
        git("add","--","docs/backtest.json")
        if git("diff","--cached","--quiet",check=False).returncode==0:
            print("NO_CHANGES");return
        git("commit","-m","Refresh bounded historical research backtest")
        push=git("push","origin","HEAD:main",check=False)
        if push.returncode==0:
            print("PUBLISHED_BACKTEST");return
        time.sleep(attempt+1)
    raise RuntimeError("Backtest report push conflicts exhausted")

if __name__=="__main__":main()
