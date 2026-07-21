# Scale-Up & Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the REL Dyeing ERP for mass data entry (hundreds of qualities, ~20 shades/quality, thousands of lots) by fixing a real O(n²) hot path, adding bulk-add and Excel export to every master table, letting machines carry a soft shade-family preference, moving load/unload time to per-quality, and building a real lot-linked storage location model with a visual Storage tab.

**Architecture:** Same zero-build-step stack throughout — `server.py` (Python stdlib HTTP server, JSON file store, no framework), `static/app.js` (shared engine: lookups, scheduler, shared widgets), `static/admin.html` (schema-driven CRUD via the `SCHEMAS` object + generic `fieldInput()`/`openModal()`/`saveModal()`), `static/index.html` (Operations: shop floor, schedule, order entry, Batch Maker). No new dependencies — SheetJS is already vendored at `static/vendor/xlsx.full.min.js`.

**Tech Stack:** Python 3 stdlib (server), vanilla JS/HTML/CSS (frontend, no build step), SheetJS (xlsx read/write, vendored), Node (for the plan's own verification scripts only — never shipped).

## Global Constraints

- No new runtime dependencies. No build step. No framework. This is a deliberate architectural choice (LAN-only factory floor app) — do not introduce React/Vue/a bundler/npm packages into `static/`, even for the new Storage tab.
- Follow the existing `SCHEMAS`-driven pattern in `admin.html` for any new master table — don't hand-roll a one-off CRUD page.
- Match the design system in the `rel-dyeing-design-insight` skill (navy palette, Inter + IBM Plex Mono, Material Symbols Rounded icons only, `--r`/`--r-c`/`--r-s` radii) for all new UI. Do not pull in 21st.dev components directly — it's a React/Tailwind registry and this codebase is vanilla; use it only as visual inspiration, hand-translated.
- Every new admin-editable field goes through `fieldInput()`/`saveModal()` — don't bypass the generic form renderer.
- **Sandbox note for whoever executes this:** the mounted dev folder is a FUSE mount where Bash `rm`/`unlink` fails with "Operation not permitted" even though `mv` and `git add`/`commit` work. If a git write command fails on a stale lock, run `mv .git/index.lock .git/index.lock.old-$RANDOM` (and the same for `.git/HEAD.lock`) before retrying — never try to `rm` the lock file.
- Verification in this codebase has no test framework — follow the established pattern from `docs/superpowers/plans/2026-07-20-weaver-import-mcno.md`: extract the relevant `<script>` block or `app.js` with Node and `eval` it with a hand-built fake `DB`, asserting on function output. Because `app.js` declares `let DB = null;` at module scope, don't pre-set `global.DB` and then `eval(fs.readFileSync(...))` separately — that creates a shadowing bug. Instead append the `DB = {...}` assignment and assertions to the *same* string you `eval`, e.g. `eval(fs.readFileSync('app.js','utf8') + "\nDB = {...}; console.log(...)")`.

---

## Task 1: Fix the O(n²) lot-allocation hot path + debounce admin search

**Files:**
- Modify: `mvp/static/app.js:215-231` (`lotAllocation`, `lotsAvailable`) and `mvp/static/app.js:118-126` (`lotRemainingTakas`)
- Modify: `mvp/static/admin.html` (search input handler in `render()`)

**Interfaces:**
- Consumes: nothing new
- Produces: `lotAllocation(lotId)` and `lotRemainingTakas(lotId)` keep their exact existing return shapes and call signatures — every existing caller (`lotsAvailable`, `wireLotPicker`'s `paint()`, `admin.html`'s `cellVal` "allocation"/rowClass, `bPrefillRow`/`bSnapRow` in `index.html`) needs zero changes.

`lotAllocation(lotId)` today re-scans all of `DB.batches` on every call (`app.js:217-220`), and `lotRemainingTakas(lotId)` (called *inside* `lotAllocation`, `app.js:222`) does a second full scan of `DB.batches`. `lotsAvailable(quality)` (`app.js:229-231`) calls `lotAllocation` once per lot, so rendering or searching the Lot master table is O(lots × batches) — and the new full-column search (`cellText()`) now computes the "Allocation" column for every row on every keystroke, making this the single most expensive thing in the app at scale (hundreds of qualities × thousands of lots × hundreds of batches).

Fix: precompute one map from `DB.lots`+`DB.batches` in O(lots+batches), cache it keyed on the `DB` object reference (the whole `DB` object is replaced wholesale by `API.db()`, so reference equality is a correct invalidation signal — no manual cache-busting needed).

- [ ] **Step 1: Write the failing Node verification script**

Create `/tmp/task1_test.js` (throwaway, not committed):

```js
const fs = require('fs');
const src = fs.readFileSync('mvp/static/app.js', 'utf8');
const harness = src + `
DB = {
  lots: [
    {id:'LOT-1', takas:[80,80,80]},
    {id:'LOT-2', takas:[100,100]},
    {id:'LOT-3', takas:[50]}
  ],
  batches: [
    {id:'B-1', lots:[{lotId:'LOT-1', pcs:2, mtr:160, takas:[80,80]}]},
    {id:'B-2', lots:[{lotId:'LOT-3', pcs:1, mtr:50, takas:[50]}]}
  ],
  settings: {}
};
const a1 = lotAllocation('LOT-1');
console.log('LOT-1', JSON.stringify(a1));
if (a1.remaining !== 80 || a1.remainingPcs !== 1 || !a1.used || a1.blocked) throw new Error('LOT-1 allocation wrong');
const a2 = lotAllocation('LOT-2');
console.log('LOT-2', JSON.stringify(a2));
if (a2.remaining !== 200 || a2.used) throw new Error('LOT-2 allocation wrong');
const a3 = lotAllocation('LOT-3');
console.log('LOT-3', JSON.stringify(a3));
if (!a3.blocked) throw new Error('LOT-3 should be fully blocked');
const avail = lotsAvailable();
if (avail.length !== 2 || avail.some(l=>l.id==='LOT-3')) throw new Error('lotsAvailable should exclude blocked LOT-3');
console.log('ALL OK');
`;
eval(harness);
```

- [ ] **Step 2: Run it against the current implementation to confirm it already passes (baseline)**

Run: `node /tmp/task1_test.js`
Expected: `ALL OK` printed — this baseline must pass *before* the refactor so the refactor is provably behavior-preserving, not fixing a bug.

- [ ] **Step 3: Replace `lotRemainingTakas`, `lotAllocation`, add the memoized map**

Two separate edits to `mvp/static/app.js` — do not paste the same code in both places, they combine into one new block that only lives at the second location:

1. Delete the entire current `function lotRemainingTakas(lotId){` ... `}` block (line 118-126) — remove it completely, nothing replaces it at this location.
2. Replace the current `function lotAllocation(lotId){` ... `}` block (line 215-228) with the full combined block below (this single block defines `_lotAllocCache`, `_lotAllocMap`, the new `lotRemainingTakas`, and the new `lotAllocation` together — it is the only place any of these four names are defined after this step):

```js
/* ---------- lot allocation: memoized per DB snapshot (was O(batches) per call — see Task 1 in
   docs/superpowers/plans/2026-07-21-scale-and-storage.md for why this matters at scale) ---------- */
let _lotAllocCache = null;   // {forDB, map}
function _lotAllocMap(){
  if(_lotAllocCache && _lotAllocCache.forDB===DB) return _lotAllocCache.map;
  const map={};
  (DB.lots||[]).forEach(l=>{ map[l.id]={pcs:0, mtr:0, by:[], pool:(l.takas||[]).map(Number).filter(n=>!isNaN(n))}; });
  (DB.batches||[]).forEach(b=>{
    const rows = b.lots || (b.lotIds||[]).map(id=>({lotId:id}));
    rows.forEach(r=>{
      const m=map[r.lotId]; if(!m) return;
      m.by.push(b.id); m.pcs+=+r.pcs||0; m.mtr+=+r.mtr||0;
      if(Array.isArray(r.takas)) r.takas.forEach(t=>{ const i=m.pool.indexOf(+t); if(i>=0) m.pool.splice(i,1); });
    });
  });
  _lotAllocCache={forDB:DB, map};
  return map;
}
function lotRemainingTakas(lotId){
  const m=_lotAllocMap()[lotId];
  return m ? m.pool.slice() : [];
}
function lotAllocation(lotId){
  const m=_lotAllocMap()[lotId];
  if(!m) return {used:false, blocked:false, batches:[], pcs:0, mtr:0, total:0, totalPcs:0, remaining:0, remainingPcs:0};
  const t=lotTotals([lotId]);
  const remaining=Math.round(m.pool.reduce((a,b2)=>a+b2,0));
  const remainingPcs=m.pool.length;
  return {used:m.by.length>0, blocked:remaining<=0 && m.by.length>0,
          batches:[...new Set(m.by)], pcs:m.pcs, mtr:Math.round(m.mtr),
          total:t.mtr, totalPcs:t.pcs, remaining:remaining, remainingPcs:remainingPcs};
}
```

`lotsAvailable` (`app.js:229-231`) is unchanged — it already just calls `lotAllocation` per lot, and each call is now O(1) instead of O(batches).

- [ ] **Step 4: Run the same verification script — must still print `ALL OK`**

Run: `node /tmp/task1_test.js`
Expected: `ALL OK` — identical output to Step 2, proving the refactor didn't change behavior.

- [ ] **Step 5: Verify no code mutates `DB.lots`/`DB.batches` in place without reassigning `DB`**

Run: `grep -n "DB\.lots\.push\|DB\.batches\.push\|DB\.lots\s*=\|DB\.batches\s*=" mvp/static/*.html mvp/static/app.js`
Expected: no matches outside of `DB = await (...).json()` in `app.js`'s `API.db()`. If any match is found, the cache invalidation assumption (new `DB` reference on every reload) is broken for that code path — fix it to call `API.db()` (which replaces `DB` wholesale) instead of mutating in place, or the memoized map will silently serve stale data.

- [ ] **Step 6: Debounce the Admin search input**

In `mvp/static/admin.html`, find the search `<input>` in `render()` (the `oninput="SEARCH[CUR]=this.value;render();setTimeout(...)"` line). Add this function right above `function render(){`:

```js
let _searchDebounce=null;
function onSearchInput(el){
  SEARCH[CUR]=el.value;
  clearTimeout(_searchDebounce);
  _searchDebounce=setTimeout(()=>{
    render();
    const i=document.querySelector('.search input');
    if(i){ i.focus(); i.setSelectionRange(i.value.length,i.value.length); }
  }, 150);
}
```

Replace the input's `oninput="SEARCH[CUR]=this.value;render();setTimeout(()=>{var i=document.querySelector('.search input');if(i){i.focus();i.setSelectionRange(i.value.length,i.value.length);}},0)"` with `oninput="onSearchInput(this)"`.

- [ ] **Step 7: Verify admin.html still parses**

Run:
```bash
python3 -c "
import re
html = open('mvp/static/admin.html', encoding='utf-8').read()
m = re.search(r'<script>(.*)</script>', html, re.S)
open('/tmp/admin_t1.js','w',encoding='utf-8').write(m.group(1))
"
node -e "new Function(require('fs').readFileSync('/tmp/admin_t1.js','utf8')); console.log('OK')"
```
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add mvp/static/app.js mvp/static/admin.html
git commit -m "perf: memoize lot allocation (was O(lots x batches)), debounce admin search"
```

---

## Task 2: Generic bulk-add engine for master tables

**Files:**
- Modify: `mvp/static/admin.html`

**Interfaces:**
- Consumes: `SCHEMAS[table]`, `API.save(table,row)`, `API.db()`, `toast()`, `renderNav()`, `render()` — all existing.
- Produces: `openBulkAdd(table)`, `parseBulkAdd(table,text)`, `commitBulkAdd(table)`, `bulkAddFields(table)`, `BULK_ADD_TABLES` (array) — new globals in `admin.html`, callable the same way `openQualityQuickAdd()`/`commitQualityQuickAdd()` already are.

Qualities already has a bulk path (`openQualityQuickAdd`/`commitQualityQuickAdd`, `admin.html`) and Lots has full Excel import — both stay as-is, they're the reference pattern. This task adds ONE generic mechanism (not eight copy-pasted ones) for every other master table: **machines, customers, suppliers, operators, qcMetrics, shadeRecipes, qualityRecipes, weavers**. `storageAreas` is excluded here — it's being redesigned into a slot-based model in Task 6 with its own bulk mechanism. `orders`, `batches`, `users`, `roles` are excluded by design (workflow-sensitive records, not suited to freeform paste).

- [ ] **Step 1: Add the bulk-add engine**

In `mvp/static/admin.html`, add directly above `function openQualityQuickAdd(){` (use that function's existing location as the anchor — the new code sits right before it):

```js
const BULK_ADD_TABLES=["machines","customers","suppliers","operators","qcMetrics","shadeRecipes","qualityRecipes","weavers"];
const BULK_ADD_SKIP_TYPES=new Set(["readonly","perms","aux","takas","lotTotal","lotqty","batchTotal","lotsel","password"]);
function bulkAddFields(table){
  return SCHEMAS[table].fields.filter(f=>!BULK_ADD_SKIP_TYPES.has(f.t)).slice(0,7);
}
function openBulkAdd(table){
  const sc=SCHEMAS[table], fields=bulkAddFields(table);
  const allSimple=SCHEMAS[table].fields.filter(f=>!BULK_ADD_SKIP_TYPES.has(f.t));
  const ex=document.getElementById("bulkOverlay"); if(ex) ex.remove();
  const o=document.createElement("div"); o.id="bulkOverlay"; o.className="modal-bg on";
  const colList=fields.map(f=>f.l).join(", ");
  o.innerHTML='<div class="modal" style="width:640px;max-width:94vw">'
    +'<div class="m-h"><h3>Bulk add '+esc(sc.label.toLowerCase())+'</h3><button class="x" onclick="this.closest(\'.modal-bg\').remove()">&times;</button></div>'
    +'<div class="m-b"><p class="small muted">One '+esc(sc.single)+' per line, comma or tab separated, in this order: <b>'+esc(colList)+'</b>. '
    +'An existing '+esc(sc.single)+' (matched by <b>'+esc(fields[0].l)+'</b>) updates in place instead of duplicating.'
    +(fields.length<allSimple.length ? ' Remaining fields still need the full Edit form.' : '')+'</p>'
    +'<textarea id="bulkText" rows="10" placeholder="'+esc(fields.map(f=>f.l).join(", "))+'"></textarea>'
    +'<div id="bulkPreview" class="small muted" style="margin-top:8px"></div></div>'
    +'<div class="m-f"><button class="btn ghost" onclick="this.closest(\'.modal-bg\').remove()">Cancel</button>'
    +'<button class="btn" id="bulkSaveBtn" onclick="commitBulkAdd(\''+table+'\')">Save all</button></div></div>';
  document.body.appendChild(o);
  document.getElementById("bulkText").addEventListener("input", ()=>{
    const n=parseBulkAdd(table, document.getElementById("bulkText").value).length;
    document.getElementById("bulkPreview").innerHTML = n ? ('<b class="tnum">'+n+'</b> row(s) ready') : "";
  });
}
function parseBulkAdd(table, text){
  const fields=bulkAddFields(table);
  return text.split("\n").map(l=>l.trim()).filter(Boolean).map(line=>{
    const parts=line.split(/\t|,/).map(s=>s.trim());
    const row={};
    fields.forEach((f,i)=>{
      let v=parts[i]!==undefined ? parts[i] : "";
      if(f.t==="number") v=v===""?"":+v;
      else if(f.t==="bool") v=/^(y|yes|true|1)$/i.test(v);
      else if(f.t==="select" && f.o && v && f.o.indexOf(v)<0) v="";
      row[f.k]=v;
    });
    return row;
  }).filter(r=>r[fields[0].k]);
}
async function commitBulkAdd(table){
  const rows=parseBulkAdd(table, document.getElementById("bulkText").value);
  if(!rows.length){ toast("Nothing to add"); return; }
  const btn=document.getElementById("bulkSaveBtn"); if(btn){ btn.disabled=true; btn.textContent="Saving…"; }
  const idKey=bulkAddFields(table)[0].k;
  const byKey={}; (DB[table]||[]).forEach(r=>{ byKey[r[idKey]]=r; });
  for(const r of rows){
    const existing=byKey[r[idKey]];
    const row=existing ? Object.assign({},existing,r) : r;
    await API.save(table, row);
  }
  await API.db(); document.getElementById("bulkOverlay").remove(); renderNav(); render();
  toast("Saved "+rows.length+" record(s)");
}
```

- [ ] **Step 2: Wire the "Bulk add" button into the toolbar**

In `render()`, find the toolbar line that already conditionally adds the lots/qualities buttons:
```js
+(CUR==="lots" ? '<button class="btn ghost" onclick="openLotImport()"><span class="material-symbols-rounded">upload_file</span>Import from Excel</button>' : '')
+(CUR==="qualities" ? '<button class="btn ghost" onclick="openQualityQuickAdd()"><span class="material-symbols-rounded">playlist_add</span>Quick add</button>' : '')
```
Add a third line directly after it:
```js
+(BULK_ADD_TABLES.includes(CUR) ? '<button class="btn ghost" onclick="openBulkAdd(\''+CUR+'\')"><span class="material-symbols-rounded">playlist_add</span>Bulk add</button>' : '')
```

- [ ] **Step 3: Write the Node verification script**

Create `/tmp/task2_test.js`:

```js
const fs = require('fs');
const html = fs.readFileSync('mvp/static/admin.html', 'utf8');
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
global.document = { getElementById: ()=>null, createElement: ()=>({}), querySelector: ()=>null, appendChild: ()=>{} };
global.esc = s => String(s==null?"":s);
const harness = script + `
DB = { weavers: [{id:'WV-0001', name:'R.E.L.(W)', contact:'', phone:''}] };
const rows = parseBulkAdd('weavers', 'R.E.L.(W), Ramesh, 9998887770\\nNEW WEAVER CO, Suresh, 9990001112');
console.log(JSON.stringify(rows));
if (rows.length !== 2) throw new Error('expected 2 rows, got ' + rows.length);
if (rows[0].name !== 'R.E.L.(W)' || rows[0].contact !== 'Ramesh') throw new Error('row 0 wrong: ' + JSON.stringify(rows[0]));
if (rows[1].name !== 'NEW WEAVER CO') throw new Error('row 1 wrong');
console.log('ALL OK');
`;
eval(harness);
```

- [ ] **Step 4: Run it**

Run: `node /tmp/task2_test.js`
Expected: `ALL OK`. (This exercises `parseBulkAdd` directly — `commitBulkAdd`/`openBulkAdd` touch the DOM and `API`, which are exercised by the manual smoke test in Step 5 instead.)

- [ ] **Step 5: Manual smoke test against a running server**

```bash
cd mvp && python3 server.py 8099 &
sleep 1.5
curl -s -c /tmp/c.txt -X POST http://localhost:8099/api -H "Content-Type: application/json" -d '{"op":"login","username":"ADMIN","password":"sonkeiwachikara"}' >/dev/null
curl -s -b /tmp/c.txt -X POST http://localhost:8099/api -H "Content-Type: application/json" -d '{"op":"upsert","table":"weavers","row":{"name":"TEST BULK WEAVER","contact":"Test"}}'
curl -s -b /tmp/c.txt -X POST http://localhost:8099/api -H "Content-Type: application/json" -d '{"op":"delete","table":"weavers","id":"<id from previous response>"}'
kill %1
```
Expected: first call returns `{"ok":true,...}` with a generated id; confirm via `/api/db` that the row appears, then confirm the delete removes it, leaving no test data behind. **Never leave test rows in the live `data.json` — always delete what you created.**

- [ ] **Step 6: Commit**

```bash
git add mvp/static/admin.html
git commit -m "feat: generic bulk-add for machines/customers/suppliers/operators/qcMetrics/shadeRecipes/qualityRecipes/weavers"
```

---

## Task 3: Excel export for every master table, the Batch list, and the Schedule

**Files:**
- Modify: `mvp/static/admin.html` (generic table export)
- Modify: `mvp/static/index.html` (batch list export, schedule export, add the vendored xlsx script tag)

**Interfaces:**
- Consumes: `SCHEMAS`, `DB`, `cellText()` (from Task-1-era `admin.html`, already exists from the earlier full-column-search work), the global `XLSX` object from the vendored SheetJS.
- Produces: `exportTableToExcel(table)` in `admin.html`; `exportBatchesToExcel()` and `exportScheduleToExcel()` in `index.html`.

- [ ] **Step 1: Add xlsx.full.min.js to index.html**

`index.html` currently only loads `app.js` (`<script src="app.js"></script>`, near the end of the file). `admin.html` already loads `<script src="vendor/xlsx.full.min.js"></script>` before `app.js`. Add the same line to `index.html`, immediately before its `<script src="app.js"></script>`:

```html
<script src="vendor/xlsx.full.min.js"></script>
<script src="app.js"></script>
```

- [ ] **Step 2: Generic export for every Admin master table**

In `mvp/static/admin.html`, add near `cellText()`:

```js
function exportTableToExcel(table){
  const sc=SCHEMAS[table], rows=DB[table]||[];
  const header=sc.cols.map(x=>x[1]);
  const body=rows.map(r=>sc.cols.map(x=>cellText(table,r,x[0])));
  const ws=XLSX.utils.aoa_to_sheet([header].concat(body));
  const wb=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sc.label.slice(0,31));
  XLSX.writeFile(wb, sc.label.replace(/[^a-z0-9]+/gi,"_")+"_"+new Date().toISOString().slice(0,10)+".xlsx");
}
```

Wire it into `render()`'s toolbar — this one works for every table (`sc.cols` always exists), so it doesn't need an allowlist like `BULK_ADD_TABLES`. Add right after the "+ Add" button's closing `</div>` is built, i.e. append a new line to the toolbar div's contents:

```js
+'<button class="btn" onclick="openModal(CUR,null)">+ Add '+sc.single+'</button>'
+'<button class="btn ghost" onclick="exportTableToExcel(CUR)"><span class="material-symbols-rounded">download</span>Export</button></div>'
```
(replacing the existing `+'<button class="btn" onclick="openModal(CUR,null)">+ Add '+sc.single+'</button></div>'` line — the export button goes inside the same `.toolbar` div, after Add.)

- [ ] **Step 3: Batch list export (index.html)**

Add near `renderBatchList()` in `mvp/static/index.html`:

```js
function exportBatchesToExcel(){
  const header=["Batch","Lot no.","Quality","Shade","Pcs","Mtr","Kg","In","Out","pH","Operator","Shift"];
  const body=(DB.batches||[]).slice().reverse().map(b=>[
    b.id, (b.lotIds||[]).join(", "), b.quality, b.shadeNo||"", b.pcs, b.mtr, b.weight,
    b.inTime||"", b.outTime||"", b.ph||"", b.operator||"", b.shift||""]);
  const ws=XLSX.utils.aoa_to_sheet([header].concat(body));
  const wb=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Batches");
  XLSX.writeFile(wb, "Batches_"+new Date().toISOString().slice(0,10)+".xlsx");
}
```

Add a button next to `<h2>Recent batches</h2>` in the Batch maker section (`<div class="card"><div class="card-h"><h2>Recent batches</h2><span class="sub" id="batchCount"></span></div>`):
```html
<div class="card"><div class="card-h"><h2>Recent batches</h2><span class="sub" id="batchCount"></span>
  <button class="btn ghost sm" onclick="exportBatchesToExcel()"><span class="material-symbols-rounded">download</span>Export</button></div>
  <div class="tbl-wrap" id="batchList"></div>
</div>
```

- [ ] **Step 4: Schedule export (index.html)**

Add next to `exportBatchesToExcel()`:

```js
function exportScheduleToExcel(){
  if(!S) return;
  const header=["Machine","Type","Kind","Batch","Order","Start (t+min)","Duration (min)","Step"];
  const body=[];
  DB.machines.forEach(m=>{
    (S.tl[m.id].blocks||[]).forEach(b=>{
      body.push([m.id, m.type, b.kind, b.batch?b.batch.batchId:"", b.batch?b.batch.order:"", b.start, b.mins, b.step||""]);
    });
  });
  const ws=XLSX.utils.aoa_to_sheet([header].concat(body));
  const wb=XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Schedule");
  XLSX.writeFile(wb, "Schedule_"+new Date().toISOString().slice(0,10)+".xlsx");
}
```

Add a button in the Schedule section's `.bar` div (`<div class="bar"><span class="small muted" id="schednote"></span></div>` in the `#v-sched` section):
```html
<div class="bar"><span class="small muted" id="schednote"></span>
  <button class="btn ghost sm" onclick="exportScheduleToExcel()"><span class="material-symbols-rounded">download</span>Export</button></div>
```

- [ ] **Step 5: Verify both files still parse**

```bash
python3 -c "
import re
for f in ['mvp/static/admin.html','mvp/static/index.html']:
    html=open(f,encoding='utf-8').read()
    m=re.search(r'<script>(.*)</script>', html, re.S)
    open('/tmp/'+f.split('/')[-1]+'.check.js','w',encoding='utf-8').write(m.group(1))
"
node -e "new Function(require('fs').readFileSync('/tmp/admin.html.check.js','utf8')); console.log('admin OK')"
node -e "new Function(require('fs').readFileSync('/tmp/index.html.check.js','utf8')); console.log('index OK')"
```
Expected: `admin OK` and `index OK`.

- [ ] **Step 6: Commit**

```bash
git add mvp/static/admin.html mvp/static/index.html
git commit -m "feat: Excel export for every master table, the batch list, and the schedule"
```

---

## Task 4: Assign shade families to machines (soft scheduling preference)

**Files:**
- Modify: `mvp/static/admin.html` (`SCHEMAS.machines`, `fieldInput()`, `saveModal()`, `cellVal()`, Settings page)
- Modify: `mvp/static/app.js` (`computeSchedule()`)

**Interfaces:**
- Consumes: `FAMILIES` (existing const in `admin.html`), `cfg()` (existing in `app.js`)
- Produces: `m.shadeFamilies` (array of strings) on machine rows; `cfg().familyPreferencePenaltyMins` (number, new setting)

Decision (confirmed with owner): **soft preference** — the scheduler prefers a family-tagged machine for that family, but falls back to a free untagged machine if the tagged one is backed up. Implemented as a scheduling penalty: an untagged-but-eligible machine only loses to a tagged one if it isn't more than `familyPreferencePenaltyMins` minutes faster.

- [ ] **Step 1: Add the `shadeFamilies` field to machines**

In `mvp/static/admin.html`, in `SCHEMAS.machines.fields` (starts at `{k:"id",l:"MC ID",...`), add after the `plc` field:

```js
{k:"shadeFamilies",l:"Preferred shade families",sec:"Capacity & process",t:"famsel",help:"Scheduler prefers this machine for these families when it's free — a soft preference, not a hard restriction"},
```

Add a column so it's visible in the machines list — in `SCHEMAS.machines.cols`, after `["plc","PLC"]`:
```js
,["shadeFamilies","Fam. pref"]
```

- [ ] **Step 2: Render/save the `famsel` field type**

In `fieldInput()` (`admin.html`), add right after the existing `if(f.t==="perms"){...}` block:

```js
if(f.t==="famsel"){
  const sel=Array.isArray(val)?val:[];
  return '<div style="display:flex;flex-wrap:wrap;gap:6px 16px">'
    +FAMILIES.map(fam=>'<label style="display:inline-flex;align-items:center;gap:6px;font-weight:500;color:var(--ink);margin:0"><input type="checkbox" data-fam="'+esc(fam)+'" '+(sel.indexOf(fam)>=0?"checked":"")+' style="width:auto;margin:0">'+esc(fam)+'</label>').join("")
    +'</div>';
}
```

In `saveModal()`, add right after the existing `if(f.t==="perms"){ row.perms=...; return; }` line:
```js
if(f.t==="famsel"){ row.shadeFamilies=[...document.querySelectorAll('#mBody [data-fam]')].filter(x=>x.checked).map(x=>x.dataset.fam); return; }
```

In `cellVal()`, add a branch (anywhere among the other `if(k===...)` branches, e.g. right after the `k==="permsCount"` branch):
```js
if(k==="shadeFamilies") return (r.shadeFamilies||[]).length ? (r.shadeFamilies||[]).map(f=>'<span class="chip">'+esc(f)+'</span>').join("") : '<span class="muted">&mdash;</span>';
```

- [ ] **Step 3: Add the tunable penalty to Settings**

In `renderSettings()` (`admin.html`), add a field to the `grid3` div, after the "Unloading time (min)" label:
```js
+'<label class="fld">Family preference penalty (min)<input id="s_fampen" type="number" value="'+(s.familyPreferencePenaltyMins||120)+'"><span class="help">A non-preferred machine only wins over a preferred one if it finishes at least this much sooner</span></label>'
```
In `saveSettings()`, add `familyPreferencePenaltyMins:+s_fampen.value` to the `st` object.

- [ ] **Step 4: Apply the soft preference in the scheduler**

In `mvp/static/app.js`, `computeSchedule()`, find:
```js
      let best=null;
      elig.forEach(m=>{
        const q=tl[m.id];
        const needWash = st.isDye && q.last && (q.last.family!==b.family || q.last.tone>b.tone);
        const start=Math.max(q.cursor,t)+(needWash?(m.wash||0):0);
        const fin=start+occ;
        if(!best||fin<best.fin) best={m,q,needWash,start,fin};
      });
```
Replace with:
```js
      const familyPenalty=+cfg().familyPreferencePenaltyMins||120;
      const preferSet=(st.isDye && b.family) ? new Set(DB.machines.filter(m=>(m.shadeFamilies||[]).includes(b.family)).map(m=>m.id)) : null;
      let best=null;
      elig.forEach(m=>{
        const q=tl[m.id];
        const needWash = st.isDye && q.last && (q.last.family!==b.family || q.last.tone>b.tone);
        const start=Math.max(q.cursor,t)+(needWash?(m.wash||0):0);
        const fin=start+occ;
        const penalty=(preferSet && preferSet.size && !preferSet.has(m.id)) ? familyPenalty : 0;
        const score=fin+penalty;
        if(!best||score<best.score) best={m,q,needWash,start,fin,score};
      });
```
`best.fin`/`best.start`/`best.needWash` are read unchanged further down (`app.js:374-378`) — only the *selection* criterion changes, not what's stored on `best`.

- [ ] **Step 5: Write the Node verification script**

Create `/tmp/task4_test.js`:

```js
const fs = require('fs');
const src = fs.readFileSync('mvp/static/app.js', 'utf8');
const harness = src + `
DB = {
  machines: [
    {id:'JET-1', type:'jet', capMax:300, wash:30, shadeFamilies:['Blue']},
    {id:'JET-2', type:'jet', capMax:300, wash:30, shadeFamilies:[]}
  ],
  qualities: [{name:'Q1', gsm:110, width:56, maxBatch:300, step3_mc:'jet', step3_time:120, dyeStep:3, loadMin:35, unloadMin:25}],
  shadeRecipes: [{quality:'Q1', shade:'Navy', family:'Blue', tone:8}],
  batches: [
    {id:'B-1', quality:'Q1', shadeNo:'Navy', lots:[{lotId:'L1', pcs:1, mtr:300, weight:100}], status:'planned'}
  ],
  settings: {loadMin:35, unloadMin:25, buffer:1.2, familyPreferencePenaltyMins:120}
};
const S = computeSchedule();
const b = S.batches.find(x=>x.key==='B-1');
console.log('assigned to', b.mcAssigned);
if (b.mcAssigned !== 'JET-1') throw new Error('expected the single batch to prefer JET-1 (tagged for Blue), got ' + b.mcAssigned);
console.log('ALL OK');
`;
eval(harness);
```

- [ ] **Step 6: Run it**

Run: `node /tmp/task4_test.js`
Expected: `assigned to JET-1` then `ALL OK`.

- [ ] **Step 7: Verify fallback-when-busy behavior with a second scenario**

Extend the same idea in `/tmp/task4b_test.js`: give `JET-1` an existing block that keeps it busy well past `familyPreferencePenaltyMins` minutes longer than `JET-2` would take, and assert the new batch lands on `JET-2` instead — proving it's a soft preference, not a hard lock. (Simplest approach: create two batches in sequence — the first forced onto `JET-1` by being the only eligible machine at that point, the second a `Blue` batch that should now prefer `JET-2` because `JET-1`'s queue is backed up.) Confirm this behaves as expected before moving on; if `JET-1` still wins even when clearly backed up, the penalty comparison in Step 4 is inverted — double check `score=fin+penalty` (higher score = worse = picked last).

