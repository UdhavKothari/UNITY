# Program Scan — on-site setup (photo → batches, fully offline)

The phone **Scan** tab lets an operator photograph the handwritten jet register (left page +
right page) and punch the batches straight into the plan. The handwriting is read by a **vision
model that runs on YOUR network** — the app server forwards the photos to it over the LAN and
gets structured data back. **Nothing is ever sent to the internet or any external API.**

```
Phone (Scan tab)  ──photos──▶  App server (LAN, no internet)  ──LAN──▶  Ollama + vision model (the iMac)
        ▲                                   │                                     │
        └────────── review + confirm ───────┘◀──────── structured batches ────────┘
```

## 1. The reader machine (the iMac)

Run the vision model on the 27" iMac (i5 6-core, Radeon Pro 580X, RAM → 16 GB min, 32–64 GB better).

Honest expectations on this hardware:
- On an **Intel Mac the AMD GPU is not used** for this — Ollama runs on the **CPU**. That's fine for
  your volume, just not instant.
- Expect roughly **30 s – 2 min per scan**, and **good-but-not-perfect** accuracy — which is exactly
  why every scan goes through the editable review screen before anything is saved.
- Set the iMac to **never sleep** (System Settings → Displays/Battery → never), so the app server can
  always reach it. Keep it plugged in and awake.

## 2. Install Ollama on the iMac

1. Download the macOS app from https://ollama.com/download and open it (it runs as a menu-bar service).
   *(This is the only step that needs internet — to download Ollama and the model once. After that the
   whole thing works with no internet.)*
2. Make Ollama listen on the LAN (not just localhost) so the app server can reach it. In Terminal:
   ```
   launchctl setenv OLLAMA_HOST 0.0.0.0:11434
   ```
   Then quit and reopen the Ollama app so it picks that up. (To make it stick across reboots, add the
   same `launchctl setenv` line to a login item / script.)
3. Pull a vision model (one-time download, needs internet just for this):
   ```
   ollama pull qwen2.5vl:7b
   ```
   Alternatives, by trade-off:
   - `qwen2.5vl:3b` — faster, lighter (good if 16 GB feels tight); a bit less accurate.
   - `qwen2.5vl:7b` — the recommended balance.
   - `minicpm-v` — strong OCR, another good option to compare against.

## 3. Point the app server at it

Find the iMac's LAN IP (System Settings → Network, e.g. `192.168.0.60`). On the **app server**, edit
`REL_DYEING/mvp/secrets.local.json` (create it from `secrets.example.json` if needed) and set:

```json
"vision": {
  "endpoint": "http://192.168.0.60:11434",
  "model": "qwen2.5vl:7b",
  "enabled": true,
  "timeoutSecs": 240
}
```

Restart the app server. `secrets.local.json` is gitignored — never commit it.

## 4. Give operators access

In the web console: **Admin → Roles →** grant the **“Program scan (photo)”** page to whichever role
should be allowed to scan. Those users get a **Scan** tab in the mobile app.

## 5. Using it

On the phone: **Scan** tab → take the **left-page** photo and the **right-page** photo of one 2-page
spread → **Read pages**. In ~1 minute a review screen appears with every batch and lot. Anything not
already in the system (an unknown lot number, a new quality/shade, an unrecognised machine) is
**highlighted amber** for you to fix or pick. When it looks right, **Confirm & punch** — the batches
appear in the plan and the two photos are stored for the record.

## 6. Where the photos live / deleting them

Stored on the app server under `REL_DYEING/mvp/program_scans/`. Manage them from **Admin → Settings →
Program scans**: it lists every scan with thumbnails and lets you **delete one** or **delete all** (the
batches already created are kept). The scan reader's status (model + endpoint) is shown there too.

## 7. If it says the reader can't be reached

- Is the iMac awake and is the Ollama app running?
- Did you set `OLLAMA_HOST 0.0.0.0:11434` and reopen Ollama? Test from the app server:
  `curl http://<imac-ip>:11434/api/tags` should list your model.
- Is the macOS firewall blocking port 11434? Allow incoming connections for Ollama.
- Is `vision.endpoint` in `secrets.local.json` the iMac's current LAN IP?
