#!/usr/bin/env python3
"""
REL Dyeing ERP - MVP server (zero external dependencies).

Run:  python server.py            (defaults to port 8080, all interfaces)
      python server.py 9000       (custom port)

Then open on the host:      http://localhost:8080/
From another LAN machine:   http://<this-machine-ip>:8080/

Data persists to data.sqlite in this folder (SQLite). On first run it imports a
legacy data.json if one is present, then serves purely from SQLite. POST /api
reset restores the seeded sample data. Back up with backup_db.py (see docs/DEPLOYMENT.md).
"""
import json, os, sys, threading, uuid, hashlib, secrets, hmac, time, sqlite3, re, csv as _csv
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
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
# every viewable "page" a role can be granted (must match static/app.js PAGE_KEYS)
ALL_PAGES = ["op_floor","op_schedule","op_order","op_batch","op_storage","op_massplan",
             "dashboard","machines","qualities","shadeRecipes","qualityRecipes","recipes",
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
    for o in db.get("operators", []):                  # every operator gets mobile-app credentials
        if not o.get("username") or not o.get("pin"):
            _ensure_operator_creds(db, o); changed = True
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
            missing = [p for p in ALL_PAGES if p not in r.get("perms", [])]
            if missing:
                r["perms"] = list(ALL_PAGES)
                changed = True
    if _migrate(db):
        changed = True
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
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return c

def _doc_tables(c):
    return [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name<>'_kv' AND name NOT LIKE 'sqlite_%'")]

def _read_all(c):
    db = {}
    for t in _doc_tables(c):
        if t in HEAVY_TABLES:                  # never load big reference tables into memory
            continue
        db[t] = [json.loads(d) for (_id, d) in c.execute('SELECT id,data FROM "%s"' % t)]
    for (k, v) in c.execute("SELECT k,v FROM _kv"):
        db[k] = json.loads(v)
    return db

def _write_all(c, db):
    c.execute("CREATE TABLE IF NOT EXISTS _kv (k TEXT PRIMARY KEY, v TEXT)")
    lists = {k for k, v in db.items() if isinstance(v, list)}
    for t in set(_doc_tables(c)) - lists - HEAVY_TABLES:   # heavy tables are managed by their own ops
        c.execute('DELETE FROM "%s"' % t)
    for k, v in db.items():
        if isinstance(v, list):
            c.execute('CREATE TABLE IF NOT EXISTS "%s" (id TEXT PRIMARY KEY, data TEXT)' % k)
            c.execute('DELETE FROM "%s"' % k)
            c.executemany('INSERT OR REPLACE INTO "%s" (id,data) VALUES (?,?)' % k,
                          [(str(r.get("id") or ("_row%d" % i)), json.dumps(r, ensure_ascii=False))
                           for i, r in enumerate(v)])
        elif isinstance(v, dict):
            c.execute("INSERT OR REPLACE INTO _kv (k,v) VALUES (?,?)", (k, json.dumps(v, ensure_ascii=False)))
    c.commit()

def save_db(db):
    c = _connect()
    try:
        _write_all(c, db)
    finally:
        c.close()

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
        return [{"quality": q, "shade": s} for (q, s) in c.execute(
            "SELECT DISTINCT quality, shade FROM recipes WHERE quality<>'' AND shade<>'' ORDER BY quality, shade")]
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
      ".woff2":"font/woff2",".woff":"font/woff"}

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

            # ---- dye recipes (big on-demand table; imported from Excel) ----
            if op == "recipesBulkAdd":
                if "recipes" not in perms:
                    return self._send(403, {"error": "forbidden"})
                n = recipes_bulk_add(req.get("rows") or [])
                _log(db, u["username"], "recipesImport", "recipes", "", "added %d recipes" % n); save_db(db)
                return self._send(200, {"ok": True, "added": n, "total": recipes_count()})

            if op == "recipesClear":
                if "recipes" not in perms:
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

            # ---- fast bulk insert into a normal table (client has already de-duped) ----
            if op == "bulkUpsert":
                table = req.get("table")
                if table in ("activityLog",) or table in HEAVY_TABLES:
                    return self._send(403, {"error": "not allowed for this table"})
                allowed = {"batches": ["batches", "op_batch"], "storageSlots": ["storageSlots", "op_storage"]}.get(table, [table])
                if not any(p in perms for p in allowed):
                    return self._send(403, {"error": "forbidden: no permission for %s" % table})
                if table not in db or not isinstance(db.get(table), list):
                    return self._send(400, {"error": "unknown table %s" % table})
                SYSTEM_IDS = ("lots", "batches", "orders")
                added = 0
                for row in (req.get("rows") or []):
                    if not row.get("id"):
                        row["id"] = _next_seq_id(db, table) if table in SYSTEM_IDS else (table[:2].upper() + "-" + uuid.uuid4().hex[:6])
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
                    row["id"] = _next_seq_id(db, table)            # batches / orders are still system-numbered
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

# ---------------------------------------------------------------- inbox: auto-import lots from CSV
# Your .bat drops a CSV into mvp/inbox/ ; this watcher reads it, turns each row into a lot
# (keyed by the source lot number, which becomes the lot id), then moves the file to
# inbox/done or inbox/error with a .log. Columns are matched by header NAME (order-independent).
# If your headers differ, just adjust LOT_COL_ALIASES below.
INBOX_DIR  = os.path.join(HERE, "inbox")
INBOX_DONE = os.path.join(INBOX_DIR, "done")
INBOX_ERR  = os.path.join(INBOX_DIR, "error")
INBOX_POLL_SECS = 45

# Header names matched (order-independent). Each CSV row is ONE taka; rows are grouped by LOT.
# TAKA length uses TakaPendingMts (falls back to Despatch, then Received). Adjust here if needed.
LOT_COL_ALIASES = {
    "lotNo":   ["LOT", "LOT NO", "LOTNO", "LOT NUMBER"],
    "quality": ["GREYQUAL", "GREY QUALITY", "GREYQUALITY", "GREY QUAL", "QUALITY", "ITEM NAME"],
    "cardNo":  ["CARDNO", "CARD NO", "CARD"],
    "inDate":  ["LOTCREATETIME", "LOT CREATE TIME", "INW DATE", "IN DATE", "DATE"],
    "takaSr":  ["TAKASRNO", "TAKA SR NO", "TAKA SRNO", "SR NO", "SRNO", "TAKA NO"],
    "takaMts": ["TAKAPENDINGMTS", "TAKA PENDING MTS", "TAKADESPATCHMTS", "TAKA DESPATCH MTS",
                "TAKARECEIVEDMTS", "PENDING MTS", "METERS", "MTS", "MTR"],
    "takaWt":  ["TAKA_WT", "TAKAWT", "TAKA WT", "WEIGHT", "WT"],
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
        if not lotno or set(lotno) <= set("- ") or "(" in lotno:   # skip dashes + SQL footers like "(445 rows affected)"
            continue
        lot = lots.get(lotno)
        if lot is None:
            lot = {"id": lotno, "status": "in stock", "takas": [], "takaNos": [], "_wts": []}
            q = str(get("quality")).strip()
            if q: lot["quality"] = q
            card = str(get("cardNo")).strip()
            if card: lot["challanNo"] = card; lot["cardNo"] = card
            dt = str(get("inDate")).strip()
            if dt:
                lot["inDate"] = dt[:10]
                if len(dt) >= 16: lot["inTime"] = dt[11:16]
            lots[lotno] = lot
        mts = _num(get("takaMts"))
        if mts <= 0:
            continue                                  # a fully-processed / zero-length taka isn't stock
        try: sr = int(float(get("takaSr")))
        except (ValueError, TypeError): sr = len(lot["takas"]) + 1
        lot["takas"].append(mts); lot["takaNos"].append(sr); lot["_wts"].append(_num(get("takaWt")))
    out = []
    for lot in lots.values():
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
        files = sorted(f for f in os.listdir(d) if f.lower().endswith((".csv", ".txt")))
    except OSError:
        return
    for old in files[:-keep]:                          # keep the newest `keep`, delete the rest (+ their .log)
        for path in (os.path.join(d, old), os.path.join(d, old + ".log")):
            try: os.remove(path)
            except OSError: pass

def _apply_lots(lots):
    with LOCK:
        db = load_db()
        by_id = {l.get("id"): l for l in db.get("lots", [])}
        added = updated = 0
        for lot in lots:
            if lot["id"] in by_id:
                by_id[lot["id"]].update(lot); updated += 1
            else:
                db.setdefault("lots", []).append(lot); by_id[lot["id"]] = lot; added += 1
        _log(db, "inbox", "lotImport", "lots", "", "imported %d lots (%d new, %d updated)" % (len(lots), added, updated))
        save_db(db)
    return added, updated

def _process_inbox(path):
    if path.lower().endswith((".xlsx", ".xls")):
        raise ValueError("Excel received — please export CSV, not Excel (the server reads CSV).")
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(_csv.reader(f))
    lots = _csv_to_lots(rows)
    if not lots:
        raise ValueError("no lots found in file")
    added, updated = _apply_lots(lots)
    return "%d lots (%d new, %d updated) from %d rows" % (len(lots), added, updated, len(rows))

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

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    load_db()  # ensure the database exists
    threading.Thread(target=_watch_and_reload, daemon=True).start()
    threading.Thread(target=_inbox_watcher, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"REL Dyeing ERP MVP running:")
    print(f"   local:   http://localhost:{port}/")
    print(f"   LAN:     http://<this-machine-ip>:{port}/   (share with floor terminals)")
    print(f"   admin:   http://localhost:{port}/admin.html")
    print(f"Data file: {DB_PATH}")
    print(f"Inbox:     drop CSVs in {INBOX_DIR} — auto-imported as lots every {INBOX_POLL_SECS}s")
    print("Auto-reload is ON (server.py edits restart it) · pages are never cached")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
