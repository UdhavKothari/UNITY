# Colour on the Floor — a use-case playbook for the REL Dyeing ERP

**Purpose:** how to use colour deliberately across the software (and the physical floor it drives) so that a worker who can't read fast — or at all — can still do the right thing at a glance, and mistakes get caught before they cost a re-dye. Researched July 2026; sources at the end.

---

## What the evidence says (and its limits)

1. **Colour is read faster than words and crosses language/literacy barriers.** In lean/5S factories, colour-coding turns a workplace into a system where "the right way is obvious at a glance" — less searching, fewer errors, faster movement, and lower mental load. This is exactly our workforce situation.
2. **But colour alone is not enough.** Comprehension improves with training and prior education, and colour-blind workers (~8% of men) can't separate red from green. The rule the research keeps repeating: **colour + icon + text/shape redundancy**, a **small** palette (~6 meanings), and **consistency everywhere**. Never encode something critical in colour alone.
3. **There is a shared "safety grammar" people half-know already** (ANSI Z535 / road signs): **red = danger/stop**, **orange = warning**, **yellow = caution**, **green = go/safe/OK**, **blue = information**. Leaning on this grammar means less to teach.
4. **In dyehouses specifically, the #1 KPI is "right-first-time"** — batches that hit the target shade with no re-dye. The costly errors are: wrong shade run, wrong lot/taka picked, wrong machine loaded, and shade drift caught too late. Colour cues should be aimed squarely at those four.

**Design guardrail (matches our `rel-dyeing-design-insight` rules):** colour must *mean* something. We keep the restrained navy UI; colour is the signal layer on top, never decoration. Every colour cue is paired with an icon and a short mono label.

---

## The REL colour language (one system, learned once)

Two *separate* colour tracks so they never collide:

**Track A — the real fabric colour (shade).** Already in the app: the shade swatch = HSL(family, tone). This is literal, not semantic. Keep it for anything about *what colour the goods are*.

**Track B — the status/safety grammar (semantic).** Reuse the tokens we already have and map them to the shared safety meanings:

| Meaning | Token | Where it fires |
|---|---|---|
| Running / OK / go | `--success` green | machine dyeing, batch done-good, QC pass |
| In-process / caution | `--warning` amber | pre-treatment, waiting-on-RFD, near-capacity |
| Wash / information | `--info` blue | machine wash, "notice" info, storage zone tags |
| Idle / neutral | grey `--muted` | free machine, empty cell |
| Stop / error / urgent | `--danger` red | over-capacity, re-dye needed, QC fail, urgent order, maintenance |

Six meanings, each already a token. That's the whole vocabulary — anyone learns it in a day.

---

## Use cases, by area (aimed at real errors)

### 1. Shop floor — "is this machine OK, and what's in it?"
- **Machine status pill** already does run/pre/wash/free/maint in the safety grammar. Reinforce with the **vat-fill tinted by the real running shade** (Track A) so a supervisor sees *both* "it's dyeing" (green pill) and "it's dyeing a dark navy" (the fill) from across the hall.
- **Over-fill guard in colour:** if a load exceeds the machine's cap, the fill turns **red** with a red cap icon — catches "too much fabric in this jet" before it's loaded.

### 2. Batch planner — "is this batch safe to run here?"
- **Sequence rows** carry the status pill (planned/running/done) in the grammar. 
- **Capacity breach = red inline** (already built) — the single most common planning error (overloading a jet).
- **Fabric-mismatch / customer-mismatch = red flag** (already built) — stops mixing fabrics or customers in one batch.
- **Shade-family band on each row:** a thin swatch in the shade's real colour so a planner sequencing light→dark *sees* the ramp and won't schedule a dark before a light on the same machine (which forces an extra wash). This turns the campaign rule into something you can see, not memorise.

