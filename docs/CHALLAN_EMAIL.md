# Mill challans from email (osbyrel@gmail.com)

Every mill challan PDF emailed to **osbyrel@gmail.com** is read automatically, parsed page-by-page
(**one page = one lot**), and filed into **Admin → Mill challans** in REL‑UNITY. It captures the
quality, customer, target shade ("To Shade"), own shade, width, PO, packing‑list no./date, the rolls
with meters, and the **real weights** (see the weight rule below).

## How it flows
```
osbyrel@gmail.com  ──IMAP──▶  challan_watch.py  ──parse PDF──▶  mvp/inbox_challan/*.json
                                                                        │
                                                        server picks it up ▶ Admin → Mill challans
```
`challan_watch.py` does the email + PDF work (it uses `pdfplumber`). The **server stays
dependency‑free** — it only files the JSON the poller produces.

## One‑time setup (on the factory PC)
1. **Install the PDF library:** `pip install pdfplumber`
2. **Create a Gmail App Password** for `osbyrel@gmail.com`:
   Google Account → Security → **2‑Step Verification** (must be ON) → **App passwords** → create one
   for “Mail”. You get a 16‑character password. (The normal account password will **not** work for IMAP.)
3. **Put it in `mvp/secrets.local.json`** (copy from `secrets.example.json` if you haven't):
   ```json
   {
     "gmailUser": "osbyrel@gmail.com",
     "gmailAppPassword": "xxxx xxxx xxxx xxxx",
     "gmailFolder": "INBOX",
     "gmailFromFilter": ""
   }
   ```
   `secrets.local.json` is gitignored — it never leaves the PC and the assistant never reads it.
   Set `gmailFromFilter` to the sender's address if you only want challans from one sender.
4. **Run the poller.** Either once (`python challan_watch.py`) or continuously
   (`python challan_watch.py --loop`, polls every 2 minutes). To have it always on, add it to Task
   Scheduler the same way as `start_server.bat`, or run it in its own window.

## The weight rule
A challan often has placeholder weight cells. **A roll's weight is treated as real only when it is
greater than 2 kg** — those are summed into the lot's *real weight*. Smaller values are ignored.

## Robust to format changes
The parser reads the **table by column position** (mapped from the header row), so renaming
`OWNSHADE`, adding the planned **TO SHADE** column, adding a **Process** ("Dyeing / RF") field, or
reordering columns won't break it. Header/footer fields (quality, customer, To Shade, totals) are
found by their **labels**, not fixed positions. Each page is validated against the challan's own
`TOTAL TAKA` / `TOTAL METER`. If the layout ever changes so much that a field is missed, only that
field comes back blank — the rest still imports, and we adjust `challan_parser.py` (one file).

## The sequence (challan first, EMPIRE lot number later)
The **challan arrives first** — it's the administrative receipt of the greige fabric. The **EMPIRE
lot number comes about a week later** through the DESPNO CSV import. So the challan is the *leading*
record: each challan page is stored as a **challan record** (status `received`) holding everything we
know at receipt (quality, customer, To Shade, rolls, meters, real weights). When the EMPIRE lot for
that fabric finally shows up, we **reconcile** the two — flip the challan to `linked` and carry its
real weights + customer + To Shade onto the EMPIRE lot.

**The one open decision is the match key** — what reliably ties a challan to its later EMPIRE lot:
- roll numbers on the challan vs the taka/card numbers in the DESPNO export, or
- packing‑list no., or
- quality + customer + taka count + total meters (a fuzzy match).

Tell me which holds true and I'll wire the automatic reconciliation. Until then the challans sit in
**Admin → Mill challans** as a clean, searchable record of everything received.
