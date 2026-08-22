#!/usr/bin/env python3
"""
REL-UNITY - MVP server (zero external dependencies).

Run:  python server.py            (defaults to port 8080, all interfaces)
      python server.py 9000       (custom port)

Then open on the host:      http://localhost:8080/
From another LAN machine:   http://<this-machine-ip>:8080/

Data persists to data.sqlite in this folder (SQLite). On first run it imports a
legacy data.json if one is present, then serves purely from SQLite. POST /api
reset restores the seeded sample data. Back up with backup_db.py (see docs/DEPLOYMENT.md).
"""
import json, os, sys, threading, uuid, hashlib, secrets, hmac, time, sqlite3, re, gzip, subprocess, csv as _csv, ipaddress, collections, copy, io
import base64, urllib.request, urllib.error   # base64: decode uploaded scan photos · urllib: the Gemini API call (the one deliberate outbound-internet call in this app)
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
MOBILE = os.path.normpath(os.path.join(HERE, "..", "UNITY-MOBILE"))   # REL-UNITY floor PWA, served under /m/

# LAN-only lock: the whole ERP (web + mobile) is a factory-network tool. When on (default), the server
# refuses any request whose client IP isn't private/loopback/link-local, so only devices on the factory
# Wi-Fi/LAN can reach it and nothing off-site can. Turn OFF for a public deployment: set REL_LAN_ONLY=0.
LAN_ONLY = os.environ.get("REL_LAN_ONLY", "1") != "0"
# Extra always-allowed IPs / CIDRs, on top of private/loopback/link-local. Tailscale hands out addresses in
# the 100.64.0.0/10 CGNAT range, which older Python's is_private does NOT recognise — so a phone on the
# tailnet gets blocked even though it's effectively on the network. We allow that whole range (covers every
# Tailscale device, even after its IP rotates) plus a couple of explicit phone IPs, and anything listed in
# the REL_LAN_ALLOW env var (comma-separated IPs or CIDRs).
_LAN_ALLOW_DEFAULT = "100.64.0.0/10, 10.67.117.39, 100.77.171.126"
def _parse_nets(s):
    nets = []
    for part in (s or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except Exception:
            pass
    return nets
LAN_ALLOW = _parse_nets(_LAN_ALLOW_DEFAULT + "," + os.environ.get("REL_LAN_ALLOW", ""))
def _client_is_lan(addr):
    try:
        ip = ipaddress.ip_address(addr)
        if getattr(ip, "ipv4_mapped", None):   # ::ffff:192.168.x.x -> treat as the embedded IPv4
            ip = ip.ipv4_mapped
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return True
        return any(ip.version == net.version and ip in net for net in LAN_ALLOW)   # Tailscale / explicit allowlist
    except Exception:
        return False

# Terminal log mirror: everything the server prints (startup, imports, restarts, tracebacks) is
# captured into a rolling buffer and surfaced in the Settings page (last 40 lines) so an admin can
# see what's going on without opening the server window. The buffer lives in this process only and
# resets on restart/auto-reload — that's fine, it's a live tail, not an audit trail (that's activityLog).
TERM_LOG = collections.deque(maxlen=400)
class _TeeStream:
    """wraps stdout/stderr: writes through to the real stream AND appends whole lines to TERM_LOG."""
    def __init__(self, stream):
        self._s = stream; self._buf = ""
    def write(self, s):
        try: self._s.write(s)
        except Exception: pass
        try:
            self._buf += s
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                TERM_LOG.append((time.strftime("%H:%M:%S ") + line) if line.strip() else "")
        except Exception:
            pass
    def flush(self):
        try: self._s.flush()
        except Exception: pass
    def isatty(self): return False
def _install_termlog():
    if not isinstance(sys.stdout, _TeeStream):
        sys.stdout = _TeeStream(sys.stdout)
    if not isinstance(sys.stderr, _TeeStream):
        sys.stderr = _TeeStream(sys.stderr)
DB_PATH = os.path.join(HERE, "data.sqlite")
JSON_PATH = os.path.join(HERE, "data.json")   # legacy store - imported once into SQLite if present
SECRETS_PATH = os.path.join(HERE, "secrets.local.json")   # user-owned, gitignored, never logged
LOCK = threading.Lock()

def load_secrets():
    """External-system credentials (e.g. Livewire / EMPIRE) the operator keeps in secrets.local.json.
    Returns {} if the file is absent. Never commit this file and never log its contents."""
    try:
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}

# ---------------------------------------------------------------- auth helpers
SESSIONS = {}                 # token -> {"username":.., "expires":ts}   (in-memory)
SESSION_TTL = 12 * 3600       # 12 hours
# every viewable "page" a role can be granted (must match static/app.js PAGE_KEYS). op_mob_log is
# mobile-only (UNITY-MOBILE/m.js) — the other op_* keys are shared between the desktop page and the
# mobile tab/view of the same name (op_floor, op_massplan).
ALL_PAGES = ["op_floor","op_schedule","op_order","op_orderstatus","op_batch","op_storage","op_massplan","op_workflows","op_scan","op_mob_log",
             "dashboard","machines","qualities","shadeRecipes","recipes","history","lotHistory","dispatch",
             "batches","lots","weavers","takaMaster",
             "customers","orders","challans","storageAreas","shelves","storageSlots","suppliers","operators","qcMetrics",
             "users","roles","plan","settings","activity","urgent_flag"]

LOG_CAP = 5000
def _log(db, user, action, table, rid, summary=""):
    """append an audit-trail entry — the single source for console + batch history"""
    lg = db.setdefault("activityLog", [])
    lg.append({"id": "LG-" + uuid.uuid4().hex[:10],
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "user": user or "system", "action": action,
               "table": table or "", "recordId": rid or "", "summary": summary or ""})
    if len(lg) > LOG_CAP:
        del lg[:len(lg) - LOG_CAP]

def _next_seq_id(db, table):
    """human-readable, sequential, system-generated id (never client supplied)"""
    prefix = {"lots":"LOT","batches":"B","orders":"SO","weavers":"WV","storageSlots":"SL"}.get(table, table[:2].upper())
    seq = db.setdefault("_seq", {})
    n = int(seq.get(table, 0)) + 1
    seq[table] = n
    return "%s-%04d" % (prefix, n)

MC_LETTER = {"jet": "T", "jigger": "R", "stentor": "S", "drum": "D", "hydro": "Y", "rope": "P"}
# Jiggers are scheduled from a pooled queue but ALLOTED to a specific machine by the software, so their
# batch code now carries the machine number just like jets (traceable to the exact jigger). A type is
# only pooled (no machine number in the code) if listed here.
MC_POOLED = {}

def _batch_id(db, row):
    """structured batch id B{letter}{machineNo}{seq}/{MMYY}; letter from the machine type.
    Per-machine (jet): BT05200/0826.  Alloted jigger: BR03200/0826.  Sequence resets monthly."""
    mid = str(row.get("machine", "") or "")
    m = next((x for x in db.get("machines", []) if x.get("id") == mid), None)
    mtype = str((m or {}).get("type", "") or "")
    letter = MC_LETTER.get(mtype) or (mtype[:1].upper() if mtype else "B")
    pooled = MC_POOLED.get(mtype, False)
    digits = re.sub(r"\D", "", mid)
    mcno = (digits[-2:] if digits else "").zfill(2)
    mmyy = time.strftime("%m%y")
    seq = db.setdefault("_batchseq", {})
    ckey = "%s/%s" % (letter, mmyy) if pooled else "%s%s/%s" % (letter, mcno, mmyy)
    n = int(seq.get(ckey, 0)) + 1
    seq[ckey] = n
    return ("B%s%03d/%s" % (letter, n, mmyy)) if pooled else ("B%s%s%03d/%s" % (letter, mcno, n, mmyy))

def _op_username(name):
    parts = [p for p in re.sub(r"[^A-Za-z ]", " ", str(name or "")).split() if p]
    if not parts:
        return "operator"
    return parts[0].capitalize() + (parts[-1].capitalize() if len(parts) > 1 else "")

def _ensure_operator_creds(db, op):
    """auto-generate login credentials for the operator mobile app: username FirstnameLastname + a 6-digit PIN"""
    ops = db.get("operators", [])
    if not op.get("username"):
        base = _op_username(op.get("name"))
        taken = {o.get("username") for o in ops if o.get("id") != op.get("id")}
        u, k = base, 2
        while u in taken:
            u = base + str(k); k += 1
        op["username"] = u
    if not op.get("pin"):
        op["pin"] = "%06d" % secrets.randbelow(1000000)

def _new_salt():
    return secrets.token_hex(16)

def _hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", (pw or "").encode(), bytes.fromhex(salt), 200000).hex()

def _make_user(uid, username, pw, role, active=True):
    salt = _new_salt()
    return {"id": uid, "username": username, "role": role, "active": active,
            "salt": salt, "passHash": _hash_pw(pw, salt)}

def _perms_for(db, user):
    role = next((r for r in db.get("roles", []) if r.get("name") == user.get("role")), None)
    return role.get("perms", []) if role else []

def _edit_perms_for(db, user):
    """pages this user may MODIFY. A role's 'edit' list is a subset of its viewable 'perms';
    older roles without an explicit 'edit' key keep full edit rights on what they can see."""
    role = next((r for r in db.get("roles", []) if r.get("name") == user.get("role")), None)
    if not role:
        return []
    edit = role.get("edit")
    view = role.get("perms", [])
    if edit is None:                       # legacy role: editable == viewable (no behaviour change)
        return list(view)
    return [p for p in edit if p in view]  # never grant edit on a page the role can't see

def _find_principal(db, username):
    """A login principal is a full user, or an operator (operators log in with username + PIN and
    carry a role too). Users take priority if a username exists in both."""
    u = next((x for x in db.get("users", []) if x.get("username") == username and x.get("active", True)), None)
    if u:
        return u
    return next((o for o in db.get("operators", [])
                 if o.get("username") == username and o.get("active", True)), None)

# EMPIRE names a quality like "AREA 60 INCH" — the trailing "<width> INCH" is the fabric width,
# not part of the quality name. Strip it so "AREA 60 INCH" and "AREA" are treated as ONE quality
# (the width is captured separately). Also handles 44", 60 IN, 60INCH, 60".
_QUAL_WIDTH_RE = re.compile(r"\s*[-,]?\s*(\d+(?:\.\d+)?)\s*(?:INCHES|INCH|INS|IN|\")\s*$", re.I)

def _normalize_quality(name):
    return _QUAL_WIDTH_RE.sub("", str(name or "").strip()).strip()

def _quality_width(name):
    m = _QUAL_WIDTH_RE.search(str(name or ""))
    try: return int(float(m.group(1))) if m else 0
    except (ValueError, TypeError): return 0

def _shade_score(s):
    """how 'real' a shade row is — used to keep the richer of two duplicates when merging."""
    sc = 0
    prog = str(s.get("program") or "").strip()
    if prog and prog != "from dye recipe": sc += 2
    if s.get("hex"): sc += 2
    for k in ("specL", "dye1", "family"):
        v = s.get(k)
        if v not in (None, "", 0): sc += 1
    return sc

def qualities_dedupe(db):
    """Collapse qualities that differ only by a width suffix ('AREA 60 INCH' vs 'AREA') into one,
    re-point every lot / batch / shade that referenced an old name, and drop duplicate shade rows.
    The canonical quality is the one already named without the width (it usually holds the real
    GSM/route); otherwise the first is renamed to the short form and its width captured."""
    quals = db.get("qualities", [])
    orig = {id(q): (q.get("name") or "").strip() for q in quals}
    groups = {}
    for q in quals:
        groups.setdefault(_normalize_quality(q.get("name")).upper(), []).append(q)
    survivors, rename, removed = [], {}, 0
    for _, items in groups.items():
        norm = _normalize_quality(items[0].get("name"))
        canonical = next((q for q in items if orig[id(q)] == norm), None) or items[0]
        for q in items:                                   # fill a missing width from any member
            w = _quality_width(orig[id(q)])
            if w and not canonical.get("width"): canonical["width"] = w
        canonical["name"] = norm
        survivors.append(canonical)
        for q in items:
            rename[orig[id(q)]] = norm
            if q is not canonical: removed += 1
    db["qualities"] = survivors

    def fix(name):
        n = (name or "").strip()
        return rename.get(n) or (_normalize_quality(n) if n else n)

    lots_fixed, shades_removed = _repoint_qualities(db, fix)
    return {"qualitiesRemoved": removed, "qualitiesNow": len(survivors),
            "lotsRepointed": lots_fixed, "shadesRemoved": shades_removed}

def _repoint_qualities(db, fix):
    """Re-point every lot / batch / shade quality through fix(name), then drop shade rows that
    became duplicate (quality, shade) — keeping the richer of the two. Shared by dedupe + merge."""
    lots_fixed = 0
    for l in db.get("lots", []):
        if l.get("quality"):
            nv = fix(l["quality"])
            if nv != l["quality"]: l["quality"] = nv; lots_fixed += 1
    for b in db.get("batches", []):
        if b.get("quality"): b["quality"] = fix(b["quality"])
    seen, newsh, shades_removed = {}, [], 0
    for s in db.get("shadeRecipes", []):
        s["quality"] = fix(s.get("quality"))
        k = (str(s.get("quality", "")).upper(), str(s.get("shade", "")).upper())
        if k in seen:
            shades_removed += 1
            if _shade_score(s) > _shade_score(seen[k]):    # keep the richer duplicate
                newsh[newsh.index(seen[k])] = s; seen[k] = s
        else:
            seen[k] = s; newsh.append(s)
    db["shadeRecipes"] = newsh
    return lots_fixed, shades_removed

def qualities_merge(db, names, into):
    """Merge a hand-picked set of qualities into one surviving name (e.g. RIVER + RIVER (AJ) -> RIVER).
    The 'into' quality keeps its config; the others are removed and every lot/batch/shade re-pointed."""
    names = [str(n).strip() for n in (names or []) if str(n).strip()]
    into = str(into or "").strip()
    ups = {n.upper() for n in names}
    ups.add(into.upper())
    if not into or into.upper() not in ups or len(ups) < 2:
        return {"error": "Pick at least two qualities and the name to keep."}
    survivors, removed, found = [], 0, False
    for q in db.get("qualities", []):
        nm = (q.get("name") or "").strip()
        if nm.upper() in ups:
            if nm.upper() == into.upper() and not found:
                q["name"] = into; found = True; survivors.append(q)     # canonical survives
            else:
                removed += 1                                            # merged away
        else:
            survivors.append(q)
    if not found:
        return {"error": "The quality to keep was not found."}
    db["qualities"] = survivors
    fix = lambda n: into if (n or "").strip().upper() in ups else (n or "").strip()
    lots_fixed, shades_removed = _repoint_qualities(db, fix)
    return {"into": into, "qualitiesRemoved": removed,
            "lotsRepointed": lots_fixed, "shadesRemoved": shades_removed}

def _ensure_quality_and_shade(db, quality):
    """Quick-add a quality stub (if new) and a shade '0' for it (if new) — used by the inbox
    importer and the 'sync qualities & shades' buttons during setup. Returns (added_q, added_shade).
    The name is normalized ("AREA 60 INCH" -> "AREA") so qualities never double up on the width."""
    width = _quality_width(quality)
    q = _normalize_quality(quality)
    if not q:
        return 0, 0
    aq = asr = 0
    quals = db.setdefault("qualities", [])
    if not any((x.get("name") or "").strip().upper() == q.upper() for x in quals):
        quals.append({"id": "Q-" + uuid.uuid4().hex[:6], "name": q, "gsm": 0, "width": width, "maxBatch": 0,
                      "dyeStep": 3, "step1_mc": "", "step1_time": 0, "step2_mc": "", "step2_time": 0,
                      "step3_mc": "jet", "step3_time": 0, "step4_mc": "stentor", "step4_time": 0})
        aq = 1
    shades = db.setdefault("shadeRecipes", [])
    if not any((x.get("quality") or "").strip().upper() == q.upper() and str(x.get("shade") or "").strip() == "0"
               for x in shades):
        shades.append({"id": "SH-" + uuid.uuid4().hex[:6], "quality": q, "shade": "0",
                       "family": "Neutral", "tone": 0, "program": ""})
        asr = 1
    return aq, asr

def _sanitized(db):
    """copy of db with password material stripped, and the (large) activity log left OUT of the
    full payload — the Activity page fetches it a page at a time via the 'logPage' op instead."""
    d = dict(db)
    d["users"] = [{k: v for k, v in u.items() if k not in ("passHash", "salt")}
                  for u in db.get("users", [])]
    d["activityLog"] = []                 # fetched on demand; keeps every page load small
    d["challans"] = []                    # ditto — challans accumulate; loaded only on the Challans page
    d["programScans"] = []                # loaded on demand via 'scansList' (Admin) — keeps /api/db lean
    d["scanSessions"] = []                 # carries bearer tokens — never goes in the bulk payload;
                                            # fetched per-session via scanSessionStatus (owner-only)
    return d

def _prepare_user_row(db, row):
    """hash a supplied plaintext password; preserve existing hash on edit; never store plaintext"""
    pw = row.pop("password", None)
    if pw:
        row["salt"] = _new_salt()
        row["passHash"] = _hash_pw(pw, row["salt"])
    else:
        ex = next((x for x in db.get("users", []) if x.get("id") == row.get("id")), None)
        if ex:
            row["salt"] = ex.get("salt")
            row["passHash"] = ex.get("passHash")
    row.pop("password", None)
    return row


def _auto_sched_maint(row):
    """schedMaint is auto-filled from lastMaint + maintIntervalDays (never typed by hand)"""
    try:
        d = datetime.strptime(str(row.get("lastMaint") or ""), "%Y-%m-%d")
        n = int(row.get("maintIntervalDays") or 0)
        if n > 0:
            row["schedMaint"] = (d + timedelta(days=n)).strftime("%Y-%m-%d")
    except Exception:
        pass
    return row

