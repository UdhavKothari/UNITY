# REL-UNITY — Pending / Roadmap notes

_Captured 2026-08-14. Living doc — items move out as they ship._

## Workflows refactor (to build next)
- Remove the `M/C 1 / M/C 1 Time / … / step1–4_mc/step1–4_time` section from the **Quality editor**.
- Replace it: pick a **workflow** for the quality; the editor then shows that workflow's machines as **arrow-connected nodes**, with a **time text field under each machine icon** (per-quality node times).
- **Link workflows ↔ qualities** (a quality references its workflow; times stored per quality).
- **Move the builder into a modal** opened by a **"Workflows"** button inside **Quality Settings**. Delete the standalone `workflows.html` page + its nav links. May be made "less visual" if it destabilises anything.
- **Visual fixes:** centre the `+` insert buttons; make long flows **wrap in an S-loop** (serpentine) so >5 machines don't require horizontal scrolling.
- **Scheduler bridge (decision pending):** the live plan reads `step1–4_mc/time`. Plan is to **derive** those from the workflow + per-node times when a quality is saved, so the scheduler keeps working with no rewrite (vs. a full cutover).

## User roles (to build)
- Allow **multiple roles per person**.
- Add an **MNTC** tag/role assignable to anyone (used for maintenance/temperature alerts below).

## PLC data (discuss first, then build)
- New **"PLC Database"** field on each machine (the MySQL database name for that machine's PLC).
- **Poller** (helper script, keeps the runtime dependency-free) polls every machine's PLC MySQL DB at **:03, :13, :23, :33, :43, :53** (every 10s) and writes readings to an inbox the server reads.
- **Use 1 — In/Out time reconciliation:** PLC has no quality/context, so anchor on the user-entered In time. Around that timestamp, find the PLC batch cycle and record **PLC In / PLC Out** (new hidden fields at first) to measure drift vs. user entries over a few days.
- **Use 2 — Alcohol ratio:** fetch the **water-flow** column (details later).
- **Use 3 — Temperature monitoring:** compare PLC temp to its setpoint; if it deviates by more than **Admin → Temperature Tolerance** (e.g. 2.5°), notify everyone tagged **MNTC**.
- **Open questions:** PLC MySQL schema (which tables/columns carry cycle start/end, temperature, water flow, machine mapping?); connection host/port/user; how MNTC alerts surface (in-app banner, and/or the mobile app below).

## REL-UNITY mobile app (roadmap — WLAN-locked)
Build order when we get to it:
1. **Operator data entry** — mobile-ify the Jet/Stenter/Jigger checklists; scan batch ID / machine QR → checklist auto-timestamps. Closes the data-lag gap.
2. **Exception / alert push** — push PLC/analytics anomalies (cycle-time drift, recipe/temp deviation) to the shift supervisor's phone.
3. **Machine micro-views** — per-machine screen: current batch, time remaining, last 3 batches output vs target (helps the JET-10 underutilisation problem).
6. **Voice-to-text notes** against a batch (supervisors won't type).

### PENDING — explicitly deferred (do later)
4. **Re-dye / rework flagging from the floor** — reason code + photo, feeds the re-dye prioritisation tool.
5. **Photo evidence for QC / dispatch disputes** — shade-match photo attached to the batch record.
