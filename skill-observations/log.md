# Skill Observation Log

Observations captured during task-oriented work on the REL Dyeing ERP. Each entry identifies a potential skill improvement or new skill opportunity.

**Status key:** OPEN = not yet actioned | ACTIONED = skill updated/created | DECLINED = user decided not to pursue

---

## 2026-07-22

### Observation 1: Verify vanilla-JS engine + DOM builders with a vm-context harness when jsdom is unavailable
**Date:** 2026-07-22
**Session context:** Building batch lifecycle / audit / taka features for the REL Dyeing ERP; needed to verify `app.js` scheduler logic and HTML-string builder functions in `index.html`/`admin.html`.
**Skill:** New skill candidate: rel-dyeing-verification (or rel-dyeing-design-insight testing note)
**Type:** internal
**Phase/Area:** Testing / verification

**Issue:** jsdom is not installable in the sandbox (npm install times out; module not found). The project's HTML is server-rendered vanilla JS with functions that return HTML strings. Rather than skip UI verification, I loaded `app.js` into a Node `vm` context with a minimal `document`/element stub, set `DB` via `vm.runInContext("DB=...")` (a `let` binding cannot be set with `ctx.DB=`), then called render functions with a fake `{innerHTML:""}` container and asserted on the produced HTML string. For inline-script functions I regex-extracted the exact function source and ran it against stubbed `esc`/`cfg`/`can`.
**Suggested improvement:** Capture this as the standard REL Dyeing UI-verification technique: (1) server + curl for the API, (2) vm-context harness for pure engine logic and HTML-string builders, (3) regex-extract inline functions when they live in HTML. Note the `let DB` gotcha explicitly.
**Principle:** When the usual UI test tool is unavailable, a lightweight vm harness over string-returning render functions still gives real coverage — assert on output strings rather than a live DOM. Verify logic, not just syntax.

### Observation 2: A full-replace settings endpoint must receive every settings key
**Date:** 2026-07-22
**Session context:** Adding a `completionMode` toggle to Admin → Settings in the REL Dyeing ERP.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Settings / data model

**Issue:** The server's `__settings__` upsert does `db["settings"] = req.get("row")` — a full replace, not a merge. The client `saveSettings()` therefore must send ALL settings keys or any omitted key is silently dropped. Adding a new setting means adding it to the save payload, not just the form.
**Suggested improvement:** Note in the design/build rules that settings save is full-replace; any new setting must be added to the `saveSettings()` payload object. Consider (future) switching the server to a merge to make this safe.
**Principle:** A full-replace persistence endpoint turns every "add one field" into a "must resend all fields" — document the contract or make the write a merge.

### Observation 3: Stamp audit/lifecycle timestamps and actor server-side, never from the client
**Date:** 2026-07-22
**Session context:** Building batch start/complete lifecycle + audit trail (`activityLog`) for the REL Dyeing ERP.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Backend / traceability

**Issue:** Batch lifecycle transitions and the audit log needed "who did it and when." I added a dedicated server op (`batchStatus`) and a `_log()` helper that stamp `time.strftime(...)` and the authenticated `u["username"]` on the server — the client only sends the target state (`to`). The activity log is also append-only (direct writes rejected 403).
**Suggested improvement:** Record as a REL Dyeing rule: traceability fields (timestamps, actor, audit entries) are always stamped server-side from the session, never accepted from the client; audit tables are append-only.
**Principle:** For any "who/when" record, the server clock and the authenticated identity are the source of truth — a client-supplied timestamp or user is unauditable.

### Observation 4: A "derive X from data" feature can be blocked by a missing field — surface the source decision, don't guess
**Date:** 2026-07-22
**Session context:** Implementing GSM auto-derivation in Qualities → Quick add for the REL Dyeing ERP.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Feature scoping / data model

**Issue:** "Derive GSM from lot data" sounds self-contained but the Lot master had no weight field, so the derivation had no input. A prior session correctly parked it with three materially-different options (add a lot field / reuse batch-row weight / inline in the paste) rather than guessing. This session the owner chose "add weight to Lot master"; GSM is now derived as kg×1000÷(meters×width) aggregated over a quality's weighed lots, with graceful fallback (typed > derived > existing > 100).
**Suggested improvement:** Record the pattern: before building a "derive/compute from existing data" feature, confirm the source field actually exists and is populated; if not, present the source options as a decision rather than picking one. Note the fallback ladder as the house style for derived values.
**Principle:** A computed field is only as real as its inputs — verify the input exists before promising the output, and make the derivation degrade gracefully when data is missing.

