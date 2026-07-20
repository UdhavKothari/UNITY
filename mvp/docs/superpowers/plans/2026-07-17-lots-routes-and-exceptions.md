# Lots, 4-Step Routes & Exceptions — Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use `- [ ]` checkboxes.

**Goal:** Extend the REL Dyeing ERP from a route-of-3 scheduler with ephemeral batches into a traceable production system: 4-step machine routes, persisted batches built from **lots**, immutable system IDs, auto maintenance, richer masters, and the urgent/redye exceptions.

**Architecture:** The pivotal change is that **batches stop being ephemeral**. Today `computeSchedule()` invents batches on every render, so nothing can attach to them (no notes, no QC result, no lot composition, no stable ID). We make batches **persisted records** assembled from **lots**, and the scheduler then *schedules existing batches* rather than inventing them. Everything else (notes, gantt hover detail, redye, urgent) hangs off that.

**Tech stack:** unchanged — Python stdlib `server.py` + JSON store, vanilla JS front end (`app.js`, `index.html`, `admin.html`), design per `skills/rel-dyeing-design-insight`.

## Global constraints
- Design must follow **REL_DYEING Design Insight** (light navy tokens, Inter + IBM Plex Mono, Material Symbols, vat-fill instrument, `t+` time convention, motion with reduced-motion fallback, no side-stripes).
- **Mill runs 24/7 continuous** — no shift calendar.
- Any system-generated number (Order ID, Batch ID, Lot No) is **immutable and server-generated**.
- No backend framework may be added; keep zero-dependency.
- Every phase must leave the app working and shippable.

---

## Phase 0 — Immutable system IDs (change #3)

**Files:** `server.py`, `static/admin.html`

- [ ] Add a server-side sequence helper `next_id(db, table, prefix)` that reads `db["_seq"][table]`, increments, saves, and returns e.g. `SO-00042`, `B-00117`, `L-00305`.
- [ ] In `do_POST` upsert: if the row already exists, **force-keep the stored `id`** (ignore any client-sent id). If new, always assign via `next_id` — never trust a client id for `orders`, `batches`, `lots`.
- [ ] In `SCHEMAS`, mark `id`/`orderId` fields `readonly:true`; in `fieldInput()` render readonly fields as a mono, disabled display (not an input). Remove `id` from the editable Orders form.
- [ ] Verify: `curl` an upsert attempting to change an existing order's id → the stored id is unchanged; the admin Orders form shows the ID as non-editable text.

## Phase 1 — Four-step quality routes (change #1)

**Files:** `server.py` (seed + migration), `static/admin.html` (Qualities schema), `static/app.js` (scheduler)

Quality Master gains an explicit 4-step route, matching the original design (`RAW_PLAN.md` page 1):

```
step1_mc, step1_time, step2_mc, step2_time, step3_mc, step3_time, step4_mc, step4_time,
dyeStep (1-4, which step is the dyeing step), maxBatch, gsm, width
```

- [ ] Migrate existing qualities: `step1 = pt_mc1/time_req1`, `step2 = pt_mc2/time_req2`, `step3 = dyeType/dyeMins` with `dyeStep=3`, `step4 = "stentor"/finishMins`. Keep old keys readable for one release, then drop.
- [ ] Rewrite `computeSchedule()` to walk **steps 1..4 in order** per batch: each step picks the earliest-free machine of that step's type; a step can't start before the previous step ends. The step whose index == `dyeStep` additionally applies the **campaign rules** (light→dark by tone, auto-wash on family change or tone drop) and the min-load check. All other steps are simple earliest-free.
- [ ] Every step reserves handling (`loadMin + unloadMin`) on top of its step time.
- [ ] Verify: a quality routed drum → jigger → jet(dye) → stentor produces four blocks per batch in the right order, stentor always after the dye step, no overlaps, no tone drops without a wash.

## Phase 2 — Lots + persisted batches + manual Batch Creator (planning Q1 & Q2)

This is the foundation for changes #4, #5 and #9.

**New table `lots`** (created at goods-inward, immutable `id`):
```
id (L-#####), challanNo, inwardDate, supplier, quality, shade (optional/earmark),
pieces (takas), meters, kg (weighed), areaId, shelf, row, col,
status: in-stock | allocated | consumed, orderId (optional earmark), notes
```

**New table `batches`** (persisted; replaces the ephemeral split):
```
id (B-#####), orderId, quality, shade, familyCache, toneCache,
lotIds[] (max 8), pieces, meters, kg, status: planned | running | done | qc-hold | redye,
urgent (bool), notes, parentBatchId (for redyes), createdBy, createdAt
```