### 3. Storage — "where is it, and did I grab the right cell?" (the overhaul)
- **Zone colour per storage area** (blue "notice" family, distinct hues per area) printed on the QR/label and shown in the grid — a picker in a hurry matches the *colour of the aisle* to the *colour on the pick list*.
- **Cell state by colour:** empty = grey, occupied = tinted by the **shade family of the fabric stored there** (Track A), reserved-for-a-batch = amber, over-capacity = red. A glance down a rack tells you what's free and what's spoken for.
- **QR/barcode label tinted by shade family + big lot number:** the label itself carries the fabric's colour block, so even before scanning, the eye confirms "this should be a red-family lot" — catches wrong-cell placement.
- **Retrieval routing:** when a batch is being assembled, the cells holding its takas light up **green** ("go get these"); once scanned/removed they flip grey. This directly attacks the "picked the wrong taka/lot" error.

### 4. Shade & QC — "did we hit the colour?"
- **Shade swatch + tone number** everywhere a shade is named (built).
- **QC result in the safety grammar:** ΔE within tolerance = **green PASS**, borderline = **amber**, out of tolerance = **red FAIL / re-dye**. Re-dye is our most expensive event — make it a red flag no one can miss.

### 5. Priority / due-date heat
- **Urgency uses red** (matches the shared "red = act now" instinct). Optional due-date heat: on-time = grey, tight = amber, late/urgent = red — so the floor self-prioritises without reading dates.

### 6. Stage / role cues (different people, different colours)
The route is greige → pre-treatment → **RFD** → dyeing → finishing → dispatch. Give each **stage** a consistent accent so each worker recognises "my step" at a glance:
- pre-treatment = amber, RFD buffer = blue, dyeing = green, finishing = a distinct 6th hue (e.g. teal), dispatch/done = grey-with-check.
A pre-treatment operator learns "amber is mine"; a dispatch clerk learns "grey check is ready to go." Colour becomes the wayfinding for people who route work without reading job cards.

---

## Non-negotiables (so colour helps instead of misleading)

1. **Never colour alone.** Every cue = colour **+** icon **+** short mono label. A red pill always also says `MAINT` with a warning glyph. (Covers colour-blindness and reinforces learning.)
2. **One meaning per colour, everywhere.** Red never means "urgent" in one screen and "selected" in another. Consistency is what the research says makes it stick.
3. **Keep it to ~6 semantic colours.** More colours = noise = people stop trusting them.
4. **Lean on the safety grammar** people already know (red/amber/green/blue) rather than inventing associations.
5. **Pair with a one-page floor chart** (printed, colour key + icon + meaning) at each station — the studies are clear that a little training multiplies the payoff, especially for lower-literacy staff.
6. **Accessibility:** test the palette in greyscale and a colour-blind simulator; because every cue also has an icon/label, it still works.

---

## Highest-leverage first (if we do this incrementally)
1. **Storage cell/zone colour + shade-tinted QR labels** — biggest daily error surface (mispick/misplace), and it rides on the storage overhaul you already want.
2. **QC pass/amber/fail = green/amber/red** — directly targets the re-dye cost.
3. **Light→dark shade band in the batch planner** — prevents avoidable washes.
4. **Stage accent colours** — wayfinding for the least-literate roles.

Each is small, uses tokens we already have, and maps to a specific error it prevents.

---

## Sources
- [5S Color Coding Chart for Visual Communication and Safety — DuraLabel](https://resources.duralabel.com/guides/5s-color-coding-chart)
- [Visual Workplace and Lean Manufacturing — DuraLabel](https://resources.duralabel.com/articles/visual-workplace-and-lean-manufacturing)
- [The Role of Color in Workplace Safety — Mr. Chain](https://mrchain.com/blogs/news/the-role-of-color-in-workplace-safety-colors)
- [Safety sign comprehension of fiberboard industry employees (NIH/PMC study)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10258412/)
- [What Are ANSI Color Codes? — SafetySign](https://www.safetysign.com/what-are-ansi-color-codes)
- [ANSI Z535.1 Safety Colors — In Compliance Magazine](https://incompliancemag.com/ansi-z535-1-safety-colors-in-focus/)
- [How Digital Process Tracking Transforms Dyeing and Finishing Operations — Appit](https://www.appitsoftware.com/blog/dyeing-finishing-process-tracking-textile-erp)
- [Textile Dyeing & Processing ERP: Recipe, Shade Matching — FlowSense](https://www.flowsense.solutions/blog/textile-dyeing-processing-erp)
- [Why Color Variance Still Stops Textile Shipments — TSG](https://textiletsg.com/blog/textile-color-variance/)
