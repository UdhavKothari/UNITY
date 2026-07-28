# REL Dyeing ERP — running it in production & operating it remotely

The factory PC is the **one host**: it runs the server, holds the database, and everyone
(floor terminals + you from home) are just browser clients pointing at it. This guide sets
that up so it runs unattended and you can monitor, use, and edit it from your laptop.

---

## 1. Run the server unattended on the factory PC

**Start it:** in the `mvp` folder, `python server.py` (add a port like `python server.py 8080`).
It serves on `http://<pc-ip>:8080/` across the LAN.

**Make it auto-start on boot** (so it survives reboots, no one has to launch it):

- Open **Task Scheduler → Create Task**.
- General: "Run whether user is logged on or not", "Run with highest privileges".
- Triggers: **At startup**.
- Actions: Program `python` (or full path to `python.exe`), Arguments `server.py 8080`,
  **Start in** = the full path to the `mvp` folder.
- Settings: tick "Restart the task if it fails" (every 1 min, a few times).

That's the simplest route. (For a "proper" Windows service with auto-restart, `NSSM` wraps
`python server.py` as a service — optional, do it later if you want.)

**Power:** put the PC on a **UPS (battery backup)**. A clean SQLite write survives a crash,
but a UPS + the daily backup below is what makes the whole thing trustworthy when no one's
watching.

---

## 2. Reach it from home — a private network (Tailscale)

The app has login + hashed passwords but **no HTTPS yet**, so do **not** port-forward it to
the open internet. Instead put both machines on a private encrypted network:

1. Install **Tailscale** on the factory PC and on your laptop; sign both into the same account.
2. From home, open `http://<factory-pc-tailscale-name>:8080/` in your laptop browser — same
   app, live data. Floor terminals keep using the normal LAN address; nothing changes for them.

(ZeroTier or a Cloudflare Tunnel are alternatives; Tailscale is the simplest and safest start.)

---

## 3. Edit the code from home — VS Code over SSH

1. On the factory PC, enable **OpenSSH Server** (Windows → Settings → Optional features → add
   "OpenSSH Server", then start the "OpenSSH SSH Server" service and set it to Automatic).
2. On your laptop, install **VS Code** + the **Remote-SSH** extension, and connect to the PC
   over Tailscale. You can now open and edit the `mvp` folder directly on the PC.

**What needs a restart:**
- The screens (`index.html`, `app.js`, `style.css`) are served fresh on every request — **just
  save and refresh the browser**, no restart.
- `server.py` (backend) changes need the server restarted (one command in the SSH terminal, or
  Task Scheduler → End + Run). Restarting logs everyone out (sessions are in memory), so do
  backend changes at a quiet time.

Optional: put the repo on a **private GitHub**. Then edit anywhere, `git push`, and `git pull`
on the PC — plus you get an off-site copy of the code and full history.

To see the actual desktop, add **RustDesk** or **Chrome Remote Desktop** (also over Tailscale).

---

## 4. Database (SQLite) & backups

The store is now **SQLite** (`data.sqlite`) — real tables, atomic writes, room to grow. The
first time you start this updated server it **automatically imports your old `data.json`** into
`data.sqlite`, losslessly, and keeps `data.json` as-is (a frozen backup of the pre-SQLite state).
Nothing else changes — same screens, same API.

**Daily backup:** schedule `backup_db.bat` (in `mvp`) with Task Scheduler → trigger **Daily**.
It writes a consistent snapshot to `mvp/backups/` (safe to run while the server is live), keeps
the newest 30, and — if you set `backup.targetPath` in `secrets.local.json` — also mirrors each
snapshot to an external drive / network share / cloud folder. **Set an off-machine target**, so a
dead disk can't take your data with it.

Restore = stop the server, copy a snapshot over `data.sqlite`, restart.

---

## 5. Secrets (`secrets.local.json`)

External credentials (the Livewire / EMPIRE SQL Servers, a backup target, etc.) go in
`mvp/secrets.local.json`. This file is **gitignored** — it is never committed, never shared, and
the assistant does not read it. `secrets.example.json` shows the format; copy it and fill in real
values. Do **not** put ERP login passwords here — those are already hashed inside the database.

---

## Setup checklist (do once, at the factory)

- [ ] Python installed (add to PATH)
- [ ] App set to auto-start on boot (Task Scheduler)
- [ ] `backup_db.bat` scheduled daily; `backup.targetPath` set to an off-machine location
- [ ] Tailscale installed + signed in (PC and laptop)
- [ ] OpenSSH Server enabled on the PC; VS Code + Remote-SSH on the laptop
- [ ] UPS on the PC; PC on wired Ethernet
- [ ] `secrets.local.json` created from the example

Once this is done, everything — monitoring, using, and editing — works from your laptop at home,
with the factory PC quietly hosting it all.
