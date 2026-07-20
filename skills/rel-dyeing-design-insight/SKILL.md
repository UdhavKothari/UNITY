---
name: REL_DYEING Design Insight
description: Design system and build rules for the REL Dyeing ERP (web app now, mobile/floor app later) — light navy palette, Inter + IBM Plex Mono, Material Symbols icons, data-instrument components (vat-fill, Gantt, swatches), motion rules, and anti-generic-AI guardrails. Use this skill any time you build, style, or review any REL Dyeing screen, component, or new module.
---

# REL_DYEING Design Insight

Design rules for the REL Dyeing ERP so every screen — today's web app and the later floor/mobile app — looks and behaves like one product.

## Register: this is PRODUCT UI, not a brand site
Design **serves the task**. A supervisor on the floor and an admin at a desk must trust it instantly and forget it's there. Earned familiarity beats novelty. The failure mode is *strangeness without purpose*, not plainness.

## 1. Colour tokens (light, navy-committed, restrained)

```css
--bg:#f4f6fa;        /* cool off-white page — never cream/beige */
--surface:#ffffff;   --surface-2:#f8fafc;  --surface-3:#eef2f8;
--ink:#18233b;       --ink-2:#48546b;      --muted:#7a8598;  --faint:#9aa4b4;
--line:#e6eaf1;      --line-2:#dbe1ea;
--primary:#1f2d4d;   --primary-hover:#172440;   /* buttons, current nav */
--accent:#3a63c4;    --accent-soft:#eaf0fb;     /* focus ring, links, active */
--success:#2e9e6b;  --warning:#c9791f;  --danger:#d64545;  --info:#3a63c4;
```
- **Restrained is the floor.** Accent = primary actions, current selection, state indicators. Never decoration.
- Colour must **mean** something: shade swatches = the real fabric colour; status = semantic (dyeing/pre-treat/wash/idle/maintenance).
- Body text ≥ 4.5:1 contrast. Use `--ink` for body, `--muted` only for labels — never muted grey for readable prose.

## 2. Type & icons
- **Inter** for all UI. **IBM Plex Mono** for numbers, IDs, times, and uppercase micro-labels (`t+4h`, `SO-1013`, `715 kg`).
- Fixed rem scale (~1.2 ratio). No fluid `clamp()` headings in product UI.
- Mono uppercase labels are *functional section headers*, not decorative eyebrows — don't put one above every block.
- **Icons: Google Material Symbols Rounded only.** One icon family, everywhere.
  `precision_manufacturing` machines · `layers` qualities · `palette` shade recipes · `science` quality recipes · `groups` customers · `receipt_long` orders · `inventory_2` storage · `local_shipping` suppliers · `badge` operators · `verified` QC · `person` users · `admin_panel_settings` roles · `calendar_view_week` plan · `tune` settings · `schedule` clock · `search` search.
  Machine types: jet `water_drop` · jigger `waves` · drum `cyclone` · stentor `compress` · hydro `mode_fan` · rope `timeline`.

## 3. Shape & elevation
Radius: 14px cards · 10px controls · 8px chips/small.
Shadow: `0 1px 2px rgba(16,24,40,.04), 0 2px 6px rgba(16,24,40,.05)`; lift on hover `0 6px 20px rgba(16,24,40,.10)`.

## 4. Signature components (reuse, don't reinvent)
- **Vat-fill machine card** — the house instrument. A rounded "vat" with a bottom-up fill showing **load vs capacity**, tinted by the shade actually running, % label on top, machine-type icon, status pill, shade swatch + order/qty, queue count in the footer. Idle = dashed, hatched, empty.
- **Gantt** — rows = machines (or orders), light rounded blocks coloured by shade, hatched patterns for wash (blue) and pre-treatment (amber), pale load/unload caps at each block's edges, hover lift + exact `t+` window in the tooltip.
- **Status pills** — `run` (dyeing, green), `pre` (amber), `wash` (blue), `free` (grey), `maint` (red). Mono, uppercase, soft-tinted background.
- **Shade swatch** — 13px rounded square, real shade colour from family + tone.
- **KPI card** — icon tile + mono number + uppercase mono label. No gradient hero-metric template.
- **Schema-driven admin tables** — sticky mono headers, hover row tint, row actions revealed on hover, compact search (≤240px) with the icon inside the field.

## 5. Time convention
Current time lives in the header as a live clock — that is **t**. Everything scheduled is expressed **relative to now**: `t+2h`, `t+4h`, `t+12h`. Never show bare hour numbers on a plan axis.

## 6. Motion
- 150–250 ms; ease-out-expo `cubic-bezier(.16,1,.3,1)`.
- Motion **conveys state**: the vat fill rising to its level, a row entering, a value changing, hover lift. No decorative or orchestrated page-load choreography.
- Stagger lists ~35 ms per item, total ≤ 300 ms.
- **Every animation needs a `prefers-reduced-motion: reduce` fallback** (crossfade or instant).

## 7. Empty & error states
Empty states **teach**: icon + one-line explanation + the action that fixes it ("Add machines in Admin and the shop floor will appear here"). Never a bare "No data".
Errors are inline and specific, next to the field — not a generic alert.

## 8. Hard bans (rewrite the element if you catch yourself)
- **Side-stripe borders** (thick coloured `border-left` on cards/rows/alerts). Use full borders, tints, leading icons.
- Gradient text; glassmorphism as decoration; the gradient hero-metric template.
- Uppercase tracked eyebrows above every section; `01 / 02 / 03` numbered section scaffolding.
- Display fonts in labels, buttons, or data.
- Cream/beige/sand body backgrounds.
- Reinvented standard affordances (custom scrollbars, odd form controls).
- Modal as the first thought — exhaust inline/progressive options first.

## 9. Accessibility & density
Touch targets comfortable for gloved floor use; high contrast for shop-floor screens read from a distance. Dense tables are fine and welcome — this is a tool, not a brochure.

## 10. When adding a new module
1. Reuse the tokens and the components above before inventing anything.
2. Ask what the operator must see **at a glance** — build the instrument for that (a fill, a bar, a swatch, a countdown), not a paragraph.
3. Keep one button vocabulary, one icon family, one control set across every screen.
