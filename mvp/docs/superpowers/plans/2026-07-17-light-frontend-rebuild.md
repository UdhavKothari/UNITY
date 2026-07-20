# Light Front-End Rebuild — Implementation Plan

**Goal:** Rebuild the front end from a dark theme to a clean, light, navy-accented product UI (matching the user's reference), with strong data visualization, Google Material Symbols icons, and purposeful motion — without touching the backend, scheduler, or auth logic.

**Architecture:** Keep `server.py`, the scheduler (`computeSchedule`), and auth engine untouched. Rewrite the presentation layer only: `style.css` (design system), the head `<link>`s (fonts + icons), and the HTML-generating renderers in `app.js` (floor cards, KPIs, Gantt, login, user box) plus the admin/index shells. All components are class-driven, so a token rewrite reskins everything; renderers get upgraded for the new visual instruments.

**Tech stack:** Vanilla HTML/CSS/JS (no build step), Google Fonts (Inter + IBM Plex Mono), Material Symbols Rounded icon font, CSS keyframe motion.

## Global constraints (verbatim)
- Backend, scheduler, and auth/RBAC behavior must not change (only presentation).
- Product register: earned familiarity, restrained color (navy accent + semantic states), consistent components, motion conveys state (150–250ms), teaching empty states.
- Absolute bans to honor: NO side-stripe borders (current `.mc::before` left bar must go), no gradient text, no glassmorphism default, no hero-metric gradient template.
- Accessibility: body text ≥ 4.5:1 contrast; every animation has a `prefers-reduced-motion` fallback.

---

## Design system (locked)

**Palette (light, navy-committed; OKLCH intent noted):**
- `--bg` cool off-white `#f4f6fa` (oklch .975 .005 255 — cool, not cream)
- `--surface` `#ffffff`; `--surface-2` (sidebar/panels) `#f8fafc`
- `--ink` `#18233b` (body, high contrast); `--ink-2` `#48546b`; `--muted` `#7a8598` (labels only)
- `--line` `#e6eaf1`; `--line-2` `#dbe1ea`
- `--primary` navy `#1f2d4d` (buttons, current selection); `--primary-hover` `#172440`; on-primary `#ffffff`
- `--accent` `#3a63c4` (focus ring, links, active)
- Status: `--success` `#2e9e6b`, `--warning` `#d98a2b`, `--danger` `#d64545`, `--info` `#3a63c4`
- Radius: 14px card, 10px control, 8px chip. Shadow: `0 1px 2px rgba(16,24,40,.04), 0 2px 6px rgba(16,24,40,.05)`.

**Type:** Inter (sans; all UI) + IBM Plex Mono (numbers, uppercase micro-labels). Fixed rem scale (1.2 ratio). Mono labels are functional section headers (like the reference), not decorative eyebrows.

**Icons:** Material Symbols Rounded via `fonts.googleapis.com`. Map: machines→`factory`/type-specific, dashboard→`grid_view`, qualities→`layers`, shadeRecipes→`palette`, orders→`receipt_long`, customers→`groups`, storage→`inventory_2`, suppliers→`local_shipping`, operators→`badge`, qc→`verified`, users→`person`, roles→`admin_panel_settings`, plan→`calendar_view_week`, settings→`tune`, logout→`logout`, search→`search`, add→`add`.

**Motion:** ease-out-expo `cubic-bezier(.16,1,.3,1)`; hover/focus 160ms; card & row entrance = fade+translateY(6px), 40ms stagger, ≤300ms total; vat-fill bar animates height on mount (state = load level); KPI numbers quick count-up (~450ms). All gated behind `@media (prefers-reduced-motion: reduce)` → opacity/instant only.

**Signature instrument — the vat-fill machine card:** replaces the banned side-stripe. A rounded "vat" showing dye load vs capacity as an animated bottom-up fill tinted by the current shade, with a % label; a machine-type Material Symbol; a status pill (Dyeing/Pre-treat/Wash/Idle); current shade swatch + order/qty; queue count. Idle vats show a faint dashed outline.

---

## Phases (each independently shippable & testable)

### Phase 1 — Design tokens & shell (style.css + head links)
- Rewrite `static/style.css` to the light system above; delete side-stripe rules; add motion tokens + keyframes + reduced-motion block; restyle header, sidebar, cards, buttons, pills, tables, forms, modal, login.
- Add Inter + IBM Plex Mono + Material Symbols `<link>`s to `index.html` and `admin.html` heads (replace the old Manrope link).
- Verify: server serves updated css; both pages load; no dark colors remain.

### Phase 2 — Data instruments in the engine (app.js)
- Rewrite `renderFloor` → vat-fill machine cards (load %, shade tint, type icon, status pill, queue), with mount animation. Compute per-machine current load vs capacity from the schedule.
- Upgrade `renderGantt` to light rounded blocks (keep wash/pretreat patterns re-themed; remove any stripe), hover lift, mono time axis.
- KPI renderer: icon + mono count-up + label.
- Verify (jsdom + server): floor cards render with fill elements; gantt blocks present; KPIs present; no JS errors.

### Phase 3 — Icons, login, empty states, admin polish
- Swap admin nav inline SVGs → Material Symbols; add icons to buttons and KPIs.
- Restyle the login overlay + header user box to light.
- Teaching empty states for floor/schedule/tables (icon + one-line guidance + primary action).
- Verify: login overlay light; admin nav icons render; empty states show when data absent.

### Phase 4 — Full verification
- `python3 server.py` + jsdom: login (ADMIN), nav + CRUD still work, floor/gantt/KPIs render, permission filtering intact, contrast spot-check, reduced-motion present in CSS.
- Confirm no backend/auth/scheduler regressions.

## Self-review
- Coverage: light theme (P1), vat-fill + visualization (P2), icons + motion (P1–P3), login/empty states (P3), no-regression (P4). ✓
- Bans: side-stripe removed (P1/P2), no gradient text/glass/hero-gradient in token set. ✓
- Consistency: single button/control/pill vocabulary from tokens; icon family unified (Material Symbols). ✓
