# REL Dyeing ERP — Project Handoff / Memory

**Purpose:** Attach or paste this file at the start of a new chat when you want to add features to this software. It gives full context so we can pick up without re-explaining.

---

## What it is
An ERP MVP (v1: **Planning & Scheduling**) for a textile **dyeing mill**. It turns fabric orders into machine schedules (pre-treatment → dyeing → finishing) and manages all master data. Runs on the factory **LAN**.

## Where it lives & how to run
- All files: `C:\Users\ravi\Desktop\Factory\REL_DYEING\mvp\`
- Run: open a terminal in `mvp` → `python server.py` (custom port: `python server.py 9000`)
- Open **http://localhost:8080/** (LAN: `http://<host-ip>:8080/`)
- **It's a live app served by the Python server — it does NOT work if you open the HTML as a file.**
- Data persists to `mvp/data.json` (a JSON file — this is the only copy; back it up).

## Stack & files
- **`server.py`** — zero-dependency Python stdlib server (`ThreadingHTTPServer`), JSON file store, auth. API: `GET /api/db` (auth-gated, strips password hashes), `GET /api/me`, `POST /api` with `op` ∈ {`login`,`logout`,`changePassword`,`upsert`,`delete`,`reset`}.
- **`static/index.html`** — Operations page: shop-floor board, schedule Gantt, new-order form.
- **`static/admin.html`** — Admin console: grouped sidebar nav, dashboard, schema-driven CRUD for every master, live plan view.
- **`static/app.js`** — shared engine: API client, quality-aware shade lookup, the scheduler (`computeSchedule`), Gantt/floor renderers, and auth (`CURRENT_USER`, `can(page)`, `boot()`, `showLogin`, `renderUserBox`, change-password), toast/esc helpers.
- **`static/style.css`** — dark design system.
- **`mvp/README.md`** — run/login/roles docs. **`REL_DYEING/dyeing_erp_design_brief.md`** — design brief.

## Auth & roles (built and tested)
- Login gates the **whole app**. Seed admin username **ADMIN** (default password is in `mvp/README.md`; change it after first login via top-right → Password).
- Passwords hashed with **PBKDF2-HMAC-SHA256** (200k iterations, per-user salt); never stored or sent in plaintext. Sessions are in-memory with an **HttpOnly cookie** (12h).
- **Roles master = per-page permissions (Discord-style):** each "page" is grantable per role. Page keys (server `ALL_PAGES`, mirrored in admin `PAGES`): `op_floor, op_schedule, op_order, dashboard, machines, qualities, shadeRecipes, qualityRecipes, customers, orders, storageAreas, suppliers, operators, qcMetrics, users, roles, plan, settings`.
- The **server enforces permissions on every mutation (403)** — UI hiding is defense-in-depth only.
- Admin creates **users** (username + password + role + active) and **roles** (name + permission checkboxes).
- ⚠ **No HTTPS yet** — add TLS before any company-domain / internet hosting.

## Data model (master tables)
- **machines** — type (drum/jigger/jet/stentor/hydro/rope), capMin/capMax (kg), wash (min), plc, lastMaint/schedMaint.
- **qualities** — greige gsm, width, dyeType, dyeMins, finishMins, maxBatch, + **2-step pre-treatment** (pt_mc1/time_req1, pt_mc2/time_req2).
- **shadeRecipes** — **quality-specific**: quality, shade, family, tone (0 light → 10 dark), dye1-3 + %, program, spectrophotometer standard (specL/speca/specb + allowed ΔE `dETol`).
- **qualityRecipes** — auxiliary/process chemicals (aux1..5 now; infra for 20).
- **customers**, **suppliers**, **operators**, **qcMetrics**.
- **orders** — multi-shade: `lines:[{shade, m}]`, cust, qual, due (days), pri (1 urgent–3 low).
- **storageAreas** — shelves × rowsPerShelf × colsPerShelf (for taka indexing), floor, locX/locY.
- **users**, **roles**, **settings** (widthDefault 56, minMeters 300, buffer 1.20, loadMin 35, unloadMin 25).