- [ ] Add both tables + migration (empty arrays) and their admin schemas (Lots under **Store & stock**, Batches under **Production**), with `lots`/`batches` added to `ALL_PAGES` and the Administrator role.
- [ ] Build the **Batch Creator** (manual for now): pick quality + shade → the screen lists `in-stock` lots of that quality → tick up to **8 lots** → a live **vat-fill** shows accumulated kg vs the target machine capacity (reuse the design system's vat instrument) → Save creates the batch, sets those lots to `allocated`, and stamps pieces/meters/kg as the sum of the chosen lots.
- [ ] Enforce: max 8 lots per batch; refuse below the 300 m minimum load with a clear inline message; a lot can only belong to one open batch.
- [ ] Change `computeSchedule()` to consume `DB.batches` (status `planned`/`running`/`redye`) instead of splitting orders. Orders remain the commercial record; batches are what gets scheduled.
- [ ] Verify: create 2 batches from 3 lots each → lots flip to `allocated`, batches appear on the Gantt, and the order-wise plan shows them under their order.

## Phase 3 — Gantt hover detail + jet batch notes (changes #4, #5)

**Files:** `static/app.js` (`renderGantt`), `static/style.css`, `static/admin.html`

- [ ] Replace the native `title` tooltip with a **hover card** (positioned `fixed`, escapes the scroll container) showing for the hovered block: **Lot No(s), pieces, meters, quality, shade no, in time (t+), out time (t+)**, plus batch ID and machine.
- [ ] Card follows the design system: white surface, 14px radius, soft shadow, mono for numbers/IDs; fades in 150 ms with a reduced-motion fallback.
- [ ] Add a **Notes** panel on the batch record — free text, timestamped, author-stamped — surfaced prominently for batches whose dye step is a **jet** (jet dyeing needs batch-specific instructions). Show a `sticky_note_2` icon on Gantt blocks that carry notes.
- [ ] Verify: hovering a block shows all seven fields; adding a note to a jet batch shows the note icon on its block and the text in the hover card.

## Phase 4 — Masters: auto maintenance, chemical units, customer fields (changes #2, #6, #7)

**Files:** `server.py` (seed/migration), `static/admin.html` (schemas), `static/app.js` (floor badge)

- [ ] **Auto maintenance:** Machine Master gains `maintIntervalDays` (e.g. drum = 60). On save, and on every `load_db`, compute `schedMaint = lastMaint + maintIntervalDays` and store it **read-only** (auto-filled, not typed). Show a `build` badge on the machine's floor card when due within 7 days, and a red `maint` pill when overdue.
- [ ] **Aux chemicals with units:** `qualityRecipes` aux entries become objects `{name, qty, unit}` with `unit ∈ {"%", "g/l"}`, up to 20 rows. UI = repeatable rows (name / qty / unit dropdown), same pattern as the order form's shade rows. Migrate existing free-text aux strings into `{name: <text>, qty: "", unit: "g/l"}`.
- [ ] **Customer fields:** add `gstNo`, `officeAddress`, `deliveryAddress`, `email`; migrate the old single `address` into `officeAddress`. Group the form into *Identity / Contact / Addresses*.
- [ ] Verify: editing `lastMaint` auto-updates `schedMaint`; an overdue machine shows the maintenance pill; a chemical saved as `2.5 %` renders as `2.5 %` and one as `40 g/l` renders correctly; customer form shows both addresses + GST + email.

## Phase 5 — Exceptions: urgent flag & redye (changes #8, #9)

**Files:** `server.py` (permission + scheduler inputs), `static/app.js` (sort), `static/admin.html`

- [ ] Add page/permission key **`urgent_flag`** and a **Master** role (department head) seeded with it. Only roles holding it may set/clear `urgent` on a batch — enforced server-side on upsert (reject the field change with 403 otherwise), not just hidden in UI.
- [ ] Batch gains `urgent`, `urgentBy`, `urgentAt`. Scheduler dispatch order becomes: **urgent → priority → due → family → tone**. Urgent batches render with a `priority_high` icon and a red accent chip on the Gantt and floor card.
- [ ] **Redye:** QC records a result per batch (`pass` / `fail` + reason). On `fail`, offer **Send for redye**: creates a new batch with `parentBatchId` set, same lots, status `redye`, routed **straight to the dye step** (skips completed pre-treatment steps), inheriting urgent if set. Original batch moves to `qc-hold`.
- [ ] Verify: a non-Master user is refused (403) when setting `urgent`; an urgent batch jumps the queue on the Gantt; a QC fail produces a linked redye batch that schedules on a jet without repeating pre-treatment.

## Deferred (explicitly parked)
- **Shade-change exception** — process not yet defined. **Reminder owed to the user before starting Phase 5.**
- Real-time now-line on the Gantt, empty production seed, Export/Backup, first-run checklist (from the earlier ship-ready plan) — still pending and independent of this plan.

## Self-review
- Coverage: #1 P1 · #2 P4 · #3 P0 · #4 P3 · #5 P3 · #6 P4 · #7 P4 · #8 P5 · #9 P5 · Lot system P2 · manual batch creator P2. Shade change explicitly deferred. ✓
- Dependency order is correct: IDs (P0) → routes (P1) → persisted batches/lots (P2) → things that attach to batches (P3, P5). ✓
- Naming consistency: `lotIds`, `parentBatchId`, `dyeStep`, `maintIntervalDays`, `urgent_flag` used identically across phases. ✓
