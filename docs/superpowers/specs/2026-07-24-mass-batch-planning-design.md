# Mass Batch Planning + Taka-wise Selection — Design

**Date:** 2026-07-24
**Status:** Approved design → ready for implementation plan
**Area:** Operations → Batch maker (`static/index.html`, `static/app.js`, `static/style.css`; `server.py` for new fields + audit)

---

## 1. Problem

Creating a day's plan today means opening the single-batch form once per batch. With ~25 jets × 4–5 batches each (100–125 batches/day), that takes ~6 hours and gets worse as machines are added. There is no way to see or edit the whole plan at once, no explicit machine-load sequence, and takas are auto-picked rather than chosen — but on the floor, specific takas are hand-selected from multiple lots per batch.

## 2. Goals

- Enter and edit an entire day's plan (100+ batches across all machines) from one scrollable, table-driven screen.
- Assign each batch to a specific machine and give it an explicit load **sequence** for the day, editable at any time.
- Let the operator hand-pick **specific takas** from each lot in a batch.
- Organize plans by **Day** (label only) for history and next-day planning, on a floor that runs 24/7 continuous.
- Reuse the existing batch data model, Gantt, floor board, audit log, and Excel export — additive, not a rewrite.

## 3. Non-goals (parked)

- **Auto-scheduling.** The greedy campaign scheduler (`computeSchedule` — light→dark campaigns, auto-wash, capacity auto-split) stays in the code but no longer drives the plan. Planning is **fully manual**; the plan is exactly what the table says. Revisited later.
- Livewire / EMPIRE integration and offline fonts are separate workstreams with their own specs.
- No calendar/time-of-day scheduling per batch — sequence is an ordering, not a clock time.

## 4. Planning model

**Fully manual.** A batch's position in the plan is defined by three fields on the batch record:

- `machine` — the assigned machine id (e.g. `JET-2`). Promotes today's optional `mcPin` (dye-step pin) to the definitive machine assignment in manual mode. `mcPin` is kept as an alias for back-compat; `machine` is the field of record.
- `planDay` — a plain day label (ISO date string, e.g. `2026-07-24`). Groups batches for a day; the floor does not stop at day boundaries. Default = today.
- `seq` — integer position within (`machine`, `planDay`). Each machine restarts at 1 each day.

The Gantt and floor board render batches in (`machine`, `planDay`, `seq`) order instead of calling the auto-scheduler for assignment. Route/duration math (`routeOf`, handling time, stentor speed) is still used to compute each batch's *length* so the Gantt blocks keep their real widths — only machine choice and ordering move from algorithm to operator.

## 5. Screens

### 5.1 Mass Batch Planning (new)

A new full-width Operations tab (`op_massplan` permission, mirroring the existing `op_batch`/`op_storage` tab pattern). Layout:

- **Toolbar:** Day selector (Today · date picker · Next day · past days for history), a machine/quality filter, batch/kg/m totals for the selected day, and an Export button.
- **Per-machine section:** every machine is a section with a sticky header showing machine id, type icon, capacity (`capMax`), and that day's queued totals (batch count · kg · m). Machines are listed even when empty.
- **Batch rows** under each machine, in `seq` order. Columns: `Seq` · `Batch` · `Quality` · `Shade` (swatch + no.) · `Lots · takas` · `Pcs` · `Mtr` · `Kg` · `Status` · actions (adjust takas, remove). All rendered in the REL navy design system (mono for numbers/ids, status pills, shade swatches) per the `rel-dyeing-design-insight` skill.
- **Sequence editing:** drag a row by its grip handle to reorder within its machine (renumbers `seq` automatically); or edit the `seq` number directly. Reordering is scoped to one machine+day.
- **Inline add-batch row** at the bottom of each machine section: pick quality → shade → add lots → pick takas; on save the batch is created already assigned to that machine and day with the next `seq`. Empty machines show a one-line "click to add" affordance.
- **Inline edit:** quality, shade, machine (move a batch to another jet), and takas are editable in place. Moving a batch to another machine appends it to that machine's day queue (next `seq`); its old machine's rows renumber to close the gap.

