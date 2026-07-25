#!/usr/bin/env python3
"""
REL Dyeing ERP - MVP server (zero external dependencies).

Run:  python server.py            (defaults to port 8080, all interfaces)
      python server.py 9000       (custom port)

Then open on the host:      http://localhost:8080/
From another LAN machine:   http://<this-machine-ip>:8080/

Data persists to data.json in this folder. Delete that file (or POST /api reset)
to restore the seeded sample data.
"""
import json, os, sys, threading, uuid, hashlib, secrets, hmac, time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
DB_PATH = os.path.join(HERE, "data.json")
LOCK = threading.Lock()

# ---------------------------------------------------------------- auth helpers
SESSIONS = {}                 # token -> {"username":.., "expires":ts}   (in-memory)
SESSION_TTL = 12 * 3600       # 12 hours
# every viewable "page" a role can be granted (must match static/app.js PAGE_KEYS)
ALL_PAGES = ["op_floor","op_schedule","op_order","op_batch","op_storage","op_massplan",
             "dashboard","machines","qualities","shadeRecipes","qualityRecipes",
             "batches","lots","weavers","takaMaster",
             "customers","orders","storageAreas","shelves","storageSlots","suppliers","operators","qcMetrics",
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

def _sanitized(db):
    """copy of db with password material stripped from users (never sent to client)"""
    d = dict(db)
    d["users"] = [{k: v for k, v in u.items() if k not in ("passHash", "salt")}
                  for u in db.get("users", [])]
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
    db.setdefault("activityLog", [])
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
    return data

def load_db():
    if not os.path.exists(DB_PATH):
        save_db(seed())
    with open(DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
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
            missing = [p for p in ALL_PAGES if p not in r.get("perms", [])]
            if missing:
                r["perms"] = list(ALL_PAGES)
                changed = True
    if _migrate(db):
        changed = True
    if changed:
        save_db(db)
    return db

def save_db(db):
    tmp = DB_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DB_PATH)

# ---------------------------------------------------------------- HTTP
CT = {".html":"text/html",".js":"application/javascript",".css":"text/css",
      ".json":"application/json",".svg":"image/svg+xml",".ico":"image/x-icon"}

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json", cookies=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # never cache: edits to html/css/js appear on a normal refresh, no hard-reload needed
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        for c in (cookies or []):
            self.send_header("Set-Cookie", c)
        self.end_headers()
        self.wfile.write(body)

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
        u = next((x for x in db.get("users", [])
                  if x.get("username") == s["username"] and x.get("active", True)), None)
        if not u:
            return None, None
        return u, _perms_for(db, u)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/me":
            with LOCK:
                db = load_db(); u, perms = self._auth(db)
            if not u:
                return self._send(401, {"error": "not authenticated"})
            return self._send(200, {"user": {"username": u["username"], "role": u["role"], "perms": perms}})
        if path == "/api/db":
            with LOCK:
                db = load_db(); u, perms = self._auth(db)
            if not u:
                return self._send(401, {"error": "login required"})
            return self._send(200, _sanitized(db))
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
        if self.path.split("?")[0] != "/api":
            return self._send(404, {"error":"unknown endpoint"})
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error":"bad json"})
        op = req.get("op")
        with LOCK:
            db = load_db()

            # ---- unauthenticated: login only ----
            if op == "login":
                username = (req.get("username") or "").strip()
                pw = req.get("password") or ""
                u = next((x for x in db.get("users", [])
                          if x.get("username") == username and x.get("active", True)), None)
                if (not u or not u.get("passHash")
                        or not hmac.compare_digest(u["passHash"], _hash_pw(pw, u["salt"]))):
                    return self._send(401, {"error": "Invalid username or password"})
                token = secrets.token_hex(24)
                SESSIONS[token] = {"username": username, "expires": time.time() + SESSION_TTL}
                perms = _perms_for(db, u)
                _log(db, username, "login", "users", u.get("id", ""), "signed in"); save_db(db)
                return self._send(200, {"ok": True, "user": {"username": username, "role": u["role"], "perms": perms}},
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

            if op == "changePassword":
                new = req.get("newPassword") or ""
                if len(new) < 6:
                    return self._send(400, {"error": "New password must be at least 6 characters"})
                if not hmac.compare_digest(u["passHash"], _hash_pw(req.get("oldPassword") or "", u["salt"])):
                    return self._send(403, {"error": "Current password is incorrect"})
                u["salt"] = _new_salt(); u["passHash"] = _hash_pw(new, u["salt"])
                _log(db, u["username"], "changePassword", "users", u.get("id", ""), "changed password"); save_db(db)
                return self._send(200, {"ok": True})

            if op == "reset":
                if "settings" not in perms:
                    return self._send(403, {"error": "forbidden"})
                who = u["username"]
                db = seed(); _log(db, who, "reset", "", "", "reset to seed data"); save_db(db)
                return self._send(200, {"ok": True})

            if op == "batchStatus":
                if not any(p in perms for p in ("batches", "op_batch")):
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

            table = req.get("table")
            if table == "activityLog":
                return self._send(403, {"error": "the activity log is append-only"})
            # a table may be reachable from more than one page (e.g. batches from the
            # Operations "Batch maker" or the Admin one) — any of them grants write access
            if table == "__settings__":
                allowed = ["settings"]
            else:
                allowed = {"batches": ["batches", "op_batch"], "storageSlots": ["storageSlots", "op_storage"]}.get(table, [table])
            if not any(p in perms for p in allowed):
                return self._send(403, {"error": f"forbidden: no permission for {table}"})

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
                    if bool(row.get("urgent")) != was and "urgent_flag" not in perms:
                        return self._send(403, {"error": "Only a Master can flag a batch urgent"})
                    if bool(row.get("urgent")) and not was:
                        row["urgentBy"] = u["username"]; row["urgentAt"] = time.strftime("%Y-%m-%d %H:%M")
                if table == "lots":
                    tk = row.get("takas") or []
                    row["takaNos"] = list(range(1, len(tk) + 1))   # stable positional taka numbers
                SYSTEM_IDS = ("lots", "batches", "orders")
                if table in SYSTEM_IDS and not existing:
                    # system-numbered tables: the id is ALWAYS generated here, never taken
                    # from the client, and an existing record can never have its id changed
                    row["id"] = _next_seq_id(db, table)
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

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    load_db()  # ensure data.json exists
    threading.Thread(target=_watch_and_reload, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"REL Dyeing ERP MVP running:")
    print(f"   local:   http://localhost:{port}/")
    print(f"   LAN:     http://<this-machine-ip>:{port}/   (share with floor terminals)")
    print(f"   admin:   http://localhost:{port}/admin.html")
    print(f"Data file: {DB_PATH}")
    print("Auto-reload is ON (server.py edits restart it) · pages are never cached")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
