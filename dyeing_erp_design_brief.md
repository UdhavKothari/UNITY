# Design Brief — REL Dyeing ERP (Planning & Scheduling)

## Product in one line
A web app for a textile **dyeing mill** that plans production and manages master
data. It converts fabric orders into machine schedules (pre-treatment → dyeing →
finishing) and lets the owner manage all reference data. Runs on the factory LAN;
used on office PCs, floor terminals, and phones.

## Primary design goals (in priority order)
1. **Reduce data-entry errors.** Operators and admins enter lots of numbers and
   references. Prefer dropdowns over free text, validate inline, show units,
   default sensibly, and preview the result of an entry before it's saved.
2. **Make dense information scannable.** Lots of tables and a schedule. Use clear
   hierarchy, grouping, whitespace, and color-coding so nothing feels like a wall
   of grey.
3. **Intuitive for non-technical mill staff.** Plain language, obvious primary
   actions, forgiving flows, no jargon in the UI chrome.

## Users & contexts
- **Owner / R&D (admin):** desktop, manages all master data. Power user, wants speed.
- **Sales:** desktop, enters orders (customer, quality, one-or-more shades, qty in
  meters, due date, priority).
- **Supervisor:** floor terminal + phone, watches live machine status and the schedule.
- **Operators:** phone on the floor, scan a batch and see instructions (later phase).

## Two surfaces
1. **Operations** (daily use): order entry, a machine **schedule (Gantt)**, and a
   **shop-floor status board**.
2. **Admin** (owner only): CRUD for all master tables + settings + a live plan view.

## Key screens to design
- **Shop-floor board:** one card per machine (drum, jigger, jet, stentor, hydro,
  rope). Each card shows current status (Idle / Dyeing / Pre-treat / Wash), the
  current shade as a colour swatch, the order + quality + meters, and queue count.
  Colour-code by shade (light→dark). Must read at a glance from across a room.
- **Schedule (Gantt):** rows = machines, x-axis = time in hours. Blocks coloured by
  shade (light→dark within a machine = a "campaign"), with distinct patterns for
  **wash** cycles and **pre-treatment**. Each dye block shows small load/unload caps.
  Legend for shade families + wash + pre-treatment.
- **New order form:** customer, quality, due date, priority, then a repeatable list
  of **shade + meters** rows (a "+ add shade" control; shades filter to the chosen
  quality). On submit, show a result: kg conversion, batch split, promised date, and
  a warning if it misses the due date.
- **Admin console:** left **sidebar** grouped by domain (Production setup, Colour &
  recipes, Commercial, Store & stock, People & QC, System), a **dashboard** with
  count cards, and per-table screens (searchable table + Add/Edit/Delete). Forms open
  in a modal, organised into labelled **sections**, with a **live shade swatch
  preview** for shade recipes.

## Master tables to accommodate (for layout/density)
Machines, Qualities (with 2-step pre-treatment fields), Shade Recipes (quality-
specific: family, tone 0–10, dyes+%, and spectrophotometer L*/a*/b* + ΔE tolerance),
Quality Recipes (auxiliary chemicals), Customers, Orders, Storage Areas (shelves ×
rows × columns for taka indexing), Suppliers, Operators, QC metrics, Users.

## Interaction & error-prevention requirements
- Dropdowns for every reference (machine type, shade family, quality, customer).
- Numeric fields show units and enforce min/max (e.g. tone 0–10, min load 300 m).
- Required fields marked; inline error messages, not just alerts.
- Live preview where meaningful (shade swatch from family+tone; batch split preview).
- Search on every table; empty states with a clear "add first record" prompt.
- Confirm before destructive actions.

## Visual direction
- Clean, modern, **industrial-but-friendly**. Flat surfaces, soft shadows, rounded
  corners. Not dull — use one accent colour plus shade-family hues for data.
- Strong typographic hierarchy; tabular numbers for all figures.
- Colour has meaning: shade swatches (light→dark), status pills (running/idle/wash/
  pre-treat/maintenance), family hues on the Gantt. Keep chrome neutral so data pops.
- Touch targets comfortable for floor/phone use; high contrast for shop-floor screens.
- Iconography: simple line icons for nav and machine types.

## Constraints
- Self-contained web app (HTML/CSS/JS), served from a local server on the LAN.
- Works responsively on desktop, floor terminal, and phone (no separate native app).
- No login yet (planned later) — design a spot in the header for it.

## Deliverables I want from you
- High-fidelity mockups of: shop-floor board, schedule Gantt, new-order flow, admin
  dashboard, and one representative admin table + its edit modal.
- A small component/style spec: colours (incl. shade-family + status palette),
  typography scale, spacing, buttons, inputs, table, card, pill, modal.
- Mobile layout for the shop-floor board and new-order form.