## 2026-08-12

### Observation 5: Refine the UI-verification technique — jsdom + live temp-server proxy, single shared eval scope, temp copies only
**Date:** 2026-08-12
**Session context:** Large REL-UNITY session (challan email pipeline, planner drag-reorder, view/edit auth, reconciliation). Verified vanilla-JS UI across many features.
**Skill:** rel-dyeing-design-insight (refines Observation 1)
**Type:** internal
**Phase/Area:** Testing / verification

**Issue:** jsdom WAS installable this session (npm install jsdom succeeded). The reliable harness: (a) start the real server.py on a TEMP COPY of mvp (never the live data.sqlite/data.json — a prior session accidentally wrote e2e data into live data.json), seeded via API; (b) load app.js + the page's inline <script> concatenated into ONE w.eval() so top-level `let DB`/`function` share scope (splitting them across evals breaks — `let` bindings don't cross indirect-eval boundaries); (c) proxy window.fetch to the temp server over Node http with a cookie jar; (d) drive real render + events and assert on DOM. Also used it to count /api/db fetches (proving patch-in-place did 0 reloads).
**Suggested improvement:** Update the verification note to prefer this jsdom+temp-server harness when jsdom installs, keep the vm-context fallback (Obs 1) for when it doesn't, and add the hard rule: test only on temp copies of mvp, never live data.
**Principle:** Real interaction coverage beats syntax checks; when the app is dependency-free HTML/JS, a jsdom harness over a live throwaway server exercises the true code path — and production data is never a test fixture.

### Observation 6: Robust semi-structured-document parser methodology (new open-source skill candidate)
**Date:** 2026-08-12
**Session context:** Built a mill-challan PDF parser (32 pages = 32 lots) whose layout the owner said WILL change.
**Skill:** New skill candidate: robust-document-parser
**Type:** open-source
**Phase/Area:** Parsing / ingestion

**Issue:** A fixed-position or fixed-line parser would break on the announced layout changes (a column renamed, a TO SHADE column added, a Process field added). The durable approach: map the table by COLUMN POSITION derived from the header row's word x-centres (so adding/renaming/reordering columns still lands values in the right field), extract header/footer fields by LABEL regex (not line number), make every field best-effort (missing → blank, never raise), and VALIDATE each record against the document's own totals (parsed roll count == printed TOTAL TAKA; summed meters == printed TOTAL METER). All 32 pages self-validated.
**Suggested improvement:** Create an open-source skill capturing this method: header-position column mapping, label-based field extraction, best-effort per-field, self-validation against in-document control totals, and a one-file parser so future format drift is a single localized edit.
**Principle:** Parse structure by relationships (headers, labels, control totals), not coordinates or line numbers — a parser that checks itself against the document's own totals tells you immediately when a format change broke it.

### Observation 7: Product renamed to REL-UNITY + new signature components — design skill is stale
**Date:** 2026-08-12
**Session context:** Rebranded the ERP to REL-UNITY (favicon/logo = stylized R) and added several reusable components.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Branding / component library

