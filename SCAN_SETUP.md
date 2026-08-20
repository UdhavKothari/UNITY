# Program Scan — setup (camera + QR handoff, Gemini API)

The Batch planner has a **camera** button. Click it and a QR code appears — scan it with any
phone on the factory Wi-Fi, no login needed on the phone. Photograph the handwritten jet register
(left page + right page of each spread), send, and close the phone — the photos already appeared
back on the **desktop that opened the code**. That person reviews and edits the read-out there,
then punches it into real batches. Only they can see/apply that session's photos.

The handwriting is read by the **Gemini API** (Google). This is the one deliberate outbound-internet
call this app makes — everything else is LAN-only.

```
Desktop (camera button)  ──QR code──▶  Phone (no login, scan_upload.html)
        │                                        │
        │  photos land on the session the        │ photographs + sends
        │  desktop opened (token-scoped)          ▼
        └──────────◀── App server (LAN) ──photos──┘
                              │
                              ▼
                        Gemini API (internet)
                              │
                              ▼
                 structured batches ──▶ reviewed + confirmed on the SAME desktop
```

## 1. Get a Gemini API key

Go to https://aistudio.google.com/apikey, create a key (a free tier is enough to start). Keep it
secret — anyone with the key can spend against your account.

## 2. Point the app server at it

On the **app server**, edit `REL_DYEING/mvp/secrets.local.json` (create it from
`secrets.example.json` if needed) and set:

```json
"gemini": {
  "apiKey": "YOUR-KEY-HERE",
  "model": "gemini-2.0-flash",
  "enabled": true,
  "timeoutSecs": 120
}
```

Restart the app server. `secrets.local.json` is gitignored — never commit it, never share the key.

## 3. Give people access

In the web console: **Admin → Roles →** grant the **"Program scan (camera)"** page (`op_scan`,
with **edit** ticked, not just view — starting a scan and applying it both cost a real API call
and create data) to whichever role should be allowed to use the camera button.

## 4. Using it

1. **Operations → Batch planner → Camera** button. A QR code appears.
2. Scan it with a phone on the factory Wi-Fi (any phone — no login, no app to install).
3. On the phone: photograph the **left page**, then the **right page** of one spread. Add as many
   spreads as you like, then **Send**. The phone shows a confirmation — you can close it.
4. Back on the desktop that opened the code, the photos appear automatically and get read within
   about a minute. A review screen shows every batch and lot. Anything not already in the system
   (an unknown lot number, a new quality/shade, an unrecognised machine) is **highlighted amber**
   for you to fix or pick.
5. **Confirm & punch** — the batches appear in the plan and the photos are archived for the record.

The QR code / upload link stays live for **20 minutes**. If it's not used within that window, or
once it's applied, it stops accepting new photos — open the camera button again for a fresh one.

## 5. Where the photos live / deleting them

Once applied, the photos are stored on the app server under `REL_DYEING/mvp/program_scans/`.
Manage them from **Admin → Settings → Program scans**: it lists every scan with thumbnails and
lets you **delete one** or **delete all** (the batches already created are kept). The scan
reader's status (model, enabled/not) is shown there too. Working photos for a scan that's still
in progress live under `REL_DYEING/mvp/scan_sessions/<id>/` and are cleaned up automatically once
applied, cancelled, or expired.

## 6. If it says the reader isn't configured / can't be reached

- Is `gemini.apiKey` actually set in `secrets.local.json` (not just `secrets.example.json`)?
- Does the app server itself have working internet access? (Everything else in this app is
  LAN-only by design — this is the one feature that needs an outbound connection.)
- Check **Admin → Settings → Server log** for the exact error Gemini returned (bad key, quota,
  etc.) — it's shown to the user on the review screen too.
- **"Gemini API error 404: models/... is not found"** — the `gemini.model` name in
  `secrets.local.json` isn't one Google currently serves for your key. Google renames/retires
  model IDs over time (this has already happened once — `gemini-2.0-flash` was the original
  default and no longer works). Look up a current model name at
  https://ai.google.dev/gemini-api/docs/models and set `gemini.model` to it — this needs
  **no server restart**, `secrets.local.json` is re-read on every scan, just try again.
  Note: `pip install google-genai` does **not** affect this — the server talks to Gemini
  directly over HTTP (`urllib`), it doesn't use that SDK, so installing/upgrading it has no
  effect either way.

## 7. If the QR code won't scan / the phone page says "link expired"

- Make sure the phone is on the **factory Wi-Fi** — this is a LAN-only app, phones on mobile data
  can't reach it.
- The link is only good for 20 minutes and only for one scan session — go back to the desktop and
  click the camera button again for a new code.
