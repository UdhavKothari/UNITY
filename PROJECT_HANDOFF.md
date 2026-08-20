# REL-UNITY (formerly "REL Dyeing ERP") — Project Handoff / Memory

**Purpose:** Attach or paste this file at the start of a new chat when you want to add features to this software. It gives full context so we can pick up without re-explaining.

> **Name:** the product is now **REL-UNITY**. Older sections below still say "REL Dyeing ERP" — same software.
> **Store now = SQLite** (`mvp/data.sqlite`), not `data.json`. `data.json` is only a one-time legacy import; ignore the "data.json is the only copy" line in the old intro. See the **Aug 2026** update for the current architecture.
> **The three consoles:** `index.html` (Operations), `sales.html` (Sales), `admin.html` (Admin) — all share `app.js`.

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
- **Roles master = per-page permissions (Discord-style):** each "page" is grantable per role. Page keys (server `ALL_PAGES`, mirrored in admin `PAGES`): `op_floor, op_schedule, op_order, op_batch, op_storage, dashboard, machines, qualities, shadeRecipes, qualityRecipes, customers, orders, storageAreas, suppliers, operators, qcMetrics, users, roles, plan, settings`.
- The **server enforces permissions on every mutation (403)** — UI hiding is defense-in-depth only.
- Admin creates **users** (username + password + role + active) and **roles** (name + permission checkboxes).
- ⚠ **No HTTPS yet** — add TLS before any company-domain / internet hosting.

## Data model (master tables)
- **machines** — type (drum/jigger/jet/stentor/hydro/rope), capMin/capMax (kg), wash (min), plc, lastMaint/schedMaint, **shadeFamilies** (multi-select — soft scheduling preference for the dye step).
- **qualities** — greige gsm, width, dyeType, dyeMins, finishMins, maxBatch, **loadMin/unloadMin** (per-quality handling time, falls back to Settings default if blank), **fabricGroup** (free-text tag — qualities sharing a tag are treated as the same fabric for batching/shades), + **2-step pre-treatment** (pt_mc1/time_req1, pt_mc2/time_req2).
- **shadeRecipes** — **quality-specific**: quality, shade, family, tone (0 light → 10 dark), dye1-3 + %, program, spectrophotometer standard (specL/speca/specb + allowed ΔE `dETol`).
- **qualityRecipes** — auxiliary/process chemicals (aux1..5 now; infra for 20).
- **customers**, **suppliers**, **operators**, **qcMetrics**.
- **orders** — multi-shade: `lines:[{shade, m}]`, cust, qual, due (days), pri (1 urgent–3 low).
- **storageAreas** — name, **shelfCount** × **colCount** (grid dimensions, drives the Storage tab), floor, locX/locY.
- **storageSlots** — lot-linked occupied slot: `{area, shelf(number), col(letter), lotId, notes}`. Only occupied coordinates exist as rows.
- **users**, **roles**, **settings** (widthDefault 56, minMeters 300, buffer 1.20, **loadMin/unloadMin now the fallback default** for qualities without their own — see item 18 below, **familyPreferencePenaltyMins** default 120 — see item 17).

## Scheduler (greedy campaign scheduler, in `app.js` `computeSchedule`)
1. meters → kg = `meters × (width_in × 0.0254) × gsm / 1000`.
2. Split order into batches ≤ `maxBatch`, never below **300 m** min load.
3. **Pass 1 — pre-treatment** (2 steps) on shared **drums/jiggers** (jiggers are a **shared pool** with dyeing) → sets `rfdReady` (the RFD buffer point).
4. **Pass 2 — dyeing campaigns**: light → dark by tone per machine; a **wash auto-inserts** when the shade family changes or tone drops; a batch can't start before its `rfdReady`. If a machine is tagged with the batch's shade family (Admin → Machines → Shade families), it's preferred — but only *softly*: a non-preferred machine still wins if it finishes meaningfully sooner (configurable penalty, Settings → Family preference penalty, default 120 min).
5. Every machine operation reserves handling time = that quality's own **loadMin/unloadMin** (Admin → Qualities), falling back to Settings' default (35 load + 25 unload) if the quality hasn't set its own.
6. Promise date = (route time + finishing) × **1.20** buffer; flags if it misses the due date.
- Verified: 0 overlaps / capacity violations / tone-drops / dye-before-RFD.

## Design language
**Light, navy-committed, restrained** (superseded the original dark-industrial mockup early on — this doc previously described the dark theme; corrected here to match what's actually shipped). Cool off-white bg `#f4f6fa`, white/`#f8fafc`/`#eef2f8` surfaces, ink `#18233b`, navy primary `#1f2d4d`, accent blue `#3a63c4`/`#eaf0fb`. **Inter** (text) + **IBM Plex Mono** (numbers, IDs, times, uppercase micro-labels). **Material Symbols Rounded** for every icon (one family, no mixing). Status pills: dyeing/`run` = green, pre-treat/`pre` = amber, wash = blue, idle/`free` = grey, maintenance/`maint` = red. Shade swatches via HSL(family, tone). Signature instrument: the **vat-fill machine card** (bottom-up fill tinted by the running shade, % label, status pill). Gantt rows use light rounded blocks, hatching for wash/pre-treat, pale load/unload caps. Schedule times are always relative to a live **t** (now), never bare clock hours. Admin: sidebar + schema-driven CRUD; sectioned forms with validation, helper text, required markers, live shade-swatch preview. Full rules (hard bans, motion, component reuse) live in the `rel-dyeing-design-insight` skill — read it before touching any screen, don't re-derive from this summary.

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

## Update — 20 Jul 2026 (evening)

### 6. Batch Maker form cleanup
Removed **Shade date** (redundant — the shade *number* already identifies it) and the **Batch ID** placeholder row from Operations → Batch maker's create-batch form. Batch IDs are still system-generated exactly as before, just no longer shown as a blank field before the batch exists.

### 7. Searchable lot picker
The plain `<select>` for choosing a lot on Operations → Batch maker didn't scale — with 20–30 new lots landing daily and ~250 open lots at any time, scrolling a dropdown was unworkable. Replaced with a type-to-filter combobox (`lotPickerHTML`/`wireLotPicker`/`lotPickVal` in `app.js`): click in, type any part of the lot no., customer, or quality, arrow keys + Enter to pick, fully-used lots shown greyed out and disabled. Same filtering rules as before (locked to the batch's quality/order once the first lot is picked). Admin → Batch maker's lot picker (the generic schema-driven modal) still uses the old plain select — lower priority since the Operations page is the daily-use path; can get the same treatment later if it becomes a pain point there too.