## Scheduler (greedy campaign scheduler, in `app.js` `computeSchedule`)
1. meters → kg = `meters × (width_in × 0.0254) × gsm / 1000`.
2. Split order into batches ≤ `maxBatch`, never below **300 m** min load.
3. **Pass 1 — pre-treatment** (2 steps) on shared **drums/jiggers** (jiggers are a **shared pool** with dyeing) → sets `rfdReady` (the RFD buffer point).
4. **Pass 2 — dyeing campaigns**: light → dark by tone per machine; a **wash auto-inserts** when the shade family changes or tone drops; a batch can't start before its `rfdReady`.
5. Every machine operation reserves **60 min handling** (35 load + 25 unload).
6. Promise date = (route time + finishing) × **1.20** buffer; flags if it misses the due date.
- Verified: 0 overlaps / capacity violations / tone-drops / dye-before-RFD.

## Design language
Dark industrial: bg `#0e1214`, panel `#141a1d`, teal accent `#2bbf9e`/`#3fd4ae`; **Manrope** (text) + **IBM Plex Mono** (numbers). Status palette: dyeing = teal, pre-treat = amber `#e0a83e`, wash = blue `#4a90d9`, idle = grey `#6b7680`, maintenance = red `#e0574a`. Shade swatches via HSL(family, tone). Admin: sidebar + schema-driven CRUD; sectioned forms with validation, helper text, required markers, and a live shade-swatch preview.

---

## ⭐ NEXT / PENDING (agreed with owner, NOT yet implemented)
The mill runs **24/7 continuous** (no shift calendar needed). Before these, discuss/confirm, then build:

1. **Ship-ready empty data** — strip all sample/business data; production seed keeps only the **ADMIN account, Administrator role, and settings**. (To go from demo to empty on the machine: delete `data.json` once and restart.)
2. **Remove the destructive "Reset sample data" button; add one-click Export/Backup** (downloads full `data.json`; note it contains password *hashes* = sensitive; restore = replace file + restart).
3. **Real-time Gantt = now-line over a stable plan.** Anchor the plan to a **server timestamp stored in `data.json`** (`planAnchor`) so it stops sliding on reload; a live **now-line** sweeps across it; axis shows **real clock times**; past greys out; **re-anchor automatically on order add/change** plus one small manual "Replan / reset clock" control; if now is past the whole plan, show a re-plan prompt; use the **server clock** so terminals stay in sync; label the board **"Planned — live tracking coming later."** (Not auto-replan-every-tick — misleading without actuals.)
4. **First-run onboarding** — dashboard **setup checklist** (add machines → qualities → shade recipes → customers → storage) that ticks off as records are added; friendly empty states on floor/schedule when there's nothing to plan.

## Future roadmap (owner's stated direction)
- **Order-ID scanning + real-time logging** so the software ascertains where every batch physically is (the big future goal).
- **Goods-inward → storage** allocation module (connect the plan to real fabric + taka locations).
- **TLS + company-domain hosting** (auth already built).
- **QC consistency layer** using spectrophotometer ΔE vs the stored standard.
- **PLC integration** for dyeing jets (jets already have PLCs).

## Testing notes (for the assistant)
- Verify by running `python3 server.py <port>` + jsdom. jsdom's node-fetch has no cookie jar, so wire a per-window jar for login; wait ~1.4s after submitting login for the async chain to finish.
- The sandbox mount occasionally serves a **stale/truncated mirror** of a file during testing — the user's real files (via the file tools) are authoritative; re-write or re-read to confirm.


## Update — 19 Jul 2026 (latest session)

Three domain rules were added on top of the lot/balance work. All verified.

### 1. One quality per batch
The **first lot added locks the quality select** in the Batch maker (dashed, disabled, hint "Locked by LOT-xxxx — a batch cannot mix qualities"). Lots of any other quality are filtered out of the remaining dropdowns, and `submitBatch()` re-checks before saving. Removing all lots unlocks it again.