### 5.2 Taka picker

Reachable from any lot row inside a batch (both the new inline add and the legacy single-batch form). Flow: **add the lot(s) to the batch first, then pick takas within each lot** (confirmed workflow).

- Opens a picker listing that lot's takas as chips: `T{takaNo} · {meters}m`. Takas already consumed by another batch are shown greyed/disabled (using the existing `_lotAllocMap`/`lotRemainingTakas` allocation data, extended to taka-number granularity).
- Ticking takas sets the batch lot-row's `takas[]` (lengths) and `takaNos[]` (the selected Sr. Nos.); `pcs`/`mtr`/`weight` recompute from the selection.
- The existing auto-pick (`pickTakas(pool, target)`) remains as a "fill to target meters" shortcut button inside the picker, but manual ticking is the default.
- Selected Sr. Nos. surface in the row detail (e.g. `LOT-0003 · T1,T2,T3,T4,T5,T6`) and flow into the Excel export.

## 6. Validation (reused + adjusted)

- **One fabric per batch** — unchanged (`sameFabric`/`fabricGroup` check).
- **One customer per batch** — unchanged.
- **Whole takas only** — unchanged; a batch is whole takas, now hand-selected.
- **Capacity:** in manual mode, if the selected takas exceed the assigned machine's `capMax`, show an inline warning and **block the save** (operator removes takas or moves to a bigger machine). The old automatic oversize-split (`splitBatchRows`) is **not** applied in Mass Planning — it would fight the operator's explicit machine choice. Auto-split stays only in the legacy single-batch form.
- **Allocation:** a taka can be in at most one batch (existing duplicate-lot guard extended to taka-number level).

## 7. Server changes

- Register the new `batches` fields (`machine`, `planDay`, `seq`, `takaNos` per lot row) — the JSON store is schemaless, so this is mostly ensuring upsert accepts and persists them; no migration needed for new records. A `_migrate` pass can default existing batches to `planDay = createdAt date`, `machine = mcPin`, and assign `seq` by creation order per machine.
- New page-permission key `op_massplan` in `ALL_PAGES` and the Administrator role sync.
- Reordering and inline edits go through the existing authenticated `upsert` op, so the **append-only `activityLog`** already records who changed a plan and when. A small batched-reorder helper may write one `update` per moved row (acceptable at ~5 rows/reorder) or a single reorder op if volume warrants — decided in the plan.
- Traceability fields stay server-stamped (per existing house rule); `seq`/`machine`/`planDay` are operator data and may come from the client.

## 8. Gantt / floor board

`batchesForSchedule()` already drops `done` batches. Extend the render path to order by (`machine`, `planDay`, `seq`) and lay blocks head-to-tail per machine using computed durations, instead of the greedy assignment. The now-line, wall-clock axis, and re-anchor behavior are unchanged. Day filter on the board optional (default: show current + future days).

## 9. Testing

- VM-context harness (jsdom still not installable in the sandbox, per handoff): reorder renumbers correctly; moving a batch between machines closes/opens gaps; taka selection sums to pcs/mtr/weight; over-capacity blocks; allocation prevents double-booking a taka.
- Live `curl` against `server.py`: new fields persist through upsert; `activityLog` captures reorders; permission `op_massplan` enforced (403 without it).
- Regression: legacy single-batch form still creates batches (with `machine`/`planDay`/`seq` defaulted); existing batches render after `_migrate`.
- Manual: enter a ~20-batch day across 3 machines, reorder, hand-pick takas, export, confirm the Gantt reflects the manual order.

## 10. Open questions / future

- Bulk "duplicate yesterday's plan to today" as a fast start for the next day (likely a strong follow-up once Days exist).
- Whether the legacy single-batch form should eventually be retired in favor of Mass Planning (keep both for now).
- Copy/paste or Excel-paste bulk entry into the table (future accelerator).
