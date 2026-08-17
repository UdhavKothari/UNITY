# REL-UNITY — Deployment Runbook

How to run the REL-UNITY ERP (web console + `/m` floor app) in the factory,
on one always-on office PC, reachable over the factory network with trusted
HTTPS so the mobile app installs and works offline.

This is a one-time setup. Once it's done, the system starts itself on boot,
restarts itself if it crashes, and updates over the "System Update" button.

---

## 0. What you're setting up

Three things run on the office PC:

1. **The Python server** (`server.py`) — the whole ERP. Serves the web console
   and the mobile app, talks to `data.sqlite`. Listens on port **8080**.
2. **Caddy** — a tiny reverse proxy that puts **HTTPS** in front of the server.
   This is what lets the phone app install as an app and cache for offline use.
3. **Nightly backup** — a scheduled copy of the database to a safe second place.

Operators reach it on the factory Wi-Fi at `https://<server-ip>/m/`.
Office staff use the web console at `https://<server-ip>/`.

The Python server never has to change for this — Caddy sits in front of it.

---

## 1. Pick the machine and give it a fixed address

The server is the office PC that's always on during production hours.

1. **Set a fixed IP** so the address in everyone's bookmark never changes. The
   easiest way is a **DHCP reservation** on your router: find the office PC's
   MAC address, and tell the router to always hand it the same IP (e.g.
   `192.168.1.50`). This is better than a manually-set static IP because the
   router still manages the network and there's no risk of a clash.
2. Write that IP down — it goes in the Caddy config and in every bookmark. This
   runbook uses `192.168.1.50` as the example; replace it everywhere with yours.