- [ ] **Step 8: Verify admin.html still parses**

```bash
python3 -c "
import re
html = open('mvp/static/admin.html', encoding='utf-8').read()
m = re.search(r'<script>(.*)</script>', html, re.S)
open('/tmp/admin_t4.js','w',encoding='utf-8').write(m.group(1))
"
node -e "new Function(require('fs').readFileSync('/tmp/admin_t4.js','utf8')); console.log('OK')"
```

- [ ] **Step 9: Commit**

```bash
git add mvp/static/admin.html mvp/static/app.js
git commit -m "feat: machines can be tagged with preferred shade families (soft scheduling preference)"
```

---

## Task 5: Move loading/unloading time from global settings to per-quality

**Files:**
- Modify: `mvp/static/admin.html` (`SCHEMAS.qualities`, `renderSettings()`, `saveSettings()`)
- Modify: `mvp/static/app.js` (`computeSchedule()`)
- Modify: `mvp/static/index.html` (`renderGantt()`'s load/unload cap width, for visual consistency)

**Interfaces:**
- Consumes: `cfg()` (existing) as the fallback when a quality hasn't set its own values yet.
- Produces: `q.loadMin`, `q.unloadMin` on quality rows; `cfg().loadMin`/`cfg().unloadMin` remain in settings **only as the fallback default**, not the primary source.

Decision: keep the two Settings fields (don't delete them outright — a fallback is architecturally necessary for qualities that haven't been configured yet, and deleting `cfg().loadMin`/`cfg().unloadMin` would break that fallback chain), but relabel them clearly as defaults, and every quality gets its own override fields.

- [ ] **Step 1: Add `loadMin`/`unloadMin` fields to qualities**

In `mvp/static/admin.html`, `SCHEMAS.qualities.fields`, add after the `maxBatch` field:
```js
{k:"loadMin",l:"Loading time (min)",sec:"Fabric",t:"number",min:0,help:"Falls back to the Settings default if left blank"},
{k:"unloadMin",l:"Unloading time (min)",sec:"Fabric",t:"number",min:0,help:"Falls back to the Settings default if left blank"},
```

- [ ] **Step 2: Relabel the Settings fields as fallback defaults**

In `renderSettings()`, change:
```js
+'<label class="fld">Loading time (min)<input id="s_load" type="number" value="'+s.loadMin+'"></label>'
+'<label class="fld">Unloading time (min)<input id="s_unload" type="number" value="'+s.unloadMin+'"></label>'
```
to:
```js
+'<label class="fld">Default loading time (min)<input id="s_load" type="number" value="'+s.loadMin+'"><span class="help">Used only when a quality has no loading time of its own</span></label>'
+'<label class="fld">Default unloading time (min)<input id="s_unload" type="number" value="'+s.unloadMin+'"><span class="help">Used only when a quality has no unloading time of its own</span></label>'
```
`saveSettings()` needs no change — it already reads `s_load`/`s_unload` into `st.loadMin`/`st.unloadMin`.

- [ ] **Step 3: Compute `H` per-batch instead of once globally**

In `mvp/static/app.js`, `computeSchedule()`, remove the single global line:
```js
  const H = (cfg().loadMin||35)+(cfg().unloadMin||25);
```
and instead compute it inside the `batches.forEach(b=>{...})` loop, right after `let t=0, steps=routeOf(b.q, b.meters);`:
```js
    const H = (+b.q.loadMin||cfg().loadMin||35) + (+b.q.unloadMin||cfg().unloadMin||25);
```
The rest of the loop (`const occ=H+st.time;` inside `steps.forEach`) is unchanged — `H` is now in the batch's scope instead of the function's.

The function's final return, `return {tl,batches,washCount,orderFinish,batchCount:batches.length,maxMin,H,BUF};`, references the now-removed outer `H`. Change it to drop `H` from the returned object (it's no longer a single meaningful value):
```js
  return {tl,batches,washCount,orderFinish,batchCount:batches.length,maxMin,BUF};
```