### 8. Shade 0 = RFP (Ready for Print), generated automatically
Every quality now gets an automatic **Shade "0"** recipe (family Neutral, tone 0 → renders near-white) the moment the quality is created — via the regular Add-quality form, Quick add, and the Excel lot importer's placeholder-quality creation. This is a real, dyeable shade — everything is dyeable to shade 0, and doing so produces **RFP (Ready for Print)** fabric (white/near-colourless, headed to the printer next), not "undyed greige." Idempotent (`ensureGreigeShade()` in `admin.html` checks for an existing shade-0 recipe on that quality before creating one), so re-saving an existing quality never duplicates it.

### 9. Stentor route steps: speed replaces time, not alongside it
Each of a quality's 4 route steps used to show 3 boxes (machine, time, stentor speed) regardless of which machine was picked — confusing, since only one of time/speed is ever meaningful for a given step. Now the time box and speed box show/hide based on that step's machine select: pick **stentor** → the time box is replaced by the speed box (m/min); pick anything else → only the time box shows. Generic mechanism (`showIf:{k,eq|ne}` on any field + `evalConditionalFields()` in `admin.html`), reusable for future conditional fields. The actual schedule math was already correct — `routeOf()` in `app.js` has always computed a stentor step's time from meters ÷ speed + setup; this was purely a form-clutter fix.

### 10. Database wiped to a clean production-empty state
Per owner's request ("ready for a test"), `mvp/data.json` was rebuilt to hold only: the `ADMIN` user (existing credentials preserved), the `Administrator` role (perms re-synced to every current page), and `settings`. Every data table — machines, qualities, shade recipes, quality recipes, customers, storage areas, suppliers, operators, QC metrics, orders, lots, batches, weavers — is now empty, and `_seq` was reset so new IDs (LOT-0001, B-0001, …) start clean. The real mill data imported earlier this session (236 lots, 118 qualities, etc.) is preserved at `mvp/data.json.backup-2026-07-20` (gitignored, not committed) in case anything needs to be restored or re-diffed later. Deleting `data.json` outright was **not** used — `server.py`'s `load_db()` reseeds `seed_data.json`'s demo dataset when the file is missing, which is not what "empty" means here.

⚠ Not done: no in-app "wipe to empty" button exists — this was a one-time direct edit of the data file. If this needs to be repeatable (e.g. for a demo reset), it should become a proper admin-gated API op rather than a manual file edit.

## Update — 20 Jul 2026 (night)

### 11. Shade 0 corrected: RFP, not "undyed"
Owner corrected an earlier mistake in this doc and in the auto-created shade-0 recipe's label: **everything is dyeable to shade 0**, and dyeing to shade 0 produces **RFP (Ready for Print)** fabric — it's a real dye step, not "nothing happens." Fixed the `program` text `ensureGreigeShade()` writes (`admin.html`) and the wording above in item 8.

### 12. Full-column search + sortable headers, every Admin table
`render()` in `admin.html` used to search only a hand-picked subset of columns per table (e.g. Qualities only searched `name`) and had no way to sort at all. Now:
- **Search** matches against every visible column's *rendered* text (`cellText()` strips the HTML that `cellVal()` produces, so computed columns like Route, Allocation, or Aux summary are searchable too, not just raw fields) — e.g. typing a quality name into the Lot master search box now matches.
- **Sort**: every column header is clickable (`toggleSort()`); numeric-looking values sort numerically, everything else sorts as text. Click again to reverse, a third click clears back to insertion order.
- The old per-schema `search:[...]` arrays are now unused (harmless, left in place) — full-column search superseded them.

