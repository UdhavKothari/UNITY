#!/usr/bin/env python3
"""
Robust mill-challan PDF parser for REL-UNITY.

One PDF page = one lot. Each page has:
  - a header block (QUALITY, Packing List No + date, delivery info)
  - a rolls table (SR, Roll No, Meters, Design, ..., OWN SHADE, [TO SHADE], Inches, Weight)
  - a footer (TOTAL TAKA / TOTAL METER, PROCESS REMARK, "To Shade : ...")

Design goals (the format is NOT final and will change):
  - The table is parsed by COLUMN POSITION, mapped from the header row's words — so adding a
    "TO SHADE" column, renaming "OWNSHADE", or reordering columns does not break it.
  - Header/footer fields are parsed by KEYWORD (label) regex, not fixed line numbers.
  - Every field is best-effort: a missing field yields "" / [] rather than an exception.
  - Weight rule: a roll's weight is treated as REAL only when it is > REAL_WEIGHT_MIN kg.

Requires pdfplumber (pip install pdfplumber). Import parse_challan_pdf() from the poller.
"""
import re, sys, json, datetime

REAL_WEIGHT_MIN = 2.0          # kg; weights at or below this are placeholders, not real
# tokens in the PROCESS REMARK that are never a customer name
_REMARK_STOP = {"GREY", "RFD", "RF", "DYEING", "PO", "MARKA", "GREIGE", "WHITE", "SEMI"}
# canonical column keys we care about, matched against the header words (normalized)
_COL_ALIASES = {
    "sr":       ["SR", "SRNO", "SR.", "S.R."],
    "rollNo":   ["ROLLNO", "ROLL", "ROLLNO.", "TAKANO", "ROLLNUMBER"],
    "meters":   ["METERS", "METER", "MTR", "MTS"],
    "design":   ["DESIGN"],
    "sku":      ["SKU"],
    "ownShade": ["OWNSHADE", "OWN"],
    "toShade":  ["TOSHADE", "TO"],
    "inches":   ["INCHES", "INCH", "WIDTH"],
    "weight":   ["WEIGHT", "WT"],
}


def _norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def _num(s):
    try:
        return float(re.sub(r"[^0-9.\-]", "", str(s)) or 0)
    except (ValueError, TypeError):
        return 0.0


def _lines_from_words(words, ytol=3):
    """group pdfplumber words into visual lines (rows) by their vertical position."""
    rows = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if rows and abs(w["top"] - rows[-1][0]) <= ytol:
            rows[-1][1].append(w)
        else:
            rows.append([w["top"], [w]])
    return [sorted(ws, key=lambda w: w["x0"]) for _, ws in rows]


def _find_header_row(lines):
    """the table header is the line that contains the roll-table labels."""
    best, best_score = None, 0
    for ln in lines:
        norms = [_norm(w["text"]) for w in ln]
        score = sum(1 for key in ("ROLL", "METERS", "WEIGHT", "OWNSHADE", "SR", "INCHES")
                    if any(n.startswith(key) or key.startswith(n) for n in norms if n))
        if score > best_score:
            best, best_score = ln, score
    return best if best_score >= 3 else None


def _column_map(header_words):
    """map each header word to a canonical column key + its x-centre, for position slicing."""
    cols = []                       # list of (key, x_center)
    used = set()
    # first pass: multi-word headers like "OWN SHADE" / "TO SHADE" collapse to the leading word
    for w in header_words:
        n = _norm(w["text"])
        if not n:
            continue
        key = None
        for k, aliases in _COL_ALIASES.items():
            if any(n == _norm(a) or n.startswith(_norm(a)) for a in aliases):
                key = k
                break
        cols.append([key, (w["x0"] + w["x1"]) / 2.0, w["text"]])
    # two OWNSHADE columns in the current layout: 1st = ownShade, 2nd = toShade (future "TO SHADE")
    own = [c for c in cols if c[0] == "ownShade"]
    if len(own) >= 2 and not any(c[0] == "toShade" for c in cols):
        own[1][0] = "toShade"
    return [(k, x) for k, x, _ in cols if k]


def _assign(row_words, colmap):
    """assign each data word to the nearest column centre; concatenate words landing in one column."""
    out = {k: [] for k, _ in colmap}
    if not colmap:
        return {}
    xs = [x for _, x in colmap]
    keys = [k for k, _ in colmap]
    for w in row_words:
        cx = (w["x0"] + w["x1"]) / 2.0
        i = min(range(len(xs)), key=lambda j: abs(xs[j] - cx))
        out[keys[i]].append(w["text"])
    return {k: " ".join(v).strip() for k, v in out.items()}


def _kv(text, label, pattern=r"([^\n]*)"):
    m = re.search(re.escape(label) + r"\s*:?\s*" + pattern, text, re.I)
    return (m.group(1).strip() if m else "")


def _parse_date(s):
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s.strip()


def _customer_from_remark(remark):
    """the customer is a '/'-delimited alphabetic token in the process remark (INDIGO, MAHAVEER…)."""
    for tok in re.split(r"[\/,]", remark):
        t = tok.strip()
        u = re.sub(r"[^A-Za-z]", "", t).upper()
        if len(u) >= 3 and u == t.replace(" ", "").upper() and u not in _REMARK_STOP \
                and not u.startswith("PO") and not u.startswith("MARKA"):
            return t
    return ""