- [ ] **Step 4: Check every caller of `S.H` before removing it**

Run: `grep -rn "\.H\b" mvp/static/index.html mvp/static/admin.html`
Expected: no matches that read `S.H` (a Gantt/Plan renderer reading a schedule-result's `.H` property). If any are found, replace that usage with the specific batch's own `H` (available via `bt.q.loadMin`/`bt.q.unloadMin` — `batchesForSchedule()` already attaches `q:q` to every pushed batch object, so `bt.q.loadMin||cfg().loadMin||35` is always available in any renderer that has the batch object).

- [ ] **Step 5: Update the Gantt's decorative load/unload cap width to match**

In `mvp/static/index.html`, `renderGantt()` currently computes one global `H`/`U` for every block's visual load/unload cap:
```js
function renderGantt(el,S,newKeys){
  newKeys=newKeys||[]; LAST_S=S;
  const H=cfg().loadMin||35, U=cfg().unloadMin||25;
```
and later, per dye block:
```js
html+='<div class="blk'+hot+(bt.urgent?' urgent':'')+'" data-bk="'+bt.key+'" style="left:'+left+'px;width:'+w+'px;background:'+shadeColor(bt.shade,bt.qual)+';color:'+(bt.tone>5?'#fff':'#20242c')+'"><div class="cap l" style="width:'+px(H)+'px"></div><div class="cap r" style="width:'+px(U)+'px"></div>'+marks+esc(bt.shade)+'<small>'+esc(bt.order)+' - '+bt.meters+'m</small></div>';
```
Change the per-block cap widths to use that batch's own quality, falling back to the global default. Replace the top-of-function line with just:
```js
function renderGantt(el,S,newKeys){
  newKeys=newKeys||[]; LAST_S=S;
```
(remove the `const H=..., U=...` line — it's still used for the pre-treat block's `<div class="blk pre" ...>` markup, which doesn't currently render a cap, so nothing else in this function needs it). Then change the dye block's cap markup to:
```js
html+='<div class="blk'+hot+(bt.urgent?' urgent':'')+'" data-bk="'+bt.key+'" style="left:'+left+'px;width:'+w+'px;background:'+shadeColor(bt.shade,bt.qual)+';color:'+(bt.tone>5?'#fff':'#20242c')+'"><div class="cap l" style="width:'+px((+bt.q.loadMin||cfg().loadMin||35))+'px"></div><div class="cap r" style="width:'+px((+bt.q.unloadMin||cfg().unloadMin||25))+'px"></div>'+marks+esc(bt.shade)+'<small>'+esc(bt.order)+' - '+bt.meters+'m</small></div>';
```
(`bt` here is `b.batch` from `S.tl[m.id].blocks`, which is the object pushed in `batchesForSchedule()` — confirm it carries `q`; it does, per `app.js`'s `out.push({key:b.id, ..., q:q, ...})`.)

- [ ] **Step 6: Write the Node verification script**

Create `/tmp/task5_test.js`:

```js
const fs = require('fs');
const src = fs.readFileSync('mvp/static/app.js', 'utf8');
const harness = src + `
DB = {
  machines: [{id:'JET-1', type:'jet', capMax:300, wash:30, shadeFamilies:[]}],
  qualities: [
    {name:'QWithOwn', gsm:110, width:56, maxBatch:300, step3_mc:'jet', step3_time:120, dyeStep:3, loadMin:10, unloadMin:5},
    {name:'QNoOwn', gsm:110, width:56, maxBatch:300, step3_mc:'jet', step3_time:120, dyeStep:3}
  ],
  shadeRecipes: [],
  batches: [
    {id:'B-1', quality:'QWithOwn', shadeNo:'', lots:[{lotId:'L1', pcs:1, mtr:300, weight:100}], status:'planned'},
  ],
  settings: {loadMin:35, unloadMin:25, buffer:1.2, familyPreferencePenaltyMins:120}
};
let S = computeSchedule();
let b1 = S.batches.find(x=>x.key==='B-1');
console.log('B-1 dyeEnd - dyeStart =', b1.dyeEnd - b1.dyeStart, '(expect 120 + 10 + 5 = 135)');
if (b1.dyeEnd - b1.dyeStart !== 135) throw new Error('expected own loadMin/unloadMin to be used, got duration ' + (b1.dyeEnd-b1.dyeStart));
DB.batches.push({id:'B-2', quality:'QNoOwn', shadeNo:'', lots:[{lotId:'L2', pcs:1, mtr:300, weight:100}], status:'planned'});
S = computeSchedule();
let b2 = S.batches.find(x=>x.key==='B-2');
console.log('B-2 dyeEnd - dyeStart =', b2.dyeEnd - b2.dyeStart, '(expect 120 + 35 + 25 = 180, using settings fallback)');
if (b2.dyeEnd - b2.dyeStart !== 180) throw new Error('expected settings fallback, got duration ' + (b2.dyeEnd-b2.dyeStart));
console.log('ALL OK');
`;
eval(harness);
```

- [ ] **Step 7: Run it**

Run: `node /tmp/task5_test.js`
Expected: both duration checks pass, then `ALL OK`.

- [ ] **Step 8: Verify all three files still parse**

```bash
python3 -c "
import re
for f in ['mvp/static/admin.html','mvp/static/index.html']:
    html=open(f,encoding='utf-8').read()
    m=re.search(r'<script>(.*)</script>', html, re.S)
    open('/tmp/'+f.split('/')[-1]+'.t5.js','w',encoding='utf-8').write(m.group(1))
"
node -e "new Function(require('fs').readFileSync('/tmp/admin.html.t5.js','utf8')); console.log('admin OK')"
node -e "new Function(require('fs').readFileSync('/tmp/index.html.t5.js','utf8')); console.log('index OK')"
node -e "new Function(require('fs').readFileSync('mvp/static/app.js','utf8')); console.log('app.js OK')"
```

- [ ] **Step 9: Commit**

```bash
git add mvp/static/admin.html mvp/static/app.js mvp/static/index.html
git commit -m "feat: loading/unloading time moves to per-quality (settings values become the fallback default)"
```

---

## Task 6: Storage data model — lot-linked slots, numbered shelves, lettered columns

**Files:**
- Modify: `mvp/server.py` (register `storageAreas` field changes are none server-side; register new `storageSlots` table)
- Modify: `mvp/static/admin.html` (`SCHEMAS.storageAreas`, new `SCHEMAS.storageSlots`, `fieldInput()` for `areasel`/`lotsel1`, `saveModal()`, `openModal()`)

**Interfaces:**
- Consumes: `lotPickerHTML(selId, extraCls)`, `wireLotPicker(root, opts)`, `lotPickVal(root)` (existing, from `app.js` — built for the Batch Maker's lot picker, reused as-is here).
- Produces: `storageSlots` table (`{id, area, shelf, col, lotId, notes}`); `colLetter(i)` helper (`app.js`) — column index (0-based) to letter, `A`..`Z`, `AA`..`AZ` beyond 26.

Decision (confirmed with owner): slots are **lot-linked** — a slot references a real `Lot` record, not a free-text quality/shade tag. Only *occupied* slots get a `storageSlots` row; an (area, shelf, col) combination with no matching row is simply empty — don't materialize thousands of empty slot rows for a large grid.

- [ ] **Step 1: Register `storageSlots` on the server**

In `mvp/server.py`, find `ALL_PAGES` (line 27) and add `"storageSlots"` to the list, next to `"storageAreas"`:
```python
ALL_PAGES = ["op_floor","op_schedule","op_order","op_batch",
             "dashboard","machines","qualities","shadeRecipes","qualityRecipes",
             "batches","lots","weavers",
             "customers","orders","storageAreas","storageSlots","suppliers","operators","qcMetrics",
             "users","roles","plan","settings","urgent_flag"]
```
In `_next_seq_id`'s prefix map (`{"lots":"LOT","batches":"B","orders":"SO","weavers":"WV"}.get(table, table[:2].upper())`), add `"storageSlots":"SL"`:
```python
    prefix = {"lots":"LOT","batches":"B","orders":"SO","weavers":"WV","storageSlots":"SL"}.get(table, table[:2].upper())
```

- [ ] **Step 2: Add `colLetter()` to app.js**

Add near the top of `mvp/static/app.js`, after `const byName = ...`:
```js
function colLetter(i){    // 0-based index -> A, B, ... Z, AA, AB, ... (spreadsheet-style)
  let n=i+1, s="";
  while(n>0){ const r=(n-1)%26; s=String.fromCharCode(65+r)+s; n=Math.floor((n-1)/26); }
  return s;
}
```

- [ ] **Step 3: Replace `storageAreas`' fixed-grid fields with shelf/column counts**

In `mvp/static/admin.html`, `SCHEMAS.storageAreas`, replace:
```js
  storageAreas:{label:"Storage areas",single:"storage area",
    cols:[["name","Area"],["shelves","Shelves"],["rowsPerShelf","Rows/shelf"],["colsPerShelf","Cols/shelf"],["slots","Total slots"],["floor","Floor"]],
    search:["name"],
    fields:[
      {k:"name",l:"Area name",sec:"Area",req:true},
      {k:"floor",l:"Floor no.",sec:"Area",t:"number",min:0},
      {k:"locX",l:"Location X",sec:"Area",t:"number"},
      {k:"locY",l:"Location Y",sec:"Area",t:"number"},
      {k:"shelves",l:"Number of shelves",sec:"Indexing (locate each taka)",t:"number",req:true,min:1,help:"Each shelf has rows x columns of slots"},
      {k:"rowsPerShelf",l:"Rows per shelf",sec:"Indexing (locate each taka)",t:"number",req:true,min:1},
      {k:"colsPerShelf",l:"Columns per shelf",sec:"Indexing (locate each taka)",t:"number",req:true,min:1,help:"A taka location = area / shelf / row / column"}]},
```
with:
```js
  storageAreas:{label:"Storage areas",single:"storage area",
    cols:[["name","Area"],["shelfCount","Shelves"],["colCount","Columns"],["floor","Floor"]],
    search:["name"],
    fields:[
      {k:"name",l:"Area name",sec:"Area",req:true},
      {k:"floor",l:"Floor no.",sec:"Area",t:"number",min:0},
      {k:"locX",l:"Location X",sec:"Area",t:"number"},
      {k:"locY",l:"Location Y",sec:"Area",t:"number"},
      {k:"shelfCount",l:"Number of shelves",sec:"Layout",t:"number",req:true,min:1,help:"Shelves are numbered 1, 2, 3…"},
      {k:"colCount",l:"Number of columns",sec:"Layout",t:"number",req:true,min:1,help:"Columns are lettered A, B, C…"}]},
```
(`slots` was a computed `k==="slots"` branch in `cellVal()` — `return (+r.shelves||0)*(+r.rowsPerShelf||0)*(+r.colsPerShelf||0);` — remove that branch from `cellVal()` since `shelves`/`rowsPerShelf`/`colsPerShelf` no longer exist; the new column count is `shelfCount x colCount`, not shown as a derived column here since Task 7's Storage tab is where the real occupancy view lives.)

Remove the `if(k==="slots") return (+r.shelves||0)*(+r.rowsPerShelf||0)*(+r.colsPerShelf||0);` line from `cellVal()`.

- [ ] **Step 4: Add `SCHEMAS.storageSlots`**

Add a new entry to `SCHEMAS`, after `storageAreas`:
```js
  storageSlots:{label:"Storage slots",single:"storage slot",
    cols:[["area","Area"],["shelf","Shelf"],["col","Column"],["lotId","Lot"],["notes","Notes"]],
    search:["area","lotId","notes"],
    fields:[
      {k:"area",l:"Storage area",sec:"Location",t:"areasel",req:true},
      {k:"shelf",l:"Shelf no.",sec:"Location",t:"number",req:true,min:1},
      {k:"col",l:"Column letter",sec:"Location",req:true,help:"A, B, C… must match the area's column count"},
      {k:"lotId",l:"Lot stored here",sec:"Contents",t:"lotsel1",help:"Which lot physically sits in this slot"},
      {k:"notes",l:"Notes",sec:"Contents",t:"textarea"}]},
```
Add `"storageSlots":"widgets"` — actually reuse an existing relevant icon; add to the `ic()` function's `M` map: `storageSlots:"inventory_2"` won't work since `storageAreas` already uses that key (`storageAreas:"inventory_2"`, confirmed at `admin.html`'s `ic()` map) — pick a distinct one: add `storageSlots:"shelves"` to the `M` object in `ic()`.

Add to `PAGES` (the page-permission list): `["storageSlots","Storage slots","Admin"],` right after the `storageAreas` entry.

Add to `NAV`'s "Store & stock" group: change
```js
  {grp:"Store & stock", items:[["storageAreas","Storage areas"],["suppliers","Suppliers"]]},
```
to
```js
  {grp:"Store & stock", items:[["storageAreas","Storage areas"],["storageSlots","Storage slots"],["suppliers","Suppliers"]]},
```
(Task 7 adds a *visual* Storage tab on top of this — this raw `storageSlots` CRUD page is the fallback direct-editing path, same relationship the Batch Maker's visual picker has to Admin's generic batch-edit modal.)

- [ ] **Step 5: Add the `areasel` and `lotsel1` field types**

In `fieldInput()`, add `areasel` alongside the other `*sel` option-list types (near `if(f.t==="wsel") opts=...`):
```js
  if(f.t==="areasel") opts=(DB.storageAreas||[]).map(x=>x.name);
```
(this falls through to the generic `if(opts) return '<select ...>'` branch already present — no further change needed for `areasel`.)

For `lotsel1`, add a dedicated branch (it needs the searchable picker widget, not a plain `<select>`) right before the generic `let opts=null;` block:
```js
  if(f.t==="lotsel1") return lotPickerHTML(val||"", "");
```

- [ ] **Step 6: Wire `wireLotPicker` after the modal renders, and read it back on save**

In `openModal()`, after the line `document.getElementById("mBody").innerHTML=html;`, add:
```js
  if(table==="storageSlots"){
    const root=document.querySelector('#mBody [data-k="lotId"]');
    if(root) wireLotPicker(root, {});
  }
```
(No `filterFn` needed here — any lot can be placed in storage, not just ones matching a locked quality.)

In `saveModal()`, add a branch for `lotsel1` right after the existing `if(f.t==="takas"){...}` block:
```js
    if(f.t==="lotsel1"){ row[f.k]=lotPickVal(document.querySelector('#mBody [data-k="'+f.k+'"]')); return; }
```

- [ ] **Step 7: Validate one occupant per slot, one slot per lot**

Still in `saveModal()`, before the final `await API.save(editTable,row);` line, add a check specific to `storageSlots`:
```js
  if(editTable==="storageSlots"){
    const clash=(DB.storageSlots||[]).find(s=>s.id!==row.id && s.area===row.area && +s.shelf===+row.shelf && s.col===row.col);
    if(clash){ toast("Shelf "+row.shelf+", column "+row.col+" in "+row.area+" is already occupied — clear it first"); return; }
    if(row.lotId){
      const dup=(DB.storageSlots||[]).find(s=>s.id!==row.id && s.lotId===row.lotId);
      if(dup){ toast("That lot is already stored at "+dup.area+" shelf "+dup.shelf+" column "+dup.col); return; }
    }
  }
```

- [ ] **Step 8: Verify admin.html and server.py**

```bash
python3 -c "
import re
html = open('mvp/static/admin.html', encoding='utf-8').read()
m = re.search(r'<script>(.*)</script>', html, re.S)
open('/tmp/admin_t6.js','w',encoding='utf-8').write(m.group(1))
"
node -e "new Function(require('fs').readFileSync('/tmp/admin_t6.js','utf8')); console.log('admin OK')"
python3 -c "import ast; ast.parse(open('mvp/server.py').read()); print('server.py OK')"
```

- [ ] **Step 9: Manual smoke test — create an area, create a slot, confirm the clash check**

```bash
cd mvp && python3 server.py 8098 &
sleep 1.5
curl -s -c /tmp/c2.txt -X POST http://localhost:8098/api -H "Content-Type: application/json" -d '{"op":"login","username":"ADMIN","password":"sonkeiwachikara"}' >/dev/null
curl -s -b /tmp/c2.txt -X POST http://localhost:8098/api -H "Content-Type: application/json" -d '{"op":"upsert","table":"storageAreas","row":{"name":"TEST AREA","shelfCount":5,"colCount":6}}'
curl -s -b /tmp/c2.txt -X POST http://localhost:8098/api -H "Content-Type: application/json" -d '{"op":"upsert","table":"storageSlots","row":{"area":"TEST AREA","shelf":1,"col":"A"}}'
curl -s -b /tmp/c2.txt http://localhost:8098/api/db | python3 -c "import json,sys; d=json.load(sys.stdin); print('areas:',[a['name'] for a in d['storageAreas']]); print('slots:',d['storageSlots'])"
# now clean up — delete both test rows using the ids printed above
kill %1
```
Expected: the area and slot both save with generated ids (`AR-xxxx`/`SL-xxxx` per `_next_seq_id`'s default `table[:2].upper()` fallback — confirm the actual prefix printed, since `storageAreas` isn't in the special-case map and falls back to `"ST"`). Delete both test rows via `{"op":"delete",...}` before finishing — **do not leave test data in the live `data.json`**.

- [ ] **Step 10: Commit**

```bash
git add mvp/server.py mvp/static/admin.html
git commit -m "feat: storageSlots table — lot-linked, numbered shelves, lettered columns"
```

---

## Task 7: Storage tab — visual grid, shelf modals, design + copy pass

**Files:**
- Modify: `mvp/static/index.html` (new "Storage" section tab, grid renderer, shelf modal)
- Modify: `mvp/static/style.css` (grid + modal styling, matching the existing design system)
- Modify: `mvp/server.py` (add `storageView` page-permission key if a separate one is wanted — see Step 1 decision)

**Interfaces:**
- Consumes: `DB.storageAreas`, `DB.storageSlots`, `DB.lots`, `colLetter()` (Task 6), `lotLabel()`, `esc()` (all existing).
- Produces: `renderStorageMap()`, `openShelfModal(area, shelf)` — new globals in `index.html`.

This is the one task in this plan with a real design-quality bar — build the grid and modal functionally first, then run an explicit polish pass before committing, per the `impeccable` skill's own rule ("polish is the last step, not the first").

- [ ] **Step 1: Reuse the `op_batch`-style page permission, add the tab**

Rather than inventing a new server-side permission key, put the Storage map inside Operations under the existing page structure the same way "Batch maker" works today — add a new section tab. In `mvp/static/index.html`, in `<div class="section-tabs" id="secTabs">`, add a fifth tab after "Batch maker":
```html
<button data-s="storage"><span class="material-symbols-rounded">shelves</span>Storage</button>
```
Add a new `<section class="view" id="v-storage" style="display:none">` after the closing `</section>` of `v-batch`:
```html
<section class="view" id="v-storage" style="display:none">
  <div class="bar">
    <select id="stg_area"></select>
    <span class="small muted" id="stg_note"></span>
  </div>
  <div id="stg_grid"></div>
</section>
```
In `server.py`'s `ALL_PAGES`, add `"op_storage"` next to `"op_batch"`. In `index.html`'s `TABMAP` (`const TABMAP={floor:"op_floor",sched:"op_schedule",order:"op_order",batch:"op_batch"};`), add `storage:"op_storage"`. In `admin.html`'s `PAGES` array, add `["op_storage","Storage","Operations"],` next to the `op_batch` entry so it can be granted to roles. Any role that should see it (at minimum Administrator, which self-heals to hold every `ALL_PAGES` entry per `server.py`'s `load_db()`) needs `op_storage` in its `perms`.

- [ ] **Step 2: Grid renderer**

In `mvp/static/index.html`'s `<script>` block, add:

```js
function renderStorageMap(){
  const sel=document.getElementById("stg_area");
  const areas=DB.storageAreas||[];
  if(!areas.length){
    document.getElementById("stg_grid").innerHTML='<div class="empty"><span class="material-symbols-rounded">shelves</span><h3>No storage areas yet</h3><p>Add one in Admin &rarr; Storage areas, with a shelf count and column count.</p></div>';
    sel.innerHTML=""; document.getElementById("stg_note").textContent=""; return;
  }
  const cur=sel.value && areas.some(a=>a.name===sel.value) ? sel.value : areas[0].name;
  sel.innerHTML=areas.map(a=>'<option'+(a.name===cur?" selected":"")+'>'+esc(a.name)+'</option>').join("");
  paintStorageGrid(cur);
}
function paintStorageGrid(areaName){
  const area=(DB.storageAreas||[]).find(a=>a.name===areaName);
  const grid=document.getElementById("stg_grid");
  if(!area){ grid.innerHTML=""; return; }
  const slots=(DB.storageSlots||[]).filter(s=>s.area===areaName);
  const byShelf={};
  slots.forEach(s=>{ (byShelf[s.shelf]=byShelf[s.shelf]||[]).push(s); });
  const occCount=slots.filter(s=>s.lotId).length;
  document.getElementById("stg_note").textContent=occCount+" of "+(area.shelfCount*area.colCount)+" slots occupied";
  let html='<div class="stg-grid" style="grid-template-columns:64px repeat('+area.colCount+',1fr)">';
  html+='<div class="stg-corner"></div>';
  for(let c=0;c<area.colCount;c++) html+='<div class="stg-colhead">'+colLetter(c)+'</div>';
  for(let sh=1;sh<=area.shelfCount;sh++){
    html+='<button type="button" class="stg-shelfhead" onclick="openShelfModal(\''+esc(areaName)+'\','+sh+')">'+sh+'</button>';
    for(let c=0;c<area.colCount;c++){
      const col=colLetter(c);
      const slot=(byShelf[sh]||[]).find(s=>s.col===col);
      const occ=slot&&slot.lotId;
      const lot=occ?(DB.lots||[]).find(l=>l.id===slot.lotId):null;
      html+='<button type="button" class="stg-cell'+(occ?" occ":"")+'" title="'+(lot?esc(lot.quality||"")+" - "+esc(slot.lotId):"empty")+'" onclick="openShelfModal(\''+esc(areaName)+'\','+sh+')">'
        +(occ?'<span class="stg-tag">'+esc(slot.lotId)+'</span>':'')+'</button>';
    }
  }
  html+='</div>';
  grid.innerHTML=html;
}
document.addEventListener("change", e=>{ if(e.target && e.target.id==="stg_area") paintStorageGrid(e.target.value); });
```

- [ ] **Step 3: Shelf modal — inline slot editing per column**

Add directly below `paintStorageGrid`:

```js
function openShelfModal(areaName, shelf){
  const area=(DB.storageAreas||[]).find(a=>a.name===areaName); if(!area) return;
  const ex=document.getElementById("shelfOverlay"); if(ex) ex.remove();
  const o=document.createElement("div"); o.id="shelfOverlay"; o.className="modal-bg on";
  const cols=[]; for(let c=0;c<area.colCount;c++) cols.push(colLetter(c));
  o.innerHTML='<div class="modal" style="width:560px;max-width:94vw">'
    +'<div class="m-h"><h3>'+esc(areaName)+' &middot; Shelf '+shelf+'</h3><button class="x" onclick="this.closest(\'.modal-bg\').remove()">&times;</button></div>'
    +'<div class="m-b"><div class="shelf-rows" id="shelfRows">'
    +cols.map(col=>shelfRowHTML(areaName,shelf,col)).join("")
    +'</div></div>'
    +'<div class="m-f"><button class="btn ghost" onclick="this.closest(\'.modal-bg\').remove()">Close</button></div></div>';
  document.body.appendChild(o);
  cols.forEach(col=>wireShelfRow(areaName,shelf,col));
}
function shelfRowHTML(areaName,shelf,col){
  const slot=(DB.storageSlots||[]).find(s=>s.area===areaName && +s.shelf===+shelf && s.col===col);
  const lot=slot&&slot.lotId?(DB.lots||[]).find(l=>l.id===slot.lotId):null;
  return '<div class="shelf-row" data-col="'+col+'">'
    +'<span class="shelf-col-badge">'+col+'</span>'
    +lotPickerHTML(slot?slot.lotId:"", "shelf-lot")
    +'<button type="button" class="btn ghost sm shelf-save">Save</button>'
    +(slot&&slot.lotId?'<button type="button" class="btn danger sm shelf-clear">Clear</button>':'')
    +'</div>';
}
async function wireShelfRow(areaName,shelf,col){
  const row=document.querySelector('.shelf-row[data-col="'+col+'"]'); if(!row) return;
  const picker=row.querySelector(".shelf-lot");
  wireLotPicker(picker, {});
  row.querySelector(".shelf-save").onclick=async ()=>{
    const lotId=lotPickVal(picker);
    const existing=(DB.storageSlots||[]).find(s=>s.area===areaName && +s.shelf===+shelf && s.col===col);
    if(!lotId){ toast("Pick a lot first, or use Clear to empty this slot"); return; }
    const dup=(DB.storageSlots||[]).find(s=>s.lotId===lotId && (!existing || s.id!==existing.id));
    if(dup){ toast("That lot is already stored at "+dup.area+" shelf "+dup.shelf+" column "+dup.col); return; }
    const row2=Object.assign({}, existing||{}, {area:areaName, shelf:+shelf, col:col, lotId:lotId});
    const res=await API.save("storageSlots", row2);
    if(res && res.error){ toast(res.error); return; }
    await API.db(); toast("Saved"); document.getElementById("shelfOverlay").remove(); openShelfModal(areaName,shelf); paintStorageGrid(areaName);
  };
  const clearBtn=row.querySelector(".shelf-clear");
  if(clearBtn) clearBtn.onclick=async ()=>{
    const existing=(DB.storageSlots||[]).find(s=>s.area===areaName && +s.shelf===+shelf && s.col===col);
    if(existing) await API.del("storageSlots", existing.id);
    await API.db(); toast("Cleared"); document.getElementById("shelfOverlay").remove(); openShelfModal(areaName,shelf); paintStorageGrid(areaName);
  };
}
```

- [ ] **Step 4: Wire into boot() and the tab switcher**

In `boot(()=>{...})` (`index.html`), add `renderStorageMap();` alongside the other `bRefresh*`/`renderBatchList()` calls near the end of the callback, before the `draw();` line.

The existing `#secTabs` click handler already toggles `.view` visibility generically by `data-s` — no change needed there. But the grid should repaint if storage data changed while the tab was hidden; add one line inside the existing tab-click listener:
```js
document.getElementById("secTabs").addEventListener("click",e=>{
  const s=e.target.dataset.s; if(!s)return;
  document.querySelectorAll("#secTabs button").forEach(b=>b.classList.toggle("on",b.dataset.s===s));
  document.querySelectorAll(".view").forEach(v=>v.style.display=(v.id==="v-"+s)?"":"none");
  if(s==="storage") renderStorageMap();
});
```

- [ ] **Step 5: CSS for the grid, cells, and shelf modal**

Add to `mvp/static/style.css`, matching the existing `.lotpick`/`.blk`/`.chip` visual language (flat surfaces, `--r-c`/`--r-s` radii, `--accent`/`--accent-soft` for occupied state, `--line-2` borders):

```css
/* ---- storage map ---- */
.stg-grid{display:grid;gap:4px;margin-top:14px}
.stg-corner{}
.stg-colhead{text-align:center;font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:6px 0}
.stg-shelfhead{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--ink);background:var(--surface-2);border:1px solid var(--line);border-radius:var(--r-s);cursor:pointer;transition:background var(--dur)}
.stg-shelfhead:hover{background:var(--accent-soft);color:var(--accent)}
.stg-cell{aspect-ratio:1;border:1px solid var(--line);border-radius:var(--r-s);background:var(--surface);cursor:pointer;display:flex;align-items:center;justify-content:center;padding:2px;transition:border-color var(--dur),background var(--dur)}
.stg-cell:hover{border-color:var(--accent)}
.stg-cell.occ{background:var(--accent-soft);border-color:var(--accent)}
.stg-tag{font-family:var(--mono);font-size:9px;color:var(--accent);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.shelf-rows{display:flex;flex-direction:column;gap:8px}
.shelf-row{display:flex;align-items:center;gap:8px}
.shelf-col-badge{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--muted);width:22px;text-align:center;flex-shrink:0}
.shelf-row .lotpick{flex:1}
```

- [ ] **Step 6: Verify index.html and style.css**

```bash
python3 -c "
import re
html = open('mvp/static/index.html', encoding='utf-8').read()
m = re.search(r'<script>(.*)</script>', html, re.S)
open('/tmp/index_t7.js','w',encoding='utf-8').write(m.group(1))
"
node -e "new Function(require('fs').readFileSync('/tmp/index_t7.js','utf8')); console.log('index OK')"
python3 -c "import ast; ast.parse(open('mvp/server.py').read()); print('server.py OK')"
```

- [ ] **Step 7: Manual smoke test — full flow**

```bash
cd mvp && python3 server.py 8097 &
sleep 1.5
curl -s -c /tmp/c3.txt -X POST http://localhost:8097/api -H "Content-Type: application/json" -d '{"op":"login","username":"ADMIN","password":"sonkeiwachikara"}' >/dev/null
curl -s -b /tmp/c3.txt -X POST http://localhost:8097/api -H "Content-Type: application/json" -d '{"op":"upsert","table":"storageAreas","row":{"name":"SMOKE AREA","shelfCount":3,"colCount":4}}'
curl -s -b /tmp/c3.txt http://localhost:8097/api/db | python3 -c "import json,sys; d=json.load(sys.stdin); print([a for a in d['storageAreas'] if a['name']=='SMOKE AREA'])"
# clean up: delete the SMOKE AREA row using its id from the response above
kill %1
```
Then open `index.html` in a real browser against a running server, click the Storage tab, confirm the grid renders for at least one real area, click a shelf number, confirm the modal opens with one row per column, assign a lot to a slot via the row's picker, Save, confirm the cell fills in on the grid behind the modal after closing.

- [ ] **Step 8: Design + copy polish pass**

Once the grid and modal are functionally correct (Step 7 confirmed), invoke the `impeccable` skill on this specific view (`mvp/static/index.html`'s `#v-storage` section, `paintStorageGrid`/`openShelfModal`, and the new CSS in `style.css`) for a structured design critique — hierarchy, spacing, empty/loading states, hover/focus affordances — checked against this project's own `rel-dyeing-design-insight` skill rather than generic guidance. Separately invoke `design:ux-copy` for the actual strings used: the empty-state copy in Step 2, the shelf modal's heading and button labels in Step 3, and `stg_note`'s "N of M slots occupied" phrasing — tighten anything that reads awkward or inconsistent with the rest of the app's voice (compare against existing copy like the Batch Maker's "add lot to build the batch" empty state). Apply both sets of findings as follow-up edits to the same files before committing. Do not skip this step — it's the reason this task exists as a separate task from Task 6's data model.

- [ ] **Step 9: Commit**

```bash
git add mvp/static/index.html mvp/static/style.css mvp/server.py mvp/static/admin.html
git commit -m "feat: visual Storage tab — grid of shelves x columns, shelf modal for lot placement"
```

---

## Final check across all seven tasks

- [ ] Run every Node verification script from Tasks 1, 2, 4, 5 one more time in sequence, confirming all print their final `ALL OK` / `OK` line.
- [ ] Start the server once, log in as ADMIN, and click through: Admin -> every master table listed in `BULK_ADD_TABLES` (confirm the Bulk add button appears and works), Admin -> every table (confirm Export downloads a real `.xlsx`), Admin -> Machines -> edit one, set shade family preferences, save, confirm it round-trips. Admin -> Qualities -> edit one, set loading/unloading time, save. Operations -> Storage tab -> confirm the grid renders and a shelf modal opens.
- [ ] Update `PROJECT_HANDOFF.md` with a new `## Update — <date>` section summarizing all seven changes, following the existing changelog format in that file.
- [ ] Confirm `git status --short` is clean and `git log --oneline -10` shows all seven feature commits plus the perf commit.
