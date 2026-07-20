# REL Dyeing ERP — MVP (v1: Planning & Scheduling)

A zero-dependency web app for trial on your LAN. Two pages:

- **Operations** (`/`) — daily use: enter orders (multi-shade), watch batches split and slot into machine campaigns, shop-floor status board, Gantt schedule.
- **Admin** (`/admin.html`) — you only: add / edit / remove every master table, tune scheduler settings, view the auto-generated Machine Schedule and Batch Master.

## Run it

You need **Python 3** (already on most machines; on Windows install from python.org and tick "Add to PATH").

```
cd mvp
python server.py
```

Then open:

- On this machine: **http://localhost:8080/**
- From any other machine on the same network (floor terminals, phones): **http://<this-machine-ip>:8080/**
  (find the IP with `ipconfig` on Windows — the IPv4 address, e.g. 192.168.1.20)

Use a custom port with `python server.py 9000`.

## Logging in (accounts & roles)

The whole app is behind a login. The seeded administrator is:

- **Username:** `ADMIN`
- **Password:** `sonkeiwachikara`

**Change this password after first login** (top-right → *Password*).

Roles control which pages each user can see (Discord-style — each page is granted per role):

- **Admin → Roles** — create a role, tick the pages it may view (Operations pages + Admin sections).
- **Admin → Users** — create a user, set a password, and assign a role. Untick *Active* to disable an account.
- A user only sees the pages their role allows; the server enforces this (hiding a page in the UI is backed by a real permission check on every save).

Security notes for this LAN trial: passwords are stored **hashed** (PBKDF2-SHA256, never in plain text) and sessions use an HttpOnly cookie. There is **no HTTPS yet**, so traffic is readable on the local network — fine for a trusted mill LAN, but add TLS before exposing this on the company domain or internet. Sessions are in memory, so restarting the server logs everyone out.

## Data

All data lives in **`data.json`** in this folder (created on first run from sample seed).
Back it up by copying that file. To restore the sample data, use **Admin → Reset sample data**, or delete `data.json` and restart.

## What the scheduler does

1. Order → converts meters to **kg** using the quality's greige GSM × width.
2. Splits into machine-sized **batches** (never below the 300 m minimum load).
3. Schedules **2-step pre-treatment** (per quality: PT M/C 1 + time, PT M/C 2 + time) on the drums/jiggers — jiggers are a **shared pool** with dyeing.
4. Fabric becomes **RFD** (ready-for-dye) — the buffer point.
5. Schedules **dyeing** as light→dark **campaigns**, auto-inserting a **wash** whenever the shade family changes or tone drops.
6. Every machine operation reserves **60 min handling** (35 load + 25 unload).
7. Promises a delivery date at **route time × 1.20 buffer**; flags if it misses the requested due date.

## Adding a new quality (with pre-treatment)

Admin → **Qualities** → *Add quality*. The pre-treatment columns are **PT M/C 1, Time req 1, PT M/C 2, Time req 2** (leave M/C 2 blank for single-step pre-treatment).

## Master tables included (from your INFO TABLES design)

Machines, Qualities (+ pre-treatment), Shades/Colours (with tone), Recipes, Customers, Storage Areas, Operators, QC metrics, Store/Suppliers, Users, Orders — plus a **Live plan** view (auto-generated Machine Schedule + Batch Master).

## Known MVP limits (next steps)

- No login yet — planned for the domain-hosted version (Users table already models username/role/auth).
- Single JSON store (fine for a trial; move to a database when concurrent load grows).
- Scheduler is a greedy planner (explainable, overridable). Wash-minimizing optimization and drag-to-override are future work.
- Times are planning estimates; PLC actuals (jets) and inward-weighed kg will replace estimates in a later phase.
