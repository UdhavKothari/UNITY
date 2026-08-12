#!/usr/bin/env python3
"""
Gmail -> challan poller for REL-UNITY.

Runs on the factory PC (or any always-on machine). It:
  1. logs into the mailbox over IMAP (read-only creds live in secrets.local.json, never committed),
  2. finds UNSEEN messages that carry a PDF attachment (optionally from a chosen sender),
  3. saves each PDF, runs the robust parser (challan_parser.parse_challan_pdf),
  4. writes the parsed lots as JSON into mvp/inbox_challan/ where the server ingests them,
  5. marks the message \\Seen so it is not processed twice.

Gmail needs an APP PASSWORD (Account -> Security -> 2-step verification -> App passwords), not the
normal password. Put these in mvp/secrets.local.json:
    { "gmailUser": "osbyrel@gmail.com", "gmailAppPassword": "xxxx xxxx xxxx xxxx",
      "gmailFolder": "INBOX", "gmailFromFilter": "" }

Run once:   python challan_watch.py
Loop mode:  python challan_watch.py --loop        (polls every CHALLAN_POLL_SECS)
Requires: pip install pdfplumber   (imaplib/email are stdlib)
"""
import os, sys, json, time, ssl, imaplib, email, hashlib, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SECRETS = os.path.join(HERE, "secrets.local.json")
OUT_DIR = os.path.join(HERE, "inbox_challan")          # server watches this
PDF_DIR = os.path.join(HERE, "inbox_challan", "pdf")   # kept copies of the source PDFs
CHALLAN_POLL_SECS = 120

sys.path.insert(0, HERE)
import challan_parser as CP

LOG = os.path.join(OUT_DIR, "challan.log")


def _log_line(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + str(msg)
    print(line, flush=True)
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _secrets():
    try:
        with open(SECRETS, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _connect(cfg):
    ctx = ssl.create_default_context()
    m = imaplib.IMAP4_SSL(cfg.get("gmailHost", "imap.gmail.com"), 993, ssl_context=ctx)
    m.login(cfg["gmailUser"], cfg["gmailAppPassword"])
    m.select(cfg.get("gmailFolder", "INBOX"))
    return m


def _pdf_attachments(msg):
    for part in msg.walk():
        fn = part.get_filename() or ""
        ct = (part.get_content_type() or "").lower()
        if fn.lower().endswith(".pdf") or ct == "application/pdf":
            payload = part.get_payload(decode=True)
            if payload:
                yield (fn or "challan.pdf"), payload


def process_once(verbose=True):
    cfg = _secrets()
    if not os.path.exists(SECRETS):
        _log_line("[challan] secrets.local.json not found — copy secrets.example.json to it and add the Gmail app password.")
        return None
    if not cfg.get("gmailUser") or not cfg.get("gmailAppPassword"):
        _log_line("[challan] gmailUser / gmailAppPassword missing (or blank) in secrets.local.json — nothing to do.")
        return None
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)
    m = _connect(cfg)
    try:
        crit = ["UNSEEN"]
        frm = (cfg.get("gmailFromFilter") or "").strip()
        if frm:
            crit += ["FROM", frm]
        typ, data = m.search(None, *crit)
        ids = data[0].split() if data and data[0] else []
        done = 0
        for mid in ids:
            typ, raw = m.fetch(mid, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            subj = str(email.header.make_header(email.header.decode_header(msg.get("Subject", ""))))
            atts = list(_pdf_attachments(msg))
            if not atts:
                continue                      # leave non-PDF mails UNSEEN
            stamp = time.strftime("%Y%m%d-%H%M%S")
            for i, (fn, payload) in enumerate(atts):
                sig = hashlib.sha1(payload).hexdigest()[:10]
                pdf_path = os.path.join(PDF_DIR, "%s-%s.pdf" % (stamp, sig))
                with open(pdf_path, "wb") as f:
                    f.write(payload)
                try:
                    lots = CP.parse_challan_pdf(pdf_path)
                except Exception as e:
                    print("[challan] parse failed for", fn, ":", e, flush=True)
                    lots = []
                out = {"source": fn, "subject": subj, "receivedAt": datetime.datetime.now().isoformat(timespec="seconds"),
                       "sig": sig, "lots": lots}
                with open(os.path.join(OUT_DIR, "%s-%s.json" % (stamp, sig)), "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False)
                if verbose:
                    print("[challan] %s -> %d lots" % (fn, len(lots)), flush=True)
                done += 1
            m.store(mid, "+FLAGS", "\\Seen")
        return done
    finally:
        try: m.logout()
        except Exception: pass


def _run_safe():
    try:
        n = process_once()
        if n is not None:
            _log_line("[challan] run complete — %d PDF attachment(s) processed" % (n or 0))
        return True
    except imaplib.IMAP4.error as e:
        _log_line("[challan] EMAIL LOGIN FAILED: %s" % e)
        _log_line("          Fix: turn ON 2-Step Verification for the Gmail account, use an APP")
        _log_line("          PASSWORD (16 chars, not the normal password), and make sure IMAP is")
        _log_line("          enabled (Gmail -> Settings -> Forwarding and POP/IMAP -> Enable IMAP).")
        return False
    except (OSError, ssl.SSLError) as e:
        _log_line("[challan] CONNECTION ERROR (no internet / firewall / wrong host): %s" % e)
        return False
    except Exception as e:
        _log_line("[challan] ERROR: %r" % e)
        return False


def main():
    if "--loop" in sys.argv:
        _log_line("[challan] polling every %ds — close the window to stop" % CHALLAN_POLL_SECS)
        while True:
            _run_safe()
            time.sleep(CHALLAN_POLL_SECS)
    else:
        _run_safe()


if __name__ == "__main__":
    main()