**Issue:** The design skill still calls the product "REL Dyeing ERP" and predates components added this session: (1) lifecycle row tints — a greyer tint (`--surface-3` + `--ink-2`) for staging/"inward-pending" rows and a green tint for "linked", paired with the existing status pills; (2) a drag-handle reorder that replaces up/down arrows and commits only on a 3-second hold ("hold-to-save") to prevent accidental changes; (3) a batch-remarks note icon carried into planner/Gantt. The banned "side-stripe border" was tried and correctly removed.
**Suggested improvement:** Update the skill: rename to REL-UNITY (note the stylized-R mark, navy #1f2d4d + accent #3a63c4), and add the three components above as house patterns (row-tint lifecycle states use tokens not raw greys; destructive/order-changing actions get a hold-to-confirm; keep the side-stripe ban).
**Principle:** A design-system skill must track the product's name and its growing component vocabulary, or new screens drift from the established language.

### Observation 8: Keep the runtime dependency-free; push dependencies + external I/O into helper scripts feeding an inbox, and make every importer idempotent
**Date:** 2026-08-12
**Session context:** Gmail→PDF→ERP challan pipeline and DESPNO CSV import for REL-UNITY.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Architecture / ingestion

**Issue:** The server is deliberately Python-stdlib-only (simple Windows deploy). Anything needing a dependency or external I/O — pdfplumber parsing, Gmail IMAP — lives in a SEPARATE script (challan_watch.py) that writes JSON/CSV into an inbox folder a server watcher ingests. Every importer is idempotent and self-healing: stable content-hash / source-key ids, dedup (processed.txt + server-side stable ids), "skip if already present", per-row/per-page try-except so one bad item never aborts the batch, and clear logging to a file so a flashing console never hides the error.
**Suggested improvement:** Record as REL-UNITY architecture rules: (1) the server stays stdlib-only — dependencies go in helper scripts that hand off via an inbox folder; (2) all external-source importers must be idempotent (stable ids + dedup), self-healing (isolate per-item failures), and log to a file.
**Principle:** Keeping the runtime dependency-free and funneling every external source through idempotent, self-healing, file-logging importers makes an on-prem system safe to re-run and cheap to deploy.

## 2026-08-14

### Observation 9: A table editable from a dedicated ops page must list that page in the upsert allow-map
**Date:** 2026-08-14
**Session context:** Code review of the Sales console commit (a48a802) for REL-UNITY — new op_order/op_orderstatus pages, orderStatusSave op.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Backend / permissions

**Issue:** The Sales console gates order entry with `op_order`, but the server's upsert maps `orders` → `["orders"]` only. A role granted the Sales pages (`op_order`/`op_orderstatus`) but not the Admin `orders` page therefore gets `403 "forbidden: no edit permission for orders"` when clicking "Log order". The established pattern maps such tables to BOTH keys (`batches` → `["batches","op_batch"]`, `storageSlots` → `["storageSlots","op_storage"]`); `orders` was missed when `op_order` became the order-entry permission. Same gap in the `bulkUpsert` map.
**Suggested improvement:** Record a REL-UNITY backend rule: whenever a table is writable from a non-admin ops page, add that page to BOTH the `upsert` and `bulkUpsert` table→page allow-maps. Audit both maps whenever a new `op_*` page is introduced. Concretely: `orders` → `["orders","op_order"]`.
**Principle:** A page permission that gates a form must also authorize the underlying table write, or the UI invites an action the server then rejects.

### Observation 10: Render the server-assigned id after create, never the client's provisional id
**Date:** 2026-08-14
**Session context:** Same Sales console review; submitOrder confirmation panel.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Frontend / data integrity

**Issue:** `submitOrder()` builds a provisional client id (`"SO-N"+(1000+DB.orders.length)`) and shows it in the success panel + toast. But `orders` is a SYSTEM_IDS table, so the server discards the client id and assigns `_next_seq_id` (`SO-000x`). The confirmation therefore reports an id that does not exist in the DB. The array-length derivation is also collision-prone in principle (reuses ids after a delete), though the server reassignment masks it here.
**Suggested improvement:** After `API.save`, render `res.row.id` (the authoritative id) in any confirmation UI; never derive an id from array length. Add to the house rules for create flows.
**Principle:** When the server owns id allocation, the client must echo the returned id — a locally-guessed id shown as fact misleads the operator.

### Observation 11: Per-user UI preferences need a self-service own-record op and must ride /api/me, not the /api/db snapshot
**Date:** 2026-08-14
**Session context:** Added per-user saveable column widths to the Sales → Order status table (REL-UNITY).
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Backend / per-user state

**Issue:** Users on shared factory PCs each want their own table sizing, so per-browser localStorage is wrong (it collides between users on one machine). The right home is the user's own account record. Implemented as a dedicated `savePrefs` op that writes only to the authenticated caller's own record (`u["prefs"]`) with NO page permission required (self-service, like changePassword), size-capped and dict-validated. Prefs are surfaced to the client via `/api/me` (which becomes CURRENT_USER), NOT relied upon from `/api/db` — the bulk snapshot is ETag/304-cached and heavy-table-trimmed, so it is the wrong channel for live per-user state.
**Suggested improvement:** Record the REL-UNITY pattern for any future saved-view/preference feature: (1) a self-service own-record write op gated by "is logged in", not by a page permission; (2) validate + size-cap the blob; (3) deliver the value through `/api/me`/CURRENT_USER, not the cached `/api/db` snapshot; (4) namespace keys (e.g. `osCols`) so modules don't collide inside one `prefs` object.
**Principle:** Preferences belong to the identity, not the device or the shared snapshot — write them to the caller's own record and hand them back on the per-session identity endpoint.

### Observation 12: For a novel visual feature discussed with a non-technical stakeholder, ship a clickable prototype as the discussion artifact — and battle-test it with headless screenshots
**Date:** 2026-08-14
**Session context:** REL-UNITY workflow/process-node builder. User wanted to "discuss first," is designing for ~15 y/o low-computer-experience operators, and asked to go big.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Design process

**Issue:** For a node-graph builder aimed at non-technical users, more prose Q&A has low yield — the concept only becomes real when clicked. A standalone vanilla-JS prototype (two seeded example flows, insert/branch/join, live batch-id preview) plus a short spec elicited far better alignment than text alone, and carried zero risk to the live app. Screenshotting it headlessly (Playwright/Chromium already in the sandbox) caught two defects a human would have hit first (icons not rendering; wires misaligned) before delivery.
**Suggested improvement:** For REL-UNITY UI features that are novel or aimed at floor operators, default to: build a throwaway standalone prototype → verify with headless screenshots → deliver for reaction → only then integrate + write the backend spec. Make "render and screenshot before delivering UI" a standing step.
**Principle:** A prototype is the cheapest way to make an abstract UI concrete for someone who can't read the code — and an agent that can render its own output should never ship UI it hasn't looked at.

### Observation 13: Offline-first floor tools — inline Material Symbols as SVG, and give SVG-over-HTML canvases explicit pixel sizing (no auto preserveAspectRatio)
**Date:** 2026-08-14
**Session context:** Building the node-graph canvas; icons failed to render and wires floated off the nodes.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Frontend / rendering

**Issue:** Two reusable gotchas surfaced. (1) The Material Symbols icon *font* from a CDN didn't load, leaving ligature text ("water_drop") over labels — unacceptable for a factory-LAN tool that may be offline and whose whole UX is icons-over-words. Fix: inline the needed icons as SVG (extracted from `@material-symbols/svg-400`, viewBox `0 -960 960 960`, `fill:currentColor`) so they always render. (2) When SVG wires overlay absolutely-positioned HTML nodes, a `<svg>` with a viewBox but `width/height:100%` gets centered/scaled by the default `preserveAspectRatio="xMidYMid meet"` whenever its pixel box is taller than the viewBox (e.g. a min-height:100% canvas), so wires drift below the HTML they should connect. Fix: set the SVG's width/height to explicit pixels matching the coordinate space and `preserveAspectRatio="none"` for a 1:1 map.
**Suggested improvement:** Bake both into the REL-UNITY build rules: inline SVG icons (never depend on an icon-font CDN) for any floor/LAN screen; and for any SVG-connector-over-HTML canvas, size the SVG in explicit px with preserveAspectRatio none and attach wires to measured node geometry (offsetLeft/Top/Width/Height), not layout-estimated coordinates.
**Principle:** On the shop floor assume no internet and pixel-exact overlays — inline the assets and pin the coordinate systems rather than trusting CDNs and SVG auto-fit.

### Observation 14: SQLite doc-store auto-creates any list-table — new tables need only seeding + a permission map, not a migration
**Date:** 2026-08-16
**Session context:** Adding processTypes / workflows / fabricGroups tables for the workflow system (REL-UNITY).
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Backend / data model

**Issue:** `_write_all` does `CREATE TABLE IF NOT EXISTS` for every `isinstance(v,list)` key in the in-memory db, and `load_db` auto-merges any new table present in `seed_data.json`. So a brand-new data table appears end-to-end just by adding it to `seed_data.json` (seeded rows or `[]`) — no schema migration, and the generic `upsert`/`delete` already handle it. The only extra wiring needed is a permission entry.
**Suggested improvement:** Record the REL-UNITY recipe for a new table: (1) add it to `seed_data.json`; (2) add its page to `ALL_PAGES`; (3) add `table -> [page]` to BOTH the `upsert` and `bulkUpsert` allow-maps (this is the recurring gotcha from Obs 9/#1 — the upsert gate keys on a page named like the table). Then CRUD, `_sanitized` delivery, and client `DB.<table>` all work automatically.
**Principle:** In a JSON-doc store, the schema is data — adding an entity should be a data + permissions change, and the permission-map step is the one that's easy to forget and silently 403s.

### Observation 15: Moving a page's inline script into a shared module requires full namespacing — global function names collide
**Date:** 2026-08-16
**Session context:** Relocating the standalone workflows.html builder into a modal loaded by admin.html.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Frontend / modularization

**Issue:** The builder defined top-level `render()`, and admin.html already has its own `render()`. Loading both as plain globals would redeclare/clobber and break the page. Wrapping the builder in an IIFE that exposes exactly one `window.WF` object (+ one `openX` entry point), with inline `onclick`s rewritten to `WF.method()`, eliminated all clash risk regardless of what the host page defines.
**Suggested improvement:** REL-UNITY rule: any builder/component extracted from a page into a shared JS file must be an IIFE exposing a single namespaced object; never rely on bare global function names surviving alongside another page's globals. Grep the host page for name clashes before porting.
**Principle:** Two scripts sharing one global scope is a landmine — encapsulate in one namespace object rather than trusting that names happen not to overlap.

### Observation 16: The mounted repo forbids unlink — commit via lock-rename, "delete" via move-out, verify via node --check before commit
**Date:** 2026-08-16
**Session context:** ~15 commits editing large HTML/py on the device this session.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Ops / device workflow

**Issue:** The device's mounted git repo cannot `unlink`, so (a) `git commit` fails on stale `HEAD.lock`/`index.lock` until they're renamed aside (`mv .git/$L .git/$L.old-$RANDOM`); (b) you cannot `rm` a file to remove it — you `mv` it out of the served dir (e.g. `mvp/static/workflows.html` → `mvp/_removed/`); (c) editing large HTML in place via python string-replace + extracting the inline `<script>` and running `node --check` before committing caught every syntax risk cheaply and never shipped a broken file.
**Suggested improvement:** Bake into the REL-UNITY ops notes: pre-commit lock-rename loop; delete = move-out; and a mandatory `node --check`(HTML inline script) / `py_compile`(server) gate before each device commit.
**Principle:** When the filesystem can't unlink, rename is your delete and your lock-clear — and a scripted syntax gate is the cheapest insurance for blind in-place edits.

### Observation 17: For a large multi-initiative prompt, segregate into BUILD/DISCUSS/DEFER and capture DEFER items to a repo doc immediately
**Date:** 2026-08-16
**Session context:** A single message mixing a workflow refactor, PLC/MySQL ingestion, multi-role, and a whole mobile app — with explicit "discuss this / store this as pending" instructions.
**Skill:** task-observer
**Type:** internal
**Phase/Area:** Process / large-prompt handling

**Issue:** The prompt bundled build asks, an explicit discussion request (PLC), and explicit deferrals (mobile points 4 & 5). Segregating up front into BUILD / DISCUSS / DEFER, then immediately writing the DEFER + roadmap items into a committed `docs/pending-notes.md`, kept the scope legible and guaranteed nothing was silently dropped while the big build proceeded. Confirming the one risky architectural fork (scheduler cutover) before touching it prevented a live-plan-breaking change.
**Suggested improvement:** Add to the large-prompt playbook: (1) segregate into BUILD/DISCUSS/DEFER; (2) commit DEFER/roadmap items to a persistent notes doc in the same turn; (3) surface and confirm any irreversible/architectural fork before building it, defaulting to the non-destructive bridge.
**Principle:** A big prompt is a backlog, not a task — triage it explicitly and persist the parts you're not doing now, or they evaporate.

### Observation 18: Mobile PWA offline/install depends on trusted HTTPS (secure context)

**Date:** 2026-08-17
**Session context:** Deploying the REL-UNITY floor app; discussed how the /m PWA reaches operators on the factory LAN.
**Skill:** rel-dyeing-mobile-design
**Type:** internal
**Phase/Area:** PWA / offline / deployment

**Issue:** The mobile app was built offline-first (service worker precache, add-to-home-screen). But a service worker only registers on a secure context — https:// or localhost. Over plain http://<lan-ip> the app still loads as a live page while on Wi-Fi, but it does NOT cache for offline and won't install as a real PWA. This is a deployment-shaping constraint that wasn't called out in the mobile design skill, so it could be discovered late (after building the offline behavior) instead of planned for.

**Suggested improvement:** Add a short "Deployment / secure context" note to the rel-dyeing-mobile-design skill's PWA section: service workers require HTTPS on the LAN; recommend a reverse proxy (Caddy) with a local CA or a domain cert; note iOS needs the separate Certificate Trust Settings toggle. Point to docs/DEPLOYMENT.md.

**Principle:** Offline-first PWA features are gated by transport security, not just code. Any skill that tells you to build a service worker should also tell you what the origin must be for it to run — otherwise the feature is built but dead in the target environment.

### Observation 19: Stub-render verification must exercise empty/denied states, not only populated happy paths

**Date:** 2026-08-17
**Session context:** Adding per-user permission gating to the mobile app; headless stub-render verification.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Verification / QA of vanilla-JS views

**Issue:** An empty() helper was referenced across several views (Alerts always calls it) but was never defined — a latent ReferenceError. Earlier stub-render tests passed with "NO ERRORS" only because they always used populated mock data, so no empty-state code path ran. The bug surfaced only when permission routing bounced a user into the Alerts (empty) view. A crash that would have hit every real user on the Alerts tab slipped verification.

**Suggested improvement:** Add a verification rule to the REL design/verification practice: every stub-render pass must also render at least one empty state and one permission-denied state, and assert zero console/pageerror events across ALL of them — not just the data-populated view. Drive views with empty arrays and a minimal-permission user, not only the happy-path fixture.

**Principle:** "No errors" from a happy-path render is not coverage. Empty states, error states, and permission-denied states are distinct code paths and are exactly where undefined helpers and typos hide. Verification fixtures must include the zero/denied cases by default.

### Observation 20: Doc-store makes per-row feature fields free, but derived state must be recomputed not stored

**Date:** 2026-08-17
**Session context:** Adding workflow-stage lot tracking to the batch planner (lots walk their quality's process flow in order).
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Data model / SQLite doc-store

**Issue:** Adding new per-batch fields (stepNode, proc) needed ZERO backend work — the doc-store `upsert` stores the whole row, so new fields persist automatically with no schema/migration and no permission-map change (that's only needed for whole new tables). The temptation was to add a lotStages table to track per-lot progress; instead progress is DERIVED from batches (each batch records which takas it processed at which step), so there is a single source of truth and no sync bug. Verified the exact behaviours (partial split by piece, plan-ahead, unplanned-prior flag) with a headless VM harness that loaded the real app.js and drove the pure helpers, before any UI render.

**Suggested improvement:** Add a short "doc-store patterns" note to the REL design insight skill: (1) new per-record fields are free — just write them on the row; only NEW TABLES need seed + ALL_PAGES + upsert allow-map entries; (2) prefer deriving cross-record state (progress, availability) over a second table, and unit-test the derivation as pure functions in a Node VM with a mock DB before wiring UI.

**Principle:** In a schema-less doc store, the cost of a new field is zero and the cost of a duplicated source of truth is high. Model progress as a projection over existing records, and verify the projection in isolation before trusting the UI.

### Observation 21: Guard big changes to production logic behind a feature predicate so the legacy path is untouched

**Date:** 2026-08-17
**Session context:** Reworking the batch planner's taka-allocation to be workflow-step-scoped without breaking qualities that have no workflow.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Planner / safe rollout of risky changes

**Issue:** The step-scoped lot availability is a deep change to the most production-critical code (fabric allocation). Rather than replace the global allocation, every new branch is gated by mpWfActive()/hasWorkflow(q): if the quality has no process flow, the editor behaves exactly as before. This bounds the blast radius — existing data and un-migrated qualities are provably unaffected — and let the change ship incrementally alongside a checkpoint commit of the unrelated finished features first.

**Suggested improvement:** Add to the REL insight skill: when changing core planner/scheduler logic, gate the new behaviour behind an explicit predicate (feature present? new field set?) and keep the legacy branch intact; commit independent finished work as a separate checkpoint before the risky change so a revert is surgical.

**Principle:** For high-blast-radius changes, additive-and-guarded beats replace-in-place: the old path stays a proven fallback, and the diff that can break production is small and clearly fenced.

### Observation 22: Verify an external-system integration against a throwaway instance before touching the live one

**Date:** 2026-08-17
**Session context:** Building the PLC MySQL poller (reads jet machine RTD tables every 10s) — could not reach the factory's 192.168.0.235 from the build sandbox.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Integrations / verification

**Issue:** The factory PLC DB is on a private LAN the build environment can't reach, and the first real run would otherwise be against production. Instead I stood up a throwaway MariaDB in the sandbox, recreated the exact database/user/table/sample row the user gave, and ran the real query + decode + reconciliation + alert path against it. Caught nothing broken, but proved the connection string shape, the identifier-safe table interpolation, the tenths-of-a-degree temp decode, in/out reconciliation and the temperature alert all work before a single byte hit the live DB.

**Suggested improvement:** Add to the REL insight skill: for any external-DB/API integration, reproduce the counterpart locally (a scratch MySQL/stub endpoint seeded with the user's real schema + sample row) and assert the full read→decode→apply path against it; only then point config at the live system. Keep credentials in the gitignored secrets file, never in the repo or the query.

**Principle:** "It compiles" is not "it connects." An integration is only verified once the actual driver has round-tripped real-shaped data; a disposable replica makes that possible without risking the production system.

### Observation 23: Native browser prompt() slipped past the design system until the skill was explicitly invoked

**Date:** 2026-08-19
**Session context:** Adding a "quick-add shade" affordance inside the REL-UNITY batch planner. First implementation used a native `window.prompt()` to collect the shade name.
**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Section 8 (Hard bans) / delivery-time enforcement

**Issue:** The first working, tested, and deployed version of the quick-add used `window.prompt()`. That is a reinvented/unstyled browser affordance and contradicts the design system's "no reinvented standard affordances" and "modal as the first thought — exhaust inline/progressive options first" rules. It was only caught and reworked into an inline field (matching the existing Excel-like planner editor) after the user explicitly invoked the rel-dyeing-design-insight skill. The design rules did not reach the moment of decision during the coding flow — they were applied only on explicit re-invocation.

**Suggested improvement:** Add `window.alert`/`confirm`/`prompt` (and other native browser dialogs) to the Section 8 Hard bans list by name, and add a short delivery-time verification checkpoint to the skill: before shipping any new interactive control, re-read Section 8 and confirm no native dialog and no reinvented affordance was introduced. Convert the ban from narrative guidance into an explicit pre-flight check item.

**Principle:** A skill full of design rules still gets violated during the creative flow unless it carries a delivery-time enforcement step. Named, greppable bans (specific API names) plus a "re-read the bans before you ship" checkpoint catch violations that broad prose ("no reinvented affordances") does not.

### Observation 24: Design-system compliance keeps getting caught on explicit re-invocation, not at build time (recurrence of #23)

**Date:** 2026-08-19
**Session context:** Added a PgNo field/column, double-click-to-edit, and moved PH to the time modal in the batch planner. A new text input (.mp-ed-remarks / PgNo) shipped without the app's standard `::placeholder{color:var(--faint)}` convention; it was only caught and fixed when the user explicitly invoked the design skill afterward.

**Skill:** rel-dyeing-design-insight
**Type:** internal
**Phase/Area:** Delivery-time enforcement / Section 8 + token-convention adherence

**Issue:** This is the SECOND time this session (see #23, the native window.prompt()) that a design-system deviation shipped in a working, tested, committed state and was only corrected when the user explicitly re-invoked rel-dyeing-design-insight. #23 was a hard-ban violation; this one was a convention miss (a new form control not matching the app's established placeholder/token usage). Two instances make it a pattern, not a one-off: the design rules are applied reactively (on explicit skill load) rather than proactively during the build.

**Suggested improvement:** Strengthens #23's proposed delivery-time checkpoint. Make the checkpoint cover two questions, not one: (1) did I introduce any hard-ban item (native alert/confirm/prompt, side-stripe border, gradient text, etc.)? and (2) does every NEW form control match the app's existing token conventions — placeholder color, focus ring, control radius, icon family — by grepping the stylesheet for how sibling controls already do it before writing new CSS? Add this as an explicit "before you ship a new/edited control" verification block in the skill.

**Principle:** A design skill enforces its rules only if it carries a build-time verification step; recurrence across a session confirms narrative rules alone don't reach the moment of decision. The check must include convention-matching (does this new element look up how the codebase already solves it?), not just ban-avoidance — most real drift is silent divergence from existing patterns, not flagrant ban violations.
