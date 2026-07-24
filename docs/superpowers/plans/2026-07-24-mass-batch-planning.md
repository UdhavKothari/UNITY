# Mass Batch Planning + Taka-wise Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the one-at-a-time batch form with a machine-grouped, day-labelled Mass Batch Planning table that lets an operator enter/edit ~100+ batches, set each machine's load sequence, and hand-pick specific takas per lot.

**Architecture:** Fully manual planning. Each batch gains `machine`, `planDay`, and `seq`; the plan is exactly what the table says (auto-scheduler `computeSchedule` stays in the tree but no longer assigns machines). Pure logic (taka availability, totals, resequencing) lives in `app.js` as standalone functions tested with a Node VM-context harness; the UI is vanilla string-template rendering in `index.html`; the server change is additive (one page permission + a `_migrate` backfill).

**Tech Stack:** Zero-dependency Python stdlib server (`server.py`, JSON store), vanilla ES5-ish JS (`app.js`, `index.html`), CSS design tokens (`style.css`). Tests: Node `vm` harness (no jsdom in sandbox), live `curl`.

## Global Constraints

- Zero runtime dependencies — no new libraries, no CDN calls (LAN-only deployment). Vendored SheetJS already present for Excel.
- Follow the `rel-dyeing-design-insight` skill for every screen: navy tokens, Inter + IBM Plex Mono, Material Symbols Rounded, status pills, shade swatches, no side-stripe borders, no modal-as-first-thought.
- Traceability fields (timestamps, actor, `activityLog`) are server-stamped only; `machine`/`planDay`/`seq`/`takaNos` are operator data and may come from the client.
- Settings/records persist via the existing authenticated `POST /api` `op:"upsert"`; the server strips password hashes on read.
- One fabric per batch, one customer per batch, whole takas only — existing rules, preserved.
- A taka (identified by its lot id + taka number) belongs to at most one batch.
- Sequence (`seq`) is an integer restarting at 1 per (`machine`, `planDay`).
- Test harness pattern: load `app.js` into a Node `vm` context with a stub `DB`/`document`, per the 2026-07-22 plan (jsdom is not installable in the sandbox).

---

### Task 1: Server — register `op_massplan` permission + backfill batch fields

**Files:**
- Modify: `mvp/server.py:27-31` (`ALL_PAGES`)
- Modify: `mvp/server.py:100-140` (`_migrate`)
- Test: `mvp/tests/test_migrate_massplan.py` (new, plain Python — no framework)

