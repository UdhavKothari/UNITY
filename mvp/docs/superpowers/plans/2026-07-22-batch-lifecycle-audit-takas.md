# Batch Lifecycle, Audit Trail & Taka Numbers — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. This project has **no unit-test framework** — verification is done with `python3 server.py <port>` + curl for the API and jsdom for the UI, exactly as prior plans in this folder. Each task ends with an explicit verification command + expected output.

**Goal:** Make the Gantt advance in real time by letting operators start/complete batches (timestamped + attributed), record a full audit trail (console history) and per-batch history, give lots stable taka numbers with a Taka master table, and raise the taka limit 30 → 50.

**Architecture:** All state stays in the single `data.json` store served by the zero-dependency Python server. A new `activityLog` table is the one source of truth for both "console history" (all events) and "batch history" (the same log filtered to one batch). Batch lifecycle transitions go through a dedicated server op (`batchStatus`) so the timestamp + user are stamped server-side and cannot be spoofed. The scheduler drops `done` batches and pins `running` ones so the plan naturally moves forward; a live now-line anchored to the wall clock sweeps the board.

**Tech Stack:** Python stdlib `http.server`; vanilla JS front end (`app.js` engine shared by `index.html` Operations + `admin.html`); Material Symbols; no build step.

## Global Constraints

- Zero external dependencies, server-side (stdlib only). No new npm/pip packages.
- System-generated IDs (`lots`, `batches`, `orders`) are never accepted from the client; `activityLog` IDs are server-generated too.
- Passwords/hashes never logged. `_sanitized()` keeps stripping `passHash`/`salt`.
- Timestamps are stamped **server-side** (`time.strftime("%Y-%m-%d %H:%M:%S")`) for lifecycle + audit events — never trust a client clock for the record of who/when.
- RBAC: every new page key added to `ALL_PAGES` in `server.py`; the Administrator self-heal loop auto-grants it. Mutations stay permission-gated (403).
- Taka limit is now **50** everywhere it was 30.
- Non-destructive to existing data: `takas` (lengths array) is untouched; `takaNos` is a new parallel array.

---

### Task 1: Server — audit log helper + log every mutation

**Files:** Modify `mvp/server.py`

**Produces:** `_log(db, user, action, table, rid, summary)`; an `activityLog` list in the DB; `activity` page key.

- [ ] Add `"activity"` to `ALL_PAGES`.
- [ ] Add helper near `_next_seq_id`:

```python
LOG_CAP = 5000
def _log(db, user, action, table, rid, summary=""):
    lg = db.setdefault("activityLog", [])
    lg.append({"id": "LG-" + uuid.uuid4().hex[:10],
               "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "user": user or "system", "action": action,
               "table": table or "", "recordId": rid or "", "summary": summary or ""})
    if len(lg) > LOG_CAP:
        del lg[:len(lg) - LOG_CAP]
```

- [ ] In `seed()` ensure `data.setdefault("activityLog", [])`.
- [ ] In `_migrate(db)` (or load path) ensure `db.setdefault("activityLog", [])`.
- [ ] Call `_log` on: `login` (action `login`), `logout`, `changePassword`, `reset`, `upsert` (action `create` when `not existing` else `update`), `delete`. Use the acting `u["username"]` (login uses the just-authenticated `username`). Summary = human string, e.g. `f"{table} {row.get('id','')}"`.
- [ ] `activityLog` must never be directly writable through `upsert`/`delete`: reject `table == "activityLog"` with 403 (append-only, server-owned).

**Verify:**
```
python3 server.py 8231 &   # login via curl, do an upsert, GET /api/db
```
Expected: `activityLog` contains a `login` entry then a `create`/`update` entry with the right user + timestamp; POST upsert to `activityLog` returns 403.

---

### Task 2: Server — batch lifecycle op (`batchStatus`)

**Files:** Modify `mvp/server.py`

**Consumes:** `_log` from Task 1.
**Produces:** `op:"batchStatus"` with body `{id, to}` where `to ∈ {"running","done","planned"}`.

- [ ] After the `reset` block (still inside the authenticated section), add:

```python
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
    else:  # planned = reopen / undo
        b["status"] = "planned"
        for k in ("completedAt", "completedBy"):
            b.pop(k, None)
    _log(db, u["username"], to, "batches", b["id"],
         "batch " + b["id"] + " -> " + to)
    save_db(db)
    return self._send(200, {"ok": True, "row": b})
```

**Verify:** curl `batchStatus` running then done on a seeded batch → row shows `startedAt/startedBy` then `completedAt/completedBy`; two matching `activityLog` entries.

---

### Task 3: Server — taka numbers on lots

**Files:** Modify `mvp/server.py`

- [ ] In the `upsert` branch, for `table == "lots"`, after the row is in hand, normalise taka numbers:

```python
if table == "lots":
    tk = row.get("takas") or []
    row["takaNos"] = list(range(1, len(tk) + 1))
```

(positional, stable, 1..N — regenerated on every save so it always matches the taka count.)

**Verify:** upsert a lot with 3 takas → stored row has `takaNos:[1,2,3]`.

---

### Task 4: Client engine — status-aware scheduler + wall-clock anchor

