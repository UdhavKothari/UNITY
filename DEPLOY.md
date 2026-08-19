# REL-UNITY — Deployment (plain HTTP on the factory network)

No Caddy, no Tailscale, no HTTPS certificate, **no custom CA on any phone**.
The app runs as a single Python process and is reached directly over the LAN
(or over any VPN that drops you onto the factory network). Security rests on
two things: the physical/VPN network boundary, and the app's own
username + password login.

## 1. Run the server

On the server box (the machine that holds `server.py` and the data file):

```
cd REL_DYEING/mvp
python3 server.py            # defaults to port 8080
python3 server.py 9000       # or pick another port
```

The server binds to `0.0.0.0`, so every device on the same Wi-Fi/LAN can
reach it. It prints the URLs on startup. Leave this process running (see
§5 for auto-start).

## 2. Point devices at it

Find the server's LAN IP (Windows: `ipconfig` → IPv4 Address, e.g.
`192.168.0.50`). Then:

- Floor terminals / office PCs: `http://192.168.0.50:8080/`
- Admin console:               `http://192.168.0.50:8080/admin.html`
- Operator mobile app:         `http://192.168.0.50:8080/m/`

Everyone signs in with their username + password/PIN. Page access is still
controlled per role in Admin → Roles.

## 3. Reaching it over VPN (optional)

Any VPN that puts the phone/laptop **on the factory network with a private
IP** works with no extra setup — connect the VPN, then open the same
`http://<server-lan-ip>:8080/` URL. Private ranges (`10.x`, `192.168.x`,
`172.16–31.x`, CGNAT `100.64.x`) all pass the built-in network guard.

If your VPN hands out a **public-looking** IP and you get "only available on
the factory network", turn the IP guard off by starting the server with:

```
REL_LAN_ONLY=0 python3 server.py
```

(The guard is defense-in-depth only; the username/password login is always
enforced regardless.)

## 4. Trade-off to know: plain HTTP and the mobile app

Because there's no HTTPS, the mobile app at `/m/` runs as a normal browser
tab. It **cannot be installed to the home screen and has no offline mode**
(browsers only allow that on HTTPS or `localhost`). Everything else works
identically. Given the floor has stable Wi-Fi to the server, this is the
accepted trade for keeping operator phones free of any certificate — their
banking / payment apps stay untouched.

If offline/installable mobile ever becomes a hard requirement, the way back
is a proper public HTTPS certificate (e.g. `tailscale serve`, which needs no
custom CA) — but that reintroduces the VPN client the operators found
awkward, so it's a deliberate future choice, not a default.

## 5. Keep it running (Windows)

Simplest: a shortcut in `shell:startup` that runs
`python3 C:\...\REL_DYEING\mvp\server.py`. For a hands-off service, wrap it
with NSSM (`nssm install REL-UNITY python3 ...\server.py`) so it starts on
boot and restarts on crash. The server already auto-reloads when `server.py`
changes and never caches pages.

## 6. Data & backups

The data file is a single SQLite database next to `server.py` (path printed
on startup). Back it up by copying that file while the server is stopped, or
use the existing git repo. The `secrets.local.json` file (PLC / email
credentials) is gitignored — never commit it.
