#!/usr/bin/env python3
"""Consistent backup of the ERP SQLite database.

Safe to run while the server is live (uses SQLite's online backup API, not a raw
file copy). Keeps the newest N snapshots in ./backups, and can also mirror each
snapshot to an off-machine folder set in secrets.local.json (backup.targetPath).

Schedule it daily with Windows Task Scheduler (see docs/DEPLOYMENT.md).
"""
import os, sqlite3, glob, time, json, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DB   = os.path.join(HERE, "data.sqlite")
BK   = os.path.join(HERE, "backups")
KEEP = 30                                   # how many local snapshots to retain

def _secrets():
    try:
        with open(os.path.join(HERE, "secrets.local.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def main():
    if not os.path.exists(DB):
        print("No data.sqlite yet — nothing to back up.")
        return
    os.makedirs(BK, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(BK, "data-%s.sqlite" % stamp)

    src = sqlite3.connect(DB)
    dst = sqlite3.connect(out)
    with dst:
        src.backup(dst)                     # online backup API = consistent snapshot
    src.close(); dst.close()
    print("Backup ->", out)

    # keep only the newest KEEP snapshots
    files = sorted(glob.glob(os.path.join(BK, "data-*.sqlite")))
    for old in files[:-KEEP]:
        try:
            os.remove(old); print("Pruned", os.path.basename(old))
        except OSError:
            pass

    # optional off-machine mirror (external drive / network share / cloud folder)
    tgt = (_secrets().get("backup") or {}).get("targetPath")
    if tgt:
        try:
            os.makedirs(tgt, exist_ok=True)
            shutil.copy2(out, os.path.join(tgt, os.path.basename(out)))
            print("Mirrored ->", tgt)
        except Exception as e:
            print("Mirror failed:", e)

if __name__ == "__main__":
    main()
