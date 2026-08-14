# REL-UNITY — Workflows, Batches & Process Types — Design

**Status:** approved-pending-review · **Date:** 2026-08-14

Design for five connected changes: (1) restricted batch edit, (2) lot-numbers-everywhere,
(3) the new batch-id scheme, (4) the visual workflow / process-node system, (5) jigger pooling.
Produced through the brainstorming flow; a clickable prototype (`rel_unity_flow_builder.html`)
accompanies §5.

## Confirmed decisions

- **Every quality runs exactly one workflow.** The workflow replaces `step1–4_mc/time` on the quality.
- **Fabric groups are the assignment lever.** A flow (and default node times) is assigned to a fabric
  group; all qualities in that group inherit it, with per-quality overrides. This avoids 570 manual assignments.
- **A "batch" is one machine-type operation,** not a whole lot journey. A lot moving Jet → Stentor
  produces a jet batch and a stentor batch (different sizes, different planning logic).
- **v1 supports branching / joins** (a DAG). Blends (poly path + cotton path merging before Stentor) are
  real, and a DAG handles linear chains as a subset.
- **Times are per-quality,** seeded from the fabric-group default, editable per quality.
- **Process types are user-editable,** each carrying its own batch-id letter and pooled/per-machine flag,
  so new machine types need no code change.

## Grounding (live SQLite)

570 qualities carry `step1–4_mc/time` + `dyeStep` (being replaced); only jets are real machines
(JET-01..03); jiggers are not machines; the `batches` table is empty → points 1–3 carry **zero migration risk**.

## 1. Data model

New/changed tables, all `(id, data-json)` blobs like the rest of the store.

**processTypes (new)** — catalog behind the palette + batch-id letters:
`{ id, name, machine, icon, letter, pooled, defaultTime }`
`machine` → a machines row/type (jet|jigger|stentor|heatset|…); `pooled=true` → global counter, no machine no.

**workflows (new)** — graph shape only, no times:
`{ id, name, nodes:[{id,kind,proc?}], edges:[{from,to}], assignedTo:[fabricGroupId] }`
`kind`: input | proc | output. A DAG with one output node, ≥1 input nodes, joins allowed.

**fabricGroups (new)** — assignment + time defaults:
`{ id, name, workflowId, defaultTimes:{ processTypeId: minutes } }`

**qualities (changed)** — add three fields; keep `step1–4_mc/time` until cutover, then drop:
`+ fabricGroup, + nodeTimes:{ workflowNodeId: minutes }` (workflow is resolved via the group; a per-quality
`workflowId` override is allowed but not required).

**batches (new shape)** — one machine-type operation:
`{ id, processType, machine?, lots:[{lotId,takaNos:[…]}], shade, weightOverride, status, seq, … }`
`pcs = count(takaNos)`, `meters = sum(selected takas)` — derived, never the source of truth.

## 2. Batch-id generator (data-driven)

`B` + `letter` + `machineNo?` + `seq` + `/MMYY`. Letter and pooled/per-machine come from the processType.

- **Per-machine (Jet):** `BT05200/0826` — jet 05, its 200th that month, Aug 2026. Counter key `(letter, machineNo, YYYYMM)`, resets monthly (3 digits covers ~240/machine/month).
- **Pooled (Jigger):** `BR200/0826` — no machine no., one shared monthly counter key `(letter, YYYYMM)`.

Counters live in the existing `_seq` store. Default letters (all editable in the process-type editor):
Jet `T` per-machine, Jigger `R` pooled, Stentor `S` pooled, Heat-set `H` pooled, Zero `Z` pooled.
**Batch ids appear only in admin/master detail views — never on operator screens.**

## 3. Restricted batch edit (data operator)

The lot is immutable. The data operator edits batch composition only:
taka selection (drives pcs + meters), shade, and weight (override, since weights are unreliable).
Pcs/meters are derived and read-only; quality and lot number are locked. Server accepts only
`{takaNos, shade, weightOverride}` from the data-operator role (mirrors the urgent-flag master check);
masters edit everything. Reuses the planner's taka-allocation logic.

## 4. Lot numbers everywhere

Every operator-facing card, Gantt block, and sheet shows the lot number(s); multi-lot batches expand to
list every lot number in full (no truncation). The structured batch id shows only in admin/master detail.

## 5. Workflow builder UX

Per the prototype: a left-to-right guided graph. Fixed Greige input(s) → process nodes → one Finished-Fabric
output. Add a step by tapping a process in the left rail (appends before output) or the ＋ on any connector
(inserts mid-flow, opens a big-tile picker). Join a second input via the ＋ on a node's left edge. Each node
has a machine badge + a big time field. "New process type" creates a type (name, machine, icon, letter,
numbering) with a live batch-id preview. Built for low-computer-experience operators: big targets, icons over
words, wires auto-route (no fiddly wire-dragging), offline-proof inline-SVG icons, on the rel-dyeing design system.

## 6. Scheduling & jigger pool (Phase 4 — detailed then)

The scheduler stops reading `step1–4` and walks the workflow graph: each proc node → a machine operation with
the quality's node time; branches run in parallel; a join waits for all inputs; ST pinned last.
Assigned machines (jets) → the machine-row Gantt. Pooled machines (jiggers) → a **jigger sheet** (an ordered
to-do list operators pull from), not a machine row. 8 jiggers, 2 closed. To be detailed in Phase 4:
whether closed jiggers are reserved for specific qualities, and sheet ordering (priority vs shade-grouped to
cut cleaning).

## 7. Build order

1. **Contained, no migration** — restricted batch edit (§3) + lot-numbers-everywhere (§4).
2. **Foundations** — processTypes, fabricGroups, data-driven batch-id generator (§2); seed the process catalog.
3. **Workflow builder** — integrate the prototype into the admin/master console; build ~15–20 flows; assign via
   fabric groups; enter per-quality node times. `step1–4` kept intact.
4. **Cutover** — scheduler walks the graph; jigger sheet; retire `step1–4`.

## 8. Non-goals (deferred, noted for later)

- The richer "materials BOM" model (inputs = greige + machine + chemicals, staged greige as an intermediate
  input) — noted as a future alternative; v1 uses the process-node graph.
- Free-form drag-to-wire node placement — the guided auto-layout is the v1 interaction.
- Jigger scheduling specifics — Phase 4.