**Interfaces:**
- Produces: every existing `batches` row gains `machine` (str, from `mcPin` or ""), `planDay` (str `YYYY-MM-DD`, from the row's created day or today), `seq` (int, per machine+day by existing order). New page key `"op_massplan"` grantable per role; Administrator self-heal (server.py:177-182) auto-grants it.

- [ ] **Step 1: Write the failing test**

Create `mvp/tests/test_migrate_massplan.py`:

```python
import importlib.util, os
spec = importlib.util.spec_from_file_location("srv", os.path.join(os.path.dirname(__file__), "..", "server.py"))
srv = importlib.util.module_from_spec(spec); spec.loader.exec_module(srv)

def test_massplan_page_registered():
    assert "op_massplan" in srv.ALL_PAGES

def test_migrate_backfills_batch_planning_fields():
    db = {"batches": [
        {"id": "B-0001", "mcPin": "JET-2"},
        {"id": "B-0002", "mcPin": "JET-2"},
        {"id": "B-0003", "mcPin": ""},
    ]}
    srv._migrate(db)
    b = {x["id"]: x for x in db["batches"]}
    assert b["B-0001"]["machine"] == "JET-2"
    assert b["B-0003"]["machine"] == ""            # no pin -> empty, still gets planDay/seq
    for x in db["batches"]:
        assert isinstance(x["seq"], int) and x["seq"] >= 1
        assert len(x["planDay"]) == 10             # YYYY-MM-DD
    # per-machine sequence restarts at 1
    assert b["B-0001"]["seq"] == 1 and b["B-0002"]["seq"] == 2

if __name__ == "__main__":
    test_massplan_page_registered()
    test_migrate_backfills_batch_planning_fields()
    print("ok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mvp && python3 tests/test_migrate_massplan.py`
Expected: FAIL — `AssertionError` on `"op_massplan" in srv.ALL_PAGES` (page not registered yet).

- [ ] **Step 3: Register the page**

In `mvp/server.py`, add `"op_massplan"` to `ALL_PAGES` (line 27-31) next to the other `op_` keys:

```python
ALL_PAGES = ["op_floor","op_schedule","op_order","op_batch","op_storage","op_massplan",
             "dashboard","machines","qualities","shadeRecipes","qualityRecipes",
             "batches","lots","weavers","takaMaster",
             "customers","orders","storageAreas","storageSlots","suppliers","operators","qcMetrics",
             "users","roles","plan","settings","activity","urgent_flag"]
```

- [ ] **Step 4: Backfill in `_migrate`**

In `mvp/server.py` `_migrate(db)`, before `db.setdefault("activityLog", [])` (line 138), add:

```python
    today = time.strftime("%Y-%m-%d")
    seq_by = {}
    for b in db.get("batches", []):
        if "machine" not in b:
            b["machine"] = b.get("mcPin") or ""; changed = True
        if "planDay" not in b:
            b["planDay"] = today; changed = True
        if "seq" not in b:
            key = (b.get("machine",""), b.get("planDay",""))
            seq_by[key] = seq_by.get(key, 0) + 1
            b["seq"] = seq_by[key]; changed = True
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd mvp && python3 tests/test_migrate_massplan.py`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add mvp/server.py mvp/tests/test_migrate_massplan.py
git commit -m "feat(server): register op_massplan page and backfill machine/planDay/seq on batches"
```

---

### Task 2: app.js — taka-number-aware allocation + selection totals

**Files:**
- Modify: `mvp/static/app.js:214-251` (`_lotAllocMap`, `lotAllocation`)
- Test: `mvp/tests/test_taka_alloc.js` (new, Node VM harness)

**Interfaces:**
- Consumes: `DB.lots` rows shaped `{id, takas:[len...], takaNos:[1..N], quality, customer}`, `DB.batches` rows shaped `{id, lots:[{lotId, takas:[len], takaNos:[n]}]}`.
- Produces:
  - `_lotAllocMap()` map entry gains `usedNos` (Set of taka numbers consumed by any batch) alongside existing `pool`/`pcs`/`mtr`/`by`.
  - `lotTakaAvailability(lotId)` → `[{no:int, meters:number, used:bool, byBatch:string|null}]`, one entry per physical taka of the lot, ordered by taka number.
  - `takaSelectionTotals(lot, nos)` → `{pcs:int, mtr:number, takas:[len...], takaNos:[n...]}` for a chosen set of taka numbers (weight is derived elsewhere from the row, so not returned here).

- [ ] **Step 1: Write the failing test**

Create `mvp/tests/test_taka_alloc.js`:

```js
const fs = require("fs"), vm = require("vm"), path = require("path");
const code = fs.readFileSync(path.join(__dirname, "..", "static", "app.js"), "utf8");
const ctx = { DB: {
  lots: [{ id:"LOT-1", quality:"CP", customer:"REL", takas:[96,96,85,85,50], takaNos:[1,2,3,4,5] }],
  batches: [{ id:"B-1", lots:[{ lotId:"LOT-1", takas:[96], takaNos:[1] }] }]
}, console };
vm.createContext(ctx); vm.runInContext(code, ctx);

const avail = ctx.lotTakaAvailability("LOT-1");
console.assert(avail.length === 5, "5 takas");
console.assert(avail[0].no === 1 && avail[0].used === true && avail[0].byBatch === "B-1", "taka 1 used by B-1");
console.assert(avail[2].no === 3 && avail[2].used === false, "taka 3 free");
console.assert(avail[2].meters === 85, "taka 3 is 85m");

const tot = ctx.takaSelectionTotals(ctx.DB.lots[0], [3,4]);
console.assert(tot.pcs === 2 && tot.mtr === 170, "selection 3+4 = 2pcs/170m");
console.assert(JSON.stringify(tot.takaNos) === "[3,4]", "takaNos preserved");
console.log("ok");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mvp && node tests/test_taka_alloc.js`
Expected: FAIL — `TypeError: ctx.lotTakaAvailability is not a function`.

- [ ] **Step 3: Extend `_lotAllocMap` to track used taka numbers**

In `mvp/static/app.js` `_lotAllocMap()` (line 214), when building each lot entry add `usedNos:new Set()`, and when consuming a batch row record its taka numbers. Replace the two relevant lines:

```js
  (DB.lots||[]).forEach(l=>{ map[l.id]={pcs:0, mtr:0, by:[], pool:(l.takas||[]).map(Number).filter(n=>!isNaN(n)), usedNos:new Set(), byNo:{}}; });
```

and inside the batches loop, after `if(Array.isArray(r.takas)) ...splice...`, add:

```js
      if(Array.isArray(r.takaNos)) r.takaNos.forEach(n=>{ m.usedNos.add(+n); m.byNo[+n]=b.id; });
```

- [ ] **Step 4: Add the two new functions**

Immediately after `lotAllocation` (ends ~line 251) in `mvp/static/app.js`, add:

```js
/* per-taka availability for the manual taka picker (add lots first, then pick takas) */
function lotTakaAvailability(lotId){
  const l=(DB.lots||[]).find(x=>x.id===lotId); if(!l) return [];
  const m=_lotAllocMap()[lotId]||{usedNos:new Set(),byNo:{}};
  const lens=l.takas||[], nos=l.takaNos||lens.map((_,i)=>i+1);
  return nos.map((no,i)=>({no:+no, meters:+lens[i]||0,
    used:m.usedNos.has(+no), byBatch:m.byNo[+no]||null}));
}
/* totals for a hand-picked set of taka numbers within one lot */
function takaSelectionTotals(lot, nos){
  const want=new Set((nos||[]).map(Number));
  const lens=lot.takas||[], tn=lot.takaNos||lens.map((_,i)=>i+1);
  const takas=[], takaNos=[];
  tn.forEach((no,i)=>{ if(want.has(+no)){ takas.push(+lens[i]||0); takaNos.push(+no); } });
  return {pcs:takaNos.length, mtr:Math.round(takas.reduce((a,b)=>a+b,0)), takas, takaNos};
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd mvp && node tests/test_taka_alloc.js`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add mvp/static/app.js mvp/tests/test_taka_alloc.js
git commit -m "feat(app): taka-number allocation tracking + selection totals for manual taka picking"
```

---

### Task 3: app.js — day/machine sequence helpers

**Files:**
- Modify: `mvp/static/app.js` (append near `batchesForSchedule`, ~line 315)
- Test: `mvp/tests/test_seq.js` (new, Node VM harness)

**Interfaces:**
- Produces:
  - `planBatches(machine, day)` → batches for that machine+day sorted ascending by `seq`.
  - `nextSeq(machine, day)` → `max(seq)+1` (or 1 if none).
  - `resequenced(batches)` → same array with `seq` rewritten 1..N in current array order (pure; returns the list, does not save).
  - `reorderPlan(list, fromIdx, toIdx)` → new array with the item moved and `seq` renumbered 1..N.

- [ ] **Step 1: Write the failing test**

Create `mvp/tests/test_seq.js`:

```js
const fs=require("fs"),vm=require("vm"),path=require("path");
const code=fs.readFileSync(path.join(__dirname,"..","static","app.js"),"utf8");
const ctx={DB:{batches:[
  {id:"B-1",machine:"JET-2",planDay:"2026-07-24",seq:2},
  {id:"B-2",machine:"JET-2",planDay:"2026-07-24",seq:1},
  {id:"B-3",machine:"JET-3",planDay:"2026-07-24",seq:1},
  {id:"B-4",machine:"JET-2",planDay:"2026-07-25",seq:1},
],lots:[]},console};
vm.createContext(ctx);vm.runInContext(code,ctx);

const p=ctx.planBatches("JET-2","2026-07-24");
console.assert(p.map(b=>b.id).join(",")==="B-2,B-1","sorted by seq");
console.assert(ctx.nextSeq("JET-2","2026-07-24")===3,"next seq 3");
console.assert(ctx.nextSeq("JET-9","2026-07-24")===1,"empty machine next seq 1");
const r=ctx.reorderPlan(p,1,0);           // move B-1 to front
console.assert(r.map(b=>b.id+":"+b.seq).join(",")==="B-1:1,B-2:2","reordered+renumbered");
console.log("ok");
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mvp && node tests/test_seq.js`
Expected: FAIL — `ctx.planBatches is not a function`.

- [ ] **Step 3: Add the helpers**

After `batchesForSchedule()` (~line 339) in `mvp/static/app.js`, add:

```js
/* ---- manual plan ordering: batches are placed by (machine, planDay, seq) ---- */
function planBatches(machine, day){
  return (DB.batches||[])
    .filter(b=>b.machine===machine && b.planDay===day)
    .slice().sort((a,b)=>(+a.seq||0)-(+b.seq||0));
}
function nextSeq(machine, day){
  const s=planBatches(machine,day).map(b=>+b.seq||0);
  return s.length ? Math.max.apply(null,s)+1 : 1;
}
function resequenced(list){ return list.map((b,i)=>Object.assign(b,{seq:i+1})); }
function reorderPlan(list, fromIdx, toIdx){
  const a=list.slice(); const [it]=a.splice(fromIdx,1); a.splice(toIdx,0,it);
  return resequenced(a);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mvp && node tests/test_seq.js`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add mvp/static/app.js mvp/tests/test_seq.js
git commit -m "feat(app): per-machine/day sequence helpers (planBatches, nextSeq, reorderPlan)"
```

---

### Task 4: Taka picker UI (per lot row)

**Files:**
- Modify: `mvp/static/index.html` (batch-maker lot-row region ~line 196-256; add picker fns near `bRows` ~line 279)
- Modify: `mvp/static/style.css` (append `.takapick` styles)

**Interfaces:**
- Consumes: `lotTakaAvailability(lotId)`, `takaSelectionTotals(lot, nos)` (Task 2), existing `bSyncTotals()`.
- Produces: `openTakaPicker(lotId, rowEl)` opens an inline panel under the lot row; on apply it writes `takas`/`takaNos`/`pcs`/`mtr` onto the row's inputs and dataset, then calls `bSyncTotals()`. Row helper `bRows()` must read `takaNos` from `row.dataset.takaNos`.

- [ ] **Step 1: Add picker styles**

Append to `mvp/static/style.css` (uses existing tokens — no new colours):

```css
.takapick{margin:6px 0 2px;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--surface-2)}
.takapick .tp-grid{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.tp-chip{font-family:var(--mono);font-size:11px;padding:4px 9px;border:1px solid var(--line-2);border-radius:8px;background:var(--surface);cursor:pointer;user-select:none}
.tp-chip.on{border-color:var(--accent);background:var(--accent-soft);color:var(--primary)}
.tp-chip.used{opacity:.45;cursor:not-allowed;text-decoration:line-through}
.tp-sum{font-family:var(--mono);font-size:11px;color:var(--ink-2);margin-top:4px}
```

- [ ] **Step 2: Add the "adjust takas" button to each lot row**

In `mvp/static/index.html` `bLotRow()` (~line 196), add a button after the meters/weight inputs (before the remove `.rm` button). The row already carries the lot picker; append:

```js
    <button type="button" class="btn ghost sm b-takabtn" title="pick specific takas" onclick="openTakaPicker(this.closest('.lotqrow'))"><span class="material-symbols-rounded">tune</span>Takas</button>
```

- [ ] **Step 3: Implement the picker**

Add near `bRows()` (~line 279) in `mvp/static/index.html`:

```js
function openTakaPicker(row){
  const lotId=lotPickVal(row.querySelector(".b-lot"));
  if(!lotId){ toast("Pick a lot first"); return; }
  const lot=(DB.lots||[]).find(x=>x.id===lotId); if(!lot){ toast("Lot not found"); return; }
  let panel=row.querySelector(".takapick");
  if(panel){ panel.remove(); return; }               // toggle closed
  const picked=new Set((row.dataset.takaNos?JSON.parse(row.dataset.takaNos):[]).map(Number));
  const avail=lotTakaAvailability(lotId);
  panel=document.createElement("div"); panel.className="takapick";
  const draw=()=>{
    const chips=avail.map(t=>{
      const mine=picked.has(t.no);
      const used=t.used && t.byBatch!==null && !mine;   // used by another batch
      const cls="tp-chip"+(mine?" on":"")+(used?" used":"");
      return `<span class="${cls}" data-no="${t.no}" ${used?"":`onclick="tpToggle(this)"`}>T${t.no} · ${t.meters}m</span>`;
    }).join("");
    const tot=takaSelectionTotals(lot,[...picked]);
    panel.innerHTML=`<div class="small muted">Tick the takas for this batch — greyed = used by another batch.</div>
      <div class="tp-grid">${chips}</div>
      <div class="tp-sum">Selected: ${tot.pcs} pcs · ${tot.mtr} m</div>
      <div style="margin-top:6px"><button type="button" class="btn sm" onclick="tpApply(this)">Apply</button>
      <button type="button" class="btn ghost sm" onclick="this.closest('.takapick').remove()">Cancel</button></div>`;
  };
  panel.tpState={picked, lot, row, draw};
  row.appendChild(panel); draw();
}
function tpToggle(chip){
  const panel=chip.closest(".takapick"), no=+chip.dataset.no, st=panel.tpState;
  st.picked.has(no)?st.picked.delete(no):st.picked.add(no); st.draw();
}
function tpApply(btn){
  const panel=btn.closest(".takapick"), st=panel.tpState;
  const tot=takaSelectionTotals(st.lot,[...st.picked]);
  const row=st.row;
  row.dataset.takas=JSON.stringify(tot.takas);
  row.dataset.takaNos=JSON.stringify(tot.takaNos);
  row.querySelector(".b-pcs").value=tot.pcs;
  row.querySelector(".b-mtr").value=tot.mtr;
  panel.remove(); bSyncTotals();
}
```

- [ ] **Step 4: Make `bRows()` carry taka numbers**

In `mvp/static/index.html` `bRows()` (~line 279), where each row object is built, include the picked taka numbers so `submitBatch` persists them:

```js
    takaNos: row.dataset.takaNos ? JSON.parse(row.dataset.takaNos) : [],
```

(Add this key alongside the existing `takas`. If `takaNos` is empty, `submitBatch`'s existing auto-`pickTakas` path still runs, so nothing regresses.)

- [ ] **Step 5: Manual verification**

Run: `cd mvp && python3 server.py 8091` then open `http://localhost:8091/`, log in (ADMIN), Operations → Batch maker, add a lot with known takas, click **Takas**, tick two, Apply. Confirm Pcs/Meters update to the selection and the batch total reflects it.
Expected: selection drives pcs/mtr; re-opening shows the ticked takas remembered from `row.dataset`.

- [ ] **Step 6: Commit**

```bash
git add mvp/static/index.html mvp/static/style.css
git commit -m "feat(batch): per-lot taka picker — hand-select specific takas by number"
```

---

### Task 5: Mass Batch Planning tab — read-only machine-grouped view

**Files:**
- Modify: `mvp/static/index.html` (section tabs ~line 32; new `<section id="v-massplan">` after storage ~line 108; renderer near `renderBatchList` ~line 413)

**Interfaces:**
- Consumes: `planBatches(machine, day)` (Task 3), `Q(name)`, `shadeColor`, `batchStatusPill`, `colLetter` not needed. Machine list = `DB.machines`.
- Produces: `renderMassPlan()` draws per-machine sections for the selected `MP_DAY` (module var, default today via `new Date().toISOString().slice(0,10)`); `mpSetDay(v)` changes the day and re-renders. A section tab button with `data-s="massplan"` gated by `can("op_massplan")`.

- [ ] **Step 1: Add the tab button (permission-gated)**

In `mvp/static/index.html` section-tabs bar (~line 32), add after the Batch maker button:

```html
    <button data-s="massplan" data-perm="op_massplan"><span class="material-symbols-rounded">table_view</span>Mass planning</button>
```

(The existing boot/`can()` wiring hides `[data-perm]` buttons the role lacks — confirm the tab bar honors `data-perm`; if not, hide in `renderMassPlan` guard. See Step 4.)

- [ ] **Step 2: Add the section container**

After the Storage `<section>` (~line 108) in `mvp/static/index.html`:

```html
  <!-- Mass planning -->
  <section class="view" id="v-massplan" style="display:none">
    <div class="bar">
      <label class="fld" style="max-width:200px">Plan day<input type="date" id="mp_day" onchange="mpSetDay(this.value)"></label>
      <span class="small muted" id="mp_note"></span>
    </div>
    <div id="mp_body"></div>
  </section>
```

- [ ] **Step 3: Wire the tab into the section switch**

In the `#secTabs` click handler (~line 142) add, alongside the `if(s==="storage")` branch:

```js
  if(s==="massplan") renderMassPlan();
```

- [ ] **Step 4: Implement the renderer**

Near `renderBatchList()` (~line 413) in `mvp/static/index.html`:

```js
let MP_DAY = new Date().toISOString().slice(0,10);
function mpSetDay(v){ MP_DAY=v||MP_DAY; renderMassPlan(); }
function renderMassPlan(){
  if(!can("op_massplan")) return;
  const dEl=document.getElementById("mp_day"); if(dEl && !dEl.value) dEl.value=MP_DAY;
  const body=document.getElementById("mp_body");
  const machines=(DB.machines||[]).slice();
  if(!machines.length){ body.innerHTML='<div class="empty"><span class="material-symbols-rounded">precision_manufacturing</span><h3>No machines yet</h3><p>Add machines in Admin and they will appear here to plan.</p></div>'; return; }
  let totB=0, totKg=0;
  body.innerHTML=machines.map(m=>{
    const rows=planBatches(m.id, MP_DAY);
    totB+=rows.length; totKg+=rows.reduce((a,b)=>a+(+b.weight||0),0);
    const head=`<div class="mp-head"><span><span class="material-symbols-rounded">${MC_ICON(m.type)}</span> <b class="tnum">${esc(m.id)}</b> <span class="mc-type">${esc(m.type||"")} · ${esc(m.capMax||"?")} kg</span></span>
      <span class="small muted">${rows.length} batch(es) · ${Math.round(rows.reduce((a,b)=>a+(+b.weight||0),0))} kg · ${rows.reduce((a,b)=>a+(+b.mtr||0),0)} m</span></div>`;
    const bodyRows = rows.length ? rows.map(b=>{
      const q=Q(b.quality);
      const takas=(b.lots||[]).map(l=>`${esc(l.lotId)}·${(l.takaNos||l.takas||[]).length}tk`).join(", ");
      return `<tr><td class="tnum">${b.seq}</td><td class="tnum">${esc(b.id)}</td><td>${esc(b.quality||"")}</td>
        <td><span class="swatch" style="background:${shadeColor(b.shadeNo,b.quality)}"></span> ${esc(b.shadeNo||"")}</td>
        <td class="small muted">${takas||"—"}</td><td class="tnum">${b.pcs||0}</td><td class="tnum">${b.mtr||0}</td><td class="tnum">${b.weight||0}</td>
        <td>${batchStatusPill(b)}</td></tr>`;
    }).join("") : `<tr><td colspan="9" class="muted" style="padding:10px">No batches for ${esc(m.id)} on this day.</td></tr>`;
    return `<div class="card mp-machine"><div class="card-b">${head}
      <div class="tbl-wrap"><table class="mp-table"><thead><tr><th>Seq</th><th>Batch</th><th>Quality</th><th>Shade</th><th>Lots · takas</th><th>Pcs</th><th>Mtr</th><th>Kg</th><th>Status</th></tr></thead>
      <tbody>${bodyRows}</tbody></table></div></div></div>`;
  }).join("");
  document.getElementById("mp_note").textContent=`${machines.length} machines · ${totB} batches · ${Math.round(totKg)} kg planned for ${MP_DAY}`;
}
function MC_ICON(t){ return {jet:"water_drop",jigger:"waves",drum:"cyclone",stentor:"compress",hydro:"mode_fan",rope:"timeline"}[t]||"precision_manufacturing"; }
```

- [ ] **Step 5: Add minimal section styles**

Append to `mvp/static/style.css`:

```css
.mp-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.mp-machine{margin-bottom:12px}
.mp-table th{position:sticky;top:0}
```

- [ ] **Step 6: Manual verification**

Run server (`python3 server.py 8091`), create 2 machines + a couple of batches via the existing form (they default to today's `planDay` after Task 6; for now set `machine`/`planDay`/`seq` via Admin batch edit or accept the Task 1 migrate defaults). Open Operations → **Mass planning**.
Expected: each machine shows as a section; batches for today appear in seq order with quality/pcs/mtr/kg/status; the Day picker switches days; empty machines show the one-line empty row.

- [ ] **Step 7: Commit**

```bash
git add mvp/static/index.html mvp/static/style.css
git commit -m "feat(massplan): read-only machine-grouped Mass Batch Planning tab with Day selector"
```

---

### Task 6: Mass Batch Planning — inline add, machine assignment, reorder

**Files:**
- Modify: `mvp/static/index.html` (`renderMassPlan` add-row + handlers; reuse `submitBatch` logic factored into a helper)
- Test: `mvp/tests/test_seq.js` (extend with a capacity-guard assertion)

**Interfaces:**
- Consumes: `nextSeq`, `reorderPlan`, `planBatches` (Task 3), `takaSelectionTotals`, existing `bRows`/validation from Task 4, `API.save`, `API.db`.
- Produces:
  - `mpAddBatch(machineId)` — opens the batch-build form pre-pinned to `machineId` and `MP_DAY`; on save sets `machine`, `planDay`, `seq=nextSeq(...)`.
  - `mpMove(batchId, dir)` — moves a batch up/down within its machine+day, persists renumbered `seq` for affected rows via `API.save`.
  - Over-capacity guard: `mpCapacityOk(machineId, kg)` → false if `kg > machine.capMax`; save is blocked with an inline message (no auto-split in manual mode).

- [ ] **Step 1: Write the failing capacity test**

Append to `mvp/tests/test_seq.js` (before the final `console.log`):

```js
ctx.DB.machines=[{id:"JET-2",type:"jet",capMax:400}];
console.assert(ctx.mpCapacityOk("JET-2",380)===true,"380<=400 ok");
console.assert(ctx.mpCapacityOk("JET-2",420)===false,"420>400 blocked");
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd mvp && node tests/test_seq.js`
Expected: FAIL — `ctx.mpCapacityOk is not a function`.

- [ ] **Step 3: Add the capacity guard (app.js)**

After `reorderPlan` (Task 3) in `mvp/static/app.js`:

```js
function mpCapacityOk(machineId, kg){
  const m=(DB.machines||[]).find(x=>x.id===machineId);
  if(!m || !m.capMax) return true;
  return (+kg||0) <= (+m.capMax);
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd mvp && node tests/test_seq.js`
Expected: `ok`

- [ ] **Step 5: Add the add-batch row + move controls (index.html)**

In `renderMassPlan()` (Task 5), append an add-affordance row inside each machine's `<tbody>` after `bodyRows`:

```js
      + `<tr class="mp-add"><td>+${nextSeq(m.id,MP_DAY)}</td><td colspan="8"><button class="btn ghost sm" onclick="mpAddBatch('${esc(m.id)}')"><span class="material-symbols-rounded">add</span>Add batch to ${esc(m.id)}</button></td></tr>`
```

and add Seq up/down buttons in each batch row's Status cell:

```js
        <button class="btn ghost sm" title="up" onclick="mpMove('${esc(b.id)}',-1)"><span class="material-symbols-rounded">arrow_upward</span></button>
        <button class="btn ghost sm" title="down" onclick="mpMove('${esc(b.id)}',1)"><span class="material-symbols-rounded">arrow_downward</span></button>
```

- [ ] **Step 6: Implement `mpAddBatch` and `mpMove`**

Add near `renderMassPlan` in `mvp/static/index.html`. `mpAddBatch` reuses the existing Batch-maker form by switching to it pre-pinned:

```js
function mpAddBatch(machineId){
  show("batch");                                  // reuse the existing build form
  document.getElementById("b_mc").value=machineId;
  document.getElementById("b_mc").dataset.mpDay=MP_DAY;      // submitBatch reads these
  document.getElementById("b_mc").dataset.mpMachine=machineId;
  toast("Building a batch for "+machineId+" · "+MP_DAY);
}
async function mpMove(batchId, dir){
  const b=(DB.batches||[]).find(x=>x.id===batchId); if(!b) return;
  const list=planBatches(b.machine,b.planDay);
  const i=list.findIndex(x=>x.id===batchId), j=i+dir;
  if(j<0||j>=list.length) return;
  const reordered=reorderPlan(list,i,j);
  for(const r of reordered){ await API.save("batches", r); }   // persists renumbered seq
  await API.db(); renderMassPlan(); draw();
  toast("Sequence updated");
}
```

- [ ] **Step 7: Persist machine/planDay/seq + capacity guard in `submitBatch`**

In `submitBatch()` (`index.html` ~line 358-365), where the per-group `row` object is built, add the manual-plan fields and guard. Replace the `mcPin:g("b_mc"),` line and add before `API.save`:

```js
    const mpMachine=document.getElementById("b_mc").dataset.mpMachine||g("b_mc");
    const mpDay=document.getElementById("b_mc").dataset.mpDay||new Date().toISOString().slice(0,10);
    if(mpMachine && !mpCapacityOk(mpMachine, tot.weight)){
      toast(mpMachine+" holds "+(Q(q)?"":"")+((DB.machines.find(x=>x.id===mpMachine)||{}).capMax)+" kg — this "+tot.weight+" kg batch is too heavy. Remove takas or pick a bigger machine."); return; }
```

and in the `row` object add:

```js
      mcPin:g("b_mc"), machine:mpMachine, planDay:mpDay, seq:nextSeq(mpMachine, mpDay),
```

After a successful save, clear the pin daydata: `delete document.getElementById("b_mc").dataset.mpMachine; delete document.getElementById("b_mc").dataset.mpDay;` (add next to the existing `b_mc` reset ~line 380).

Note: in manual mode `submitBatch` still calls `splitBatchRows`; with the capacity guard above blocking over-cap saves, the split path only triggers if a single group already fits — leave `splitBatchRows` in place for the legacy form but the guard prevents oversize manual assignment.

- [ ] **Step 8: Manual verification**

Run server; Operations → Mass planning → **Add batch to JET-2**; build a batch with hand-picked takas; save; confirm it lands under JET-2 for the current day with the next seq. Use up/down to reorder; confirm seq renumbers and persists across reload. Try to add a batch heavier than the machine capMax; confirm it's blocked with the inline message.
Expected: add + reorder + capacity block all behave; `activityLog` (Admin → Activity log) shows the update entries.

- [ ] **Step 9: Commit**

```bash
git add mvp/static/index.html mvp/static/app.js mvp/tests/test_seq.js
git commit -m "feat(massplan): inline add-to-machine, up/down resequencing, over-capacity guard"
```

---

### Task 7: Render Gantt + floor board in manual (machine, seq) order

**Files:**
- Modify: `mvp/static/app.js:315-419` (`batchesForSchedule` / `computeSchedule`)
- Test: `mvp/tests/test_manualplan.js` (new, Node VM harness)

**Interfaces:**
- Consumes: `planBatches`, `routeOf(q, meters)`, `Q`, `DB.machines`.
- Produces: `computeSchedule()` gains a manual path — when any batch has a `machine`+`seq`, batches are laid head-to-tail per machine in seq order using `routeOf` durations, producing the same `S` shape (`S.tl[machineId]={blocks:[...],cursor}`, `S.batchCount`, `S.washCount`) that `renderGantt`/`renderFloor` already consume. Auto-assignment remains as the fallback when no batch is manually placed (keeps existing demo/tests green).

- [ ] **Step 1: Inspect the `S` shape**

Read `mvp/static/app.js:356-509` to confirm the exact fields `renderGantt`/`renderFloor` read off `S` (`S.tl[m.id].cursor`, `.blocks`, block `{key,shade,qual,start,end,kind,load,unload}`, `S.batchCount`, `S.washCount`, `S.orderFinish`). Record the shape as a comment atop the new function.

- [ ] **Step 2: Write the failing test**

Create `mvp/tests/test_manualplan.js`:

```js
const fs=require("fs"),vm=require("vm"),path=require("path");
const code=fs.readFileSync(path.join(__dirname,"..","static","app.js"),"utf8");
const ctx={DB:{
  machines:[{id:"JET-2",type:"jet",capMax:400}],
  qualities:[{name:"CP",gsm:100,width:56,step3_mc:"jet",step3_time:120,dyeStep:3,step1_mc:"",step2_mc:"",step4_mc:""}],
  shadeRecipes:[], orders:[], lots:[],
  batches:[
    {id:"B-1",machine:"JET-2",planDay:"2026-07-24",seq:2,quality:"CP",shadeNo:"0",pcs:5,mtr:400,weight:200},
    {id:"B-2",machine:"JET-2",planDay:"2026-07-24",seq:1,quality:"CP",shadeNo:"0",pcs:5,mtr:400,weight:200},
  ]},console,Date};
vm.createContext(ctx);vm.runInContext(code,ctx);
const S=ctx.computeSchedule();
const blocks=S.tl["JET-2"].blocks.filter(b=>b.key);
console.assert(blocks[0].key.indexOf("B-2")>=0,"seq1 (B-2) runs before seq2 (B-1)");
console.assert(blocks[0].end<=blocks[1].start,"no overlap on the machine");
console.log("ok");
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd mvp && node tests/test_manualplan.js`
Expected: FAIL — order not guaranteed / auto-scheduler ignores `seq` (assertion on B-2 first fails).

- [ ] **Step 4: Add the manual path to `computeSchedule`**

At the top of `computeSchedule()` (line 356), branch to a manual layout when manual placement exists:

```js
  const manual=(DB.batches||[]).some(b=>b.machine && b.seq);
  if(manual) return manualSchedule();
```

Then add `manualSchedule()` immediately after `computeSchedule` — lay each machine's `planBatches` head-to-tail:

```js
function manualSchedule(){
  const S={tl:{}, batchCount:0, washCount:0, orderFinish:{}};
  (DB.machines||[]).forEach(m=>{ S.tl[m.id]={blocks:[], cursor:0}; });
  const day=(DB.batches||[]).reduce((d,b)=>b.planDay&&(!d||b.planDay<d)?b.planDay:d,null);
  (DB.machines||[]).forEach(m=>{
    const tl=S.tl[m.id];
    planBatches(m.id, day).forEach(b=>{
      const q=Q(b.quality)||{}; const dur=routeOf(q,+b.mtr||0).dye || (+q.step3_time||120);
      const load=(+q.loadMin||cfg().loadMin||35), unload=(+q.unloadMin||cfg().unloadMin||25);
      const start=tl.cursor, end=start+load+dur+unload;
      tl.blocks.push({key:b.id+" · "+(b.shadeNo||""), shade:b.shadeNo, qual:b.quality,
        start, end, kind:"dye", load, unload, status:b.status||"planned"});
      tl.cursor=end; S.batchCount++;
    });
  });
  return S;
}
```

Note: `routeOf(q, meters)` returns per-step times; use its dye component (confirm its return shape in Step 1 and adjust the `.dye` access to match — if it returns a total, use that). This is deliberately simple (no wash campaigns) because ordering is now the operator's.

- [ ] **Step 5: Run to verify it passes**

Run: `cd mvp && node tests/test_manualplan.js`
Expected: `ok`

- [ ] **Step 6: Regression — existing schedule test still green**

Run the existing scheduler harness if present (`node tests/*.js`); confirm the no-manual-placement path still uses the greedy scheduler (the `manual` flag is false when no batch has machine+seq).
Expected: existing tests pass unchanged.

- [ ] **Step 7: Manual verification**

Run server, build a manual plan with 2 batches on one jet in a chosen order, open Operations → Schedule (Gantt) and Floor.
Expected: blocks render in your seq order, head-to-tail, no overlap; now-line + wall-clock axis unchanged.

- [ ] **Step 8: Commit**

```bash
git add mvp/static/app.js mvp/tests/test_manualplan.js
git commit -m "feat(schedule): render Gantt/floor in manual (machine, seq) order when batches are hand-placed"
```

---

### Task 8: Export takas + Sr. Nos., permission wiring, whole-branch review

**Files:**
- Modify: `mvp/static/index.html` (`exportBatchesToExcel` ~line 421; ensure Mass-plan export)
- Modify: `mvp/README.md` and `PROJECT_HANDOFF.md` (document the feature)

**Interfaces:**
- Consumes: everything above.
- Produces: Excel export includes `Machine`, `Plan day`, `Seq`, and per-lot `Taka Nos`. Handoff/readme updated. `op_massplan` documented as a page permission.

- [ ] **Step 1: Extend the batch export**

In `mvp/static/index.html` `exportBatchesToExcel()` (~line 421), add columns:

```js
  const header=["Batch","Machine","Plan day","Seq","Lot no.","Taka Nos","Quality","Shade","Pcs","Mtr","Kg","In","Out","pH","Operator","Shift"];
  const body=(DB.batches||[]).slice().reverse().map(b=>[
    b.id, b.machine||"", b.planDay||"", b.seq||"",
    (b.lotIds||(b.lots||[]).map(l=>l.lotId)||[]).join(", "),
    (b.lots||[]).map(l=>(l.lotId+":"+(l.takaNos||[]).join("/"))).join("  "),
    b.quality, b.shadeNo||"", b.pcs, b.mtr, b.weight,
    b.inTime||"", b.outTime||"", b.ph||"", b.operator||"", b.shift||""]);
```

- [ ] **Step 2: Manual verification of export**

Run server, export from Operations → Batch maker; open the `.xlsx`.
Expected: Machine, Plan day, Seq, and Taka Nos columns are populated for manually planned batches.

- [ ] **Step 3: Update docs**

Append a dated section to `PROJECT_HANDOFF.md` summarizing: manual planning model, `machine`/`planDay`/`seq` fields, Mass Batch Planning tab (`op_massplan`), taka picker, capacity guard, and that the auto-scheduler is parked. Note the new test files under `mvp/tests/`.

- [ ] **Step 4: Commit**

```bash
git add mvp/static/index.html mvp/README.md PROJECT_HANDOFF.md
git commit -m "feat(export): include machine/plan-day/seq/taka-nos; docs: Mass Batch Planning handoff"
```

- [ ] **Step 5: Whole-branch review**

REQUIRED SUB-SKILL: Use superpowers:requesting-code-review across all commits from Task 1. Verify against the spec `docs/superpowers/specs/2026-07-24-mass-batch-planning-design.md`: manual planning honored, taka Sr. Nos. carried end-to-end, capacity blocks (no manual auto-split), permission enforced, existing Gantt/board/audit/export intact. Fix findings, re-run all `mvp/tests/*.js` and `mvp/tests/test_migrate_massplan.py`.

---

## Self-Review

**Spec coverage:** §4 planning model → Tasks 1,7. §5.1 Mass Planning screen (per-machine sections, Day selector, drag/number reorder, inline add, empty state, full-info columns) → Tasks 5,6. §5.2 taka picker (add lots then pick, greyed used, Sr. Nos., pcs/mtr recompute) → Tasks 2,4. §6 validation (capacity block, no manual split, taka double-book) → Tasks 2,6. §7 server (fields, page key, audit via upsert) → Task 1. §8 Gantt/board by machine+seq → Task 7. §9 testing → per-task harness + curl + manual. Export (§5.1 toolbar) → Task 8. Covered.

**Placeholder scan:** No TBD/TODO; every code step shows real code. One explicit uncertainty flagged for the implementer: `routeOf`'s return shape (Task 7 Step 1/4) must be confirmed and the `.dye` access adjusted — this is a read-first instruction, not a placeholder.

**Type consistency:** `machine`/`planDay`/`seq`/`takaNos` used identically across Tasks 1–8. `planBatches`, `nextSeq`, `reorderPlan`, `resequenced`, `mpCapacityOk`, `lotTakaAvailability`, `takaSelectionTotals`, `manualSchedule` names are consistent between definition and callers.

## Execution Handoff

Ready to execute. Recommended: subagent-driven (fresh subagent per task with review between). Alternatively inline execution with checkpoints.