### 13. Rebranded qualities — "same fabric" group tag
Some qualities are the exact same physical fabric sold again under a different commercial name, and the mill dyes them together. Added a **Fabric group** free-text field to Quality (`fabricGroup` — new column + form field in `admin.html`). Two qualities sharing the same non-empty tag are treated as one fabric:
- **Batch Maker**: lots from either name can now go into the same batch (`bLotFilter`/`bLockQuality`/`submitBatch`'s mixing check in `index.html` all compare by `sameFabric()`, not literal name).
- **Shades**: `shadesForQuality()`/`SH()` in `app.js` look across the whole tag group, so both names see the same shade list — set shades up once under either name.
- **GSM/route/max batch are *not* inherited** — each quality keeps its own (deliberately simple: a tag, not a data hierarchy). If the rebrand really is identical fabric, fill in matching GSM/route on both; the app won't auto-sync them.
- (Considered a "canonical alias" model where GSM/route/shades would auto-inherit from one parent quality — owner decided that was more confusing than useful; the flat tag is what shipped.)

## Update — 21 Jul 2026 (scale-up + storage)

Seven-task plan (`docs/superpowers/plans/2026-07-21-scale-and-storage.md`), executed with `superpowers:subagent-driven-development` — fresh subagent per task, spec-compliance + code-quality review after each, then one whole-branch review at the end. Prompted by the owner needing the app ready for **mass data entry** (hundreds of qualities, ~20 shades each) plus new machine-assignment and storage-tracking capability. All 12 commits (`2a62608`..`27235e0`) are on `master`.

### 14. Performance: lot allocation no longer scans every batch per lot
`lotAllocation()`/`lotRemainingTakas()` in `app.js` used to re-scan the *entire* batches array on every call — O(lots × batches), fine at demo scale, a real problem heading into hundreds of qualities / thousands of lots. Replaced with `_lotAllocMap()`, a single O(lots + batches) pass memoized per `DB` object reference (auto-invalidates whenever the data reloads). Admin table search also got a **debounce** so typing in a search box with thousands of rows doesn't re-render on every keystroke.

### 15. Bulk (mass) add for every master table
Admin → any of **Machines, Customers, Suppliers, Operators, QC metrics, Shade recipes, Quality recipes, Weavers** → **Bulk add**. Paste one row per line, comma-separated fields in schema order; matches an existing record (by name, or by a compound key for tables like Shade recipes where `quality` alone isn't unique — see `BULK_ADD_KEY_FIELDS`) and updates it in place instead of duplicating. Relational-select fields (machine type, quality, etc.) are validated against the live DB before commit rather than silently accepting garbage.
- ⚠ Qualities itself isn't in the bulk-add table list — it already has its own dedicated Quick add (item 4 above), which is deliberately narrower/simpler for that table's specific fields.

### 16. Excel export for every master table, Batch maker, and the schedule
Every Admin table, plus Operations → Batch maker's batch list and the Schedule view, now has an **Export** button producing a real `.xlsx` (vendored SheetJS, same library as the Task 3-era lot importer — no server round-trip, generated client-side from the same rendered data as the on-screen table).

### 17. Machines can be tagged with preferred shade families (soft preference)
Admin → Machines → **Shade families** (multi-select). When scheduling a batch's dye step, a machine tagged for that shade's family is preferred, but it's a **soft** preference, not a lock: `computeSchedule()` scores each eligible machine as `finish time + penalty (if not preferred)`, so a busy preferred machine can still lose to a free non-preferred one. Penalty is configurable at Admin → Settings → **Family preference penalty (min)** (default 120). Backward compatible — with no machine tagged (today's live state), scheduling is unchanged.

### 18. Loading/unloading handling time moved from global Settings to per-Quality
Every quality now has its own **Loading time (min)** / **Unloading time (min)** fields (Admin → Qualities). The old Settings fields (Admin → Settings) are relabeled **"Default loading/unloading time"** and now only apply as a fallback for qualities that haven't set their own. `computeSchedule()`, the Gantt's handling-time cap widths, and the order-confirmation preview text all read the per-quality value with the same fallback.

### 19. Storage data model: lot-linked slots, numbered shelves, lettered columns
New `storageSlots` table (`{id, area, shelf(number), col(letter), lotId, notes}`) — only *occupied* slots are materialized as rows; an empty coordinate simply has no record. `storageAreas` gained `shelfCount`/`colCount` (replacing the old `shelves`/`rowsPerShelf`/`colsPerShelf` fields) so a grid can be drawn without per-cell records existing in advance. New `colLetter(i)` helper in `app.js` does spreadsheet-style column lettering (0→A … 25→Z, 26→AA, 27→AB, …).

### 20. Visual Storage tab
Operations gained a fifth section tab, **Storage** (`op_storage` permission, same pattern as the existing Batch maker tab). Shows a grid — shelf numbers down the side, lettered columns across — for the selected storage area; occupied cells are tagged with their lot id and tinted, empty cells are plain. Clicking any shelf number or cell opens a modal listing every column on that shelf as an editable row (assign or clear a lot via the same searchable lot picker used in Batch maker), with a duplicate-lot guard so one lot can't occupy two slots at once. Went through an explicit design + copy polish pass (touch targets, focus-visible states, aria-labels, empty-state and toast copy matched to the app's existing voice) as its own step, per the `impeccable` skill's "polish last, not first" rule.

### Fixes caught during review (all 7 tasks)
- Orphaned lot references (a batch pointing at a deleted lot) no longer silently drop out of the allocation map.
- Bulk-add's shade-recipe matching now uses a **delimited** compound key (`quality\0shade`) — the original undelimited join could theoretically conflate two different quality/shade pairs at a value boundary (e.g. `"AB"+"CD"` vs `"ABC"+"D"`).
- A storage-area name containing an apostrophe could break out of the Storage tab's inline `onclick` JS string and inject script (low-severity, admin-entered-only) — fixed by escaping single quotes at both call sites. The same latent pattern exists at two pre-existing, out-of-scope spots in Admin's bulk-add UI (`admin.html:412`, `:848`) — both are safe today (table names are a hardcoded whitelist, never admin-entered text) but worth a general `esc()`-for-JS-context sweep if that ever changes.

### Known non-issues, deliberately left as-is (final review's call)
- A quality's `loadMin`/`unloadMin` of exactly `0` is indistinguishable from "unset" and falls back to the Settings default (JS `||` falsy-zero) — not fixed, since zero-minute handling isn't a real scenario on a dye floor and a `??` swap would actually break the intentional "blank string → fallback" behavior for genuinely-unset fields.
- `storageSlots`' intended `SL-` id prefix is dead code (falls through to the same `ST-` prefix as `storageAreas`, since neither is in the server's `SYSTEM_IDS` list) — cosmetic only, IDs stay unique via the random suffix, mirrors a pre-existing identical gap for `weavers`/`WV`.