### 2. Takas cannot be cut
A batch is assembled from **whole takas**. Enter the meters you want and the row snaps to a real set of pieces:

- `pickTakas(pool, target)` in `app.js` returns the **fewest takas**, and among those the **least overshoot**. It is a small DP over achievable sums per taka-count — a naive largest-first greedy overshot badly (asked 200 m, gave 277 m when 3x85 = 255 m was sitting there).
- The chosen lengths are stored on the batch lot row as `takas:[…]`, so `lotRemainingTakas()` computes the running balance by removing consumed takas from the lot pool — the balance is now piece-accurate, not just meter-accurate.
- Each row shows its pick: `5 whole takas · 96 + 96 + 96 + 85 + 85 = 458 m (asked 450 m; +8 m — takas cannot be cut)`.

### 3. Stentor runs at a speed, not a fixed time
The stentor's time scales with meters, so each quality step now has an optional **`stepN_speed` (m/min)** used when that step's machine is `stentor`:

```
time = meters / speed + settings.stentorSetupMins      (setup default 90 min)
```

Verified on Cotton Poplin @ 30 m/min: 300 m → 100 min, 450 m → 105, 900 m → 120, 1800 m → 150. Every other machine keeps its fixed per-batch time. Setup minutes are editable in Admin → Settings.

**Stentor is a post-dyeing finish.** The server now rejects any quality whose stentor step sits before `dyeStep`:
`"Stentor is a post-dyeing finish - it cannot be step 1 when dyeing is step 3"`.

### 4. Oversized batches auto-split at creation (Batch maker)
The Batch maker let you group lots into a batch heavier than the quality's `maxBatch`, with no machine ever big enough to run it — it just sat `unplanned` on the Gantt (e.g. B-0002, 678 kg vs. Cotton Poplin's 400 kg cap / JET-2's 400 kg max).

Fixed at the source: `submitBatch()` now checks the total against the quality's `maxBatch` and, if over, calls `splitBatchRows()` (new, in `app.js`) before saving — **two separate batch records** are created instead of one oversized one, "for factory floor clarity" (owner's words — a batch is one physical machine load).

- `splitBatchRows(rows, capacityKg, minMeters)` — best-fit-decreasing bin packing at the **taka level** (nothing gets cut): largest taka first, into whichever in-progress batch leaves the least spare room without exceeding `capacityKg`. This is a hard cap — every resulting batch fits some real machine, unlike a naive even-split. A trailing batch left under the 300 m floor gets folded back into another with room.
- `bSyncTotals()` shows a live warning while building the batch ("exceeds 400 kg max for Cotton Poplin — will save as 2 separate batches") before you even hit Create.
- `submitBatch()` saves each group with a sequential `API.save` call (server assigns B-000x ids in order) and reports all created batches together.
- Verified against the real B-0002 data (LOT-0003 + LOT-0004, 678.2 kg): splits into two batches (386.7 kg + 291.4 kg), both under JET-2's 400 kg cap, all 40 takas conserved exactly.

## Update — 20 Jul 2026 (later same day)

**Now under git.** This project had no version control before today — `git init` was run in `REL_DYEING/` with one baseline commit, then each feature below landed as its own commit (`git log --oneline` has the full list). Note for future sessions: the mounted dev folder has a filesystem quirk where Bash-level `rm`/`unlink` fails ("Operation not permitted") even though file edits and `git add`/`git commit` work fine — git write commands may need `mv .git/index.lock .git/index.lock.old-$RANDOM` (rename, not delete) before retrying if a stale lock blocks them. Harmless `.git/*.lock.old-*` and `.git/objects/*/tmp_obj_*` files may be lying around from this — safe to ignore or clean up later from a normal (non-sandboxed) terminal.

