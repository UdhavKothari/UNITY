# UNITY-MOBILE

The REL-UNITY mobile app for the factory floor — used by the Factory Head, supervisors, and operators
while walking the floor. **Locked to the factory WLAN** (reachable only on the LAN, same as the ERP).

Scaffold only for now; build order is tracked in `../docs/pending-notes.md`.

## Intended scope
1. **Operator data entry** — mobile-ify the Jet/Stenter/Jigger checklists; scan a batch ID / machine QR →
   checklist opens and auto-timestamps. Closes the lag between what happened and what got typed in.
2. **Exception / alert push** — push PLC & analytics anomalies (cycle-time drift, recipe/temperature
   deviation) to the shift supervisor's / MNTC-tagged phones.
3. **Machine micro-views** — per-machine screen: current batch, time remaining, last 3 batches vs target.
6. **Voice-to-text notes** against a batch.

### Deferred (later)
4. Re-dye / rework flagging from the floor (reason code + photo).
5. Photo evidence for QC / dispatch disputes.

## Likely approach (to confirm when we build)
- A **PWA** served by the existing Python server on the LAN (installable, offline-tolerant, no app store),
  sharing the same `/api` + auth as the web app — simplest to keep inside the WLAN sphere.
- Same session/login model; role/tag gated (operators, supervisors, MNTC).