3. Make sure Windows is set to **never sleep** and **never hibernate** while
   plugged in (Settings → Power → Screen and sleep → "When plugged in, put my
   device to sleep after" → **Never**). A sleeping PC = a dark shop floor.

---

## 2. Install Python and get the code on the PC

1. Install **Python 3** (python.org → "Add python.exe to PATH" during install).
   The server has **zero external dependencies**, so nothing else to `pip`.
2. The project already lives at
   `C:\Users\ravi\Desktop\Factory\REL_DYEING`. Keep it there, or move it to a
   less personal path like `C:\REL_DYEING` if this PC will be shared — just keep
   the folder structure intact (`mvp\` and `UNITY-MOBILE\` side by side).
3. Confirm it runs by hand once: open a Command Prompt in the `mvp` folder and
   run `python server.py`. You should see it print the local and LAN URLs. Open
   `http://localhost:8080/` in the PC's browser to confirm, then close it
   (Ctrl-C). We'll make it run automatically in step 4.

---

## 3. Set up HTTPS with Caddy (the important part)

The mobile app's "install to home screen" and offline mode only work over
HTTPS. Over plain `http://192.168.1.50` the app still opens as a normal web
page while on Wi-Fi, but it won't install as a real app and won't cache for
offline. Caddy fixes that.

Download **Caddy** for Windows (caddyserver.com/download → Windows amd64) — a
single `caddy.exe`. Put it in a folder like `C:\caddy\` alongside the
`Caddyfile` from this kit.

Now choose a certificate method. Both give you trusted HTTPS on the LAN.

### Method A — Local certificate authority (recommended, no domain needed)

Caddy issues its own certificate for the server's IP. You install Caddy's root
certificate on each device once, and from then on every device trusts it. This
needs **no domain and no internet** — ideal for a factory where the connection
can be flaky, since nothing ever has to phone home to renew.

1. In the `Caddyfile`, set the site address to your fixed IP and keep the
   `tls internal` line (it's already set up this way in the provided file).
2. Start Caddy once (step 4 makes it permanent):
   `caddy run --config C:\caddy\Caddyfile`
3. Find Caddy's root certificate — Caddy installs it into the Windows trust
   store automatically on the server PC, and also writes it to:
   `C:\Users\<user>\AppData\Roaming\Caddy\pki\authorities\local\root.crt`
4. **Put that `root.crt` on each phone/terminal** and trust it:
   - **Email or AirDrop the file to the device**, or host it briefly on the LAN.
   - **iPhone/iPad:** open the file → Settings shows "Profile Downloaded" →
     Settings → General → VPN & Device Management → install the profile → then
     **Settings → General → About → Certificate Trust Settings → turn it ON**
     for the Caddy root. (Both steps are required on iOS.)
   - **Android:** Settings → Security → "Encryption & credentials" → "Install a
     certificate" → "CA certificate" → pick the file → confirm.
   - **Windows terminals:** double-click `root.crt` → Install Certificate →
     Local Machine → "Trusted Root Certification Authorities".
5. Operators now open `https://192.168.1.50/m/` and it's a trusted, installable,
   offline-capable app.

### Method B — Real domain + automatic Let's Encrypt (no per-device cert install)

If you own a company domain and would rather not touch each phone, use a real
hostname with a free auto-renewing certificate. Devices trust it out of the box.

1. Pick a hostname, e.g. `rel.yourcompany.com`, and add a **DNS A record**
   pointing it at the server's LAN IP (`192.168.1.50`). A public record pointing
   at a private IP is fine — only devices on your Wi-Fi will resolve and reach it.
2. Because the server isn't exposed to the internet, use the **DNS-01 challenge**
   (Caddy proves domain ownership via a DNS record, not an open port). This needs
   the DNS-provider plugin for Caddy and an API token from wherever your domain's
   DNS is hosted (Cloudflare, GoDaddy, Route53, etc.). Build Caddy with that
   plugin using `xcaddy`, or download a Caddy build that includes it.
3. In the `Caddyfile`, replace `192.168.1.50` with `rel.yourcompany.com`, remove
   `tls internal`, uncomment the `email` line, and add your DNS block, e.g. for
   Cloudflare:
   ```
   rel.yourcompany.com {
       tls {
           dns cloudflare {env.CF_API_TOKEN}
       }
       @lan remote_ip 192.168.0.0/16 10.0.0.0/8 172.16.0.0/12 127.0.0.1/8 ::1
       handle @lan { encode zstd gzip; reverse_proxy 127.0.0.1:8080 }
       handle { respond "REL-UNITY is only available on the factory network." 403 }
   }
   ```
   Set the `CF_API_TOKEN` environment variable to your token.
4. Operators open `https://rel.yourcompany.com/m/` — trusted immediately, nothing
   to install on devices.

> Which to choose: Method A is the most self-contained and works with no
> internet at all, at the cost of installing one certificate per device (a
> handful of phones, once). Method B is zero-touch on devices but depends on a
> domain, a DNS API, and periodic internet for renewal. For a floor app that
> must survive an internet outage, **Method A is the safer default.**

---

## 4. Make everything start on boot and restart on crash

Use **NSSM** (the "Non-Sucking Service Manager", nssm.cc — a single `nssm.exe`)
to run both the server and Caddy as Windows services. Services start before
anyone logs in and auto-restart if the process dies.

Open an **Administrator** Command Prompt.

**The Python server:**
```
nssm install REL-UNITY "C:\Path\To\python.exe" "server.py"
nssm set REL-UNITY AppDirectory "C:\Users\ravi\Desktop\Factory\REL_DYEING\mvp"
nssm set REL-UNITY Start SERVICE_AUTO_START
nssm set REL-UNITY AppExit Default Restart
nssm start REL-UNITY
```

**Caddy:**
```
nssm install REL-Caddy "C:\caddy\caddy.exe" "run --config C:\caddy\Caddyfile"
nssm set REL-Caddy AppDirectory "C:\caddy"
nssm set REL-Caddy Start SERVICE_AUTO_START
nssm set REL-Caddy AppExit Default Restart
nssm start REL-Caddy
```

**The challan watcher** (if you use the email/challan import) can be a third
service the same way, pointing at `challan_watch.py`.

To check status later: `nssm status REL-UNITY`. To stop for maintenance:
`nssm stop REL-UNITY`. Reboot the PC once and confirm everything comes back up
on its own before you consider it done.

---

## 5. Firewall — only expose HTTPS

You want devices to reach Caddy (443), and you want the raw Python port (8080)
**not** reachable from the network — everything should go through HTTPS.

In Windows Defender Firewall (Advanced):

- **Allow inbound TCP 443** (Caddy). Name it "REL-UNITY HTTPS".
- **Block inbound TCP 8080** from the network. Caddy talks to the server over
  `127.0.0.1`, which is not affected by an inbound-network block, so the app
  keeps working while outsiders can't hit the unencrypted port directly.

(If you're on Method B and want an http→https redirect, also allow 80.)

---

## 6. Backups — automated and off the machine

You already have `backup_db.py`. Schedule it so a copy of `data.sqlite` lands
somewhere safe every night, and keep a couple of weeks of history.

1. Open **Task Scheduler** → Create Task.
2. Trigger: **Daily**, a quiet hour (e.g. 01:00).
3. Action: run `python.exe` with argument `backup_db.py`, "Start in" set to the
   `mvp` folder.
4. Point the backup destination at a **second location** — another physical
   drive, a NAS share, or a cloud-synced folder (OneDrive/Google Drive). A backup
   that lives only on the same disk as the original doesn't protect you from that
   disk dying.
5. Once a month, actually open a backup copy to confirm it's a real, complete
   database — an untested backup isn't a backup.

The database is a single `data.sqlite` file, so a "backup" is really just a safe
copy of that file taken while the server is briefly consistent — which is exactly
what `backup_db.py` handles.

---

## 7. Power protection

Put the office PC (and the network switch/router it depends on) on a small
**UPS** (battery backup). A power blip during a database write is the one thing
that can corrupt SQLite, and a UPS both prevents that and keeps the floor online
through short outages. Even a basic ~₹5–8k consumer UPS is enough for one PC and
a switch.

---

## 8. How updates work after go-live

You develop as you do now (push to GitHub). To update the factory:

- **From inside the app:** the **System Update** button (Settings, admin only)
  runs `git pull` on the PC. If `server.py` changed, the server's file-watcher
  restarts it within about a second; if only the web/mobile files changed, a
  browser refresh (or reopening the phone app) picks them up.
- **By hand on the PC:** run `update.bat`, or `git pull` in the project folder.
- Caddy config changes: edit the `Caddyfile`, then `nssm restart REL-Caddy`.

No database migrations are needed for normal feature updates — new tables are
created automatically from the seed on first run.

---

## 9. Go-live checklist

Work down this list; don't call it live until every box is genuinely true.

- [ ] Server PC has a fixed IP (DHCP reservation) and never sleeps.
- [ ] `python server.py` runs clean by hand; `http://localhost:8080/` loads.
- [ ] Caddy running; `https://<ip>/` loads with a **trusted** lock (no warning)
      on a real phone that has the certificate installed (Method A) or on any
      phone (Method B).
- [ ] On a phone: open `https://<ip>/m/`, log in, **Add to Home Screen**, then
      turn Wi-Fi off and confirm the app still opens (offline shell works).
- [ ] Start/Finish a test batch from the phone; confirm it shows in the web
      console with the operator's name and time.
- [ ] Both services set to auto-start; **reboot the PC** and confirm the web and
      mobile apps come back with no one logging in.
- [ ] Port 8080 is blocked from the network; 443 is open.
- [ ] A backup has run and you've opened the copy to confirm it's valid.
- [ ] The PC (and switch) are on a UPS.
- [ ] A couple of real operators have logged in on their own phones and can see
      only the pages their role allows.

---

## 10. Troubleshooting

**The phone app opens but won't install / doesn't work offline.**
The origin isn't trusted HTTPS. Confirm you're on `https://` (not `http://`),
that the address bar shows a real lock with no warning, and — for Method A —
that the Caddy root certificate is installed *and trusted* on that device
(on iOS, the separate "Certificate Trust Settings" toggle is the usual miss).

**"This system is only available on the factory network."**
The device isn't on a private LAN IP — check it's on the factory Wi-Fi, not
cellular or a guest network on a different subnet.

**A phone can't reach the server at all.**
Confirm the phone is on the same Wi-Fi/subnet as the server, that the server's
IP hasn't changed (DHCP reservation in place?), and that inbound 443 is allowed
in the firewall.

**Everything was fine, then died after a reboot.**
Check both services: `nssm status REL-UNITY` and `nssm status REL-Caddy`. If one
is stopped, `nssm start` it and check its log. Auto-start + auto-restart should
prevent this; if a service won't stay up, its NSSM "AppDirectory" or exe path is
probably wrong.

**Web console works on the PC (`localhost`) but not from other machines.**
That's the firewall or the IP. `localhost` bypasses both. Test from another
machine using the actual IP over `https://`.

---

## 11. PLC live data (jet machines)

The server polls the PLC's MySQL database every 10 seconds and pulls each jet's
current reading (temperature, step, program, alarms), reconciles real in/out
times against what operators typed, and raises a maintenance alert when a
running machine's temperature drifts past the tolerance set in Settings
(default 3°C).

Setup on the office PC:

1. Install the MySQL driver once: `pip install pymysql --break-system-packages`
   (this is the server's only outside dependency).
2. Connection lives in `mvp/secrets.local.json` under a `"plc"` block
   (host, port, user, password, database) — this file is gitignored and is
   never committed. It's already filled in for the jet_machines database.
3. On each machine record (Admin → Machines), set the **PLC table** field to
   that machine's table, e.g. `jet_mch_1_rtd` for jet 1. Machines with the
   field blank are simply skipped by the poller.
4. Set **Temperature tolerance (°C)** in Settings (defaults to 3).

The poller only reads (SELECT) and only accepts plain identifier table names,
so it can't be used to alter the PLC database. If pymysql isn't installed or the
`plc` block is missing, the poller stays idle and the `PLC_Inbox` folder remains
available as a manual Excel-export fallback. Live alerts appear on the mobile
app's Alerts tab.