def _migrate(db):
    """bring older data files up to the current shape"""
    changed = False
    for q in db.get("qualities", []):                      # 3-step -> explicit 4-step route
        if "step3_mc" not in q:
            q["step1_mc"] = q.get("pt_mc1") or ""; q["step1_time"] = q.get("time_req1") or 0
            q["step2_mc"] = q.get("pt_mc2") or ""; q["step2_time"] = q.get("time_req2") or 0
            q["step3_mc"] = q.get("dyeType") or "jet"; q["step3_time"] = q.get("dyeMins") or 0
            q["step4_mc"] = "stentor"; q["step4_time"] = q.get("finishMins") or 0
            q["dyeStep"] = 3
            if not q["step2_mc"]:                          # only one pre-treat step -> shift up
                q["step2_mc"], q["step2_time"] = q["step3_mc"], q["step3_time"]
                q["step3_mc"], q["step3_time"] = q["step4_mc"], q["step4_time"]
                q["step4_mc"], q["step4_time"] = "", 0
                q["dyeStep"] = 2
            changed = True
    for c in db.get("customers", []):                      # split address + gst/email
        if "officeAddress" not in c:
            c["officeAddress"] = c.pop("address", "")
            c.setdefault("deliveryAddress", ""); c.setdefault("gstNo", ""); c.setdefault("email", "")
            changed = True
    for r in db.get("qualityRecipes", []):                 # aux strings -> {name, qty, unit}
        if "aux" not in r:
            aux = []
            for i in range(1, 21):
                v = r.pop("aux%d" % i, None)
                if v:
                    aux.append({"name": v, "qty": "", "unit": "g/l"})
            r["aux"] = aux; changed = True
    for m in db.get("machines", []):                       # maintenance interval + auto date
        if "maintIntervalDays" not in m:
            m["maintIntervalDays"] = 60; changed = True
        before = m.get("schedMaint"); _auto_sched_maint(m)
        if m.get("schedMaint") != before: changed = True
    for l in db.get("lots", []):                            # stable positional taka numbers
        want = list(range(1, len(l.get("takas") or []) + 1))
        if l.get("takaNos") != want:
            l["takaNos"] = want; changed = True
    for c in db.get("challans", []):                        # normalize challans ingested by an older build
        if c.get("status") == "received":
            c["status"] = "inward-pending"; changed = True
        if not c.get("weaverChallanNo") and c.get("packingListNo"):
            c["weaverChallanNo"] = c["packingListNo"]; changed = True
        c.setdefault("lotId", "")
    if _dedupe_challans(db):                                # one-time cleanup of pre-existing re-sent challans
        changed = True
    today = time.strftime("%Y-%m-%d")
    seq_by = {}
    for b in db.get("batches", []):
        if "machine" not in b:
            b["machine"] = b.get("mcPin") or ""; changed = True
        if "planDay" not in b:
            b["planDay"] = today; changed = True
        if "seq" not in b:
            key = (b.get("machine",""), b.get("planDay",""))
            seq_by[key] = seq_by.get(key, 0) + 1
            b["seq"] = seq_by[key]; changed = True
    for o in db.get("operators", []):                  # every operator gets mobile-app credentials
        if not o.get("username") or not o.get("pin"):
            _ensure_operator_creds(db, o); changed = True
    db.setdefault("activityLog", [])
    db.setdefault("scanSessions", [])
    db.setdefault("settings", {}).setdefault("completionMode", "manual")
    return changed

# ---------------------------------------------------------------- seed data
# NOTE: all seed/reference DATA lives in seed_data.json - this file holds only logic.
SEED_PATH = os.path.join(HERE, "seed_data.json")
DEFAULT_ADMIN_USER = "ADMIN"
DEFAULT_ADMIN_PW   = "sonkeiwachikara"

def seed():
    """load the starting dataset from seed_data.json and add the bootstrap admin user"""
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["users"] = [_make_user("U-01", DEFAULT_ADMIN_USER, DEFAULT_ADMIN_PW, "Administrator")]
    data.setdefault("_seq", {})
    data.setdefault("activityLog", [])
    data.setdefault("challans", [])        # table always exists so edits/adds work before the first import
    return data

_DB_CACHE = None   # in-memory db, once loaded (this process is the sole writer of data.sqlite).
                   # Every caller of load_db() already holds LOCK, so serving the same cached dict
                   # instead of re-reading + re-parsing every SQLite table on every request is safe:
                   # nothing else touches the file while we're up. This also means the one-time
                   # migrate/self-heal scans below run ONCE per process lifetime, not on every
                   # GET/POST — they were previously re-scanning every quality/lot/batch/etc. on
                   # every single request, serialized behind the same global lock every other
                   # request was waiting on.

def load_db():
    global _DB_CACHE
    if _DB_CACHE is not None:
        return _DB_CACHE
    db = _load_raw()
    # auto-migrate: ensure any new tables/keys from the current seed exist
    base = seed()
    changed = False
    for k, v in base.items():
        if k not in db:
            db[k] = v
            changed = True
    # bootstrap auth on older data files: if no user can log in, seed roles + ADMIN
    if not any(u.get("passHash") for u in db.get("users", [])):
        db["users"] = base["users"]
        if not db.get("roles"):
            db["roles"] = base["roles"]
        changed = True
    # self-heal: the Administrator role must always hold every page that exists,
    # otherwise newly added pages stay invisible on an existing data file
    for r in db.get("roles", []):
        if r.get("name") == "Administrator":
            if [p for p in ALL_PAGES if p not in r.get("perms", [])]:
                r["perms"] = list(ALL_PAGES); changed = True
            if r.get("edit") != list(ALL_PAGES):          # Administrator can always edit everything
                r["edit"] = list(ALL_PAGES); changed = True
    if _migrate(db):
        changed = True
    _DB_CACHE = db          # set before save_db() so a save triggered from in here doesn't recurse
    if changed:
        save_db(db)
    return db

# ---------------------------------------------------------------- SQLite store
# Each data-table is a SQLite table of (id, data-JSON) documents, so records keep
# their flexible shape and the whole API/UI is unchanged, while we gain real
# tables, indexes, atomic transactions and headroom. _seq + settings live in _kv.
# Writes are already serialized by the request handler's LOCK, so these don't lock.
# HEAVY_TABLES are big reference sets (e.g. 60k dye-recipe lines) that must NOT be
# loaded into the in-memory db or sent in /api/db — they're queried on demand instead.
HEAVY_TABLES = {"recipes"}

def _connect():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("PRAGMA journal_mode=WAL")        # readers never block the single writer
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=5000")       # wait up to 5s for a lock instead of erroring
    return c

