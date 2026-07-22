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