Four features, built from a real inventory export (`LOT INF.xlsx`, 475 lots / 118 distinct qualities from the mill's actual stock sheet) and a plan written with `superpowers:writing-plans` (`docs/superpowers/plans/2026-07-20-weaver-import-mcno.md` — full column-mapping rationale and verification numbers live there):

### 1. Weaver master table
New Admin page (`SCHEMAS.weavers` in `admin.html`): name, contact person, phone, notes. Server-registered like every other table (`WV-0001` ids, `weavers` page-permission key in `server.py`). Lot master gained a `weaver` select field plus a `master` free-text field (the mill's process/category tag, e.g. "PRINT" — confirmed constant across all 475 real rows, so it's plain text, not its own master table).

### 2. Lot master gained full mill-tracking fields
`srcLotNo` (the weaver's own lot number, for matching physical rolls), `inwardPcs`/`inwardMeters`, `dispatchedPcs`/`dispatchedMeters`, `oldStockPcs`/`oldStockMeters`, `prodMeters`/`pendingProd` — all informational, mirroring the mill's existing tracking sheet columns. None of these feed the scheduler; only `takas` does.

### 3. Mass import lots from Excel
Admin → Lot master → **Import from Excel**. Vendored SheetJS (`static/vendor/xlsx.full.min.js` — fetched via npm during the session since the sandbox blocks CDN pulls; no runtime CDN dependency, matches the LAN-only deployment) parses the mill's `.xlsx` by header name (tolerant of column order). Verified end-to-end against the real file: **475 lots parsed, 1 skipped (the sheet's own "GRAND TOTAL" row), 118 new qualities, 1 new customer ("RAVI EXPORTS LTD."), 2 new weavers ("R.E.L.(W)", "R.E.L. (M)")**.

- The sheet has no per-piece taka lengths, only `BAL PC` (count) and `BAL MTS.` (total) — `synthTakas()` (new, in `app.js`) generates that many pieces at the average length (nearest 0.5 m), with the last piece absorbing the rounding remainder so the sum is exact. Owner confirmed this approach explicitly.
- New qualities are created as **placeholder stubs** (gsm 100, width 56, maxBatch 300 kg) — not real process data. Report says so; Quick add (below) is how you fix them in bulk.
- ⚠ **Known gap**: re-importing an updated sheet later will create *duplicate* qualities/customers/weavers rather than reusing existing ones by name — `commitLotImport()` doesn't do the `byName`-lookup-and-reuse-id merge that Quick add (below) does. Fine for a one-time bulk load; would need that same merge pattern added before this becomes a recurring weekly import.

### 4. Quick add for Qualities
Admin → Qualities → **Quick add**. Paste one quality per line (`name` alone, or `name, gsm, width, maxBatch`) — an existing name updates that quality in place (reuses its id) instead of duplicating it. Built specifically to flesh out the 118 placeholder qualities the importer creates. Doesn't touch the 4-step route — that still needs the full Edit form per quality.

### 5. M/C No — manual machine pin on the Batch Maker
Operations → Batch maker gained an optional **M/C No** dropdown (populated from machines matching the quality's dye-step type). Pin applies only to the dye step — pre-treatment stays on the shared auto-assigned pool as before.
- Pin matches and fits → batch is forced onto that exact machine.
- Pin is the wrong machine *type* for this quality → falls back to auto-assign, batch gets a visible `pinWarning` (Gantt hover + Live plan) rather than failing silently.
- Pin fits the type but is too small for the batch's kg → batch stays `unplanned` with a specific reason (`"JET-1 (250 kg) is too small for this 300 kg batch"`) instead of being silently reassigned — the operator chose that machine on purpose.
- Unpinned batches schedule exactly as before (regression-tested).
- Also editable from Admin → Batch maker (new `msel` field type) — which surfaced and fixed a **pre-existing bug**: `saveModal()` had a corrupted block (referenced an undefined `val`) that threw on saving *any* batch edited through Admin's generic modal. Fixed — Admin batch editing now works.