def _doc_tables(c):
    return [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name<>'_kv' AND name NOT LIKE 'sqlite_%'")]

# Per-thread snapshot of the last-loaded DB (row id -> serialized JSON), so a save writes ONLY the
# rows that actually changed instead of rewriting every table. DB_VERSION bumps on every save and
# drives the /api/db ETag so unchanged clients get a cheap 304. (Scales to ~150 concurrent users.)
_SNAP = threading.local()
_BOOT = secrets.token_hex(4)
DB_VERSION = 0

def _rowmap(v):
    return {str(r.get("id") or ("_row%d" % i)): json.dumps(r, ensure_ascii=False) for i, r in enumerate(v)}

def _snapshot(db):
    _SNAP.data = {k: _rowmap(v) for k, v in db.items() if isinstance(v, list)}

def _read_all(c):
    db = {}
    snap = {}
    for t in _doc_tables(c):
        if t in HEAVY_TABLES:                  # never load big reference tables into memory
            continue
        rows, raw = [], {}
        for (_id, d) in c.execute('SELECT id,data FROM "%s"' % t):
            rows.append(json.loads(d)); raw[str(_id)] = d
        db[t] = rows; snap[t] = raw
    for (k, v) in c.execute("SELECT k,v FROM _kv"):
        db[k] = json.loads(v)
    _SNAP.data = snap                          # remember exactly what was on disk, for diffed writes
    return db

def _write_all(c, db):
    """Persist only what changed vs. the snapshot taken at load time (falls back to a full
    write for any table with no snapshot, e.g. a brand-new table)."""
    c.execute("CREATE TABLE IF NOT EXISTS _kv (k TEXT PRIMARY KEY, v TEXT)")
    snap = getattr(_SNAP, "data", None) or {}
    lists = {k for k, v in db.items() if isinstance(v, list)}
    for t in set(_doc_tables(c)) - lists - HEAVY_TABLES:   # a whole table dropped from the in-memory db
        c.execute('DELETE FROM "%s"' % t)
    for k, v in db.items():
        if isinstance(v, list):
            c.execute('CREATE TABLE IF NOT EXISTS "%s" (id TEXT PRIMARY KEY, data TEXT)' % k)
            cur = _rowmap(v)
            old = snap.get(k)
            if old is None:                                # unknown table -> full write, once
                c.execute('DELETE FROM "%s"' % k)
                if cur:
                    c.executemany('INSERT OR REPLACE INTO "%s" (id,data) VALUES (?,?)' % k, list(cur.items()))
            else:
                removed = [(rid,) for rid in old if rid not in cur]
                if removed:
                    c.executemany('DELETE FROM "%s" WHERE id=?' % k, removed)
                changed = [(rid, js) for rid, js in cur.items() if old.get(rid) != js]
                if changed:
                    c.executemany('INSERT OR REPLACE INTO "%s" (id,data) VALUES (?,?)' % k, changed)
        elif isinstance(v, dict):
            c.execute("INSERT OR REPLACE INTO _kv (k,v) VALUES (?,?)", (k, json.dumps(v, ensure_ascii=False)))
    c.commit()
    _snapshot(db)                                          # snapshot now matches disk again

def save_db(db):
    global DB_VERSION, _DB_CACHE
    c = _connect()
    try:
        _write_all(c, db)
    finally:
        c.close()
    DB_VERSION += 1
    _DB_CACHE = db          # keep the in-memory cache authoritative and in sync with disk

def _etag():
    return '"%s-%d"' % (_BOOT, DB_VERSION)

def _load_raw():
    c = _connect()
    try:
        c.execute("CREATE TABLE IF NOT EXISTS _kv (k TEXT PRIMARY KEY, v TEXT)")
        fresh = (not _doc_tables(c)) and (c.execute("SELECT COUNT(*) FROM _kv").fetchone()[0] == 0)
        if fresh:                                  # one-time: import legacy data.json, else seed
            if os.path.exists(JSON_PATH):
                with open(JSON_PATH, "r", encoding="utf-8") as f:
                    base = json.load(f)
            else:
                base = seed()
            _write_all(c, base)
        return _read_all(c)
    finally:
        c.close()

# ---- dye recipes: a big on-demand table (imported from Excel), not part of /api/db ----
def _ensure_recipes(c):
    c.execute("CREATE TABLE IF NOT EXISTS recipes "
              "(id TEXT PRIMARY KEY, name TEXT, party TEXT, quality TEXT, shade TEXT, data TEXT)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_recipes_qs ON recipes(quality, shade)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_recipes_name ON recipes(name)")

def recipes_bulk_add(rows):
    c = _connect()
    try:
        _ensure_recipes(c)
        payload = [( "RC-" + uuid.uuid4().hex[:10], r.get("name", ""), r.get("party", ""),
                     r.get("quality", ""), str(r.get("shade", "")), json.dumps(r, ensure_ascii=False) )
                   for r in rows]
        c.executemany("INSERT INTO recipes (id,name,party,quality,shade,data) VALUES (?,?,?,?,?,?)", payload)
        c.commit()
        return len(payload)
    finally:
        c.close()

def recipes_search(q, limit=200):
    c = _connect()
    try:
        _ensure_recipes(c)
        q = (q or "").strip()
        if q:
            like = "%" + q + "%"
            rows = c.execute(
                "SELECT data FROM recipes WHERE name LIKE ? OR party LIKE ? OR quality LIKE ? OR shade LIKE ? "
                "ORDER BY name LIMIT ?", (like, like, like, like, limit)).fetchall()
        else:
            rows = c.execute("SELECT data FROM recipes ORDER BY name LIMIT ?", (limit,)).fetchall()
        return [json.loads(d) for (d,) in rows]
    finally:
        c.close()

def recipes_count():
    c = _connect()
    try:
        _ensure_recipes(c)
        return c.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    finally:
        c.close()

def recipes_distinct_shades():
    c = _connect()
    try:
        _ensure_recipes(c)
        return [{"quality": q, "shade": s, "name": n} for (q, s, n) in c.execute(
            "SELECT quality, shade, MIN(name) FROM recipes WHERE quality<>'' AND shade<>'' "
            "GROUP BY quality, shade ORDER BY quality, shade")]
    finally:
        c.close()

def recipes_clear():
    c = _connect()
    try:
        _ensure_recipes(c)
        c.execute("DELETE FROM recipes"); c.commit()
    finally:
        c.close()

# ---------------------------------------------------------------- HTTP
CT = {".html":"text/html",".js":"application/javascript",".css":"text/css",
      ".json":"application/json",".svg":"image/svg+xml",".ico":"image/x-icon",
      ".woff2":"font/woff2",".woff":"font/woff",".webmanifest":"application/manifest+json"}

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json", cookies=None, extra=None, cache=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        enc = None
        if body and len(body) > 900 and "gzip" in (self.headers.get("Accept-Encoding", "") or ""):
            body = gzip.compress(body, 5); enc = "gzip"     # shrink big JSON/JS/CSS payloads on the wire
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if enc:
            self.send_header("Content-Encoding", enc)
            self.send_header("Vary", "Accept-Encoding")
        # default: never cache, so edits to html/css/js appear on a normal refresh. Endpoints that
        # support revalidation (e.g. /api/db with an ETag) pass cache="no-cache" instead.
        self.send_header("Cache-Control", cache or "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        for k, v in (extra or []):
            self.send_header(k, v)
        for c in (cookies or []):
            self.send_header("Set-Cookie", c)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _session_ok(self):
        """cheap check that a live session cookie exists — no DB read (for the 304 fast path)"""
        tok = self._sid()
        s = SESSIONS.get(tok) if tok else None
        return bool(s and s["expires"] >= time.time())

    def _sid(self):
        raw = self.headers.get("Cookie", "") or ""
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sid":
                return v
        return None

    def _auth(self, db):
        """returns (user_dict, perms) for the current session, or (None, None)"""
        tok = self._sid()
        s = SESSIONS.get(tok) if tok else None
        if not s or s["expires"] < time.time():
            if tok:
                SESSIONS.pop(tok, None)
            return None, None
        u = _find_principal(db, s["username"])
        if not u:
            return None, None
        return u, _perms_for(db, u)

    def _lan_guard(self):
        """returns True and sends a 403 when LAN_ONLY is on and the caller is off-network"""
        if LAN_ONLY and not _client_is_lan(self.client_address[0]):
            self._send(403, {"error": "This system is only available on the factory network."})
            return True
        return False

    def do_GET(self):
        if self._lan_guard():
            return
        path = self.path.split("?")[0]
        if path == "/api/me":
            with LOCK:
                db = load_db(); u, perms = self._auth(db)
            if not u:
                return self._send(401, {"error": "not authenticated"})
            return self._send(200, {"user": {"username": u["username"], "role": u.get("role", ""),
                                             "perms": perms, "edit": _edit_perms_for(db, u),
                                             "prefs": u.get("prefs") or {}}})
        if path == "/api/db":
            # fast path: an unchanged DB + a live session -> 304, with no lock and no full load
            if self.headers.get("If-None-Match") == _etag() and self._session_ok():
                return self._send(304, b"", cache="no-cache", extra=[("ETag", _etag())])
            with LOCK:
                db = load_db(); u, perms = self._auth(db)
            if not u:
                return self._send(401, {"error": "login required"})
            return self._send(200, _sanitized(db), cache="no-cache", extra=[("ETag", _etag())])
        if path == "/api/termlog":
            # last N lines of the server's own console output — shown at the bottom of Settings.
            with LOCK:
                db = load_db(); u, perms = self._auth(db)
            if not u:
                return self._send(401, {"error": "login required"})
            if "settings" not in (perms or []):
                return self._send(403, {"error": "forbidden"})
            n = 40
            q = self.path.split("?", 1)[1] if "?" in self.path else ""
            for part in q.split("&"):
                if part.startswith("n="):
                    try: n = int(part[2:])
                    except Exception: n = 40
            n = max(1, min(n, 400))
            return self._send(200, {"lines": list(TERM_LOG)[-n:]}, cache="no-cache")
        if path.startswith("/scan-img/"):
            # stored program-scan photo — only for signed-in users who can see scans
            with LOCK:
                db = load_db(); u, perms = self._auth(db)
            if not u:
                return self._send(401, {"error": "login required"})
            if "op_scan" not in (perms or []) and "settings" not in (perms or []):
                return self._send(403, {"error": "forbidden"})
            fn = os.path.basename(path[len("/scan-img/"):])
            sp = os.path.normpath(os.path.join(PROGRAM_SCANS_DIR, fn))
            if not sp.startswith(PROGRAM_SCANS_DIR) or not os.path.isfile(sp):
                return self._send(404, {"error": "not found"})
            with open(sp, "rb") as f:
                return self._send(200, f.read(), "image/jpeg")
        # REL-UNITY mobile PWA (served from ../UNITY-MOBILE under /m/)
        if path == "/m":                            # canonicalise: /m -> /m/ so relative assets resolve
            self.send_response(301); self.send_header("Location", "/m/"); self.end_headers(); return
        if path.startswith("/m/"):
            rel = path[len("/m"):].lstrip("/")     # "/m/" -> "" -> index.html
            if rel == "":
                rel = "index.html"
            mp = os.path.normpath(os.path.join(MOBILE, rel))
            if not mp.startswith(MOBILE) or not os.path.isfile(mp):
                mp = os.path.join(MOBILE, "index.html")   # SPA fallback so deep links resolve
                if not os.path.isfile(mp):
                    return self._send(404, {"error":"not found"})
            mext = os.path.splitext(mp)[1]
            with open(mp, "rb") as f:
                return self._send(200, f.read(), CT.get(mext, "application/octet-stream"))
        # static files
        if path == "/" or path == "":
            path = "/index.html"
        fp = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            return self._send(404, {"error":"not found"})
        ext = os.path.splitext(fp)[1]
        with open(fp, "rb") as f:
            self._send(200, f.read(), CT.get(ext, "application/octet-stream"))

    def do_POST(self):
        if self._lan_guard():
            return
        if self.path.split("?")[0] != "/api":
            return self._send(404, {"error":"unknown endpoint"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error":"bad json"})
        op = req.get("op")

        # ---- QR camera-scan: token-authenticated ops used by the PHONE (no login on the phone —
        # the unguessable, short-lived token from the QR code IS the credential for these three ops
        # only). Desktop-side session ops (scanSessionStart/Status/Read/Apply/Cancel) are further
        # down, behind the normal cookie login like everything else.
        if op in ("scanUploadPair", "scanTokenInfo", "scanSessionFinish"):
            with LOCK:
                db = load_db()
                row = next((s for s in db.get("scanSessions", []) if s.get("token") == req.get("token")), None)
                live = bool(row) and row.get("status") in ("open", "finished") and time.time() <= row.get("expiresAt", 0)
                if op == "scanTokenInfo":
                    if not row:
                        return self._send(404, {"error": "This scan link isn't valid."})
                    return self._send(200, {"ok": True, "live": live, "status": row.get("status"),
                                            "pairCount": len(row.get("pairs", []))})
                if not live:
                    return self._send(200, {"ok": False,
                        "error": "This scan link has expired or was already used — go back to the desktop and open the camera again for a new code."})
                if op == "scanSessionFinish":
                    row["status"] = "finished"; save_db(db)
                    return self._send(200, {"ok": True})
                # scanUploadPair {token, left, right}: left page is required, right page optional
                # (mirrors the old phone flow's "left page req'd" rule) — stored to disk, not kept
                # in the JSON row (keeps /api/db and the doc-store small).
                left, right = req.get("left"), req.get("right")
                if not str(left or "").strip():
                    return self._send(400, {"error": "Left page photo is required."})
                sdir = os.path.join(SCAN_SESSIONS_DIR, row["id"])
                try: os.makedirs(sdir, exist_ok=True)
                except OSError: pass
                idx = len(row.get("pairs", []))
                pair = {"idx": idx, "left": "", "right": "", "read": False,
                        "at": time.strftime("%Y-%m-%d %H:%M:%S")}
                for side, val in (("left", left), ("right", right)):
                    s = str(val or "")
                    if "," in s and s.strip().lower().startswith("data:"): s = s.split(",", 1)[1]
                    if not s.strip(): continue
                    try:
                        raw = base64.b64decode(s, validate=False)
                        fn = "pair%d_%s.jpg" % (idx, side)
                        with open(os.path.join(sdir, fn), "wb") as f: f.write(raw)
                        pair[side] = fn
                    except Exception as e:
                        print("[scan] could not store %s photo:" % side, repr(e), flush=True)
                if not pair["left"]:
                    return self._send(400, {"error": "Couldn't read that photo — try again."})
                row.setdefault("pairs", []).append(pair)
                row["status"] = "open"
                save_db(db)
                return self._send(200, {"ok": True, "pairCount": len(row["pairs"])})

        # scanSessionRead forwards the session's photos to the Gemini API, which can take tens of
        # seconds. Run it OUTSIDE the global LOCK (only brief locks for auth + the final write) so
        # it never freezes every other user's requests — same reasoning the old scanRead had.
        if op == "scanSessionRead":
            with LOCK:
                db = load_db(); u, perms = self._auth(db)
            if not u: return self._send(401, {"error": "login required"})
            if "op_scan" not in _edit_perms_for(db, u): return self._send(403, {"error": "forbidden"})
            sid = req.get("id")
            with LOCK:
                db = load_db()
                row = next((s for s in db.get("scanSessions", []) if s.get("id") == sid), None)
                if not row or row.get("createdBy") != u["username"]:
                    return self._send(404, {"error": "scan session not found"})
                unread = [dict(p) for p in row.get("pairs", []) if not p.get("read")]
                sdir = os.path.join(SCAN_SESSIONS_DIR, sid)
            cfg = _gemini_cfg()
            if not cfg["enabled"]:
                return self._send(200, {"ok": False,
                    "error": "The scan reader isn't set up yet — an admin must set gemini.apiKey in secrets.local.json."})
            machines, errors, done_idx = [], [], []
            for p in unread:
                try:
                    imgs = []
                    for fn in (p.get("left"), p.get("right")):
                        if not fn: continue
                        with open(os.path.join(sdir, fn), "rb") as f:
                            imgs.append(base64.b64encode(f.read()).decode("ascii"))
                    prog = _gemini_extract(imgs, cfg)
                    machines.extend(prog.get("machines") or [])
                except RuntimeError as e:
                    errors.append({"spread": p.get("idx", 0) + 1, "error": str(e)})
                except Exception as e:
                    errors.append({"spread": p.get("idx", 0) + 1, "error": "Reader error: %s" % (e,)})
                done_idx.append(p.get("idx"))
            with LOCK:
                db = load_db()
                row = next((s for s in db.get("scanSessions", []) if s.get("id") == sid), None)
                if row:
                    for p in row.get("pairs", []):
                        if p.get("idx") in done_idx:
                            p["read"] = True
                    save_db(db)
            return self._send(200, {"ok": True, "machines": machines, "errors": errors})

        with LOCK:
            db = load_db()

            # ---- unauthenticated: login only ----
            if op == "login":
                username = (req.get("username") or "").strip()
                pw = req.get("password") or ""
                u = next((x for x in db.get("users", [])
                          if x.get("username") == username and x.get("active", True)), None)
                ok = bool(u and u.get("passHash") and hmac.compare_digest(u["passHash"], _hash_pw(pw, u["salt"])))
                if not ok:                                     # operator logging in with their username + PIN
                    o = next((x for x in db.get("operators", [])
                              if x.get("username") == username and x.get("active", True)), None)
                    if o and pw and hmac.compare_digest(str(o.get("pin") or ""), pw):
                        u = o; ok = True
                if not ok:
                    return self._send(401, {"error": "Invalid username or password"})
                # only ONE active session per user — drop any earlier one (logs out the previous device)
                for _t in [t for t, s in list(SESSIONS.items()) if s.get("username") == username]:
                    SESSIONS.pop(_t, None)
                token = secrets.token_hex(24)
                SESSIONS[token] = {"username": username, "expires": time.time() + SESSION_TTL}
                perms = _perms_for(db, u)
                _log(db, username, "login", "users", u.get("id", ""), "signed in"); save_db(db)
                return self._send(200, {"ok": True, "user": {"username": username, "role": u.get("role", ""),
                                                            "perms": perms, "edit": _edit_perms_for(db, u),
                                                            "prefs": u.get("prefs") or {}}},
                                  cookies=[f"sid={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age={SESSION_TTL}"])

            if op == "logout":
                tok = self._sid()
                who = SESSIONS.get(tok, {}).get("username") if tok else None
                if tok:
                    SESSIONS.pop(tok, None)
                if who:
                    _log(db, who, "logout", "users", "", "signed out"); save_db(db)
                return self._send(200, {"ok": True}, cookies=["sid=; HttpOnly; Path=/; Max-Age=0"])

            # ---- everything below requires a valid session ----
            u, perms = self._auth(db)
            if not u:
                return self._send(401, {"error": "login required"})
            eperms = _edit_perms_for(db, u)     # pages this user may MODIFY (subset of perms)
            def _need_edit(pages):
                # True (=> caller should 403) when the user can't edit ANY of these pages
                return not any(p in eperms for p in pages)

            if op == "changePassword":
                new = req.get("newPassword") or ""
                if len(new) < 6:
                    return self._send(400, {"error": "New password must be at least 6 characters"})
                if not hmac.compare_digest(u["passHash"], _hash_pw(req.get("oldPassword") or "", u["salt"])):
                    return self._send(403, {"error": "Current password is incorrect"})
                u["salt"] = _new_salt(); u["passHash"] = _hash_pw(new, u["salt"])
                _log(db, u["username"], "changePassword", "users", u.get("id", ""), "changed password"); save_db(db)
                return self._send(200, {"ok": True})

            if op == "savePrefs":
                # a user saves their OWN ui preferences (e.g. Order-status column widths).
                # self-service: writes only to the caller's own record, so no page permission is needed.
                prefs = req.get("prefs")
                if not isinstance(prefs, dict):
                    return self._send(400, {"error": "prefs must be an object"})
                if len(json.dumps(prefs)) > 8000:
                    return self._send(400, {"error": "prefs too large"})
                cur = u.get("prefs")
                if not isinstance(cur, dict):
                    cur = {}
                cur.update(prefs)
                u["prefs"] = cur
                save_db(db)
                return self._send(200, {"ok": True, "prefs": cur})

            # ---- QR camera-scan: desktop-side session ops (cookie-authenticated, owner-only) ----
            if op == "scanSessionStart":
                # Batch planner "camera" button: mint a short-lived, unguessable token + QR-able URL.
                # Nobody but this user can read/apply what gets uploaded to it (checked below by
                # comparing session.createdBy to the caller on every other scanSession* op).
                if _need_edit(("op_scan",)):
                    return self._send(403, {"error": "forbidden"})
                _scan_sessions_gc(db)
                sid = "SS-" + uuid.uuid4().hex[:8]
                token = secrets.token_urlsafe(24)
                row = {"id": sid, "token": token, "createdBy": u["username"],
                       "createdAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "expiresAt": time.time() + SCAN_SESSION_TTL, "status": "open", "pairs": []}
                db.setdefault("scanSessions", []).append(row)
                save_db(db)
                return self._send(200, {"ok": True, "id": sid, "token": token, "expiresIn": SCAN_SESSION_TTL})

            if op == "scanSessionStatus":
                row = next((s for s in db.get("scanSessions", []) if s.get("id") == req.get("id")), None)
                if not row or row.get("createdBy") != u["username"]:
                    return self._send(404, {"error": "scan session not found"})
                return self._send(200, {"ok": True, "status": row.get("status"),
                    "pairCount": len(row.get("pairs", [])),
                    "unreadCount": sum(1 for p in row.get("pairs", []) if not p.get("read")),
                    "expired": time.time() > row.get("expiresAt", 0)})

            if op == "scanSessionCancel":
                row = next((s for s in db.get("scanSessions", []) if s.get("id") == req.get("id")), None)
                if row and row.get("createdBy") == u["username"] and row.get("status") not in ("applied",):
                    row["status"] = "cancelled"; save_db(db)
                    _scan_session_cleanup_files(row["id"])
                return self._send(200, {"ok": True})

            if op == "scanSessionApply":
                # create real batches from the reviewed program + archive the session's photos into
                # programScans for the record (same shape scanCommit used to write)
                if _need_edit(("op_scan",)):
                    return self._send(403, {"error": "forbidden"})
                row = next((s for s in db.get("scanSessions", []) if s.get("id") == req.get("id")), None)
                if not row or row.get("createdBy") != u["username"]:
                    return self._send(404, {"error": "scan session not found"})
                if row.get("status") == "applied":
                    return self._send(400, {"error": "This scan was already applied."})
                program = req.get("program") or {}
                if not isinstance(program, dict) or not program.get("machines"):
                    return self._send(400, {"error": "Nothing to save."})
                created = _create_scan_batches(db, program, u["username"])
                if not created:
                    return self._send(400, {"error": "No batches could be created — check the machine names and lots."})
                pid = "PS-" + time.strftime("%y%m%d") + "-" + uuid.uuid4().hex[:6]
                files = []
                sdir = os.path.join(SCAN_SESSIONS_DIR, row["id"])
                for p in row.get("pairs", []):
                    for fn in (p.get("left"), p.get("right")):
                        if not fn: continue
                        src = os.path.join(sdir, fn)
                        if not os.path.isfile(src): continue
                        dest_fn = "%s_%s" % (pid, fn)
                        try:
                            with open(src, "rb") as sf, open(os.path.join(PROGRAM_SCANS_DIR, dest_fn), "wb") as df:
                                df.write(sf.read())
                            files.append(dest_fn)
                        except OSError as e:
                            print("[scan] could not archive %s:" % fn, repr(e), flush=True)
                rec = {"id": pid, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "by": u["username"],
                       "machines": sorted({str(m.get("machine", "")) for m in program.get("machines", [])}),
                       "batchIds": created, "files": files}
                db.setdefault("programScans", []).append(rec)
                row["status"] = "applied"
                _log(db, u["username"], "create", "programScans", pid,
                     "punched %d batch(es) from a QR camera scan" % len(created))
                save_db(db)
                _scan_session_cleanup_files(row["id"])   # copies now live in program_scans/; drop the working files
                return self._send(200, {"ok": True, "created": len(created), "batchIds": created, "scanId": pid})

            if op == "scansList":
                if "op_scan" not in perms and "settings" not in perms:
                    return self._send(403, {"error": "forbidden"})
                rows = [{k: v for k, v in r.items()} for r in db.get("programScans", [])]
                return self._send(200, {"rows": rows, "gemini": {k: _gemini_cfg()[k] for k in ("model", "enabled")}})

            if op == "scanDelete":
                if _need_edit(("op_scan", "settings")):
                    return self._send(403, {"error": "forbidden"})
                sid = req.get("id")
                scans = db.get("programScans", [])
                rec = next((r for r in scans if r.get("id") == sid), None)
                if not rec:
                    return self._send(404, {"error": "scan not found"})
                for fn in (rec.get("files") or []):
                    try: os.remove(os.path.join(PROGRAM_SCANS_DIR, fn))
                    except OSError: pass
                db["programScans"] = [r for r in scans if r.get("id") != sid]
                _log(db, u["username"], "delete", "programScans", sid, "deleted a stored scan + its photos")
                save_db(db)
                return self._send(200, {"ok": True})

            if op == "batchStatus":
                if _need_edit(("batches", "op_batch")):
                    return self._send(403, {"error": "forbidden"})
                to = req.get("to")
                if to not in ("running", "done", "planned"):
                    return self._send(400, {"error": "bad status"})
                b = next((x for x in db.get("batches", []) if x.get("id") == req.get("id")), None)
                if not b:
                    return self._send(404, {"error": "batch not found"})
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                if to == "running":
                    b["status"] = "running"; b["startedAt"] = now; b["startedBy"] = u["username"]
                elif to == "done":
                    b["status"] = "done"; b["completedAt"] = now; b["completedBy"] = u["username"]
                    if not b.get("startedAt"):
                        b["startedAt"] = now; b["startedBy"] = u["username"]
                else:  # planned = reopen / undo a completion
                    b["status"] = "planned"
                    b.pop("completedAt", None); b.pop("completedBy", None)
                _log(db, u["username"], to, "batches", b["id"], "batch " + b["id"] + " -> " + to)
                save_db(db)
                return self._send(200, {"ok": True, "row": b})

            if op == "batchAddAddition":
                # mid-batch dye ADDITION: the jet is cooled to pull a sample, the supervisor calls for
                # more of some dye (or a different one) to correct the shade WHILE the fabric is still
                # inside the machine. Logged on the batch itself — no new batch, no cap on how many times
                # (an addition is a small top-up, not a full re-run). Distinct from a REDYE (below).
                if _need_edit(("batches", "op_batch")):
                    return self._send(403, {"error": "forbidden"})
                b = next((x for x in db.get("batches", []) if x.get("id") == req.get("id")), None)
                if not b:
                    return self._send(404, {"error": "batch not found"})
                note = str(req.get("note") or "").strip()
                if not note:
                    return self._send(400, {"error": "Add a note describing what was added"})
                entry = {"id": "AD-" + uuid.uuid4().hex[:6], "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "by": u["username"], "note": note}
                b.setdefault("additions", []).append(entry)
                _log(db, u["username"], "addition", "batches", b["id"], "logged a dye addition on " + b["id"] + ": " + note)
                save_db(db)
                return self._send(200, {"ok": True, "row": b})

            if op == "batchRedye":
                # REDYE: the fabric already came OUT of the jet (batch completed) and there's a colour
                # mismatch, so the whole piece has to go back in. This is a NEW batch (same lots/takas/
                # quality/shade/machine as the original, same workflow step) linked back via redyeOf, so
                # Lot history / Batch history can show the lineage. Capped at 5 redyes per ORIGINAL batch
                # (redyeOf always points at the root of the chain, so redyeing a redye still counts
                # against the same cap rather than resetting it).
                if _need_edit(("batches", "op_batch")):
                    return self._send(403, {"error": "forbidden"})
                orig = next((x for x in db.get("batches", []) if x.get("id") == req.get("id")), None)
                if not orig:
                    return self._send(404, {"error": "batch not found"})
                if orig.get("status") != "done":
                    return self._send(400, {"error": "Only a completed batch (fabric already out of the machine) can be redyed"})
                note = str(req.get("note") or "").strip()
                if not note:
                    return self._send(400, {"error": "Add a note describing the colour mismatch"})
                root = orig.get("redyeOf") or orig["id"]
                existing = [x for x in db.get("batches", []) if x.get("redyeOf") == root]
                next_no = len(existing) + 1
                if next_no > 5:
                    return self._send(400, {"error": "This batch has already been redyed 5 times — the maximum."})
                row = {"lots": copy.deepcopy(orig.get("lots") or []), "lotIds": list(orig.get("lotIds") or []),
                       "quality": orig.get("quality", ""), "shadeNo": orig.get("shadeNo", ""),
                       "machine": orig.get("machine", ""), "mcPin": orig.get("mcPin") or orig.get("machine", ""),
                       "pgNo": orig.get("pgNo", ""), "pcs": orig.get("pcs", 0), "mtr": orig.get("mtr", 0),
                       "weight": orig.get("weight", 0), "status": "planned",
                       "redyeOf": root, "redyeNo": next_no, "redyeNote": note,
                       "seq": max([int(x.get("seq") or 0) for x in db.get("batches", []) if x.get("machine") == orig.get("machine")] or [0]) + 1}
                if orig.get("stepNode"):
                    row["stepNode"] = orig["stepNode"]; row["proc"] = orig.get("proc", "")
                row["id"] = _batch_id(db, row)
                db.setdefault("batches", []).append(row)
                _log(db, u["username"], "redye", "batches", row["id"],
                     "redye #%d of %s (from %s): %s" % (next_no, root, orig["id"], note))
                save_db(db)
                return self._send(200, {"ok": True, "row": row, "redyeNo": next_no})

            if op == "systemUpdate":
                # pull the latest code from GitHub so the system can be updated WITHOUT visiting the PC.
                # If server.py changed, the file-watcher auto-restarts within ~1s; static changes show on
                # a browser refresh. Admin/settings-edit only, and logged.
                if _need_edit(("settings",)):
                    return self._send(403, {"error": "forbidden"})
                root = os.path.dirname(HERE)
                try:
                    r = subprocess.run(["git", "pull", "--ff-only"], cwd=root,
                                       capture_output=True, text=True, timeout=120)
                    out = ((r.stdout or "") + (r.stderr or "")).strip()
                    changed = (r.returncode == 0) and ("up to date" not in out.lower())
                    _log(db, u["username"], "update", "settings", "",
                         "git pull: " + ("updated" if changed else "no change")); save_db(db)
                    return self._send(200, {"ok": r.returncode == 0, "changed": changed, "output": out[-4000:]})
                except Exception as e:
                    return self._send(200, {"ok": False, "changed": False, "output": "git pull failed: %s" % e})

            if op == "systemRestart":
                if _need_edit(("settings",)):
                    return self._send(403, {"error": "forbidden"})
                _log(db, u["username"], "restart", "settings", "", "manual server restart"); save_db(db)
                threading.Thread(target=_restart_process, daemon=True).start()
                return self._send(200, {"ok": True, "message": "Server restarting — refresh in a few seconds."})

            if op == "orderStatusSave":
                # the Order-status page edits a few tracking fields on a lot (dates, design, remark)
                if _need_edit(("op_orderstatus",)):
                    return self._send(403, {"error": "forbidden"})
                lid = req.get("lotId")
                lot = next((l for l in db.get("lots", []) if l.get("id") == lid), None)
                if not lot:
                    return self._send(404, {"error": "lot not found"})
                allow = ("designNo", "scourDate", "polyDyeDate", "cottonDyeDate", "finishDate",
                         "orderRemark", "toShade")
                fields = req.get("fields")
                if not isinstance(fields, dict):
                    return self._send(400, {"error": "fields must be an object"})
                for k, v in fields.items():
                    if k in allow:
                        lot[k] = v
                _log(db, u["username"], "orderStatus", "lots", lid, "updated order-status fields")
                save_db(db)
                return self._send(200, {"ok": True, "row": lot})

            if op == "challansLoad":
                # challans are kept OUT of /api/db (they accumulate) — the Challans page loads them here
                if "challans" not in perms:
                    return self._send(403, {"error": "forbidden"})
                return self._send(200, {"rows": db.get("challans", [])})

            if op == "challanReconcile":
                # manually match inward-pending challans to their EMPIRE lots (also runs automatically
                # on every lot import + challan import)
                if _need_edit(("challans",)):
                    return self._send(403, {"error": "forbidden"})
                linked = _reconcile_challans(db)
                if linked:
                    _log(db, u["username"], "challanReconcile", "challans", "", "linked %d challans to lots" % linked)
                    save_db(db)
                pending = sum(1 for c in db.get("challans", []) if c.get("status") == "inward-pending")
                return self._send(200, {"ok": True, "linked": linked, "pending": pending})

            if op == "qualitiesMerge":
                # merge a hand-picked set of qualities into one (RIVER + RIVER (AJ) -> RIVER).
                if _need_edit(("qualities",)):
                    return self._send(403, {"error": "forbidden"})
                res = qualities_merge(db, req.get("names"), req.get("into"))
                if res.get("error"):
                    return self._send(400, res)
                _log(db, u["username"], "update", "qualities", "",
                     "merged %d qualities into '%s' (re-pointed %d lots, dropped %d shade rows)"
                     % (res["qualitiesRemoved"], res["into"], res["lotsRepointed"], res["shadesRemoved"]))
                save_db(db)
                return self._send(200, {"ok": True, **res})

            if op == "qualitiesDedupe":
                # merge width-suffix duplicate qualities ('AREA 60 INCH' -> 'AREA') and re-point
                # every lot/batch/shade. Destructive — admin/edit-on-qualities only, and logged.
                if _need_edit(("qualities",)):
                    return self._send(403, {"error": "forbidden"})
                res = qualities_dedupe(db)
                _log(db, u["username"], "update", "qualities", "",
                     "merged %d duplicate qualities, re-pointed %d lots, dropped %d shade rows"
                     % (res["qualitiesRemoved"], res["lotsRepointed"], res["shadesRemoved"]))
                save_db(db)
                return self._send(200, {"ok": True, **res})

            if op == "dispatchReturn":
                # undo one lotDispatches record (Admin -> Dispatch page): reverses its itemized per-taka
                # meters back onto the lot's active stock, mirroring _apply_dispatch's subtract-not-delete
                # model - a taka that's still present (partially dispatched, or a 0m no-op row) gets its
                # reported meters ADDED BACK onto its current length; a taka that dropped out entirely
                # gets re-inserted at the reported length. Exact restore (uses the ledger's own sr/mts/wt),
                # not a guess - covers a dispatch report matching the wrong lot, or matching too early.
                if _need_edit(("dispatch",)):
                    return self._send(403, {"error": "forbidden"})
                did = req.get("id")
                rec = next((d for d in db.get("lotDispatches", []) if d.get("id") == did), None)
                if not rec:
                    return self._send(404, {"error": "dispatch record not found"})
                if rec.get("returnedAt"):
                    return self._send(400, {"error": "already returned"})
                lot, added, _touched = _undo_dispatch_record(db, rec, u["username"])
                if not lot:
                    return self._send(404, {"error": "lot " + str(rec.get("lotId")) + " no longer exists"})
                _log(db, u["username"], "dispatchReturn", "lots", lot.get("id"),
                     "returned dispatch %s to stock (%d taka(s) restored)" % (did, added))
                save_db(db)
                return self._send(200, {"ok": True, "added": added, "lot": lot})

            if op == "dispatchReconcile":
                # Manual "Reconcile from file" upload (Dispatch page): re-process an OLD dispatch report
                # that was originally applied by the pre-fix, delete-based logic. See
                # _reconcile_dispatch_entries's docstring for exactly what this does and its limits.
                if _need_edit(("dispatch",)):
                    return self._send(403, {"error": "forbidden"})
                csv_text = req.get("csvText") or ""
                if not str(csv_text).strip():
                    return self._send(400, {"error": "no file content received"})
                try:
                    rows = list(_csv.reader(io.StringIO(csv_text)))
                    entries = _csv_to_dispatch(rows)
                except Exception as e:
                    return self._send(400, {"error": "could not read that file: %s" % (e,)})
                if not entries:
                    return self._send(400, {"error": "no dispatched takas found in that file"})
                report = _reconcile_dispatch_entries(db, entries, u["username"])
                save_db(db)
                return self._send(200, {"ok": True, "report": report})

            if op == "processedFiles":
                # Dispatch page "Processed files" panel: lists what's accumulated in inbox/done+error,
                # inbox_dispatch/done+error and inbox_challan/done+error — read-only, view-only permission.
                if "dispatch" not in perms:
                    return self._send(403, {"error": "forbidden"})
                return self._send(200, {
                    "lots": _list_processed_dir(INBOX_DONE, INBOX_ERR),
                    "dispatch": _list_processed_dir(DISPATCH_DONE, DISPATCH_ERR),
                    "challan": _list_processed_dir(CHALLAN_DONE, CHALLAN_ERR),
                })

            if op == "processedFileRead":
                # Open a file from the Processed files panel — same view-only gate as the list itself.
                if "dispatch" not in perms:
                    return self._send(403, {"error": "forbidden"})
                try:
                    text = _read_processed_file(req.get("kind"), req.get("status"), req.get("file"))
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True, "text": text})

            if op == "reprocessFile":
                # Processed files panel "Reprocess" button: re-run the SAME import pipeline the
                # relevant watcher would (as if this file had just been dropped back into its inbox
                # folder). Each kind's own apply logic already guards re-runs its own way:
                #   - lots: _apply_lots_core skips any lot id already present -> always a safe no-op
                #     for an already-imported lot, never double-adds.
                #   - challan: _apply_challan_core's record ids are derived from the payload's own
                #     content signature -> re-processing the identical file never double-adds either.
                #   - dispatch: plain re-apply is NOT safe to repeat (nothing stops it subtracting the
                #     same meters twice) - so this routes dispatch files through
                #     _reconcile_dispatch_entries instead, which has its own already-reconciled guard
                #     and is the same logic behind "Reconcile from this file" elsewhere on this page.
                kind = req.get("kind")
                if kind == "lots":
                    if _need_edit(("lots",)):
                        return self._send(403, {"error": "forbidden"})
                elif kind == "dispatch":
                    if _need_edit(("dispatch",)):
                        return self._send(403, {"error": "forbidden"})
                elif kind == "challan":
                    if _need_edit(("challans",)):
                        return self._send(403, {"error": "forbidden"})
                else:
                    return self._send(400, {"error": "unknown file kind"})
                try:
                    text = _read_processed_file(kind, req.get("status"), req.get("file"))
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                try:
                    if kind == "lots":
                        rows = list(_csv.reader(io.StringIO(text)))
                        lots = _csv_to_lots(rows)
                        if not lots:
                            return self._send(400, {"error": "no lots found in that file"})
                        added, skipped = _apply_lots_core(db, lots)
                        save_db(db)
                        return self._send(200, {"ok": True, "kind": "lots", "added": added, "skipped": skipped, "total": len(lots)})
                    if kind == "dispatch":
                        rows = list(_csv.reader(io.StringIO(text)))
                        entries = _csv_to_dispatch(rows)
                        if not entries:
                            return self._send(400, {"error": "no dispatched takas found in that file"})
                        report = _reconcile_dispatch_entries(db, entries, u["username"])
                        save_db(db)
                        return self._send(200, {"ok": True, "kind": "dispatch", "report": report})
                    if kind == "challan":
                        payload = json.loads(text)
                        added = _apply_challan_core(db, payload)
                        save_db(db)
                        return self._send(200, {"ok": True, "kind": "challan", "added": added,
                                                "total": len(payload.get("lots", []))})
                except Exception as e:
                    return self._send(400, {"error": "could not process that file: %s" % (e,)})

            if op == "flushEmptyLots":
                # Settings -> "Flush all lots". See _flush_empty_lots's docstring for exactly what
                # this does; the op just gates permission, runs it, and saves.
                if _need_edit(("lots",)):
                    return self._send(403, {"error": "forbidden"})
                result = _flush_empty_lots(db, u["username"])
                save_db(db)
                return self._send(200, dict({"ok": True}, **result))

            if op == "lotsClear":
                # wipe ALL lots (used when switching the lot-number scheme, e.g. to DESPNO). Qualities,
                # shades, recipes and batches are left alone. Admin/edit-on-lots only, and logged.
                if _need_edit(("lots",)):
                    return self._send(403, {"error": "forbidden"})
                n = len(db.get("lots", []))
                db["lots"] = []
                _log(db, u["username"], "delete", "lots", "", "cleared ALL %d lots" % n)
                save_db(db)
                return self._send(200, {"ok": True, "cleared": n})

            # ---- dye recipes (big on-demand table; imported from Excel) ----
            if op == "recipesBulkAdd":
                if _need_edit(("recipes",)):
                    return self._send(403, {"error": "forbidden"})
                n = recipes_bulk_add(req.get("rows") or [])
                _log(db, u["username"], "recipesImport", "recipes", "", "added %d recipes" % n); save_db(db)
                return self._send(200, {"ok": True, "added": n, "total": recipes_count()})

            if op == "recipesClear":
                if _need_edit(("recipes",)):
                    return self._send(403, {"error": "forbidden"})
                recipes_clear()
                _log(db, u["username"], "recipesClear", "recipes", "", "cleared all recipes"); save_db(db)
                return self._send(200, {"ok": True})

            if op == "recipesSearch":
                if "recipes" not in perms:
                    return self._send(403, {"error": "forbidden"})
                return self._send(200, {"rows": recipes_search(req.get("q"), int(req.get("limit") or 200)),
                                        "total": recipes_count()})

            if op == "recipesShades":
                if "recipes" not in perms:
                    return self._send(403, {"error": "forbidden"})
                return self._send(200, {"pairs": recipes_distinct_shades()})

            if op == "recipeCreate":
                # manually create ONE dye recipe (party-quality-shade + chemical lines)
                if _need_edit(("recipes",)):
                    return self._send(403, {"error": "forbidden"})
                r = req.get("row") or {}
                party = (r.get("party") or "").strip()
                quality = (r.get("quality") or "").strip()
                shade = str(r.get("shade") or "").strip()
                if not (quality and shade):
                    return self._send(400, {"error": "Quality and Shade are required."})
                name = (r.get("name") or "").strip() or "-".join(x for x in (party, quality, shade) if x)
                row = {"name": name, "party": party, "quality": quality, "shade": shade,
                       "unit": (r.get("unit") or "KG"), "machine": (r.get("machine") or ""),
                       "items": r.get("items") or []}
                recipes_bulk_add([row])
                # keep the catalog in step: ensure this quality + a shade entry exist for planning
                _ensure_quality_and_shade(db, quality)
                exists = any(str(s.get("quality", "")).upper() == quality.upper()
                             and str(s.get("shade", "")).upper() == shade.upper() for s in db.get("shadeRecipes", []))
                if not exists:
                    db.setdefault("shadeRecipes", []).append(
                        {"id": "SH-" + uuid.uuid4().hex[:6], "quality": quality, "shade": shade,
                         "family": "Neutral", "tone": 0, "program": name})
                _log(db, u["username"], "recipeCreate", "recipes", "", "created recipe " + name)
                save_db(db)
                return self._send(200, {"ok": True, "name": name, "total": recipes_count()})

            if op == "catalogSync":
                # setup helper: make sure every quality/shade referenced by lots AND by imported
                # recipes exists in the catalog (quality stub + shade '0', plus recipe-named shades)
                if _need_edit(("qualities", "shadeRecipes")):
                    return self._send(403, {"error": "forbidden"})
                aq = ash = 0
                for q in {(l.get("quality") or "").strip() for l in db.get("lots", [])}:
                    a, s = _ensure_quality_and_shade(db, q); aq += a; ash += s
                existing = {}
                for s in db.get("shadeRecipes", []):
                    existing[(str(s.get("quality", "")).upper(), str(s.get("shade", "")).upper())] = s
                fixed = 0
                for p in recipes_distinct_shades():
                    key = (str(p["quality"]).upper(), str(p["shade"]).upper())
                    a, _ = _ensure_quality_and_shade(db, p["quality"]); aq += a
                    s = existing.get(key)
                    if not s:
                        row = {"id": "SH-" + uuid.uuid4().hex[:6], "quality": p["quality"], "shade": p["shade"],
                               "family": "Neutral", "tone": 0, "program": p.get("name") or ""}
                        db.setdefault("shadeRecipes", []).append(row); existing[key] = row; ash += 1
                    elif (not s.get("program")) or s.get("program") == "from dye recipe":
                        s["program"] = p.get("name") or ""; fixed += 1
                _log(db, u["username"], "catalogSync", "qualities", "",
                     "added %d qualities, %d shades; program-fixed %d" % (aq, ash, fixed))
                save_db(db)
                return self._send(200, {"ok": True, "qualities": aq, "shades": ash, "fixed": fixed})

            if op == "recipesShadeSync":
                # create a shade entry for every quality-shade in the recipes, and set each shade's
                # program to its recipe name (fixing the old "from dye recipe" placeholder)
                if _need_edit(("shadeRecipes",)):
                    return self._send(403, {"error": "forbidden"})
                existing = {}
                for s in db.get("shadeRecipes", []):
                    existing[(str(s.get("quality", "")).upper(), str(s.get("shade", "")).upper())] = s
                added = fixed = 0
                for p in recipes_distinct_shades():
                    key = (str(p["quality"]).upper(), str(p["shade"]).upper())
                    s = existing.get(key)
                    if not s:
                        row = {"id": "SH-" + uuid.uuid4().hex[:6], "quality": p["quality"], "shade": p["shade"],
                               "family": "Neutral", "tone": 0, "program": p.get("name") or ""}
                        db.setdefault("shadeRecipes", []).append(row); existing[key] = row; added += 1
                    elif (not s.get("program")) or s.get("program") == "from dye recipe":
                        s["program"] = p.get("name") or ""; fixed += 1
                _log(db, u["username"], "recipesShadeSync", "shadeRecipes", "", "added %d, program-fixed %d" % (added, fixed))
                save_db(db)
                return self._send(200, {"ok": True, "added": added, "fixed": fixed})

            if op == "logPage":
                # paginated activity log (newest first) — kept out of /api/db so page loads stay small
                if "activity" not in perms:
                    return self._send(403, {"error": "forbidden"})
                q = (req.get("q") or "").strip().lower()
                off = max(0, int(req.get("offset") or 0))
                lim = min(max(1, int(req.get("limit") or 100)), 500)
                rows = list(reversed(db.get("activityLog", [])))
                if q:
                    rows = [e for e in rows if any(q in str(e.get(k, "")).lower()
                            for k in ("ts", "user", "action", "table", "recordId", "summary"))]
                return self._send(200, {"rows": rows[off:off + lim], "total": len(rows)})

            # ---- fast bulk insert into a normal table (client has already de-duped) ----
            if op == "bulkUpsert":
                table = req.get("table")
                if table in ("activityLog",) or table in HEAVY_TABLES:
                    return self._send(403, {"error": "not allowed for this table"})
                allowed = {"batches": ["batches", "op_batch"], "storageSlots": ["storageSlots", "op_storage"], "orders": ["orders", "op_order"], "workflows": ["op_workflows"], "processTypes": ["op_workflows"], "fabricGroups": ["op_workflows"]}.get(table, [table])
                if _need_edit(allowed):
                    return self._send(403, {"error": "forbidden: no edit permission for %s" % table})
                if table not in db or not isinstance(db.get(table), list):
                    return self._send(400, {"error": "unknown table %s" % table})
                SYSTEM_IDS = ("lots", "batches", "orders")
                added = 0
                for row in (req.get("rows") or []):
                    if not row.get("id"):
                        row["id"] = (_batch_id(db, row) if table == "batches" else _next_seq_id(db, table)) if table in SYSTEM_IDS else (table[:2].upper() + "-" + uuid.uuid4().hex[:6])
                    db[table].append(row); added += 1
                _log(db, u["username"], "bulkUpsert", table, "", "added %d rows" % added); save_db(db)
                return self._send(200, {"ok": True, "added": added})

            table = req.get("table")
            if table == "activityLog":
                return self._send(403, {"error": "the activity log is append-only"})
            # a table may be reachable from more than one page (e.g. batches from the
            # Operations "Batch maker" or the Admin one) — any of them grants write access
            if table == "__settings__":
                allowed = ["settings"]
            else:
                allowed = {"batches": ["batches", "op_batch"], "storageSlots": ["storageSlots", "op_storage"], "orders": ["orders", "op_order"], "workflows": ["op_workflows"], "processTypes": ["op_workflows"], "fabricGroups": ["op_workflows"]}.get(table, [table])
            if _need_edit(allowed):
                return self._send(403, {"error": f"forbidden: no edit permission for {table}"})

            if table == "__settings__":
                db["settings"] = req.get("row", {}); save_db(db)
                return self._send(200, {"ok": True})
            if table not in db or not isinstance(db.get(table), list):
                return self._send(400, {"error": f"unknown table {table}"})

            if op == "upsert":
                row = req.get("row", {})
                if table == "users":
                    row = _prepare_user_row(db, row)
                if table == "machines":
                    _auto_sched_maint(row)
                existing = next((r for r in db[table] if r.get("id") == row.get("id")), None) if row.get("id") else None
                if table == "qualities":
                    dye = int(row.get("dyeStep") or 3)
                    for i in range(1, 5):
                        if row.get("step%d_mc" % i) == "stentor" and i < dye:
                            return self._send(400, {"error":
                                "Stentor is a post-dyeing finish - it cannot be step %d when dyeing is step %d" % (i, dye)})
                if table == "batches":
                    was = bool(existing.get("urgent")) if existing else False
                    if bool(row.get("urgent")) != was and "urgent_flag" not in eperms:
                        return self._send(403, {"error": "Only a Master can flag a batch urgent"})
                    if bool(row.get("urgent")) and not was:
                        row["urgentBy"] = u["username"]; row["urgentAt"] = time.strftime("%Y-%m-%d %H:%M")
                    if existing and "urgent_flag" not in eperms:   # data operators may edit shade/takas/weight only
                        if row.get("quality") != existing.get("quality"):
                            return self._send(403, {"error": "Only a Master can change a batch's quality"})
                        oldl = sorted(str(l.get("lotId")) for l in (existing.get("lots") or []))
                        newl = sorted(str(l.get("lotId")) for l in (row.get("lots") or []))
                        if newl != oldl:
                            return self._send(403, {"error": "Only a Master can change which lots are in a batch"})
                lotno = ""
                if table == "lots":
                    tk = row.get("takas") or []
                    row["takaNos"] = list(range(1, len(tk) + 1))   # stable positional taka numbers
                    lotno = str(row.pop("lotNo", "") or row.get("id") or "").strip()   # the number IS the lot's identity
                if table == "operators":
                    _ensure_operator_creds(db, row)   # auto username + PIN for the mobile app
                SYSTEM_IDS = ("batches", "orders")                 # lots are no longer auto-numbered (point 3)
                if table == "lots" and not existing:
                    # the lot number comes from the source system (Livewire/EMPIRE), never allocated here
                    if not lotno:
                        return self._send(400, {"error": "A lot number is required — this system no longer allocates lot numbers."})
                    if any(r.get("id") == lotno for r in db["lots"]):
                        return self._send(400, {"error": "Lot number '%s' already exists." % lotno})
                    row["id"] = lotno
                    db["lots"].append(row)
                elif table in SYSTEM_IDS and not existing:
                    row["id"] = _batch_id(db, row) if table == "batches" else _next_seq_id(db, table)   # structured batch id
                    db[table].append(row)
                elif not row.get("id"):
                    row["id"] = table[:2].upper() + "-" + uuid.uuid4().hex[:6]
                    db[table].append(row)
                else:
                    arr = db[table]; found = False
                    for i, r in enumerate(arr):
                        if r.get("id") == row["id"]:
                            arr[i] = row; found = True; break
                    if not found: arr.append(row)
                _log(db, u["username"], "create" if not existing else "update", table,
                     row.get("id", ""), (table + " " + str(row.get("name") or row.get("id") or "")).strip())
                save_db(db)
                safe = {k: v for k, v in row.items() if k not in ("passHash", "salt")}
                return self._send(200, {"ok": True, "row": safe})
            if op == "delete":
                rid = req.get("id")
                db[table] = [r for r in db[table] if r.get("id") != rid]
                _log(db, u["username"], "delete", table, rid, "deleted " + str(rid))
                save_db(db); return self._send(200, {"ok": True})
        return self._send(400, {"error": "unknown op"})

    def log_message(self, *a):  # quieter console
        pass

def _restart_process():
    """re-exec this server (used by the admin 'Restart server' button). Waits briefly so the HTTP
    response is flushed to the browser before the process is replaced."""
    time.sleep(0.8)
    try:
        os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
    except Exception as e:
        print("restart failed, please restart manually:", e, flush=True)

def _watch_and_reload(interval=1.0):
    """restart this process automatically when server.py is edited — no manual restart"""
    me = os.path.abspath(__file__)
    try:
        last = os.path.getmtime(me)
    except OSError:
        return
    while True:
        time.sleep(interval)
        try:
            cur = os.path.getmtime(me)
        except OSError:
            continue
        if cur != last:
            print("\n>> server.py changed — reloading automatically...\n", flush=True)
            try:
                os.execv(sys.executable, [sys.executable, me] + sys.argv[1:])
            except Exception as e:
                print("auto-reload failed, please restart manually:", e, flush=True)
                return

# ---------------------------------------------------------------- inbox: auto-import lots from CSV
# Your .bat drops a CSV into mvp/inbox/ ; this watcher reads it, turns each row into a lot
# (keyed by the source lot number, which becomes the lot id), then moves the file to
# inbox/done or inbox/error with a .log. Columns are matched by header NAME (order-independent).
# If your headers differ, just adjust LOT_COL_ALIASES below.
INBOX_DIR  = os.path.join(HERE, "inbox")
INBOX_DONE = os.path.join(INBOX_DIR, "done")
INBOX_ERR  = os.path.join(INBOX_DIR, "error")
INBOX_POLL_SECS = 45

# Header names matched (order-independent). Each CSV row is ONE taka; rows are grouped by the LOT
# NUMBER, which is the DESPNO (despatch number) column — NOT the "LOT" column. LOT is kept only as a
# fallback for older exports that had no DESPNO. TAKA length is TakaPendingMts (the balance still to
# be dyed), falling back to Despatch, then Received. Adjust here if your headers differ.
LOT_COL_ALIASES = {
    "lotNo":   ["DESPNO", "DESP NO", "DESPATCHNO", "DESPATCH NO", "LOT", "LOT NO", "LOTNO", "LOT NUMBER"],
    "quality": ["GREYQUAL", "GREY QUALITY", "GREYQUALITY", "GREY QUAL", "QUALITY", "ITEM NAME"],
    "cardNo":  ["CARDNO", "CARD NO", "CARD"],
    "inDate":  ["LOTCREATETIME", "LOT CREATE TIME", "INW DATE", "IN DATE", "DATE"],
    "takaSr":  ["TAKASRNO", "TAKA SR NO", "TAKA SRNO", "SR NO", "SRNO", "TAKA NO"],
    "takaMts": ["TAKAPENDINGMTS", "TAKA PENDING MTS", "TAKADESPATCHMTS", "TAKA DESPATCH MTS",
                "TAKARECEIVEDMTS", "PENDING MTS", "METERS", "MTS", "MTR"],
    "takaWt":  ["TAKA_WT", "TAKAWT", "TAKA WT", "WEIGHT", "WT"],
    "lotPcs":  ["LOTPCS", "LOT PCS", "LOT PIECES"],           # reference totals from the source system
    "lotMts":  ["LOTMTS", "LOT MTS", "LOTMTRS", "LOT MTRS", "LOT METERS"],
}

def _norm_hdr(h): return re.sub(r"[^A-Z0-9]", "", str(h).upper())

def _num(x):
    try: return float(str(x).replace(",", "").strip() or 0)
    except (ValueError, TypeError): return 0.0

def _colmap(headers):
    norm = [_norm_hdr(h) for h in headers]; m = {}
    for field, aliases in LOT_COL_ALIASES.items():
        for a in aliases:
            na = _norm_hdr(a)
            if na in norm:
                m[field] = norm.index(na); break
    return m

def _find_header(rows):
    # skip SQL-dump noise ("Changed database context...", a dashes row); the header row has LOT + a taka/quality column
    for i, r in enumerate(rows):
        norm = [_norm_hdr(x) for x in r]
        if "LOT" in norm and any(h in norm for h in ("TAKASRNO", "GREYQUAL", "GREYQUALITY")):
            return i
    return 0

def _csv_to_lots(rows):
    if not rows:
        return []
    hi = _find_header(rows)
    cm = _colmap(rows[hi])
    if "lotNo" not in cm:
        raise ValueError("no lot column found (looked for %s); header row was %s"
                         % (LOT_COL_ALIASES["lotNo"], rows[hi]))
    lots = {}
    for r in rows[hi + 1:]:
        if not any(str(x).strip() for x in r):
            continue
        get = lambda f: (r[cm[f]] if (f in cm and cm[f] < len(r)) else "")
        lotno = str(get("lotNo")).strip()
        # skip dashes, SQL footers like "(445 rows affected)", and rows with no real despatch number
        if not lotno or set(lotno) <= set("- ") or "(" in lotno or lotno.upper() in ("0", "NULL"):
            continue
        lot = lots.get(lotno)
        if lot is None:
            lot = {"id": lotno, "status": "in stock", "takas": [], "takaNos": [], "_wts": [], "_seen": set()}
            q = _normalize_quality(get("quality"))     # "AREA 60 INCH" -> "AREA" (same quality)
            if q: lot["quality"] = q
            card = str(get("cardNo")).strip()
            if card: lot["challanNo"] = card; lot["cardNo"] = card
            dt = str(get("inDate")).strip()
            if dt:
                lot["inDate"] = dt[:10]
                if len(dt) >= 16: lot["inTime"] = dt[11:16]
            sp = _num(get("lotPcs")); sm = _num(get("lotMts"))    # reference totals from EMPIRE, if filled
            if sp > 0: lot["srcPcs"] = int(sp)
            if sm > 0: lot["srcMeters"] = round(sm)
            lots[lotno] = lot
        # EMPIRE emits ONE ROW PER PROCESS STEP, so every taka repeats (same DESPNO + TAKASRNO).
        # Record each taka exactly once — ignore all later rows for a taka already counted.
        sr_raw = str(get("takaSr")).strip()
        key = sr_raw or None
        if key is not None and key in lot["_seen"]:
            continue
        mts = _num(get("takaMts"))
        if mts <= 0:
            continue                                  # a fully-processed / zero-length taka isn't stock
        if key is not None:
            lot["_seen"].add(key)
        try: sr = int(float(sr_raw))
        except (ValueError, TypeError): sr = len(lot["takas"]) + 1
        lot["takas"].append(mts); lot["takaNos"].append(sr); lot["_wts"].append(_num(get("takaWt")))
    out = []
    for lot in lots.values():
        lot.pop("_seen", None)
        if not lot["takas"]:
            continue                                   # drop any lot that ended up with no real takas (noise)
        order = sorted(range(len(lot["takaNos"])), key=lambda i: lot["takaNos"][i])   # by taka SR no.
        lot["takas"]   = [lot["takas"][i] for i in order]
        lot["takaNos"] = [lot["takaNos"][i] for i in order]
        wts = [lot["_wts"][i] for i in order]; lot.pop("_wts", None)
        lot["pcs"] = len(lot["takas"]); lot["meters"] = round(sum(lot["takas"]))
        if sum(wts) > 0:
            lot["weight"] = round(sum(wts) * 10) / 10; lot["takaWts"] = wts
        out.append(lot)
    return out

def _prune_dir(d, keep=30):
    try:
        files = sorted(f for f in os.listdir(d) if f.lower().endswith((".csv", ".txt", ".json")))
    except OSError:
        return
    for old in files[:-keep]:                          # keep the newest `keep`, delete the rest (+ their .log)
        for path in (os.path.join(d, old), os.path.join(d, old + ".log")):
            try: os.remove(path)
            except OSError: pass

def _list_processed_dir(done_dir, err_dir):
    """One entry per processed file in a watcher's done/ + error/ folders, newest first — powers the
    Dispatch page's 'Processed files' panel (op processedFiles). Each processed file was renamed
    '<stamp>-<original name>' with a sibling '<name>.log' holding 'OK: <summary>' or 'ERROR: <error>'
    (see _inbox_watcher / _dispatch_watcher / _challan_watcher)."""
    out = []
    for status, d in (("ok", done_dir), ("error", err_dir)):
        try:
            names = [f for f in os.listdir(d) if not f.endswith(".log") and not f.startswith(".")]
        except OSError:
            continue
        for name in names:
            path = os.path.join(d, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            summary = ""
            try:
                with open(path + ".log", "r", encoding="utf-8") as lf:
                    summary = lf.read().strip()
                    for prefix in ("OK: ", "ERROR: "):
                        if summary.startswith(prefix):
                            summary = summary[len(prefix):]; break
            except OSError:
                pass
            # strip the "<stamp>-" the watcher prefixed on file (stamp is fixed-width: YYYYMMDD-HHMMSS-)
            orig = re.sub(r"^\d{8}-\d{6}-", "", name)
            out.append({"name": orig, "file": name, "status": status, "summary": summary,
                        "at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)), "size": st.st_size})
    out.sort(key=lambda r: r["at"], reverse=True)
    return out

PROCESSED_DIRS = {   # kind -> (done dir, error dir), shared by op processedFiles / processedFileRead
    "lots":     (lambda: (INBOX_DONE, INBOX_ERR)),
    "dispatch": (lambda: (DISPATCH_DONE, DISPATCH_ERR)),
    "challan":  (lambda: (CHALLAN_DONE, CHALLAN_ERR)),
}

def _read_processed_file(kind, status, name):
    """Read one already-processed file's raw text back out of inbox*/done or inbox*/error, for the
    Dispatch page's 'Processed files' panel (open a file to view it / reconcile straight from it).
    `name` MUST be the exact on-disk filename (the 'file' field from _list_processed_dir, i.e. still
    carrying its '<stamp>-' prefix) - rejects anything that isn't a plain filename actually inside the
    resolved directory, so this can never be used to read an arbitrary path on the server."""
    if kind not in PROCESSED_DIRS or status not in ("ok", "error"):
        raise ValueError("unknown file kind/status")
    done_dir, err_dir = PROCESSED_DIRS[kind]()
    d = done_dir if status == "ok" else err_dir
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError("invalid file name")
    path = os.path.realpath(os.path.join(d, name))
    if os.path.dirname(path) != os.path.realpath(d) or not os.path.isfile(path):
        raise ValueError("file not found")
    size = os.path.getsize(path)
    if size > 3_000_000:
        raise ValueError("file is too large to preview here (%.1f MB) — open it directly on the server" % (size / 1e6,))
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()

def _iter_processed_files(kind):
    """Every processed file for one inbox kind, oldest first (by the fixed-width stamp prefix each
    watcher renamed it with) - done and error folders merged into one chronological sequence, since
    that's the order they'd have been dropped into the live inbox originally. Yields
    (status, on-disk name) pairs; use _read_processed_file(kind, status, name) to get the text.
    Powers Settings -> Flush all lots (reprocess EVERY file of every kind, in order)."""
    done_dir, err_dir = PROCESSED_DIRS[kind]()
    items = []
    for status, d in (("ok", done_dir), ("error", err_dir)):
        try:
            names = [f for f in os.listdir(d) if not f.endswith(".log") and not f.startswith(".")]
        except OSError:
            continue
        for name in names:
            items.append((name, status, name))   # sort key is the stamped on-disk name itself
    items.sort(key=lambda t: t[0])
    return [(status, name) for _key, status, name in items]

def _apply_lots_core(db, lots):
    """Lock-free core of the lot-inbox apply — same logic as always, just split out so a caller that
    already holds LOCK + a loaded db (e.g. the Processed files 'Reprocess' button) can call it directly
    instead of re-entering the lock (threading.Lock isn't reentrant - that would deadlock the server).
    _apply_lots (below) is the locking, top-level entry the watcher itself uses."""
    by_id = {l.get("id"): l for l in db.get("lots", [])}
    added = skipped = 0
    new_quals = set()
    for lot in lots:
        if lot["id"] in by_id:
            skipped += 1                            # already imported — leave the existing record
            continue                                #   untouched (guard against re-runs / double entry)
        db.setdefault("lots", []).append(lot); by_id[lot["id"]] = lot; added += 1
        new_quals.add((lot.get("quality") or "").strip())
    aq = ash = 0                                    # quick-add each NEW lot's quality + a shade '0'
    for q in new_quals:
        a, s = _ensure_quality_and_shade(db, q); aq += a; ash += s
    linked = _reconcile_challans(db)                # a lot's inward challan may already be waiting
    _log(db, "inbox", "lotImport", "lots", "",
         "imported: %d new lots, %d already present (skipped); +%d qualities, +%d shades; linked %d challans"
         % (added, skipped, aq, ash, linked))
    return added, skipped

def _apply_lots(lots):
    with LOCK:
        db = load_db()
        added, skipped = _apply_lots_core(db, lots)
        save_db(db)
    return added, skipped

def _process_inbox(path):
    if path.lower().endswith((".xlsx", ".xls")):
        raise ValueError("Excel received — please export CSV, not Excel (the server reads CSV).")
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(_csv.reader(f))
    lots = _csv_to_lots(rows)
    if not lots:
        raise ValueError("no lots found in file")
    added, skipped = _apply_lots(lots)
    return "%d lots in file: %d new, %d already present (skipped), from %d rows" % (len(lots), added, skipped, len(rows))

def _inbox_watcher():
    for d in (INBOX_DIR, INBOX_DONE, INBOX_ERR):
        try: os.makedirs(d, exist_ok=True)
        except OSError: pass
    while True:
        try:
            for name in sorted(os.listdir(INBOX_DIR)):
                p = os.path.join(INBOX_DIR, name)
                if not os.path.isfile(p) or name.startswith(".") or not name.lower().endswith((".csv", ".txt", ".xlsx", ".xls")):
                    continue
                stamp = time.strftime("%Y%m%d-%H%M%S")
                try:
                    summary = _process_inbox(p)
                    dest = os.path.join(INBOX_DONE, stamp + "-" + name); os.replace(p, dest)
                    with open(dest + ".log", "w", encoding="utf-8") as lf: lf.write("OK: " + summary + "\n")
                    print("[inbox]", name, "->", summary, flush=True)
                except Exception as e:
                    try: dest = os.path.join(INBOX_ERR, stamp + "-" + name); os.replace(p, dest)
                    except OSError: dest = p
                    try:
                        with open(dest + ".log", "w", encoding="utf-8") as lf: lf.write("ERROR: " + str(e) + "\n")
                    except OSError: pass
                    print("[inbox] ERROR", name, ":", e, flush=True)
            _prune_dir(INBOX_DONE); _prune_dir(INBOX_ERR)   # retain only the newest 30 processed files
        except Exception as e:
            print("[inbox] watcher error:", e, flush=True)
        time.sleep(INBOX_POLL_SECS)

# ---------------------------------------------------------------- dispatch inbox: taka-wise "Dispatch
# Report ..." CSVs (one row per dispatched taka, from the mill's GREYRET/CHALTRN dispatch query).
# Drop one in mvp/inbox_dispatch/ ; this watcher removes each dispatched taka from its lot's ACTIVE
# stock (so Storage / Taka master stop showing it) and files an itemized record in lotDispatches so
# the Lot history page can still show what left, when, and on which challan — even once a lot's stock
# empties out entirely. Same CSV-only / header-matched-by-name convention as the lot inbox above.
DISPATCH_DIR  = os.path.join(HERE, "inbox_dispatch")
DISPATCH_DONE = os.path.join(DISPATCH_DIR, "done")
DISPATCH_ERR  = os.path.join(DISPATCH_DIR, "error")
DISPATCH_POLL_SECS = 45
LOT_DISPATCHES_CAP = 20000   # per-taka records; oldest trimmed once exceeded (mirrors LOG_CAP's approach)

DISPATCH_COL_ALIASES = {
    # Lot_No is the mill's plain lot number (matches lot IDs as created by the inbound-lot importer
    # above, e.g. "5934") and is blank in Lot_No_Display for nearly every row. But per the mill: when
    # Lot_No_Display holds "O"/"OO"/"OOOO" etc, that's NOT noise — it's a suffix on the lot's real
    # identity (denotes how many years old that stock is), e.g. Lot_No "1969" + Lot_No_Display "O" is
    # actually lot "1969O", a DIFFERENT lot than plain "1969". Kept as two separate fields so
    # _csv_to_dispatch can combine them instead of just picking one column.
    "lotNo":       ["LOT_NO", "LOT NO", "LOTNO", "DESPNO"],
    "lotNoSuffix": ["LOT_NO_DISPLAY", "LOT NO DISPLAY"],
    "cardNo":     ["CHALLAN_CARDNO", "CHALLAN CARDNO", "CARDNO", "CARD NO"],
    "dispDate":   ["DISPATCH_DATE", "DISPATCH DATE", "CUTDATE"],
    "quality":    ["QUALITY", "GREYQUAL"],
    "jobChallan": ["JOB_CHALLAN", "JOB CHALLAN"],
    "takaSr":     ["TAKA_NO", "TAKA NO", "TAKASRNO", "TAKA SR NO"],
    "takaMts":    ["TAKA_MTS", "TAKA MTS", "MTS"],
    "takaWt":     ["TAKA_WT", "TAKA WT", "WT"],
    "remark":     ["REMARK", "WRMK"],
}

def _dispatch_colmap(headers):
    norm = [_norm_hdr(h) for h in headers]; m = {}
    for field, aliases in DISPATCH_COL_ALIASES.items():
        for a in aliases:
            na = _norm_hdr(a)
            if na in norm:
                m[field] = norm.index(na); break
    return m

def _find_dispatch_header(rows):
    for i, r in enumerate(rows):
        norm = [_norm_hdr(x) for x in r]
        if any(h in norm for h in ("LOTNODISPLAY", "LOTNO", "DESPNO")) and any(h in norm for h in ("TAKANO", "TAKASRNO")):
            return i
    return 0

def _csv_to_dispatch(rows):
    """CSV rows (one row per dispatched taka) -> flat list of per-taka dispatch dicts."""
    if not rows:
        return []
    hi = _find_dispatch_header(rows)
    cm = _dispatch_colmap(rows[hi])
    if "lotNo" not in cm or "takaSr" not in cm:
        raise ValueError("no Lot_No_Display / Taka_No columns found; header row was %s" % (rows[hi],))
    out = []
    for r in rows[hi + 1:]:
        if not any(str(x).strip() for x in r):
            continue
        get = lambda f: (r[cm[f]] if (f in cm and cm[f] < len(r)) else "")
        lotno_raw = str(get("lotNo")).strip()
        if not lotno_raw or set(lotno_raw) <= set("- ") or "(" in lotno_raw or lotno_raw.upper() in ("0", "NULL"):
            continue                                    # SQL-dump noise / footer rows, same guard as the lot inbox
        suffix = str(get("lotNoSuffix")).strip().upper()
        lotno = lotno_raw + suffix if suffix and set(suffix) <= set("O") else lotno_raw
        sr_raw = str(get("takaSr")).strip()
        if not sr_raw:
            continue
        try: sr = int(float(sr_raw))
        except (ValueError, TypeError): continue
        out.append({"lotNo": lotno, "cardNo": str(get("cardNo")).strip(), "dispDate": str(get("dispDate")).strip()[:10],
                    "quality": _normalize_quality(get("quality")), "jobChallan": str(get("jobChallan")).strip(),
                    "takaSr": sr, "takaMts": _num(get("takaMts")), "takaWt": _num(get("takaWt")),
                    "remark": str(get("remark")).strip()})
    return out

REMAINDER_EPS = 0.5   # meters left after subtraction below this counts as fully dispatched (rounding slack)

def _apply_dispatch_one_lot(db, lot, lotno, rows, source="watcher"):
    """Core of the dispatch-apply logic for ONE lot's worth of report rows: SUBTRACT each row's
    reported meters (and weight, if tracked) from that taka's own current length, and file one
    itemized lotDispatches record (kept even after the lot's own stock empties out, so Lot history
    and the Dispatch page always have something to show). Shared by the normal inbox watcher
    (_apply_dispatch, below) and the manual reconcile-from-file flow (_reconcile_dispatch_entries).

    Per the mill: a dispatch-report row naming a taka does NOT mean that whole taka left stock - it
    means THAT MANY METERS left it. A taka can appear on a report with 0 meters dispatched (about 40%
    of rows in a typical report), which must be a true no-op, not a deletion. A taka only drops out
    once its remaining length is ~0.

    Returns the new ledger record dict (already appended to db["lotDispatches"]) plus whether the
    lot ended up fully dispatched by this application."""
    recs = db.setdefault("lotDispatches", [])
    rec = {"id": "DSP-" + uuid.uuid4().hex[:8], "lotId": lotno, "source": source,
           "cardNo": rows[0].get("cardNo") or "", "date": rows[0].get("dispDate") or time.strftime("%Y-%m-%d"),
           "jobChallan": rows[0].get("jobChallan") or "",
           "quality": rows[0].get("quality") or ((lot or {}).get("quality") or ""),
           "takas": [{"sr": r["takaSr"], "mts": r["takaMts"], "wt": r["takaWt"], "remark": r.get("remark") or ""} for r in rows],
           "importedAt": time.strftime("%Y-%m-%d %H:%M:%S")}
    recs.append(rec)
    if len(recs) > LOT_DISPATCHES_CAP:
        del recs[:len(recs) - LOT_DISPATCHES_CAP]
    if not lot:
        return rec, False
    # a taka can appear more than once in one report (separate part-dispatches of the same
    # piece) - subtract the TOTAL reported for that serial, not just the last row seen.
    by_sr = {}
    for r in rows:
        key = str(r["takaSr"]); e2 = by_sr.setdefault(key, {"mts": 0.0, "wt": 0.0})
        e2["mts"] += r["takaMts"] or 0; e2["wt"] += r["takaWt"] or 0
    taka_nos = lot.get("takaNos") or []; takas = lot.get("takas") or []
    tracks_wt = "takaWts" in lot; taka_wts = (lot.get("takaWts") or []) if tracks_wt else []
    new_nos, new_mts, new_wts = [], [], []
    touched = False
    for i, sr in enumerate(taka_nos):
        cur_m = takas[i] if i < len(takas) else 0
        cur_w = taka_wts[i] if (tracks_wt and i < len(taka_wts)) else 0
        d = by_sr.get(str(sr))
        if d is None:
            new_nos.append(sr); new_mts.append(cur_m)
            if tracks_wt: new_wts.append(cur_w)
            continue
        touched = True
        rem_m = cur_m - d["mts"]                      # a 0m-dispatched row subtracts 0 -> unchanged, as it should
        if rem_m > REMAINDER_EPS:
            new_nos.append(sr); new_mts.append(round(rem_m, 2))
            if tracks_wt: new_wts.append(max(0.0, round(cur_w - d["wt"], 2)))
        # else: fully dispatched (remaining length ~0) - taka drops out of active stock
    fully = False
    if touched:
        lot["takaNos"] = new_nos; lot["takas"] = new_mts
        if tracks_wt: lot["takaWts"] = new_wts
        lot["pcs"] = len(lot.get("takas") or [])
        lot["meters"] = round(sum(lot.get("takas") or []))
        if tracks_wt:
            lot["weight"] = round(sum(lot["takaWts"] or []) * 10) / 10
        if not lot.get("takas"):
            lot["status"] = "dispatched"
            fully = True
    return rec, fully

def _apply_dispatch(entries):
    """Normal inbox-watcher path: group per-taka rows by lot and apply each lot via
    _apply_dispatch_one_lot. See that function's docstring for the subtract-not-delete semantics."""
    with LOCK:
        db = load_db()
        by_lot = {}
        for e in entries:
            by_lot.setdefault(e["lotNo"], []).append(e)
        taka_count = 0; matched_lots = 0; dispatched_lots = 0; unmatched = 0
        for lotno, rows in by_lot.items():
            lot = next((l for l in db.get("lots", []) if str(l.get("id")) == str(lotno)), None)
            taka_count += len(rows)
            if not lot:
                unmatched += 1
                _apply_dispatch_one_lot(db, None, lotno, rows)
                continue
            matched_lots += 1
            _rec, fully = _apply_dispatch_one_lot(db, lot, lotno, rows)
            if fully:
                dispatched_lots += 1
        _log(db, "inbox", "dispatch", "lots", "",
             "dispatch report: %d taka(s) across %d lot(s) (%d fully dispatched, %d lot id not found in system)"
             % (taka_count, matched_lots + unmatched, dispatched_lots, unmatched))
        save_db(db)
    return taka_count, matched_lots, dispatched_lots, unmatched

def _undo_dispatch_record(db, rec, actor):
    """Reverse one lotDispatches record's itemized per-taka meters back onto the lot's active stock -
    the shared core of the Dispatch page's 'Return dispatch' button AND the reconcile-from-file flow's
    auto-undo of a legacy (pre-fix) record. A taka that's still present (partially dispatched, or a 0m
    no-op row) gets its reported meters ADDED BACK onto its current length; a taka that dropped out
    entirely gets re-inserted at the reported length - exact for a record made by the corrected
    subtract logic, best-effort (see _reconcile_dispatch_entries) for one made by the old delete-based
    logic. Returns (lot_or_None, added_count, restored_taka_info) where restored_taka_info is a list of
    {"sr","mts","wasMissing"} for every taka this touched, so the caller can flag any that are
    best-effort restores of otherwise-unrecoverable stock."""
    lot = next((l for l in db.get("lots", []) if str(l.get("id")) == str(rec.get("lotId"))), None)
    if not lot:
        return None, 0, []
    lot.setdefault("takas", []); lot.setdefault("takaNos", [])
    tracks_wt = "takaWts" in lot
    if tracks_wt:
        lot.setdefault("takaWts", [])
    taka_nos, takas = lot["takaNos"], lot["takas"]
    taka_wts = lot["takaWts"] if tracks_wt else None
    idx_by_sr = {str(sr): i for i, sr in enumerate(taka_nos)}
    added = 0; touched_takas = []
    for t in (rec.get("takas") or []):
        sr = t.get("sr")
        if sr is None:
            continue
        key = str(sr)
        was_missing = key not in idx_by_sr
        mts = t.get("mts") or 0
        if not was_missing:
            i = idx_by_sr[key]
            takas[i] = round((takas[i] if i < len(takas) else 0) + mts, 2)
            if tracks_wt:
                while len(taka_wts) <= i:
                    taka_wts.append(0.0)
                taka_wts[i] = round(taka_wts[i] + (t.get("wt") or 0), 2)
            added += 1
        elif mts > 0:
            # missing taka, positive recorded amount -> reinstate it at that amount (exact restore
            # under the normal subtract model; best-effort under a legacy delete-based record - see
            # _reconcile_dispatch_entries, which flags this case for the mill to verify)
            taka_nos.append(sr); takas.append(mts)
            idx_by_sr[key] = len(taka_nos) - 1
            if tracks_wt:
                taka_wts.append(t.get("wt") or 0)
            added += 1
        # else: missing taka, 0m recorded -> nothing to restore (no stored length for it at all);
        # don't insert a phantom zero-length taka, just flag it (see caller)
        touched_takas.append({"sr": sr, "mts": mts, "wasMissing": was_missing})
    lot["pcs"] = len(lot["takas"])
    lot["meters"] = round(sum(lot["takas"]) if lot["takas"] else 0)
    if tracks_wt:
        lot["weight"] = round(sum(lot["takaWts"] or []) * 10) / 10
    if lot.get("status") == "dispatched" and lot["takas"]:
        lot["status"] = "in stock"
    rec["returnedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    rec["returnedBy"] = actor
    return lot, added, touched_takas

def _reconcile_dispatch_entries(db, entries, actor, skip_undo_lots=None):
    """Manual 'Reconcile from file' upload (Dispatch page): the mill re-uploads an OLD dispatch report
    that was originally processed by the pre-fix, delete-based logic (which wiped a taka's entire
    stock just for being mentioned on a report, even when 0m was actually dispatched - see
    _apply_dispatch_one_lot's docstring). For each lot in the file:

      1. Find any not-yet-returned LEGACY ledger record (source != "reconcile") for this lot with the
         same challan/card number - that's the earlier, possibly-bad application of this same report.
         If a RECONCILE-sourced record for this lot+card already exists and hasn't been returned, this
         exact file was already reconciled once - skip the lot entirely (no double-processing).
      2. Undo every matching legacy record (_undo_dispatch_record) - this is a BEST-EFFORT restore:
         a record's stored "mts" is what that report said was dispatched, not the taka's true length
         beforehand, so for a taka the old code wiped on a 0m-dispatched row, undoing it adds back 0
         (i.e. cannot recover it at all - there is no stored number for its real length). Every taka
         touched by an undo is flagged in the report returned to the caller so the mill can verify
         against physical stock; a 0m/still-missing one is flagged as unrecoverable, not just approximate.
      3. Re-apply this file's rows for the lot through the CORRECTED subtract logic
         (_apply_dispatch_one_lot), tagged source="reconcile", so the lot ends up in the state the
         corrected logic would have produced if it had run from the start.

    `skip_undo_lots` (Settings -> Flush all lots only): a set of lot ids that were JUST deleted and
    freshly recreated from their original inbound file in this same operation, before this function
    runs. Their current stock is the true, pristine original - NOT a post-old-delete survivor - so
    step 2's undo must NOT run for them (there is nothing to undo: the old delete never touched this
    fresh copy of the lot). Skipping straight to step 3 for these lots applies the report's meters once,
    correctly, onto the pristine stock. Any OLD legacy ledger record for such a lot is left alone
    (stale, but harmless — it no longer describes any lot state that still exists).
    Caller (do_POST's dispatchReconcile / flushEmptyLots op) already holds LOCK and a loaded db, and
    is responsible for calling save_db() after — this function does not lock or save itself."""
    skip_undo_lots = skip_undo_lots or set()
    by_lot = {}
    for e in entries:
        by_lot.setdefault(e["lotNo"], []).append(e)
    report = []
    any_change = False
    for lotno, rows in by_lot.items():
        card = str(rows[0].get("cardNo") or "").strip()
        lot = next((l for l in db.get("lots", []) if str(l.get("id")) == str(lotno)), None)
        recs = db.setdefault("lotDispatches", [])
        same_card = lambda r: str(r.get("cardNo") or "").strip() == card
        already = [r for r in recs if str(r.get("lotId")) == str(lotno) and r.get("source") == "reconcile"
                   and not r.get("returnedAt") and same_card(r)]
        if already:
            report.append({"lotId": lotno, "skipped": True,
                            "reason": "already reconciled from this report — no changes made", "flagged": []})
            continue
        fresh = str(lotno) in {str(x) for x in skip_undo_lots}
        legacy = [] if fresh else [r for r in recs if str(r.get("lotId")) == str(lotno) and r.get("source") != "reconcile"
                  and not r.get("returnedAt") and same_card(r)]
        flagged = []; undone = 0
        for r in legacy:
            _lot2, added, touched = _undo_dispatch_record(db, r, actor + " (reconcile)")
            undone += added
            for t in touched:
                if t["wasMissing"] and (t["mts"] or 0) <= 0:
                    flagged.append({"sr": t["sr"], "mts": t["mts"],
                                     "severity": "unrecoverable",
                                     "note": "this taka's original length was never recorded — its stock could not be restored; verify against physical stock and add it back manually if it still exists"})
                elif t["wasMissing"]:
                    flagged.append({"sr": t["sr"], "mts": t["mts"], "severity": "approximate",
                                     "note": "restored using the meters recorded on the original report, which may be less than its true original length — verify against physical stock"})
        if not lot:
            report.append({"lotId": lotno, "skipped": True,
                            "reason": "lot no longer exists in Lot master", "flagged": flagged})
            continue
        new_rec, fully = _apply_dispatch_one_lot(db, lot, lotno, rows, source="reconcile")
        any_change = True
        report.append({"lotId": lotno, "skipped": False, "legacyUndone": len(legacy),
                        "takasRestored": undone, "newRecordId": new_rec["id"],
                        "fullyDispatched": fully, "flagged": flagged})
    if any_change:
        _log(db, actor, "dispatchReconcile", "lots", "",
             "reconciled dispatch file: %d lot(s), %d skipped (already done / lot missing)"
             % (sum(1 for r in report if not r["skipped"]), sum(1 for r in report if r["skipped"])))
    return report

def _process_dispatch_inbox(path):
    if path.lower().endswith((".xlsx", ".xls")):
        raise ValueError("Excel received — please export CSV, not Excel (the server reads CSV).")
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(_csv.reader(f))
    entries = _csv_to_dispatch(rows)
    if not entries:
        raise ValueError("no dispatched takas found in file")
    taka_count, matched_lots, dispatched_lots, unmatched = _apply_dispatch(entries)
    return ("%d taka(s) across %d lot(s): %d fully dispatched, %d lot id not found in system"
            % (taka_count, matched_lots + unmatched, dispatched_lots, unmatched))

def _dispatch_watcher():
    for d in (DISPATCH_DIR, DISPATCH_DONE, DISPATCH_ERR):
        try: os.makedirs(d, exist_ok=True)
        except OSError: pass
    while True:
        try:
            for name in sorted(os.listdir(DISPATCH_DIR)):
                p = os.path.join(DISPATCH_DIR, name)
                if not os.path.isfile(p) or name.startswith(".") or not name.lower().endswith((".csv", ".txt", ".xlsx", ".xls")):
                    continue
                stamp = time.strftime("%Y%m%d-%H%M%S")
                try:
                    summary = _process_dispatch_inbox(p)
                    dest = os.path.join(DISPATCH_DONE, stamp + "-" + name); os.replace(p, dest)
                    with open(dest + ".log", "w", encoding="utf-8") as lf: lf.write("OK: " + summary + "\n")
                    print("[dispatch]", name, "->", summary, flush=True)
                except Exception as e:
                    try: dest = os.path.join(DISPATCH_ERR, stamp + "-" + name); os.replace(p, dest)
                    except OSError: dest = p
                    try:
                        with open(dest + ".log", "w", encoding="utf-8") as lf: lf.write("ERROR: " + str(e) + "\n")
                    except OSError: pass
                    print("[dispatch] ERROR", name, ":", e, flush=True)
            _prune_dir(DISPATCH_DONE); _prune_dir(DISPATCH_ERR)
        except Exception as e:
            print("[dispatch] watcher error:", e, flush=True)
        time.sleep(DISPATCH_POLL_SECS)

# ---------------------------------------------------------------- mill challans (parsed from emailed PDFs)
# challan_watch.py (a separate helper, uses pdfplumber) drops parsed JSON here; the server stays
# dependency-free and just files the results into the 'challans' table. One PDF page = one challan lot.
CHALLAN_DIR  = os.path.join(HERE, "inbox_challan")
CHALLAN_DONE = os.path.join(CHALLAN_DIR, "done")
CHALLAN_ERR  = os.path.join(CHALLAN_DIR, "error")

def _challan_no_key(c):
    """normalized Packing List / mill challan number ('ML05859/26') used to spot re-sends of the
    same challan — case/whitespace-insensitive so 'ml05859/26' and 'ML05859 / 26' still collide."""
    return re.sub(r"\s+", "", str(c.get("packingListNo") or c.get("weaverChallanNo") or "").strip().upper())

def _dedupe_challans(db):
    """The mill sometimes re-sends a corrected challan under the same Packing List (ML...) number —
    challan_watch.py's dedup is by exact PDF content hash, so a corrected PDF (different bytes) comes
    through as a brand-new record even though it's the same challan. Enforce one challan per number:
    keep only the newest (by receivedAt, ties broken by original insertion order) and drop the rest.
    If a dropped duplicate was already linked to an EMPIRE lot, the surviving (newer) challan takes
    over that link so the correction actually reaches the lot instead of the link being lost."""
    groups = {}
    for c in db.get("challans", []):
        key = _challan_no_key(c)
        if not key:
            continue
        groups.setdefault(key, []).append(c)
    removed = 0
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        group.sort(key=lambda c: str(c.get("receivedAt") or ""))   # stable sort: ties keep insertion order
        newest = group[-1]
        for dupe in group[:-1]:
            if newest.get("status") != "linked" and dupe.get("status") == "linked" and dupe.get("lotId"):
                lot = next((l for l in db.get("lots", []) if l.get("id") == dupe["lotId"]), None)
                if lot:
                    _link_challan_to_lot(db, newest, lot)         # newer challan's data now reaches the lot
            db["challans"].remove(dupe)
            removed += 1
    if removed:
        _log(db, "system", "challanDedupe", "challans", "",
             "removed %d superseded challan record(s) — a mill re-send under the same Packing List no. keeps only the newest" % removed)
    return removed

def _cl_match(c, lot):
    """does an inward-pending challan describe the same fabric as this EMPIRE lot?
    Match on quality + piece count + total meters (within tolerance). Dates are a week apart, so
    they're used only as a soft guard (the lot must not predate the challan)."""
    # ALL THREE must be present AND agree: quality, piece count, and meters — both the TOTAL and,
    # when the challan carries per-roll meters, each individual taka length (sorted, element-wise).
    # Never fall back to quality+pcs alone — that stuck challans to similar-but-different lots.
    q = _normalize_quality(lot.get("quality"))
    if not q or _normalize_quality(c.get("quality")) != q:
        return False
    lot_takas = sorted(_num(t) for t in (lot.get("takas") or []))
    ch_takas = sorted(_num(t) for t in (c.get("takas") or []))
    lpcs, cpcs = len(lot_takas), int(c.get("pcs") or 0)
    if not lpcs or not cpcs or lpcs != cpcs:
        return False
    lm = sum(lot_takas)                                   # total meters of every taka on the lot
    cm = _num(c.get("meters") or c.get("totalMeter"))     # the challan's total meters
    if lm <= 0 or cm <= 0:                                # meters REQUIRED on both sides
        return False
    if abs(cm - lm) > max(2.0, 0.01 * max(cm, lm)):       # totals must match closely (2 m or 1%)
        return False
    if ch_takas and len(ch_takas) == lpcs:               # each individual taka must line up too
        for a, b in zip(lot_takas, ch_takas):
            if abs(a - b) > max(3.0, 0.05 * max(a, b, 1)):   # per-taka: within 3 m or 5%
                return False
    cd, ld = str(c.get("packingDate") or ""), str(lot.get("inDate") or "")
    if cd and ld and ld < cd:            # the lot's inward date can't be before the challan's
        return False
    return True

def _link_challan_to_lot(db, c, lot):
    """carry the challan's data onto the EMPIRE lot and mark the challan linked."""
    lot["weaverChallanNo"] = c.get("weaverChallanNo") or c.get("packingListNo") or ""
    if c.get("customer") and not lot.get("customer"):
        lot["customer"] = c["customer"]
    if c.get("toShade"):
        lot["toShade"] = c["toShade"]
    if c.get("ownShade") and not lot.get("ownShade"):
        lot["ownShade"] = c["ownShade"]
    rw = _num(c.get("realWeightKg"))
    if rw > 0 and not _num(lot.get("weight")):
        lot["weight"] = round(rw, 1)         # real weighed kg — only when the lot has none (don't clobber)
    c["status"] = "linked"; c["lotId"] = lot.get("id", "")

def _reconcile_challans(db):
    """Link inward-pending challans to matching lots. Only links an UNAMBIGUOUS match (exactly one
    candidate lot) so two identical deliveries never cross-link. Lots are bucketed by quality so this
    is O(challans + lots), not O(challans x lots). Returns the number linked."""
    buckets = {}
    for lot in db.get("lots", []):
        if lot.get("weaverChallanNo"):        # already has its challan
            continue
        buckets.setdefault(_normalize_quality(lot.get("quality")), []).append(lot)
    linked = 0
    for c in db.get("challans", []):
        if c.get("status") != "inward-pending":
            continue
        bucket = buckets.get(_normalize_quality(c.get("quality")), [])
        cands = [lot for lot in bucket if _cl_match(c, lot)]
        if len(cands) == 1:                   # exactly one match -> safe to auto-link
            _link_challan_to_lot(db, c, cands[0])
            bucket.remove(cands[0])           # that lot is now taken
            linked += 1
    return linked

def _apply_challan_core(db, payload):
    """Lock-free core of the challan-inbox apply — split out so a caller that already holds LOCK + a
    loaded db (e.g. the Processed files 'Reprocess' button) can call it directly instead of re-entering
    the lock. _apply_challan (below) is the locking, top-level entry the watcher itself uses."""
    added = 0
    by_id = {c.get("id"): c for c in db.get("challans", [])}
    sig = payload.get("sig") or uuid.uuid4().hex[:10]
    for i, lot in enumerate(payload.get("lots", [])):
        cid = "CH-%s-%d" % (sig, i + 1)                 # stable id -> re-processing never duplicates
        if cid in by_id:
            continue
        rolls = lot.get("rolls", [])
        pkg = lot.get("packingListNo", "")
        rec = {"id": cid, "sig": sig, "source": payload.get("source", ""),
               "receivedAt": payload.get("receivedAt", ""), "status": "inward-pending", "page": i + 1,
               "quality": _normalize_quality(lot.get("quality")), "customer": lot.get("customer", ""),
               "toShade": lot.get("toShade", ""), "ownShade": lot.get("ownShade", ""),
               "width": lot.get("width", 0), "po": lot.get("po", ""),
               "packingListNo": pkg, "weaverChallanNo": pkg, "packingDate": lot.get("packingDate", ""),
               "process": lot.get("process", ""), "processRemark": lot.get("processRemark", ""),
               "totalTaka": lot.get("totalTaka", 0), "totalMeter": lot.get("totalMeter", 0),
               "pcs": lot.get("pcs", len(lot.get("takas", []))), "meters": lot.get("meters", 0),
               "realWeightKg": lot.get("realWeightKg", 0), "lotId": "",
               "takas": lot.get("takas", []), "takaWts": lot.get("takaWts", []),
               "rollNos": [r.get("rollNo", "") for r in rolls]}
        db.setdefault("challans", []).append(rec); by_id[cid] = rec; added += 1
    deduped = _dedupe_challans(db)                # a re-sent/corrected challan under the same ML no. supersedes the old one (logs its own entry)
    linked = _reconcile_challans(db)              # a matching EMPIRE lot may already be here
    if added or linked or deduped:
        _log(db, "challan", "challanImport", "challans", "",
             "imported %d challan lot(s) from %s; linked %d to lots" % (added, payload.get("source", "email"), linked))
    return added

def _apply_challan(payload):
    with LOCK:
        db = load_db()
        added = _apply_challan_core(db, payload)
        save_db(db)
    return added

def _flush_empty_lots(db, actor):
    """Settings -> 'Flush all lots': delete every lot currently sitting at 0 meters (that's the shape
    bad historical dispatch data leaves behind), then replay EVERY retained file across all three
    inboxes, in order: lots first, then dispatch reports, then challans - exactly as if the whole
    inbox history were being fed through the watchers again from scratch.

    Deleting the empty lots FIRST matters: _apply_lots_core skips any lot id already on record, so a
    wiped-but-still-present 0m lot would otherwise block its own original inbound file from ever
    recreating it with its true taka data. Once it's gone, that same original file (if still sitting
    in inbox/done or inbox/error - each watcher keeps only the newest 30 of each) recreates it fresh,
    and the dispatch replay then re-subtracts whatever was legitimately dispatched since, using the
    corrected subtract-not-delete logic (_reconcile_dispatch_entries, same as "Reconcile from file").

    Lock-free: caller (do_POST's flushEmptyLots op) already holds LOCK + a loaded db and saves after.
    A file that fails to parse/apply (or an already-corrupt one sitting in an error/ folder) is
    skipped and counted, not allowed to abort the whole flush."""
    lots = db.get("lots", [])
    empty_ids = [l.get("id") for l in lots if sum(l.get("takas") or []) <= 0]
    empty_set = {str(x) for x in empty_ids}
    if empty_ids:
        db["lots"] = [l for l in lots if l.get("id") not in set(empty_ids)]

    lot_added = lot_skipped = lot_files = lot_failed = 0
    for status, name in _iter_processed_files("lots"):
        lot_files += 1
        try:
            text = _read_processed_file("lots", status, name)
            parsed = _csv_to_lots(list(_csv.reader(io.StringIO(text))))
            if parsed:
                a, s = _apply_lots_core(db, parsed)
                lot_added += a; lot_skipped += s
        except Exception:
            lot_failed += 1

    dispatch_report = []; dispatch_files = 0; dispatch_failed = 0
    for status, name in _iter_processed_files("dispatch"):
        dispatch_files += 1
        try:
            text = _read_processed_file("dispatch", status, name)
            entries = _csv_to_dispatch(list(_csv.reader(io.StringIO(text))))
            if entries:
                dispatch_report.extend(_reconcile_dispatch_entries(db, entries, actor, skip_undo_lots=empty_set))
        except Exception:
            dispatch_failed += 1

    challan_added = challan_files = challan_failed = 0
    for status, name in _iter_processed_files("challan"):
        challan_files += 1
        try:
            text = _read_processed_file("challan", status, name)
            challan_added += _apply_challan_core(db, json.loads(text))
        except Exception:
            challan_failed += 1

    still_missing = [i for i in empty_ids
                      if not any(str(l.get("id")) == str(i) for l in db.get("lots", []))]
    dispatch_done = [r for r in dispatch_report if not r.get("skipped")]
    dispatch_restored = sum(r.get("takasRestored", 0) for r in dispatch_done)
    dispatch_flagged = sum(len(r.get("flagged") or []) for r in dispatch_done)
    _log(db, actor, "flushLots", "lots", "",
         "flush all lots: deleted %d empty lot(s) (%d could not be recreated - no surviving inbound file); "
         "replayed %d lot file(s) (+%d new, %d already present, %d failed), "
         "%d dispatch file(s) (%d lot-touches, %d taka(s) restored, %d flagged, %d failed), "
         "%d challan file(s) (+%d new, %d failed)"
         % (len(empty_ids), len(still_missing), lot_files, lot_added, lot_skipped, lot_failed,
            dispatch_files, len(dispatch_done), dispatch_restored, dispatch_flagged, dispatch_failed,
            challan_files, challan_added, challan_failed))
    return {
        "deletedLots": len(empty_ids), "stillMissing": still_missing,
        "lots": {"files": lot_files, "added": lot_added, "skipped": lot_skipped, "failed": lot_failed},
        "dispatch": {"files": dispatch_files, "report": dispatch_report, "failed": dispatch_failed,
                     "restored": dispatch_restored, "flagged": dispatch_flagged, "touched": len(dispatch_done)},
        "challan": {"files": challan_files, "added": challan_added, "failed": challan_failed},
    }

def _challan_watcher():
    for d in (CHALLAN_DIR, CHALLAN_DONE, CHALLAN_ERR):
        try: os.makedirs(d, exist_ok=True)
        except OSError: pass
    while True:
        try:
            for name in sorted(os.listdir(CHALLAN_DIR)):
                p = os.path.join(CHALLAN_DIR, name)
                if not os.path.isfile(p) or not name.lower().endswith(".json"):
                    continue
                stamp = time.strftime("%Y%m%d-%H%M%S")
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                    n = _apply_challan(payload)
                    os.replace(p, os.path.join(CHALLAN_DONE, stamp + "-" + name))
                    print("[challan]", name, "->", n, "lots", flush=True)
                except Exception as e:
                    try: os.replace(p, os.path.join(CHALLAN_ERR, stamp + "-" + name))
                    except OSError: pass
                    print("[challan] ERROR", name, ":", e, flush=True)
            _prune_dir(CHALLAN_DONE); _prune_dir(CHALLAN_ERR)
        except Exception as e:
            print("[challan] watcher error:", e, flush=True)
        time.sleep(INBOX_POLL_SECS)

def _challan_email_scheduler():
    """Fetch new mill challans from email on a schedule, so it doesn't depend on Windows Task
    Scheduler. Runs the standalone poller (challan_watch.py, which has pdfplumber/IMAP) as a
    subprocess — the server itself stays dependency-free. Default every 2 hours; set
    'gmailPollHours' in secrets.local.json to change it, or 0 to turn this off."""
    script = os.path.join(HERE, "challan_watch.py")
    if not os.path.exists(script):
        return
    time.sleep(20)                                     # let the server finish coming up first
    while True:
        try:
            hrs = float(load_secrets().get("gmailPollHours", 2) or 2)
        except (ValueError, TypeError):
            hrs = 2
        if hrs <= 0:                                   # disabled — check again in an hour
            time.sleep(3600); continue
        try:
            print("[challan] scheduled email check...", flush=True)
            subprocess.run([sys.executable, script], cwd=HERE, timeout=900)
        except Exception as e:
            print("[challan] scheduled email poll error:", e, flush=True)
        time.sleep(max(300.0, hrs * 3600))             # at least 5 minutes between runs

def _bind_server(preferred):
    """Bind to the preferred port; if Windows refuses it (in use, or inside a reserved/excluded
    range — common with Hyper-V/WSL/Docker), fall back to the next few ports with a clear message."""
    candidates = [preferred] + [p for p in (8090, 8000, 5000, 3000, 8081, 8888) if p != preferred]
    last = None
    for p in candidates:
        try:
            srv = ThreadingHTTPServer(("0.0.0.0", p), Handler)
            if p != preferred:
                print(f"[!] Port {preferred} was refused by Windows (in use, or a reserved range).")
                print(f"    Started on {p} instead — use http://localhost:{p}/ , or free {preferred}")
                print(f"    (netstat -ano | findstr :{preferred}) / restart WinNAT: net stop winnat & net start winnat")
            return srv, p
        except OSError as e:
            last = e
            continue
    print("Could not bind any port. Last error:", last)
    print("Fix: run as Administrator, free the port, or pass one explicitly:  python server.py 8090")
    sys.exit(1)

# ---------------------------------------------------------------- PLC live poll (MySQL, every 10s)
# Each machine carries a `plcTable` (e.g. jet_mch_1_rtd) in one MySQL database. Every 10s we read that
# machine's single current-state row, decode it, reconcile it to the batch our plan says is running on
# the machine, and raise a maintenance alert if the temperature drifts past tolerance. The connection
# lives in secrets.local.json under "plc" (host/port/user/password/database) — never committed, never
# logged. If no config or no pymysql, the poller stays idle and the PLC_Inbox folder is the fallback.
PLC_STEPS = {1:"FILL NORMAL",2:"DRAIN NORMAL",3:"HEAT",4:"RUN",5:"CHEMICAL IN",6:"LOAD",7:"FILL RECO",
             8:"DRAIN RECO",9:"COOL",10:"RUNWASH",11:"COLOR PASS",12:"MAAL UNLOAD",13:"STOP",
             14:"DRAIN DISCHARGE",15:"SAMPLE",16:"RUNWASH-2",17:"AUXILIARY",18:"ACK"}
# HEAT (3) and COOL (9) are temperature RAMPS: the bath is deliberately moving toward its target, so
# act vs set diverges by design (e.g. cooling 120->75 over 5 min). Skip the variance alert on these
# steps so a normal ramp doesn't fire a false "temperature off" flag.
PLC_RAMP_STEPS = {3, 9}
PLC_FILL_STEPS = {1, 7}          # FILL NORMAL, FILL RECO — a rising litre reading during these steps is fresh water going in
PLC_EVENT_RETAIN_DAYS = 7        # machine-wise LOAD/UNLOAD event log (mobile "activity" page shows the last 24h of it)
PLC_COLS = ["id","Date","Time","Batch_Name","MC_Status","Auto_Manual","Step_Name","Step_Number",
            "Running_Pgm_No","Set_Temp","Act_Temp","Act_MV_Litre","Max_MV_LTR","LiqRatio_SetLitre_Sel",
            "Curr_Batch_Time","Remain_Time","Alarm_1","Alarm_2","Alarm_3"]
PLC_POLL_SECS = 10
_PLC_TBL_RE = re.compile(r"^[A-Za-z0-9_]+$")   # table names can't be parameterized — allow only safe identifiers

def _plc_num(v):
    try: return float(v)
    except Exception: return 0.0

def _plc_decode(row):
    """raw PLC row (dict keyed by PLC_COLS) -> decoded, unit-corrected values"""
    step = int(_plc_num(row.get("Step_Name")))
    running = str(row.get("MC_Status") or "0").strip() not in ("0", "") and step != 13   # 13 = STOP
    return {
        "program": str(row.get("Batch_Name") or "").strip(),
        "step": step, "stepName": PLC_STEPS.get(step, str(step)),
        "stepNo": int(_plc_num(row.get("Step_Number"))), "pgmNo": int(_plc_num(row.get("Running_Pgm_No"))),
        "auto": str(row.get("Auto_Manual") or "") == "1",
        "setTemp": round(_plc_num(row.get("Set_Temp")) / 10.0, 1),     # tenths of a degree -> C
        "actTemp": round(_plc_num(row.get("Act_Temp")) / 10.0, 1),
        "litre": round(_plc_num(row.get("Act_MV_Litre"))), "liqRatio": _plc_num(row.get("LiqRatio_SetLitre_Sel")),
        "alarms": [int(_plc_num(row.get("Alarm_1"))), int(_plc_num(row.get("Alarm_2"))), int(_plc_num(row.get("Alarm_3")))],
        "battime": int(_plc_num(row.get("Curr_Batch_Time"))), "remain": int(_plc_num(row.get("Remain_Time"))),
        "running": running,
        "at": (str(row.get("Date") or "") + " " + str(row.get("Time") or "")).strip(),
    }

def _plc_running_batch(db, machine_id):
    """the batch our plan associates with this machine: the running one, else the first planned (lowest seq)"""
    rows = [b for b in db.get("batches", []) if b.get("machine") == machine_id and not b.get("wash") and b.get("status") != "done"]
    rows.sort(key=lambda b: (0 if b.get("status") == "running" else 1, _plc_num(b.get("seq"))))
    return rows[0] if rows else None

def _plc_log_event(db, machine_id, kind):
    """append a machine-wise LOAD ('in') / MAAL UNLOAD ('out') event, decoupled from whatever batch the
    plan thinks is running (the mobile maintenance view cares that fabric physically moved, not which
    batch record it got attributed to — that attribution can be wrong when the plan is haywire).
    Pruned to the last PLC_EVENT_RETAIN_DAYS days."""
    ev = db.setdefault("plcEvents", [])
    ev.append({"machine": machine_id, "kind": kind, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    if len(ev) > 200:      # only pay for the prune walk once the list has actually grown
        cutoff = time.time() - PLC_EVENT_RETAIN_DAYS * 86400
        def _fresh(e):
            try: return time.mktime(time.strptime(e["at"], "%Y-%m-%d %H:%M:%S")) >= cutoff
            except Exception: return True
        db["plcEvents"] = [e for e in ev if _fresh(e)]

def _plc_alert(db, machine_id, kind, message):
    """append a de-duplicated PLC/maintenance alert (surfaced in the app; MNTC push comes later)"""
    al = db.setdefault("plcAlerts", []); now = time.time()
    for a in al:
        if a.get("machine") == machine_id and a.get("kind") == kind and not a.get("cleared") and (now - a.get("_ts", 0)) < 900:
            a["message"] = message; a["_ts"] = now; a["ts"] = time.strftime("%Y-%m-%d %H:%M:%S"); return
    al.append({"id": "AL-" + uuid.uuid4().hex[:8], "machine": machine_id, "kind": kind, "message": message,
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "_ts": now, "cleared": False})
    if len(al) > 500: del al[:len(al) - 500]

def _plc_apply(db, machine, dec, tol):
    """store the reading in the separate live-map (NOT on the machine record, so the 10s poll can never
    clobber admin edits like the PLC-table field), auto-catalogue the program, reconcile the batch,
    and raise temperature / alarm alerts."""
    mid = machine.get("id")
    now = dec["at"] or time.strftime("%Y-%m-%d %H:%M:%S")
    prev = (db.get("plcLive") or {}).get(mid) or {}   # last reading, read BEFORE we overwrite it below
    live = {k: dec[k] for k in ("stepName", "step", "setTemp", "actTemp", "litre", "liqRatio",
                                "program", "pgmNo", "running", "remain", "battime", "alarms", "at")}
    live["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    live["diff"] = round(dec["actTemp"] - dec["setTemp"], 1) if (dec["running"] and dec["setTemp"] > 0) else 0
    db.setdefault("plcLive", {})[mid] = live          # keyed by machine id; the machines table is untouched
    # rolling last-5-minutes trend per machine (poll is every 10s -> ~30 points)
    hist = db.setdefault("plcHistory", {}).setdefault(mid, [])
    hist.append({"t": live["updated"], "act": dec["actTemp"], "set": dec["setTemp"],
                 "diff": live["diff"], "step": dec["step"], "run": dec["running"]})
    if len(hist) > 30:
        del hist[:len(hist) - 30]
    if dec["program"]:                                   # universal programs catalogue (auto-filled)
        progs = db.setdefault("programs", [])
        if not any((p.get("name") or "").upper() == dec["program"].upper() for p in progs):
            progs.append({"id": "PGM-" + uuid.uuid4().hex[:6], "name": dec["program"], "firstSeen": time.strftime("%Y-%m-%d %H:%M")})
    # machine-wise LOAD/UNLOAD event log: edge-triggered (only the moment the step CHANGES into 6/12,
    # not every 10s poll while parked there), decoupled from batch reconciliation below — see _plc_log_event.
    prev_step = prev.get("step")
    if dec["step"] == 6 and prev_step != 6:
        _plc_log_event(db, mid, "in")
    elif dec["step"] == 12 and prev_step != 12:
        _plc_log_event(db, mid, "out")
    b = _plc_running_batch(db, mid)
    if b:
        # ACT IN time: the LOAD step (6) is the real load moment; if we join mid-run, the first running read stands in
        if not b.get("actInTime"):
            if dec["step"] == 6 or dec["running"]:
                b["actInTime"] = now
                if dec["program"]: b["plcProgram"] = dec["program"]
        # ACT OUT time: the first MAAL UNLOAD (12) or STOP (13) after loading
        if b.get("actInTime") and not b.get("actOutTime") and dec["step"] in (12, 13):
            b["actOutTime"] = now
        b["plcIn"] = b.get("actInTime"); b["plcOut"] = b.get("actOutTime")   # keep the old field names in sync
        b["plcStep"] = dec["stepName"]; b["plcActTemp"] = dec["actTemp"]; b["plcSetTemp"] = dec["setTemp"]
        b["plcLitre"] = dec["litre"]; b["plcUpdated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        # cumulative water SPENT on this batch: sum every rise in litre seen while in a FILL step. The
        # live "litre" field alone is just the current vat level — it falls again on drain, so it can't
        # tell you how much fresh water the batch has gone through in total; this can.
        prev_litre = prev.get("litre")
        if (dec["step"] in PLC_FILL_STEPS and prev.get("step") in PLC_FILL_STEPS
                and prev_litre is not None and dec["litre"] > prev_litre):
            delta = dec["litre"] - prev_litre
            cap = float(machine.get("capMax") or 0) or 99999
            if 0 < delta <= cap * 3:            # guard against a garbage/glitch PLC reading
                b["plcWaterTotal"] = round((b.get("plcWaterTotal") or 0) + delta, 1)
    if (dec["running"] and dec["step"] not in PLC_RAMP_STEPS and dec["setTemp"] > 0
            and abs(dec["actTemp"] - dec["setTemp"]) > tol):     # HEAT/COOL ramps are exempt (see PLC_RAMP_STEPS)
        _plc_alert(db, mid, "temp", "%s temperature %.1f°C vs set %.1f°C (tolerance ±%g)" % (mid, dec["actTemp"], dec["setTemp"], tol))
    if any(dec["alarms"]):
        _plc_alert(db, mid, "alarm", "%s PLC alarm: %s" % (mid, "/".join(str(a) for a in dec["alarms"] if a)))

_PLC = {"conn": None, "warned_no_tbl": False, "last": "", "paused": False}
def _plc_drop_conn():
    c = _PLC.get("conn")
    if c is not None:
        try: c.close()
        except Exception: pass
    _PLC["conn"] = None
def _plc_get_conn(pymysql, cfg):
    """ONE long-lived connection, reused every cycle (ping + reconnect if dropped). Re-opening a MySQL
    connection every 10s can wedge against a constrained PLC MySQL — the first connect works, later ones
    hang ('data only at startup'). A persistent connection avoids that entirely."""
    c = _PLC.get("conn")
    if c is not None:
        try:
            c.ping(reconnect=True); return c
        except Exception:
            _plc_drop_conn()
    _PLC["conn"] = pymysql.connect(host=cfg.get("host"), port=int(cfg.get("port", 3306)), user=cfg.get("user"),
                                   password=cfg.get("password"), database=cfg.get("database"),
                                   connect_timeout=5, read_timeout=5, write_timeout=5, autocommit=True,
                                   cursorclass=pymysql.cursors.DictCursor)
    return _PLC["conn"]

_PLC_ERR = {}   # machine id -> consecutive read-error count (a good read resets it)
def _plc_conn_error(pymysql, e):
    """True for connection-level failures (reconnect), False for table-level ones (skip that machine)."""
    err = getattr(pymysql, "err", None)
    try:
        if err and isinstance(e, err.InterfaceError): return True
        if err and isinstance(e, err.OperationalError):
            code = e.args[0] if e.args else 0
            return code in (0, 2002, 2003, 2006, 2013, 2055)   # connect / server-gone / lost-connection
    except Exception:
        pass
    return False
def _plc_bump_err(mid, tbl, why):
    """count a per-machine read failure; after 30 in a row, clear that machine's PLC table so one bad
    table can't keep breaking the poll (and the admin doesn't have to remove it by hand)."""
    n = _PLC_ERR.get(mid, 0) + 1
    _PLC_ERR[mid] = n
    if n >= 30:
        with LOCK:
            db = load_db()
            mm = next((x for x in db.get("machines", []) if x.get("id") == mid), None)
            if mm and (mm.get("plcTable") or "").strip():
                mm["plcTable"] = ""; save_db(db)
                print("[plc] %s: cleared its PLC table '%s' after 30 failed reads (%s)" % (mid, tbl, why), flush=True)
        _PLC_ERR[mid] = 0

def _plc_cycle(pymysql, cfg):
    with LOCK:
        db = load_db()
        enabled = (db.get("settings", {}) or {}).get("plcEnabled", True) is not False
        machines = [dict(id=m.get("id"), plcTable=(m.get("plcTable") or "").strip())
                    for m in db.get("machines", []) if (m.get("plcTable") or "").strip()] if enabled else []
        tol = float((db.get("settings", {}) or {}).get("tempToleranceC", cfg.get("tempToleranceC", 3)) or 3)
    if not enabled:                                   # paused from Settings -> drop the connection, do nothing
        if not _PLC.get("paused"):
            print("[plc] import PAUSED from Settings.", flush=True); _PLC["paused"] = True
        _plc_drop_conn(); return
    if _PLC.get("paused"):
        print("[plc] import RESUMED.", flush=True); _PLC["paused"] = False
    if not machines:
        if not _PLC["warned_no_tbl"]:
            print("[plc] connected OK, but NO machine has a 'PLC table' set — nothing to poll. "
                  "Set it in Admin -> Machines (e.g. jet_mch_1_rtd) for each jet.", flush=True)
            _PLC["warned_no_tbl"] = True
        return
    _PLC["warned_no_tbl"] = False
    conn = _plc_get_conn(pymysql, cfg)
    seen = []
    readings = []                                   # (mid, dec) collected here, applied in ONE batch below
    cur = conn.cursor()
    for m in machines:
        mid, tbl = m["id"], m["plcTable"]
        if not _PLC_TBL_RE.match(tbl):
            seen.append("%s:BAD-NAME" % mid); _plc_bump_err(mid, tbl, "unsafe table name"); continue
        q = "SELECT " + ",".join("`%s`" % c for c in PLC_COLS) + " FROM `%s` ORDER BY `id` DESC LIMIT 1" % tbl
        try:
            cur.execute(q); row = cur.fetchone()
        except Exception as e:
            if _plc_conn_error(pymysql, e):
                raise                                # connection dropped -> let the poller reconnect
            seen.append("%s:ERR(%s)" % (mid, str(e)[:45]))   # table-level (missing table etc.) -> skip this one
            _plc_bump_err(mid, tbl, str(e)[:80]); continue
        _PLC_ERR.pop(mid, None)                      # a good read clears the error count
        if not row:
            seen.append("%s:no-row" % mid); continue
        dec = _plc_decode(row)
        seen.append("%s:%s%s" % (mid, (dec["stepName"] if dec["running"] else "idle"),
                                 (" %.1f°" % dec["actTemp"] if dec["running"] else "")))
        readings.append((mid, dec))
    # Apply every machine's reading in ONE load+save, not one per machine — with N jets on PLC tables
    # this used to take the global LOCK (and reload/rewrite the whole db) N times per 10s cycle, right
    # alongside every user request. Table reads above already happened outside the lock, so this is
    # just the in-memory apply + a single write.
    if readings:
        with LOCK:
            db = load_db()
            by_id = {x.get("id"): x for x in db.get("machines", [])}
            applied = False
            for mid, dec in readings:
                mm = by_id.get(mid)
                if mm:
                    _plc_apply(db, mm, dec, tol); applied = True
            if applied:
                save_db(db)
    summary = "[plc] " + ", ".join(seen)            # only log when it changes (avoids flooding the console)
    if summary != _PLC["last"]:
        print(summary, flush=True); _PLC["last"] = summary

def _plc_poller():
    cfg = load_secrets().get("plc")
    if not cfg or not cfg.get("host"):
        print("[plc] no 'plc' block in secrets.local.json — live poll disabled (PLC_Inbox fallback only).", flush=True); return
    try:
        import pymysql, pymysql.cursors
    except Exception:
        print("[plc] pymysql not installed — run:  pip install pymysql --break-system-packages", flush=True); return
    print("[plc] live poll every %ds -> %s/%s (persistent connection)" % (PLC_POLL_SECS, cfg.get("host"), cfg.get("database")), flush=True)
    last_beat = 0.0
    while True:                                                 # this loop must never exit — it IS the poller
        try:
            wait = ((3 - time.localtime().tm_sec) % 10) or 10   # wake on the :03/:13/:23... second
            time.sleep(wait)
            t0 = time.time()
            wd = threading.Timer(8.0, _plc_drop_conn)           # hard ceiling: if a read wedges, close the
            wd.daemon = True; wd.start()                        # socket from another thread so the read errors out
            try:
                _plc_cycle(pymysql, load_secrets().get("plc") or cfg)
            finally:
                wd.cancel()
            if time.time() - last_beat > 30:                    # periodic proof-of-life in the Server log
                print("[plc] heartbeat — last cycle %.0f ms" % ((time.time() - t0) * 1000), flush=True)
                last_beat = time.time()
        except Exception as e:
            print("[plc] cycle error:", repr(e), flush=True)
            _plc_drop_conn()                                    # force a fresh connection next cycle
            time.sleep(3)

# ================================================================ program-scan (photo -> batches)
# A desktop user clicks the camera button on the Batch planner, gets a QR code, scans it with a
# phone (no login on the phone — the QR's token is a short-lived bearer credential for that one
# session), photographs the handwritten jet register (2 pages: a left page with Sr.No/Lot/Pcs/Mtr/
# Weight/Quality/Shade and a right page with Page No/In/Out/PH/Remarks), and can close the phone —
# the photos already appeared on the desktop that opened the QR. That desktop user (and only them —
# every scanSession* op checks session.createdBy) reads the photos through the Gemini API and
# reviews/edits the result before punching it into real batches. Config lives in secrets.local.json
# under "gemini": {apiKey, model, enabled}. Session bookkeeping is the "scanSessions" table (short-
# lived, stripped from /api/db — see _sanitized); working photos live under scan_sessions/<id>/ until
# applied, at which point copies move into program_scans/ (the permanent scanned-batch record).
PROGRAM_SCANS_DIR = os.path.join(HERE, "program_scans")
try: os.makedirs(PROGRAM_SCANS_DIR, exist_ok=True)
except OSError: pass

SCAN_SESSIONS_DIR = os.path.join(HERE, "scan_sessions")
try: os.makedirs(SCAN_SESSIONS_DIR, exist_ok=True)
except OSError: pass
SCAN_SESSION_TTL = 20 * 60   # a QR code / upload link stays live this long (seconds)

def _scan_session_cleanup_files(sid):
    """delete a scan session's working photo files (called once its images are archived into
    program_scans/, or when it's cancelled/expired and never applied)."""
    d = os.path.join(SCAN_SESSIONS_DIR, sid)
    try:
        for fn in os.listdir(d):
            try: os.remove(os.path.join(d, fn))
            except OSError: pass
        os.rmdir(d)
    except OSError:
        pass

def _scan_sessions_gc(db):
    """expire stale QR sessions (past their TTL) and drop old finished ones + their photo files, so
    the table and scan_sessions/ directory don't grow unbounded from abandoned/never-applied scans."""
    now = time.time()
    keep = []
    for row in db.get("scanSessions", []):
        if row.get("status") in ("open", "finished") and now > row.get("expiresAt", 0):
            row["status"] = "expired"
        if row.get("status") in ("applied", "cancelled", "expired") and now - row.get("expiresAt", now) > 3600:
            _scan_session_cleanup_files(row.get("id", ""))
            continue
        keep.append(row)
    if len(keep) != len(db.get("scanSessions", [])):
        db["scanSessions"] = keep

def _gemini_cfg():
    g = (load_secrets() or {}).get("gemini", {}) or {}
    return {"apiKey": str(g.get("apiKey", "") or ""),
            "model": str(g.get("model", "") or "gemini-2.5-flash"),
            "enabled": bool(g.get("enabled", True)) and bool(g.get("apiKey")),
            "timeout": int(g.get("timeoutSecs", 120) or 120)}

_SCAN_PROMPT = (
"You are transcribing a factory dyeing 'jet program' written by hand in a ruled register. You are given "
"TWO photos of ONE 2-page spread: the FIRST image is the LEFT page, the SECOND image is the RIGHT page. "
"They share the same rows. LEFT page columns: Sr.No, Lot No, Pcs, Mtr, Weight, Quality, Shade. RIGHT page "
"columns: Page No, In Time, Out Time, PH, Remarks. A machine header like 'JET-01' or 'JET-02' (often "
"underlined) starts that machine's program; every row under it until the next header belongs to that "
"machine. One Sr.No is ONE batch. A batch can span several lot lines (multiple Lot No/Pcs/Mtr/Weight rows "
"under a single Sr.No that share one Quality/Shade) — put every such lot line in that batch's 'lots' array. "
"Transcribe EXACTLY what is written; do not invent or correct values. Use null for any blank/unreadable "
"cell. Numbers must be digits only (strip units like 'kg'). Times as written (e.g. '12:24'). "
"Return ONLY JSON of this exact shape: "
'{"machines":[{"machine":"JET-01","batches":[{"srNo":1,"lots":[{"lotNo":"25226","pcs":6,"mtr":572,"weight":308}],'
'"quality":"CHIFFON","shade":"11","pageNo":"72","inTime":"12:24","outTime":"5:32","ph":"4.3","remarks":"P3(1200)"}]}]}'
)

def _gemini_extract(images_b64, cfg):
    """Send the (already base64) page photos to the Gemini API and return the parsed program dict.
    Raises RuntimeError with a friendly message on any failure. This is the ONLY place this server
    ever calls out to the public internet — everything else in the app is LAN-only."""
    if not cfg.get("enabled") or not cfg.get("apiKey"):
        raise RuntimeError("The scan reader isn't configured yet — an admin must set gemini.apiKey in secrets.local.json.")
    parts = [{"text": _SCAN_PROMPT}]
    for b in images_b64:
        s = str(b or "")
        if "," in s and s.strip().lower().startswith("data:"):   # strip a data:image/...;base64, prefix if present
            s = s.split(",", 1)[1]
        s = s.strip()
        if s:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": s}})
    payload = {"contents": [{"parts": parts}],
               "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    data = json.dumps(payload).encode("utf-8")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"
           % (cfg["model"], cfg["apiKey"]))
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode("utf-8", "replace")[:300]
        except Exception: pass
        hint = ""
        if e.code == 404:
            hint = (" — the model name in gemini.model (currently %r) isn't valid for this API key/region. "
                    "Model names change over time; set gemini.model in secrets.local.json to a current one "
                    "(see https://ai.google.dev/gemini-api/docs/models), or leave it blank to use the server's "
                    "built-in default." % (cfg.get("model"),))
        raise RuntimeError("Gemini API error %s: %s%s" % (e.code, body or e.reason, hint))
    except urllib.error.URLError as e:
        raise RuntimeError("Couldn't reach the Gemini API — check the server's internet connection (%s)"
                           % (getattr(e, "reason", e),))
    except Exception as e:
        raise RuntimeError("Gemini request failed: %s" % (e,))
    try:
        outer = json.loads(raw)
        content = outer["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError("The reader replied but the result couldn't be understood (unexpected Gemini response).")
    prog = _coerce_program(content)
    if prog is None:
        raise RuntimeError("The reader replied but the result couldn't be understood. Try clearer, straighter photos.")
    return prog

def _coerce_program(content):
    """Pull the JSON program object out of the model's reply (handles code fences / stray prose)."""
    if isinstance(content, dict):
        obj = content
    else:
        s = str(content or "").strip()
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z]*\n?", "", s); s = re.sub(r"\n?```$", "", s).strip()
        try:
            obj = json.loads(s)
        except ValueError:
            m = re.search(r"\{.*\}", s, re.S)          # last resort: first {...} block
            if not m: return None
            try: obj = json.loads(m.group(0))
            except ValueError: return None
    if isinstance(obj, list):                          # model returned the machines array directly
        obj = {"machines": obj}
    if not isinstance(obj, dict) or "machines" not in obj:
        return None
    return obj

def _snum(v):
    """scan cell -> number: pull the first integer/decimal out (strips units like 'kg', '#')"""
    if v is None: return 0
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))
    return (float(m.group(0)) if ("." in m.group(0)) else int(m.group(0))) if m else 0

def _create_scan_batches(db, program, user):
    """Turn a reviewed program dict into real planned batches. Returns the list of created batch ids."""
    machines = {str(m.get("id")): m for m in db.get("machines", [])}
    created = []
    seqbase = {}
    for mc in (program.get("machines") or []):
        mid = str(mc.get("machine", "") or "").strip()
        if mid not in machines:                        # tolerate 'JET1' vs 'JET-01' style
            hit = next((k for k in machines if re.sub(r"\W", "", k).upper() == re.sub(r"\W", "", mid).upper()), None)
            if hit: mid = hit
        if mid not in machines:
            continue                                   # unknown machine — skip (flagged in preview already)
        if mid not in seqbase:
            seqbase[mid] = max([int(b.get("seq") or 0) for b in db.get("batches", []) if b.get("machine") == mid] or [0])
        for b in (mc.get("batches") or []):
            lots = []
            for l in (b.get("lots") or []):
                lid = str(l.get("lotNo") or l.get("lotId") or "").strip()
                if not lid: continue
                lots.append({"lotId": lid, "pcs": _snum(l.get("pcs")), "mtr": _snum(l.get("mtr")),
                             "weight": _snum(l.get("weight")), "takaNos": [], "takas": []})
            if not lots: continue
            seqbase[mid] += 1
            row = {"machine": mid, "mcPin": mid, "seq": seqbase[mid],
                   "lots": lots, "lotIds": [l["lotId"] for l in lots],
                   "quality": str(b.get("quality") or "").strip(), "shadeNo": str(b.get("shade") or "").strip(),
                   "pgNo": str(b.get("pageNo") or "").strip(), "ph": str(b.get("ph") or "").strip(),
                   "notes": str(b.get("remarks") or "").strip(),
                   "pcs": sum(l["pcs"] for l in lots), "mtr": int(sum(l["mtr"] for l in lots)),
                   "weight": round(sum(l["weight"] for l in lots), 1), "status": "planned", "fromScan": True}
            it = str(b.get("inTime") or "").strip(); ot = str(b.get("outTime") or "").strip()
            day = time.strftime("%Y-%m-%d")
            if it: row["startedAt"] = day + " " + it; row["startedBy"] = user; row["status"] = "running"
            if it and ot: row["completedAt"] = day + " " + ot; row["completedBy"] = user; row["status"] = "done"
            row["id"] = _batch_id(db, row)
            db.setdefault("batches", []).append(row)
            created.append(row["id"])
    return created

if __name__ == "__main__":
    _install_termlog()   # mirror console output into the Settings log panel
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    load_db()  # ensure the database exists
    threading.Thread(target=_watch_and_reload, daemon=True).start()
    threading.Thread(target=_inbox_watcher, daemon=True).start()
    threading.Thread(target=_dispatch_watcher, daemon=True).start()
    threading.Thread(target=_challan_watcher, daemon=True).start()
    threading.Thread(target=_challan_email_scheduler, daemon=True).start()
    threading.Thread(target=_plc_poller, daemon=True).start()
    srv, port = _bind_server(port)
    print(f"REL-UNITY server running:")
    print(f"   local:   http://localhost:{port}/")
    print(f"   LAN:     http://<this-machine-ip>:{port}/   (share with floor terminals)")
    print(f"   admin:   http://localhost:{port}/admin.html")
    print(f"Data file: {DB_PATH}")
    print(f"Inbox:     drop CSVs in {INBOX_DIR} — auto-imported as lots every {INBOX_POLL_SECS}s")
    print(f"Dispatch:  drop \"Dispatch Report ...\" CSVs in {DISPATCH_DIR} — taka-wise, removed from active stock and filed to Lot history every {DISPATCH_POLL_SECS}s")
    print("Auto-reload is ON (server.py edits restart it) · pages are never cached")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