### Still pending (not part of this plan)
- **[DONE 22 Jul — see item 27] Quality Quick Add: derive GSM from lot data** — when adding/updating a quality via Quick add, if GSM isn't given directly, calculate it from a linked lot's meters + weight (assuming 54" width, GSM = weight_kg × 1000 ÷ (meters × 1.3716)). Requested mid-session, deliberately deferred to land after the scale-and-storage plan.
  - **Blocked on one open question, asked of the owner, not yet answered:** the Lot master has **no weight field at all today** — only pieces, meters, and taka lengths (confirmed against both the live `SCHEMAS.lots` in `admin.html` and the original mill import sheet's column mapping in `docs/superpowers/plans/2026-07-20-weaver-import-mcno.md`, which never had a weight/kg column either). The only place "weight (kg)" is ever entered anywhere in the app is per lot-row inside Batch Maker, typed in manually by the operator at batch-creation time — it isn't stored on the Lot record itself. So before building this, the owner needs to pick where the weight figure should come from:
    1. **Add a new `weight` (kg) field to Lot master** — entered/imported per lot; Quick Add looks up a lot by number and computes GSM from that lot's meters + this new field.
    2. **Reuse Batch Maker's existing per-row weight** — only works for lots that have already been used in at least one batch (weight isn't known before that).
    3. **Skip lot lookup entirely** — Quick Add's paste format gains an optional inline meters+weight pair (e.g. `MILAN 60 INCH, 300m, 45kg`), computed on the spot with no dependency on lot data.
  - Do not guess an answer and build ahead of this — the three options have materially different scope (schema change vs. reuse vs. pure UI), so implementation shouldn't start until the owner picks one.
- ⚠ Not done: Admin's own batch-edit modal (`lotQRow`/`lotQRows`) and order-matching (`bRefreshOrders`) still compare by literal quality name, not fabric group — lower priority than the Operations Batch Maker, which is the daily-use path.

## Update — 22 Jul 2026 (batch lifecycle, audit trail, taka numbers)

Plan: `mvp/docs/superpowers/plans/2026-07-22-batch-lifecycle-audit-takas.md`. One commit `e08bfde`. All verified with live curl + VM-harness tests (jsdom still not installable in the sandbox; used vm-context harnesses instead).

### 21. Batch lifecycle — Start / Complete, timestamped and attributed
Operators now drive the board. Each batch has a status **planned → running → done** (plus **Reopen** to undo a completion). Transitions go through a dedicated server op `batchStatus {id,to}` that stamps `startedAt/startedBy` and `completedAt/completedBy` **server-side** (never a client clock) and writes an audit entry. Controls live on Operations → Batch maker's batch list (status pills + Start/Complete/Reopen buttons), permission-gated by `op_batch`. Admin batch rows get a **History** button.

### 22. The Gantt now moves forward
`batchesForSchedule()` **drops `done` batches**, so a finished load frees its machine and the remaining batches pull earlier — the plan advances as work completes. The Gantt axis now shows **real wall-clock times** (not `t+Nh`), a live **now-line** sweeps across (updates every 20 s), running blocks pulse, and the Operations board **re-anchors every 3 minutes** so it stays current without a manual refresh. (This supersedes the old pending item #3's "stable-plan + now-line" idea with a simpler now==t0 anchor that re-runs periodically.)

### 23. Console history + batch history (audit trail)
New append-only **`activityLog`** table is the single source for both. `_log()` in `server.py` records **login, logout, changePassword, reset, create, update, delete, and every batch lifecycle transition** with user + server timestamp. Direct writes to `activityLog` are refused (403). Two views: Admin → **Activity log** (full console history, searchable, Excel export) and a per-batch **History** modal (the same log filtered to one batch id). Capped at 5000 entries (oldest trimmed).

### 24. Taka numbers + Taka master
Every lot's takas now carry stable **positional taka numbers** (`takaNos = [1..N]`), assigned automatically on save; `_migrate` backfilled all 475 existing lots. New Admin → **Taka master** page: a wide grid of `Lot no. | Customer | Quality | Pcs | Total m | T1 | T2 | …` where each numbered cell is that piece's length in metres (Excel export included). The `takas` length array is unchanged — `takaNos` is a parallel, non-destructive field, so all existing pick/balance/split logic is untouched.

### 25. Admin toggle: batch completion mode
Settings → **Batch completion**: `manual` (default — operators press Start/Complete) vs `auto` ("Automatic (IoT sensors — coming soon)"). Groundwork for wiring jets to sensors later; in auto mode the buttons show a "sensor-driven" note but manual override stays available. Seeded `completionMode:"manual"`.

### 26. Taka limit 30 → 50
Every 30-taka cap (add guard, `NxM` bulk expander, trim, and the two schema labels) is now driven by a `MAX_TAKAS=50` constant.

⚠ Note for next session: editing `server.py` auto-reloads the user's live server, which re-runs `_migrate` on the real `data.json` — that's how the 475 lots got `takaNos`/`activityLog`/`completionMode` this session. Safe, but be aware live data changes shape the moment the server file is saved.

## Update — 22 Jul 2026 (later — GSM quick-add unblocked)

### 27. Lot weight + GSM auto-derivation in Qualities Quick add
The GSM-from-lot-data feature (parked in item 26's "Still pending" on the open weight-source question) is **built**. Owner chose **option 1 — add weight to Lot master**.
- **Lot master** gains a **Greige weight (kg)** field.
- **Qualities → Quick add**: leave GSM blank and it's **derived** as `kg × 1000 ÷ (meters × width_m)` aggregated over that quality's **weighed lots** (`deriveGsmForQuality()`), width from the row/default. Fallback ladder: **typed > derived > kept-existing > 100**. The live preview lists each row's resolved GSM and its source ("from 2 weighed lots" / "typed" / "default"). Verified: 350 m + 52.5 kg → GSM 105.
- Existing 118 placeholder qualities can now be fleshed out by entering lot weights (or importing them later) and re-running Quick add name-only.
- ⚠ The Excel lot importer still has no weight column mapping (the mill sheet has none); weight is entered manually per lot for now. If EMPIRE/weaver sheets later carry a weight column, map it in `commitLotImport()`.

## Update — 24 Jul 2026 (Mass Batch Planning + taka-wise selection)

Plan: `docs/superpowers/plans/2026-07-24-mass-batch-planning.md`, spec: `docs/superpowers/specs/2026-07-24-mass-batch-planning-design.md`. Eight tasks, executed with `superpowers:subagent-driven-development`. Prompted by the owner: entering a day's plan one batch at a time (~25 jets × 4–5 batches) was taking ~6 hours; there was no whole-day view, no explicit machine load order, and takas were auto-picked rather than hand-selected off the floor.

### Planning model: fully manual
Auto-scheduling (light→dark campaign assignment, auto-wash insertion, capacity auto-split) is **parked, not removed** — `computeSchedule()` stays in the code as a fallback path but no longer drives the day's plan. A batch's place in the plan is now three explicit fields on the batch record:
- `machine` — the assigned machine id. Promotes the old optional `mcPin` (dye-step pin) to the definitive assignment; `mcPin` is kept as a back-compat alias.
- `planDay` — a plain ISO date label (e.g. `2026-07-24`) grouping batches for a day; the floor runs 24/7 and doesn't stop at day boundaries.
- `seq` — integer position within (`machine`, `planDay`); each machine restarts at 1 each day.

The Gantt and floor board render batches ordered by (`machine`, `planDay`, `seq`) instead of calling the greedy scheduler for assignment — route/duration math still computes each block's *length*, only machine choice and ordering moved from algorithm to operator. If the auto-scheduler path is ever reactivated, it renders the manual plan in machine+seq order across all plan-days, i.e. it degrades to reading the same explicit fields rather than reassigning batches — so both paths agree on layout.

### New tab: Mass planning (`op_massplan`)
Operations gained a new full-width tab, gated by the new `op_massplan` page permission (same pattern as `op_batch`/`op_storage`). One scrollable table-driven screen for an entire day's plan: a Day selector (today / date-pick / next day / history), per-machine sections (sticky header with machine id, type, capacity, and that day's batch/kg/m totals — shown even when empty), batch rows in `seq` order with inline add/edit, and drag-or-type sequence reordering scoped to one machine+day. `op_massplan` was already present server-side in `ALL_PAGES` (Task 1); this pass surfaces it as a checkbox in Admin → Roles (`mvp/static/admin.html`'s `PAGES` array), so non-Administrator roles can be granted the tab.

### Per-lot taka picker (hand-selected Sr. Nos.)
Reachable from any lot row in a batch (Mass Planning's inline add and the legacy single-batch form both use it). Flow: add the lot(s) to the batch, then pick takas within each lot from a chip list (`T{takaNo} · {meters}m`); takas already consumed by another batch show greyed/disabled (existing `_lotAllocMap`/`lotRemainingTakas` allocation logic, extended to taka-number granularity). Ticking takas sets both `takas[]` (lengths) and `takaNos[]` (the selected Sr. Nos.) and recomputes `pcs`/`mtr`/`weight`. The old "fill to target meters" auto-pick (`pickTakas`) remains available as a shortcut button inside the picker, but manual ticking is the default. Selected Sr. Nos. are shown in the row detail (`LOT-0003 · T1,T2,T3,…`) and now flow into the Excel export.

### Capacity guard: block, don't auto-split
In Mass Planning, if hand-picked takas exceed the assigned machine's `capMax`, the save is blocked with an inline warning — the operator removes takas or moves the batch to a bigger machine. The legacy single-batch form's automatic oversize-split (`splitBatchRows`) is **not** applied here; it would silently fight the operator's explicit machine choice. Allocation still guarantees a given taka can be in at most one batch.

### Excel export: machine/plan-day/seq/taka columns
`exportBatchesToExcel()` (`mvp/static/index.html`) gained four columns — `Machine`, `Plan day`, `Seq`, and per-lot `Taka Nos` (e.g. `LOT-0003:1/2/3`, one segment per lot in the batch) — ahead of the existing Quality/Shade/Pcs/Mtr/Kg/In/Out/pH/Operator/Shift columns. Same vendored SheetJS as every other export in the app, generated client-side.

### New tests
`mvp/tests/test_migrate_massplan.py` (server-side `_migrate` backfill of `planDay`/`machine`/`seq` on existing batches), `mvp/tests/test_taka_alloc.js` (taka-level allocation/double-booking guard), `mvp/tests/test_seq.js` (sequence renumbering on reorder and cross-machine move), `mvp/tests/test_manualplan.js` (manual-plan rendering order, capacity block, no auto-split). All pass alongside the existing `mvp/tests/*` suite.

---

## Update — 14 Aug 2026 (consolidated: rename, SQLite scale-up, permissions, challan email pipeline, Sales console)

This block consolidates the work between late July and 14 Aug. Product renamed **REL → REL-UNITY**. All changes are committed on `master`.

### 🔐 Standing security constraints (carry into every session, verbatim)
- **`mvp/secrets.local.json` is gitignored and MUST NOT be read** by the assistant. It holds external-system creds only (Gmail app password, future SQL Server creds). Template is `mvp/secrets.example.json`.
- **Gmail needs an APP PASSWORD** (Google Account → Security → 2-step → App passwords), not the normal password.
- **Never write test data into the live `data.sqlite` / `data.json`.** Test only on temp copies (copy `server.py` + `seed_data.json` + `static/` to `/tmp`, run there). The server auto-reloads on `server.py` edits and re-runs `_migrate` on live data — be aware saving the server file reshapes live data.
- **There can be NEVER a duplicate LOT no.** Enforced server-side; keep it that way.

### 🗄️ Architecture now: SQLite document store (replaced the single JSON blob)
- Store is **`mvp/data.sqlite`**. Each logical table = rows of `(id TEXT PRIMARY KEY, data TEXT JSON)`; `_kv` holds settings + `_seq`. `data.json` is imported once on first run then ignored.
- **Scalability for ~150 concurrent LAN users:** targeted **per-row writes** (snapshot-diff, not full-file rewrite), **gzip** responses, **ETag/304** caching, SQLite `busy_timeout`, and **patch-in-place** on the client (`API.save/del` patch the local `DB` + row instead of reloading everything). `patchLocalRow`/`removeLocalRow` in `app.js`.
- **Heavy tables excluded from `/api/db`:** `recipes` (≈60k dye recipes), `activityLog`, and `challans` are NOT sent in the bulk snapshot — they load on demand (`challansLoad` op, recipe lookups). `_sanitized(db)` strips password hashes AND blanks `activityLog`/`challans`.
- **Default pagination:** big tables load **200 rows** then stop (infinite-scroll in the modal for the rest).
- **Port fallback:** `_bind_server()` tries the preferred port then falls back through `8090,8000,5000,3000,8081,8888` on Windows **WinError 10013** (port blocked/reserved).

### 👤 Per-page view + edit permissions, single-session, operators-as-users
- Roles now carry **`perms`** (which pages you can *view*) and **`edit`** (subset you can *change*). Server helpers `_edit_perms_for`, `_need_edit`; every mutation is `_need_edit`-gated (403 otherwise). Legacy roles default `edit == view`.
- **One active session per user** — a new login drops the previous device's token (logs it out).
- **Operators are login users:** they sign in with username + **PIN** (`operators` table, `pin` compared with `hmac.compare_digest`), get a role + page access like any user. (PINs are intentionally cleartext for now — hashing them is a deferred nicety.)
- Admin default password unchanged: user **ADMIN** / see `mvp/README.md`.

### 🎨 Shade colour engine (custom hex → family/tone)
- A shade recipe can take a **custom hex**; `app.js` converts hex → **L\*a\*b\*** and derives **family + tone** automatically so swatches and light→dark ordering still work. "Sync" sets each shade's `program` to its recipe name.

### 📇 Lot import (new EMPIRE/DyeingSM CSV format) + de-dup + idempotent guard
- **The lot number is `DESPNO`** (not the column literally called "LOT"), and per-taka meters come from **`TakaPendingMts`**. `LotPcs`/`LotMts` are read as cross-check reference.
- **EMPIRE emits one row per process step**, so a taka repeats many times — the importer **records each taka once** (dedup) and is **idempotent**: it hashes content to a stable id and checks whether an entry already exists before adding, so re-running the same import never creates duplicates or extra entries.
- **"Clear all lots"** exists but was **moved into Admin → Settings → Data maintenance** (`clearAllLots()`), off the main toolbar. It's admin/edit-gated and logged.

### ⚙️ Operations / batch changes
- **25 kg batch capacity tolerance** — `capTolerance` so a load slightly over `capMax` isn't falsely blocked.
- **Dye recipes got a `machine` field (JET / JIGGER);** `dyeStepOf()` = JET if set else JIGGER. `recipeCreate` op builds a recipe (with machine) from a lot; a **"Create Dye Recipe"** button seeds it.
- **Schedule cursor modal** no longer shows the M/C field.
- **Batch planner:** drag-to-reorder rows, a **rightmost per-batch notes** column (`mp_remarks`), and **hold-to-save (3 s press)** to commit a reordered sequence (`mpHoldStart`/`mpCommitOrder`) — avoids accidental saves while dragging.
- **History page** (past/completed batches) was built then **moved into Admin**, permission-gated (`history`).
- **Import + Export** were **combined into one "Excel" dropdown button** (`dataMenu`) instead of two separate buttons, on every page.

### 📨 Mill-challan email → PDF → ERP pipeline (the big new subsystem)
Connected mailbox **osbyrel@gmail.com**. Flow: weaver emails a **challan PDF** → we ingest it as an **"inward-pending"** record → ~1 week later EMPIRE issues the **lot no.**, and we **auto-match** the challan to the new lot.

- **`mvp/challan_watch.py`** — Gmail **IMAP** poller. Reads creds from `secrets.local.json` (`gmailUser/gmailAppPassword/gmailFolder/gmailFromFilter/gmailSinceDays` default 5`/gmailPollHours`). Searches a **SINCE date window** (read *and* unread, `BODY.PEEK` so it doesn't mark mail read), dedups via `processed.txt` + attachment SHA-1, writes one JSON per challan to `inbox_challan/`, logs to `challan.log`, prunes stored PDFs to the newest 200. All IMAP/connection errors caught and reported clearly.
- **`mvp/challan_parser.py`** — **position-based** `pdfplumber` parser (not blind text-split). Builds a column map from the header words' x-centres, extracts labelled fields, and **self-validates each page against the document's own TOTAL TAKA / TOTAL METER control totals**. Layout facts learned from real challans: two shade columns = **OWN SHADE + TO SHADE**; "Process" text = **"Dyeing / RF"**; customer names like **INDIGO**; **one page = one lot**; a taka **weight > 2 kg is real** (`REAL_WEIGHT_MIN=2.0`). Validated 32/32 pages on sample `CHALLAN_R00085`.
- **Server ingestion:** `_challan_watcher` polls the `inbox_challan/` folder every **45 s** and `_apply_challan` writes each as a challan row with `status:"inward-pending"`, `weaverChallanNo = packingListNo` (challan no. starting **ML…**), stable id `CH-<hash>-<n>`.
- **Server also re-checks the mailbox itself every 2 hours:** `_challan_email_scheduler` runs `challan_watch.py` as a **subprocess** every `gmailPollHours` (default 2; **0 = off**) so the main server stays dependency-free. (Added because the poller only picked up new mail on restart otherwise.)
- **Reconciliation `_cl_match(c, lot)`** (quality-bucketed for O(challans + lots)): a challan links to a lot **only if ALL of** — quality matches, **pcs exact**, **total meters** (`abs ≤ max(2, 1%)`), **and per-taka sorted meters** (`abs ≤ max(3, 5%)`). It **auto-links only when exactly one lot matches** (refuses ambiguous), and never falls back to the looser quality+pcs test. On link it fills the lot's weight only if empty and enriches it. This tightening came after a bug where matching on quality+pcs alone **stuck challans to the wrong similar lots**.
- **UI:** challans are reached via an **"Inward pending" button inside Lots Master** (not a left-nav item). Inward-pending rows are highlighted a **slightly greyer** colour; linked = green. `_migrate` upgrades old `status:"received"` challans to `inward-pending` and backfills `weaverChallanNo`/`lotId`.
- **Quality-merge guardrails:** an earlier "auto-track width variants" feature accidentally merged *everything* to "5 STAR". The dangerous auto-tick was **removed**; `qualitiesMerge`/`qualitiesDedupe` now show an **impact preview + typed "MERGE" confirm** for risky merges (>4 qualities or >20 lots), and width-suffix dedup (`_normalize_quality` strips trailing `" NN INCH"`) is per-group and safe.
- Docs: `mvp/docs/CHALLAN_EMAIL.md`.

### 🧾 NEW this session — Sales console (`mvp/static/sales.html`)
A **third top-level console** alongside Operations and Admin. Header nav on all three is now **Operations | Sales | Admin**.
- **Tab 1 "Sales"** = the order-entry form **moved out of Operations** (the old Operations "Sales" tab, `v-order`, and its `addShadeLine/refreshShadeSelects/shadeOptions/submitOrder` functions were removed from `index.html`; `sales.html`'s copy of `submitOrder` drops the `draw()`/`S` Gantt dependencies that lived in `index.html`).
- **Tab 2 "Order status"** = an **18-column tracker** over `DB.lots`: Date (`inDate`), Lot no. (`id`), Challan (`weaverChallanNo`), Pcs (len takas), Mtr (sum takas), Weight, Quality, Shade (`toShade`), Design no., Party (`customer`), Scouring/Poly-dyeing/Cotton-dyeing/Finish dates, **Process time (finish−scour)**, **Lead time (finish−in)**, **Age (today−in, or finish−in if finished)**, Remark. Search + newest-first sort.
- **Editable manual fields** (`designNo, toShade, scourDate, polyDyeDate, cottonDyeDate, finishDate, orderRemark`) via a per-row Edit modal → new server op **`orderStatusSave`** (whitelists exactly those keys, gated by `_need_edit(("op_orderstatus",))`, 404 on unknown lot). Verified with a live temp-server smoke test: whitelist honoured (an injected `hackField` was rejected), 404 on bad lot.
- **Permissions:** new page key **`op_orderstatus`** added to server `ALL_PAGES`; `op_order` + `op_orderstatus` appear in Admin → Roles under a new **"Sales"** group (`PAGES` in `admin.html`). A role with neither sees a "No sales access" message.

### 🚚 Deployment gotcha (recurring — READ THIS if "the new feature isn't showing at the factory")
The factory PC runs a **stale copy** unless you do all of: **(1)** `git pull` in a terminal, **(2)** fully **close the server window and re-run `start_server.bat`** (a running Python process keeps serving old code even after the files change), **(3)** hard-refresh the browser **Ctrl+F5** (static files are cached). The in-app "update" button can't pull a **private** repo without stored GitHub creds. Symptom seen this session: an op returned `403 "no edit permission for None"` purely because the *running* server predated that op. Offered but not yet done: make `start_server.bat` do a clean **pull + restart** itself.

### Still pending / offered, not built
- Make `start_server.bat` do pull-then-clean-restart; make the in-app updater work for the private repo.
- Hash operator PINs (currently cleartext, intentional).
- Lazy-load `lots` + `shadeRecipes` off `/api/db` (Phase 2 of the scale work).
- "Undo last merge" safety net for the quality merge tool.
- Push of the two local commits (`a48a802` Sales console + the prior challan-scheduler commit) — the sandbox can't reach GitHub, so **the owner pushes from their own terminal**.

## Update — 20 Aug 2026 (perf: in-memory DB cache + batched PLC writes; camera scan rebuilt on QR + Gemini)

### 28. Performance: `load_db()` no longer re-reads SQLite on every request
Every GET/POST — including trivial ones like `changePassword`/`savePrefs`/`batchStatus` — was calling
`load_db()`, which did a full read of every SQLite table PLUS re-ran the full `_migrate()` and
Administrator-role self-heal scans, all under the single global request lock (`LOCK`), which
serializes every request in the app. Fine at demo scale; a real cost heading toward the ~150-
concurrent-user target, especially since the client polls `/api/db` every 4s per user. Now the
deserialized `db` dict is cached in-process after first load (`_DB_CACHE` in `server.py`) and kept
in sync by `save_db()`; migrate/self-heal run once per process lifetime, not on every read. Safe
because this process is the sole writer of `data.sqlite`. Verified: writes still persist correctly
across a restart, the `/api/db` ETag 304 fast-path still works.

### 29. Performance: the PLC poller no longer reloads/rewrites the whole DB per machine
`_plc_cycle()` (the 10s jet-temperature poll) used to do a separate `load_db()`+`save_db()` **per
machine** inside its loop — N jets with PLC tables meant N full lock/reload/rewrite cycles every
10 seconds, competing with live user requests. MySQL reads still happen outside the lock (unchanged),
but all machines' readings are now applied in **one** load+save per cycle. Verified with a 3-machine
mock cycle: `save_db()` called once (was 3), all three machines' `plcLive` updated correctly.

### 30. Camera scan rebuilt: QR handoff from desktop + Gemini API (replaces the old phone-login flow)
The local on-site vision model plan (Ollama on an iMac) didn't work out in practice, so the reader
is now the **Gemini API** — the one deliberate outbound-internet call this app makes; everything
else stays LAN-only. The whole capture/review workflow also moved from "log into the phone app and
do everything there" to a **QR handoff**:

- **Operations → Batch planner** gained a **camera** button (`mp_camera_btn` in `index.html`,
  gated on `canEdit("op_scan")`). Clicking it calls `scanSessionStart` and shows a QR code (rendered
  client-side with the vendored `qrcode-generator` library, `static/vendor/qrcode.js` — MIT, no
  server dependency, matches how `xlsx.full.min.js` is vendored) encoding
  `location.origin + "/scan_upload.html?t=<token>"`.
- **`static/scan_upload.html`** — new, self-contained, **no login**. The token in the URL is a
  short-lived (20 min) bearer credential for that one session only. Same left-page/right-page
  "spread" capture UX as the old phone flow (downscale to 1600px / JPEG q0.72 client-side, same as
  before), but sends photos via three new **token-authenticated** ops
  (`scanUploadPair`/`scanTokenInfo`/`scanSessionFinish` — validated by token, not by cookie/login,
  special-cased in `do_POST` ahead of the normal auth block) instead of doing the read+review+commit
  on the phone itself.
- The desktop polls `scanSessionStatus` every 3s while the QR modal is open; as soon as the phone
  signals it's done (or the link expires with unread photos on it), the desktop **automatically**
  calls `scanSessionRead` (Gemini, run outside the global lock — same reasoning the old `scanRead`
  had, since a Gemini call can take tens of seconds) and switches into the review screen — the user
  never has to click "check for photos."
- **Review/edit/apply now lives on desktop** (`app.js`: `scanQr*` functions), ported near-verbatim
  from the old phone-side `m.js` reviewer (same amber-flag-unknown-lot/quality/shade/machine logic,
  same field editing) — just retargeted from `shell()`-per-page rendering to a `.modal-bg` (the same
  modal pattern as the PLC-live and change-password modals). `scanSessionApply` (replaces the old
  `scanCommit`) creates the batches and archives the session's photos into `program_scans/` exactly
  as before; `programScans`/`scansList`/`scanDelete`/Admin's "Program scans" panel are unchanged.
- **Ownership is enforced server-side**: every `scanSession*` desktop op checks
  `session.createdBy == caller.username` — only the person who opened the QR code can see or apply
  what lands on it, even though the phone that uploaded needed no login at all.
- New `scanSessions` table (short-lived; stripped from `/api/db` like `activityLog`/`challans` — it
  carries bearer tokens) + `scan_sessions/<id>/` working-photo directory, garbage-collected
  (`_scan_sessions_gc`) on each new session start: sessions past their 20-minute TTL flip to
  `expired`, and applied/cancelled/expired sessions older than an hour are dropped along with their
  files.
- **Removed entirely** (per owner's call — QR replaces it, not adds to it): the phone `/m` app's
  **Scan** tab and all `scan*`/`sp-*` functions in `m.js`/`m.css` (`op_scan`'s old phone route),
  `_ollama_extract`/`_vision_cfg` in `server.py`, and the old `scanRead`/`scanCommit` ops.
  `secrets.local.json`'s `vision` block is replaced by a `gemini` block (`apiKey`, `model` — default
  `gemini-2.0-flash`, `enabled`, `timeoutSecs`). `SCAN_SETUP.md` rewritten for the new flow.
- The `.scan-*`/`.sp-*` CSS moved from `m.css` (mobile-only) into `style.css` (shared) since both
  `scan_upload.html` and the desktop review modal use it now; icons switched from `m.js`'s inline-SVG
  `svg()` helper to the standard `.material-symbols-rounded` ligature spans, per the design skill
  ("one icon family, everywhere").
- Verified end-to-end with a scripted smoke test against a temp copy of the server (monkeypatched
  Gemini call): session start → token upload (including a left-page-only spread) → status →
  finish → read (twice — second call correctly finds nothing unread) → apply → batch created,
  session files cleaned up, photos archived into `programScans`, and `scanSessions`/tokens
  confirmed stripped from the `/api/db` payload.

⚠ Not done / left for the owner: Gemini API pricing and rate limits weren't sized against real
scan volume — worth watching usage on https://aistudio.google.com/ once this is in daily use.