def parse_page(page):
    text = page.extract_text() or ""
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    lines = _lines_from_words(words)

    lot = {"quality": "", "customer": "", "customerGuess": "", "toShade": "", "ownShade": "",
           "width": 0, "process": "", "packingListNo": "", "packingDate": "", "po": "",
           "processRemark": "", "totalTaka": 0, "totalMeter": 0.0,
           "rolls": [], "takas": [], "takaWts": [], "realWeightKg": 0.0}

    # ---- header / footer fields by keyword ----
    for line in text.splitlines():                    # "QUALITY : : LEAD" -> take after the last colon
        if "QUALITY" in line.upper():
            tail = line.upper().split("QUALITY", 1)[1]
            q = tail.split(":")[-1].strip()
            q = re.split(r"\s{2,}", q)[0].strip()      # drop any trailing column bleed
            if q:
                lot["quality"] = q
            break
    # "Packing List :ML05859/26" — require the colon right after the label so the
    # "Packing List Dt. :12/08/2026" line is not mistaken for the number.
    m = re.search(r"Packing List\s*:\s*([A-Z0-9][A-Z0-9/\-]+)", text, re.I)
    if m:
        lot["packingListNo"] = m.group(1).strip()
    m = re.search(r"Packing List Dt\.?\s*:?\s*([0-9/\-]+)", text, re.I)
    if m:
        lot["packingDate"] = _parse_date(m.group(1))
    m = re.search(r"To\s*Shade\s*:?\s*([A-Z0-9\-]+)", text, re.I)
    if m:
        lot["toShade"] = m.group(1).strip()
    m = re.search(r"PROCESS REMARK\s*(.+?)(?:\s+To\s*Shade|\n|$)", text, re.I | re.S)
    if m:
        lot["processRemark"] = re.sub(r"\s+", " ", m.group(1)).strip()
    rk = lot["processRemark"]
    lot["customerGuess"] = _customer_from_remark(rk)
    lot["customer"] = lot["customerGuess"]
    mp = re.search(r"PO[-\s]*([A-Z0-9+]+)", rk, re.I)
    if mp:
        lot["po"] = mp.group(1).strip()
    mw = re.search(r'(\d{2,3})\s*"', rk) or re.search(r'(\d{2,3})\s*(?:INCH|IN)\b', rk, re.I)
    if mw:
        lot["width"] = int(mw.group(1))
    m = re.search(r"TOTAL\s*TAKA\s*:?\s*(\d+)", text, re.I)
    if m:
        lot["totalTaka"] = int(m.group(1))
    m = re.search(r"TOTAL\s*METER\s*:?\s*([0-9.]+)", text, re.I)
    if m:
        lot["totalMeter"] = _num(m.group(1))

    # ---- rolls table by column position ----
    header = _find_header_row(lines)
    if header:
        colmap = _column_map(header)
        htop = header[0]["top"]
        for ln in lines:
            if ln[0]["top"] <= htop:
                continue
            first = _norm(ln[0]["text"])
            # a data row starts with the SR integer; stop at footer lines
            if not re.fullmatch(r"\d{1,3}", ln[0]["text"].strip()):
                # stop once we hit the footer ("Parcel", "TOTAL", etc.)
                if any(_norm(w["text"]).startswith(("PARCEL", "TOTAL", "PROCESS")) for w in ln):
                    continue
                continue
            row = _assign(ln, colmap)
            roll = (row.get("rollNo") or "").split()[0] if row.get("rollNo") else ""
            meters = _num(row.get("meters"))
            weight = _num(row.get("weight"))
            if meters <= 0:                     # meters are often glued to the design ("94.000420193_1")
                joined = " ".join(w["text"] for w in ln)
                mm = re.search(r"(?<![\d.])(\d{1,4}\.\d{3})(?!\d*\.)", joined)   # meters carry 3 decimals
                if mm:
                    meters = _num(mm.group(1))
            if not roll and not meters:
                continue
            real = weight > REAL_WEIGHT_MIN
            lot["rolls"].append({"rollNo": roll, "meters": round(meters, 2),
                                 "weight": round(weight, 2), "realWeight": real,
                                 "ownShade": (row.get("ownShade") or "").strip(),
                                 "toShade": (row.get("toShade") or "").strip()})
            if meters > 0:
                lot["takas"].append(round(meters, 2))
                lot["takaWts"].append(round(weight, 2) if real else 0.0)
            if not lot["ownShade"] and row.get("ownShade"):
                lot["ownShade"] = row["ownShade"].strip()

    lot["realWeightKg"] = round(sum(r["weight"] for r in lot["rolls"] if r["realWeight"]), 2)
    lot["pcs"] = len(lot["takas"])
    lot["meters"] = round(sum(lot["takas"]), 2)
    return lot


def parse_challan_pdf(path):
    import pdfplumber
    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            try:
                lot = parse_page(page)
            except Exception as e:              # never let one bad page abort the whole challan
                lot = {"error": str(e), "rolls": [], "takas": []}
            if lot.get("rolls") or lot.get("takas"):
                out.append(lot)
    return out


if __name__ == "__main__":
    data = parse_challan_pdf(sys.argv[1])
    print(json.dumps(data, indent=2, ensure_ascii=False))