**Files:** Modify `mvp/static/app.js`

**Consumes:** batch `status`, `startedAt` from server.
**Produces:** `batchesForSchedule()` excludes `done`; `computeSchedule()` unchanged signature; new `nowMinutesInto(S)` + `planClockLabel(min)` helpers used by renderers.

- [ ] In `batchesForSchedule()` add `status:b.status||"planned", startedAt:b.startedAt||"", completedAt:b.completedAt||"", startedBy:b.startedBy||"", completedBy:b.completedBy||""` to the pushed object, and **skip done batches**: `if(b.status==="done") return;` at the top of the loop (a finished load has left the machine, so it frees and the rest pull forward).
- [ ] Add clock helpers:

```js
function planClockLabel(min){                 // min from plan t0(=now) -> "HH:MM" wall clock
  const d=new Date(Date.now()+min*60000);
  return d.getHours().toString().padStart(2,"0")+":"+d.getMinutes().toString().padStart(2,"0");
}
```

- [ ] In `renderGantt`, change the axis tick labels from `t+Nh` to real clock: use `planClockLabel(h*60)`.
- [ ] In `renderGantt`, after building tracks, append a now-line element at `left:0` (t0 == now) with class `nowline`, plus render `running` batch blocks with a `.running` class and `done`-excluded (already handled). Mark a block `.running` when `bt.status==="running"`.

**Verify:** jsdom — with one batch set `status:"done"`, `computeSchedule().batchCount` drops by 1; axis first tick renders as an `HH:MM` string, not `t+0h`.

---

### Task 5: Client — Start/Complete controls + status pills (Operations)

**Files:** Modify `mvp/static/index.html`

**Consumes:** `API` client; new `API.batchStatus(id,to)`.

- [ ] Add to the `API` object in `app.js`: `batchStatus(id,to){ return this._post({op:"batchStatus",id,to}); }`.
- [ ] In `renderBatchList()`, for each batch render a status pill (planned/running/done) + action buttons:
  - planned → **Start** button (`API.batchStatus(id,'running')`)
  - running → **Complete** button (`'done'`) + elapsed since `startedAt`
  - done → completed time + by-whom, plus a small **Reopen** (`'planned'`) for correction.
  - Hide the buttons when `!can('op_batch')`.
  - When `cfg().completionMode==='auto'`, show a muted "sensor-driven" note next to the buttons but still allow the manual action (override).
- [ ] After any lifecycle action: `await API.db(); renderBatchList(); draw();` so the Gantt advances immediately.

**Verify:** jsdom click Start → row shows Running + Complete button; click Complete → row shows Done + name; Gantt block count drops.

---

### Task 6: Client — Activity log page + Batch history (Admin)

**Files:** Modify `mvp/static/admin.html`

- [ ] Add nav entry + icon for `activity` ("Activity log") under a new **History** group.
- [ ] Render `activity` as a read-only, reverse-chronological table: Time, User, Action, Table, Record, Summary. Full-column search + sort reuse the existing `render()` path (add a `SCHEMAS.activity` with `readonly:true`, `cols` only, no form).
- [ ] Add a **Taka master** nav entry (`takaMaster`, gated under `lots` perm) rendering LOT No + Taka 1..50 columns (value = length; blank if absent). Wide table, horizontally scrollable.
- [ ] Batch history: in the batches table row actions (or the batch modal), add a "History" link that filters `DB.activityLog` to `recordId===batchId` and shows it in a modal.

**Verify:** jsdom — Activity log table lists the seeded events newest-first; Taka master shows a lot's lengths under numbered columns; a batch's History modal lists only that batch's events.

---

### Task 7: Admin settings toggle + raise taka limit to 50

**Files:** Modify `mvp/static/admin.html`, `mvp/seed_data.json`, `mvp/server.py` (seed default)

- [ ] `renderSettings`: add a **Batch completion mode** control — radio/select `manual` | `auto` (auto labelled "Automatic (IoT sensors — coming soon)"). Persist `completionMode` in the settings upsert payload.
- [ ] Seed default `completionMode:"manual"` in `seed_data.json` settings and wherever settings default is built.
- [ ] Replace every `30` taka limit with `50`: `admin.html:470` (`>=30` guard + message), `:480` (`Math.min(+m[1],30)`), `:483` (`>30` trim + message), and the two `sec` labels at `:211`/`:212` ("up to 30" → "up to 50"). Add a `MAX_TAKAS=50` const and use it.

**Verify:** Settings saves `completionMode`; pasting `60x100` into the taka bulk box yields 50 takas (not 30) with the "Trimmed to the first 50" toast.

---

### Task 8: Full end-to-end verification

**Files:** none (test only)

- [ ] Start server on a scratch copy; login; create machine+quality+shade+lot+batch; Start then Complete the batch via `batchStatus`; confirm: batch has started/completed stamps + user, `activityLog` has login + create(s) + running + done, Gantt (jsdom) drops the done batch and axis shows clock times, Taka master shows numbered takas, settings round-trips `completionMode`, taka limit is 50.
- [ ] `python3 -c "import ast; ast.parse(open('server.py').read())"` and `node --check static/app.js`.
- [ ] Commit.
