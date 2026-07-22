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
- **Quality Quick Add: derive GSM from lot data** — when adding/updating a quality via Quick add, if GSM isn't given directly, calculate it from a linked lot's meters + weight (assuming 54" width, GSM = weight_kg × 1000 ÷ (meters × 1.3716)). Requested mid-session, deliberately deferred to land after the scale-and-storage plan.
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
