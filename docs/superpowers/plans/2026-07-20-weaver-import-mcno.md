# Weaver Data + Lot Import + M/C Pin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual machine (M/C No) pin to the Batch Maker, a Weaver master table, richer Lot tracking fields, a bulk .xlsx importer for the mill's real "LOT INF" stock sheet, and a bulk quick-add tool for Qualities — so all 475 real lots (118 distinct qualities) can be brought into the ERP in one pass.

**Architecture:** This is a zero-build vanilla JS + Python-stdlib app (no bundler, no test runner beyond ad-hoc Node/jsdom scripts and Playwright e2e). All new UI lives in the two existing hand-rolled pages (`static/index.html` = Operations, `static/admin.html` = Admin) plus shared logic in `static/app.js`. The server (`server.py`) is schema-agnostic — any JSON row can be `upsert`ed to any table; the only server change needed is registering the new `weavers` table's id prefix and page key. Excel parsing runs client-side via a vendored SheetJS build (already fetched into `static/vendor/xlsx.full.min.js` — no CDN dependency, matches the LAN-only deployment).

**Tech Stack:** Vanilla JS (ES6, no modules), Python 3 stdlib HTTP server, SheetJS (vendored `xlsx.full.min.js`) for `.xlsx` parsing, Node.js (already on the dev machine) for verification scripts — never a browser test runner, this project doesn't have one wired up.

**Reference data:** The real file is `LOT INF.xlsx`, sheet `VREPORT`, 477 rows (1 header + 475 lots + 1 "GRAND TOTAL" row). Confirmed facts from inspecting it directly (see analysis commands in Task 5):
- Column A has no real header text (blank/space) but holds the external lot number, e.g. `28185OO`, `9302` — 475 unique values.
- `INW DATE` is an Excel serial date (e.g. `45747` → `2025-03-31`).
- `PTY CH` is a challan number string, e.g. `"22338"`.
- `QUALITY` has **118 distinct real fabric names** (`BRITANNIA`, `MILAN 60 INICH`, `CRYSTAL LINE 60 INCH`, …) — none match the current demo seed data (`Cotton Poplin`). All must be created.
- `PARTY GROUP` is always the single value `"RAVI EXPORTS LTD.,"` (trailing comma+space) — the sister weaving company, acting as the Customer whose greige fabric this is.
- `INW PC` / `INW MTS.` and `BAL PC` / `BAL MTS.` are **identical on every row** in this snapshot (nothing dispatched yet) — `BAL` is what should become the lot's takas.
- `DSP PCS` / `DSP. MTS.` are `0` on every row.
- `WEAVER` has 3 distinct values: `"R.E.L.(W)"`, `"R.E.L. (M)"`, and blank.
- `MASTER` is the constant `"PRINT"` on every row — a process/category tag, not a person, so it's a plain text field on the lot, **not** a master-data table.
- `OLD STK MT` / `OLD STK PC` and `PROD MTS` / `PEND PROD` are mostly `0` or blank — kept as informational fields only, not used by the scheduler.
- Implied average taka length (`BAL MTS. / BAL PC`) ranges 45–291 m, mean 94.6 m — consistent with the existing "usually 80–120 m" taka guidance already in the Lot master UI.

## Global Constraints
- Zero external runtime dependencies on the server (`server.py` stays stdlib-only).
- No CDN calls at runtime — the factory LAN may not have internet. `xlsx.full.min.js` is vendored at `mvp/static/vendor/xlsx.full.min.js` (already fetched via npm in this session, confirmed to load and report `XLSX.version === "0.18.5"`).
- Follow existing code conventions exactly: schema-driven CRUD via `SCHEMAS` in `admin.html`, system-generated sequential ids (`B-0001`, `LOT-0001`, …) via `server.py`'s `_next_seq_id`, "takas cannot be cut" philosophy for lot quantities, minimal/no framework — plain string-built HTML like the rest of the file.
- No git repo is present in this project (confirmed: `git rev-parse` fails). Skip the "commit" steps from the standard plan template — this project's change-log convention is appending to `PROJECT_HANDOFF.md` instead (final task).
- This project has no unit test runner. "Verify" steps use Node one-liners (`node -e "..."`) evaluating `app.js` directly, exactly as done for the prior `splitBatchRows` feature — follow that precedent, not a pytest/jest template.

---

### Task 1: Weaver table server plumbing

**Files:**
- Modify: `mvp/server.py:27-31` (`ALL_PAGES`), `mvp/server.py:35` (`_next_seq_id` prefix map)

**Interfaces:**
- Produces: page key `"weavers"` usable in role `perms`; id prefix `WV` so new weaver rows get ids `WV-0001`, `WV-0002`, …

- [ ] **Step 1: Add the page key and id prefix**

In `mvp/server.py`, change:

```python
ALL_PAGES = ["op_floor","op_schedule","op_order","op_batch",
             "dashboard","machines","qualities","shadeRecipes","qualityRecipes",
             "batches","lots",
             "customers","orders","storageAreas","suppliers","operators","qcMetrics",
             "users","roles","plan","settings","urgent_flag"]
```
to:
```python
ALL_PAGES = ["op_floor","op_schedule","op_order","op_batch",
             "dashboard","machines","qualities","shadeRecipes","qualityRecipes",
             "batches","lots","weavers",
             "customers","orders","storageAreas","suppliers","operators","qcMetrics",
             "users","roles","plan","settings","urgent_flag"]
```

And change:
```python
    prefix = {"lots":"LOT","batches":"B","orders":"SO"}.get(table, table[:2].upper())
```
to:
```python
    prefix = {"lots":"LOT","batches":"B","orders":"SO","weavers":"WV"}.get(table, table[:2].upper())
```

- [ ] **Step 2: Verify**

Run: `python3 -c "import ast; ast.parse(open('mvp/server.py').read())"` — expect no output (syntax OK).

Start the server on a scratch port and confirm `weavers` round-trips through `upsert`:

```bash
cd mvp && python3 server.py 8199 & sleep 1
curl -s -c /tmp/c.txt -X POST http://localhost:8199/api -H 'Content-Type: application/json' \
  -d '{"op":"login","username":"ADMIN","password":"<see mvp/README.md>"}'
curl -s -b /tmp/c.txt -X POST http://localhost:8199/api -H 'Content-Type: application/json' \
  -d '{"op":"upsert","table":"weavers","row":{"name":"Test Weaver"}}'
# Expect: {"row":{"id":"WV-0001","name":"Test Weaver"}} (id auto-generated)
kill %1
```

(Use the sandbox-writable path for the cookie jar, e.g. `/sessions/.../mnt/outputs/c.txt`, not `/tmp`, if `/tmp` is not writable in this environment — same issue hit earlier in this session.)

---

### Task 2: Weaver master admin schema + navigation

**Files:**
- Modify: `mvp/static/admin.html` — `ic()` (~line 47), `SCHEMAS` (~line 60), `PAGES` (~line 233), `NAV` (~line 242)

**Interfaces:**
- Produces: `SCHEMAS.weavers` (fields: `name`, `contact`, `phone`, `notes`), selectable everywhere a weaver needs to be picked (Task 3 reuses `DB.weavers`).

- [ ] **Step 1: Register the icon**

In `ic()`'s `M` map, add: `weavers:"factory",` (Material Symbols `factory` — distinct from `machines`' `precision_manufacturing`).

- [ ] **Step 2: Add the schema**

Insert a new entry in `SCHEMAS`, after `lots:{...}` and before `operators:{...}`:

```js
  weavers:{label:"Weavers",single:"weaver",
    cols:[["name","Name"],["contact","Contact person"],["phone","Phone"],["lotCount","Lots"]],
    search:["name","contact","phone"],
    fields:[
      {k:"name",l:"Weaver name",sec:"Weaver",req:true,help:"Matches the WEAVER column when importing lots, e.g. R.E.L.(W)"},
      {k:"contact",l:"Contact person",sec:"Weaver"},
      {k:"phone",l:"Phone no.",sec:"Weaver"},
      {k:"notes",l:"Notes",sec:"Notes",t:"textarea"}]},
```

- [ ] **Step 3: Add the `lotCount` derived column**

In `cellVal()`, add a branch (near the other derived columns like `takaCount`):

```js
  if(k==="lotCount") return '<span class="tnum">'+((DB.lots||[]).filter(l=>l.weaver===r.name).length)+'</span>';
```

- [ ] **Step 4: Wire into PAGES and NAV**

In `PAGES`, add `["weavers","Weavers","Admin"],` next to the `lots` entry:
```js
  ["batches","Batch maker","Admin"],["lots","Lot master","Admin"],["weavers","Weavers","Admin"],
```

In `NAV`, add it to the "Production" group next to Lot master:
```js
  {grp:"Production", items:[["batches","Batch maker"],["lots","Lot master"],["weavers","Weavers"]]},
```

- [ ] **Step 5: Verify**

`node -e "new Function(require('fs').readFileSync('mvp/static/admin.html','utf8').match(/<script>([\s\S]*?)<\/script>\s*<\/body>/)[1])"` — expect no throw (syntax OK). Then start the server, log in as ADMIN in a real browser (or note for manual check), open Admin → Weavers, add one row, confirm it lists and the id is `WV-0001`.

---

### Task 3: Extend Lot schema with weaver + production-tracking fields

**Files:**
- Modify: `mvp/static/admin.html` — `SCHEMAS.lots` (~line 181), `fieldInput()` (~line 496, add `wsel` option type)

**Interfaces:**
- Consumes: `DB.weavers` (Task 2).
- Produces: new lot fields `srcLotNo`, `weaver`, `master`, `inwardPcs`, `inwardMeters`, `dispatchedPcs`, `dispatchedMeters`, `oldStockPcs`, `oldStockMeters`, `prodMeters`, `pendingProd` — all consumed by Task 5's importer and, for `weaver`/`master`, editable by hand too.

- [ ] **Step 1: Add the `wsel` option type**

In `fieldInput()`, alongside the existing `opts` assignments:
```js
  if(f.t==="csel") opts=DB.customers.map(x=>x.name);
```
add:
```js
  if(f.t==="wsel") opts=[""].concat((DB.weavers||[]).map(x=>x.name));
```

- [ ] **Step 2: Extend `SCHEMAS.lots`**

Replace the `lots` entry with (new fields marked `// NEW`):

```js
  lots:{label:"Lot master",single:"lot",
    cols:[["id","Lot No."],["srcLotNo","Weaver lot no."],["customer","Customer"],["quality","Quality"],["weaver","Weaver"],["takaCount","Pcs"],["lotMeters","Meters"],["inDate","In date"],["location","Location"],["allocation","Allocated to"]],
    search:["id","srcLotNo","customer","quality","weaver","location","status","challanNo"],
    rowClass:r=>lotAllocation(r.id).blocked?"blocked":"",
    fields:[
      {k:"id",l:"Lot No.",sec:"Lot",t:"readonly",help:"Generated by the system — cannot be edited"},
      {k:"srcLotNo",l:"Weaver lot no.",sec:"Lot",help:"The weaver's own lot/roll number, for matching the physical fabric"},   // NEW
      {k:"customer",l:"Customer name",sec:"Lot",t:"csel",help:"Whose fabric this lot belongs to"},
      {k:"quality",l:"Quality",sec:"Lot",t:"qsel"},
      {k:"weaver",l:"Weaver",sec:"Lot",t:"wsel",help:"Which weaving unit produced this fabric"},   // NEW
      {k:"master",l:"Master / process tag",sec:"Lot",help:"e.g. PRINT — free text, matches the mill's MASTER column"},   // NEW
      {k:"challanNo",l:"Inward challan no.",sec:"Lot"},
      {k:"empireRef",l:"EMPIRE reference",sec:"Lot",help:"Reference from EMPIRE (excise software) when this lot is imported"},
      {k:"inDate",l:"In date",sec:"Lot",t:"date"},
      {k:"inTime",l:"In time",sec:"Lot",t:"time",help:"When the lot physically came in"},
      {k:"location",l:"Storage location",sec:"Lot",help:"Where this fabric physically sits (area / shelf / row / column)"},
      {k:"status",l:"Status",sec:"Lot",t:"select",o:["in-stock","allocated","consumed"]},
      {k:"totalMeters",l:"Lot total",sec:"Takas (up to 30) - usually 80-120 m each",t:"lotTotal",help:"Worked out from the taka lengths - cannot be typed"},
      {k:"takas",l:"Taka lengths in meters",sec:"Takas (up to 30) - usually 80-120 m each",t:"takas",help:"Pieces and total meters are worked out from these lengths"},
      {k:"inwardPcs",l:"Inward pcs",sec:"Mill tracking (informational)",t:"number",min:0,help:"As received from the weaver — historical, not used by the scheduler"},   // NEW
      {k:"inwardMeters",l:"Inward meters",sec:"Mill tracking (informational)",t:"number",min:0},   // NEW
      {k:"dispatchedPcs",l:"Dispatched pcs",sec:"Mill tracking (informational)",t:"number",min:0},   // NEW
      {k:"dispatchedMeters",l:"Dispatched meters",sec:"Mill tracking (informational)",t:"number",min:0},   // NEW
      {k:"oldStockPcs",l:"Old stock pcs",sec:"Mill tracking (informational)",t:"number",min:0},   // NEW
      {k:"oldStockMeters",l:"Old stock meters",sec:"Mill tracking (informational)",t:"number",min:0},   // NEW
      {k:"prodMeters",l:"Production meters",sec:"Mill tracking (informational)",t:"number",min:0},   // NEW
      {k:"pendingProd",l:"Pending production",sec:"Mill tracking (informational)",t:"number",min:0},   // NEW
      {k:"notes",l:"Notes",sec:"Notes",t:"textarea"}]},
```

Note: these `inward*`/`dispatched*`/`oldStock*`/`prod*`/`pending*` fields are plain numbers, so they go through the generic `fieldInput()` path already — no new field-type code needed for them, only for `wsel` (Step 1).

- [ ] **Step 3: Verify**

`node -e "new Function(require('fs').readFileSync('mvp/static/admin.html','utf8').match(/<script>([\s\S]*?)<\/script>\s*<\/body>/)[1])"` — expect no throw. Manually: Admin → Lot master → Add lot, confirm the new "Mill tracking" section renders and a Weaver dropdown appears populated from Task 2's data.

---

### Task 4: Shared taka-synthesis helper (`app.js`)

**Files:**
- Modify: `mvp/static/app.js` — add near `pickTakas`/`splitBatchRows` (~line 100)

**Interfaces:**
- Produces: `synthTakas(totalMeters, pieceCount)` → `number[]` of length `pieceCount` summing to `Math.round(totalMeters)` (to the nearest 0.5 m, matching the existing manual taka-entry step of `0.5`).
- Consumed by: Task 5's importer.

This exists because the source sheet has no per-piece lengths — only `BAL PC` (piece count) and `BAL MTS.` (total meters). The user confirmed: synthesize `BAL PC` takas of the average length (`BAL MTS. / BAL PC`), adjusting so the sum matches exactly (nothing gets silently lost or invented).

- [ ] **Step 1: Add the function**

```js
/* ---------- synthesize taka lengths when only piece-count + total meters are known ---------- */
/* Used by the lot importer: the source sheet has BAL PC / BAL MTS but no per-piece lengths.
   Every piece gets the average length (rounded to the nearest 0.5 m, matching manual taka
   entry); the last piece absorbs the rounding remainder so the sum is exact. */
function synthTakas(totalMeters, pieceCount){
  const n=Math.max(1,Math.round(pieceCount)||1);
  const avg=Math.round((totalMeters/n)*2)/2;              // nearest 0.5 m
  const out=Array(n-1).fill(avg);
  const used=avg*(n-1);
  const last=Math.round((totalMeters-used)*2)/2;
  out.push(Math.max(0.5,last));                            // never a zero/negative last piece
  return out;
}
```

- [ ] **Step 2: Verify with real numbers from the sheet**

```bash
cd mvp/static && node -e "
global.DB=null; const fs=require('fs'); eval(fs.readFileSync('app.js','utf8'));
[[101.5,1],[1246,10],[488.75,6],[514,6],[2192,22],[87,1]].forEach(([m,p])=>{
  const t=synthTakas(m,p);
  const sum=t.reduce((a,b)=>a+b,0);
  console.log('total='+m,'pieces='+p,'->',t,'sum='+sum,'match='+(Math.abs(sum-m)<0.01));
});
"
```
Expected: every `match=true`, and `t.length === p` for every case (spot-check the console output — this is a Node script, not an assertion harness, so read the printed `match=` values).

---

### Task 5: xlsx import for Lot master

**Files:**
- Modify: `mvp/static/admin.html` — vendor script include (`<head>`/before `app.js`), `render()` toolbar (~line 330, only when `CUR==="lots"`), new functions `openLotImport()`, `parseLotWorkbook()`, `commitLotImport()`.
- Uses: `mvp/static/vendor/xlsx.full.min.js` (already vendored).

**Interfaces:**
- Consumes: `synthTakas` (Task 4), `SCHEMAS.lots`/`SCHEMAS.weavers`/`SCHEMAS.customers`/`SCHEMAS.qualities` (Tasks 2–3), `API.save` (`app.js`).
- Produces: an "Import from Excel" button that only appears on the Lot master page, opening a modal with file picker → mapped preview/report → commit.

**Column mapping (confirmed against the real file, header row 1 of sheet `VREPORT`):**

| Sheet column | Lot field | Notes |
|---|---|---|
| *(col A, blank header)* | `srcLotNo` | external/weaver lot no. |
| `INW DATE` | `inDate` | Excel serial → `YYYY-MM-DD` |
| `PTY CH` | `challanNo` | |
| `QUALITY` | `quality` | match-or-create by exact trimmed name |
| `PARTY GROUP` | `customer` | match-or-create by trimmed name (strips trailing `,`) |
| `INW PC` / `INW MTS.` | `inwardPcs` / `inwardMeters` | informational |
| `BAL PC` / `BAL MTS.` | `takas` (synthesized) | drives `pcs`/`meters` — this is the actual stock |
| `DSP PCS` / `DSP. MTS.` | `dispatchedPcs` / `dispatchedMeters` | informational |
| `WEAVER` | `weaver` | match-or-create by trimmed name; blank → blank |
| `MASTER` | `master` | plain text, stored as-is |
| `OLD STK MT` / `OLD STK PC` | `oldStockMeters` / `oldStockPcs` | informational |
| `PROD MTS` / `PEND PROD` | `prodMeters` / `pendingProd` | informational |
| *(fixed)* | `status` | `"in-stock"` |

Rows where the balance quantity is `0` are skipped (nothing to stock). A row whose first cell is `"GRAND TOTAL"` (or any summary row with no `QUALITY`) is skipped.

- [ ] **Step 1: Vendor script include**

In `mvp/static/admin.html`, right before `<script src="app.js"></script>`:
```html
<script src="vendor/xlsx.full.min.js"></script>
```

- [ ] **Step 2: Toolbar button (lots page only)**

In `render()`, the toolbar line currently reads:
```js
    +'<div class="toolbar"><div class="search">...</div>'
    +'<div class="spacer"></div><button class="btn" onclick="openModal(CUR,null)">+ Add '+sc.single+'</button></div>'
```
Change the second line to conditionally add an import button when `CUR==="lots"`:
```js
    +'<div class="spacer"></div>'
    +(CUR==="lots" ? '<button class="btn ghost" onclick="openLotImport()"><span class="material-symbols-rounded">upload_file</span>Import from Excel</button>' : '')
    +'<button class="btn" onclick="openModal(CUR,null)">+ Add '+sc.single+'</button></div>'
```

- [ ] **Step 3: Import modal shell + file handling**

Add near the other modal-adjacent functions (after `closeModal()`):

```js
function openLotImport(){
  const ex=document.getElementById("importOverlay"); if(ex) ex.remove();
  const o=document.createElement("div"); o.id="importOverlay"; o.className="modal-bg on";
  o.innerHTML='<div class="modal" style="width:720px;max-width:94vw">'
    +'<div class="m-h"><h3>Import lots from Excel</h3><button class="x" onclick="this.closest(\'.modal-bg\').remove()">&times;</button></div>'
    +'<div class="m-b" id="importBody">'
    +'<p class="small muted">Pick the mill\'s lot stock sheet (.xlsx). Columns are matched by header name — '
    +'LOT NO. / INW DATE / PTY CH / QUALITY / PARTY GROUP / INW PC / INW MTS. / BAL PC / BAL MTS. / DSP PCS / DSP. MTS. / WEAVER / MASTER / OLD STK MT / OLD STK PC / PROD MTS / PEND PROD.</p>'
    +'<input type="file" id="importFile" accept=".xlsx,.xls">'
    +'<div id="importReport" style="margin-top:14px"></div></div>'
    +'<div class="m-f"><button class="btn ghost" onclick="this.closest(\'.modal-bg\').remove()">Cancel</button>'
    +'<button class="btn" id="importCommitBtn" style="display:none" onclick="commitLotImport()">Import</button></div></div>';
  document.body.appendChild(o);
  document.getElementById("importFile").addEventListener("change", handleLotImportFile);
}
function handleLotImportFile(e){
  const file=e.target.files[0]; if(!file) return;
  const reader=new FileReader();
  reader.onload=()=>{
    try{
      const wb=XLSX.read(reader.result, {type:"array", cellDates:false});
      const sheet=wb.Sheets[wb.SheetNames[0]];
      const rows=XLSX.utils.sheet_to_json(sheet, {header:1, raw:true, defval:""});
      window._importPlan=parseLotWorkbook(rows);
      renderImportReport(window._importPlan);
    }catch(err){
      document.getElementById("importReport").innerHTML='<div class="flag">Could not read this file: '+esc(err.message)+'</div>';
    }
  };
  reader.readAsArrayBuffer(file);
}
```

- [ ] **Step 4: The parser (pure function — easiest to unit-test)**

```js
/* ---------- lot workbook parser: header-name matched, tolerant of column order ---------- */
function excelSerialToISO(n){
  if(typeof n!=="number") return "";
  const d=new Date(Math.round((n-25569)*86400*1000));
  return d.toISOString().slice(0,10);
}
function parseLotWorkbook(rows){
  if(!rows.length) return {rows:[],newQualities:[],newCustomers:[],newWeavers:[],skipped:0};
  const header=rows[0].map(h=>String(h||"").trim().toUpperCase());
  const col=name=>header.indexOf(name);
  const idx={
    lot:0, inDate:col("INW DATE"), ptyCh:col("PTY CH"), qual:col("QUALITY"), party:col("PARTY GROUP"),
    inwPc:col("INW PC"), inwMt:col("INW MTS."), balPc:col("BAL PC"), balMt:col("BAL MTS."),
    dspPc:col("DSP PCS"), dspMt:col("DSP. MTS."), weaver:col("WEAVER"), master:col("MASTER"),
    oldMt:col("OLD STK MT"), oldPc:col("OLD STK PC"), prodMt:col("PROD MTS"), pend:col("PEND PROD")
  };
  const existQ=new Set((DB.qualities||[]).map(q=>q.name));
  const existC=new Set((DB.customers||[]).map(c=>c.name));
  const existW=new Set((DB.weavers||[]).map(w=>w.name));
  const newQ=new Set(), newC=new Set(), newW=new Set();
  const out=[]; let skipped=0;

  for(let r=1;r<rows.length;r++){
    const row=rows[r]; if(!row||!row.length) continue;
    const lotNo=String(row[idx.lot]||"").trim();
    const qual=String(row[idx.qual]||"").trim();
    const balPc=+row[idx.balPc]||0, balMt=+row[idx.balMt]||0;
    if(!qual || !lotNo || lotNo.toUpperCase()==="GRAND TOTAL" || balPc<=0 || balMt<=0){ skipped++; continue; }

    const party=String(row[idx.party]||"").replace(/,\s*$/,"").trim();
    const weaver=String(row[idx.weaver]||"").trim();
    const master=String(row[idx.master]||"").trim();

    if(!existQ.has(qual)) newQ.add(qual);
    if(party && !existC.has(party)) newC.add(party);
    if(weaver && !existW.has(weaver)) newW.add(weaver);

    out.push({
      srcLotNo:lotNo, quality:qual, customer:party, weaver:weaver, master:master,
      challanNo:String(row[idx.ptyCh]||"").trim(),
      inDate:excelSerialToISO(row[idx.inDate]),
      inwardPcs:+row[idx.inwPc]||0, inwardMeters:+row[idx.inwMt]||0,
      dispatchedPcs:+row[idx.dspPc]||0, dispatchedMeters:+row[idx.dspMt]||0,
      oldStockPcs:+row[idx.oldPc]||0, oldStockMeters:+row[idx.oldMt]||0,
      prodMeters:(row[idx.prodMt]===""?0:+row[idx.prodMt]||0),
      pendingProd:(row[idx.pend]===""?0:+row[idx.pend]||0),
      takas:synthTakas(balMt, balPc),
      status:"in-stock"
    });
  }
  return {rows:out, newQualities:[...newQ], newCustomers:[...newC], newWeavers:[...newW], skipped};
}
```

- [ ] **Step 5: Report + commit**

```js
function renderImportReport(plan){
  const el=document.getElementById("importReport");
  const chip=(label,list)=> list.length ? ('<div class="small" style="margin-top:8px"><b>'+list.length+'</b> new '+label+' will be created: '
    +list.slice(0,12).map(x=>'<span class="chip">'+esc(x)+'</span>').join("")+(list.length>12?' <span class="muted">+'+(list.length-12)+' more</span>':'')+'</div>') : '';
  el.innerHTML = '<div class="lot-totals"><span class="material-symbols-rounded">functions</span><b>'+plan.rows.length+'</b> lots ready to import'
    +(plan.skipped?' &middot; <span class="muted">'+plan.skipped+' row(s) skipped (blank quality, zero balance, or a total row)</span>':'')+'</div>'
    + chip("qualities", plan.newQualities) + chip("customers", plan.newCustomers) + chip("weavers", plan.newWeavers)
    + (plan.newQualities.length ? '<div class="small muted" style="margin-top:8px">New qualities are created with placeholder GSM/route — use Qualities → Quick add to fill them in before scheduling.</div>' : '');
  document.getElementById("importCommitBtn").style.display = plan.rows.length ? "" : "none";
}
async function commitLotImport(){
  const plan=window._importPlan; if(!plan||!plan.rows.length) return;
  const btn=document.getElementById("importCommitBtn"); btn.disabled=true; btn.textContent="Importing…";
  for(const name of plan.newCustomers) await API.save("customers",{name});
  for(const name of plan.newWeavers) await API.save("weavers",{name});
  for(const name of plan.newQualities) await API.save("qualities",{name, gsm:100, width:(cfg().widthDefault||56), maxBatch:300});
  await API.db();
  let ok=0;
  for(const r of plan.rows){ const res=await API.save("lots",r); if(!(res&&res.error)) ok++; }
  await API.db();
  document.getElementById("importOverlay").remove();
  renderNav(); render();
  toast("Imported "+ok+" of "+plan.rows.length+" lots");
}
```

Placeholder quality defaults (`gsm:100, maxBatch:300`) are deliberately conservative stand-ins — they are *not* real process data, and the report string says so. Task 6's quick-add tool is how the user corrects them in bulk afterward.

- [ ] **Step 6: Verify the parser against the real file (Node, no browser needed)**

```bash
cd mvp/static && node -e "
global.DB={qualities:[{name:'Cotton Poplin'}],customers:[],weavers:[]};
const fs=require('fs');
eval(fs.readFileSync('app.js','utf8'));
global.XLSX=require('/sessions/dazzling-jolly-lamport/mnt/outputs/xlsxlib/node_modules/xlsx');
const wb=XLSX.readFile('/sessions/dazzling-jolly-lamport/mnt/uploads/LOT INF.xlsx');
const rows=XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], {header:1, raw:true, defval:''});
const plan=parseLotWorkbook(rows);
console.log('lots parsed:', plan.rows.length, 'skipped:', plan.skipped);
console.log('new qualities:', plan.newQualities.length, '(expect 118)');
console.log('new customers:', plan.newCustomers, '(expect [\"RAVI EXPORTS LTD.\"])');
console.log('new weavers:', plan.newWeavers, '(expect [\"R.E.L.(W)\", \"R.E.L. (M)\"])');
const r0=plan.rows[0];
console.log('first row:', JSON.stringify(r0));
console.log('taka sum matches balMt?', Math.abs(r0.takas.reduce((a,b)=>a+b,0) - r0.inwardMeters) < 1);
"
```
Expected: `lots parsed: 475`, `skipped: 0`, `new qualities: 118`, `new customers: ["RAVI EXPORTS LTD."]` (trailing comma stripped), `new weavers: ["R.E.L.(W)", "R.E.L. (M)"]` (blank weaver excluded since blanks aren't counted as "new"), first row's synthesized takas summing to its `inwardMeters`.

- [ ] **Step 7: Manual browser check**

Start the server, log in as ADMIN, Admin → Lot master → "Import from Excel" → pick `LOT INF.xlsx` → confirm the report shows 475 lots / 118 new qualities / 1 new customer / 2 new weavers → Import → confirm Lot master now lists 475 rows and Qualities lists 118 (+ any demo ones).

---

### Task 6: Quick-add bulk tool for Qualities

**Files:**
- Modify: `mvp/static/admin.html` — toolbar in `render()` (extend Task 5's conditional), new `openQualityQuickAdd()` / `commitQualityQuickAdd()`.

**Interfaces:**
- Consumes: `API.save("qualities", …)`, `cfg()` for the default width.
- Produces: a bulk paste box (one quality per line: `name` or tab/comma-separated `name, gsm, width, maxBatch`), upserting by exact name match (updates the existing stub if the name already exists, else creates).

This is the direct follow-up to Task 5's placeholder qualities: after importing, the user pastes rows like `BRITANNIA\t120\t60\t350` (or just names, taking defaults) to flesh out real GSM/width/max-batch for all 118 in one paste instead of 118 modal round-trips. It does **not** set the 4-step route — that still needs the full Edit form per quality (route machines/times are too varied to safely bulk-guess).

- [ ] **Step 1: Toolbar button (qualities page only)**

Extend the conditional added in Task 5 Step 2:
```js
    +(CUR==="lots" ? '<button class="btn ghost" onclick="openLotImport()"><span class="material-symbols-rounded">upload_file</span>Import from Excel</button>' : '')
    +(CUR==="qualities" ? '<button class="btn ghost" onclick="openQualityQuickAdd()"><span class="material-symbols-rounded">playlist_add</span>Quick add</button>' : '')
```

- [ ] **Step 2: The modal + parser + commit**

```js
function openQualityQuickAdd(){
  const ex=document.getElementById("qqaOverlay"); if(ex) ex.remove();
  const o=document.createElement("div"); o.id="qqaOverlay"; o.className="modal-bg on";
  o.innerHTML='<div class="modal" style="width:640px;max-width:94vw">'
    +'<div class="m-h"><h3>Quick add qualities</h3><button class="x" onclick="this.closest(\'.modal-bg\').remove()">&times;</button></div>'
    +'<div class="m-b"><p class="small muted">One quality per line. Just a name is fine (defaults: GSM 100, width '+(cfg().widthDefault||56)+', max batch 300 kg) '
    +'— or tab/comma-separated <b>name, gsm, width, maxBatch</b>. An existing name updates that quality instead of duplicating it. Route (machine steps) still needs the full Edit form.</p>'
    +'<textarea id="qqaText" rows="10" placeholder="BRITANNIA\nMILAN 60 INCH, 110, 60, 300\nCRYSTAL LINE 60 INCH"></textarea>'
    +'<div id="qqaPreview" class="small muted" style="margin-top:8px"></div></div>'
    +'<div class="m-f"><button class="btn ghost" onclick="this.closest(\'.modal-bg\').remove()">Cancel</button>'
    +'<button class="btn" onclick="commitQualityQuickAdd()">Save all</button></div></div>';
  document.body.appendChild(o);
  document.getElementById("qqaText").addEventListener("input", ()=>{
    const n=parseQualityQuickAdd(document.getElementById("qqaText").value).length;
    document.getElementById("qqaPreview").textContent = n ? (n+" quality row(s) ready") : "";
  });
}
function parseQualityQuickAdd(text){
  const dW=cfg().widthDefault||56;
  return text.split("\n").map(l=>l.trim()).filter(Boolean).map(line=>{
    const parts=line.split(/\t|,/).map(s=>s.trim());
    return { name:parts[0], gsm:+parts[1]||100, width:+parts[2]||dW, maxBatch:+parts[3]||300 };
  }).filter(r=>r.name);
}
async function commitQualityQuickAdd(){
  const rows=parseQualityQuickAdd(document.getElementById("qqaText").value);
  if(!rows.length){ toast("Nothing to add"); return; }
  const byName={}; (DB.qualities||[]).forEach(q=>byName[q.name]=q);
  for(const r of rows){
    const existing=byName[r.name];
    const row=existing ? Object.assign({},existing,r) : r;
    await API.save("qualities", row);
  }
  await API.db(); document.getElementById("qqaOverlay").remove(); renderNav(); render();
  toast("Saved "+rows.length+" quality(ies)");
}
```

- [ ] **Step 3: Verify the parser (Node)**

```bash
node -e "
function parseQualityQuickAdd(text, dW){
  return text.split('\n').map(l=>l.trim()).filter(Boolean).map(line=>{
    const parts=line.split(/\t|,/).map(s=>s.trim());
    return { name:parts[0], gsm:+parts[1]||100, width:+parts[2]||dW, maxBatch:+parts[3]||300 };
  }).filter(r=>r.name);
}
const text='BRITANNIA\nMILAN 60 INCH, 110, 60, 300\n\nCRYSTAL LINE 60 INCH';
const rows=parseQualityQuickAdd(text, 56);
console.log(JSON.stringify(rows, null, 2));
console.log('count:', rows.length, '(expect 3 — blank line skipped)');
"
```
Expected: 3 rows — `BRITANNIA` with defaults `{gsm:100,width:56,maxBatch:300}`, `MILAN 60 INCH` with `{gsm:110,width:60,maxBatch:300}`, `CRYSTAL LINE 60 INCH` with defaults. This is a standalone re-implementation of the same one-liner logic for a quick Node check — after editing `admin.html`, also do the manual browser check below since `parseQualityQuickAdd` itself lives inline in that file's `<script>` block, not in `app.js`.

- [ ] **Step 4: Manual browser check**

Admin → Qualities → Quick add → paste a few of the 118 real names from Task 5's import with made-up gsm/width/maxBatch → Save all → confirm the qualities list updates those rows (not duplicated — re-open Quick add, paste the same names again with different numbers, confirm they update in place rather than creating `BRITANNIA` twice).

---

### Task 7: M/C No — manual machine pin on the Batch Maker

**Files:**
- Modify: `mvp/static/index.html` — Batch Maker form (`#v-batch`, ~line 73), `submitBatch()` (~line 317), `bSyncTotals()` and friends (add a machine-select alongside quality/shade).
- Modify: `mvp/static/app.js` — `computeSchedule()` (~line 188), `batchesForSchedule()` (~line 150).
- Modify: `mvp/static/admin.html` — `SCHEMAS.batches` (~line 164) so the pin is visible/editable from Admin too.

**Interfaces:**
- Produces: batch field `mcPin` (a machine id, e.g. `JET-2`, or empty for auto-assign).
- `computeSchedule()`'s dye-step eligibility filter changes from "any machine of the right type with enough capacity" to "if `mcPin` is set, only that machine — and only if it's the right type; otherwise fall back to auto" and reports a clear reason when a pin can't be honored (wrong type, or too small) instead of silently ignoring the user's choice.

**Design decision (locked in, not to be re-litigated per task):** the pin applies **only to the dye step** — pre-treatment/finishing stay on the shared auto-assigned pool exactly as today, because those are fungible shared machines in this mill (per the existing scheduler design) and the dye machine is the one meaningful "which machine" choice an operator makes when logging a batch. If the pinned machine's `type` doesn't match the quality's dye-step machine type at all (an operator error, e.g. picking a jigger for a jet-dye quality), the scheduler falls back to auto-assign and the batch gets a visible `pinWarning` rather than silently failing. If the pinned machine's `type` matches but its `capMax` is too small for the batch's kg, the batch is left `unplanned` with a specific reason (`"JET-1 (250 kg) is too small for this 386.7 kg batch"`) rather than silently reassigned — the operator asked for that machine, so a capacity mismatch needs their attention, not a silent override.

- [ ] **Step 1: Add the field to the Batch Maker form**

In `mvp/static/index.html`, in the `#v-batch` "Create a batch" card, add a machine select next to Shade date:

```html
          <label class="fld">Shade date<input id="b_shadeDate" type="date"></label>
          <label class="fld">M/C No <span class="small muted">(optional — pin to a specific dye machine)</span><select id="b_mc"><option value="">— auto-assign —</option></select></label>
```
(insert the new `<label>` right after the existing Shade date one, inside the same `.grid2`)

- [ ] **Step 2: Populate the machine dropdown from the selected quality**

In `bRefreshShades()` (index.html), which already runs whenever the quality changes, add a sibling function and call it from the same places `bRefreshShades()` is called (`b_qual` change handler, and inside `bAddLot`'s onchange chain where quality can get auto-locked):

```js
function bRefreshMachines(){
  const q=Q(document.getElementById("b_qual").value);
  const sel=document.getElementById("b_mc"); if(!sel) return;
  const cur=sel.value;
  const dyeType = q ? routeStep(q, +q.dyeStep||3).mc : "";
  const list = dyeType ? DB.machines.filter(m=>m.type===dyeType) : [];
  sel.innerHTML = '<option value="">— auto-assign —</option>'
    + list.map(m=>'<option value="'+esc(m.id)+'"'+(m.id===cur?" selected":"")+'>'+esc(m.id)+' ('+m.capMax+' kg)</option>').join("");
}
```

Wire it in three places (mirroring how `bRefreshShades()` is already wired):
1. `bLockQuality()` — after `bRefreshShades(); bRefreshOrders(); bRefreshLotSelects();` add `bRefreshMachines();`
2. The `b_qual.addEventListener("change", ...)` handler in `boot()` — add `bRefreshMachines();` to the same line as `bRefreshShades(); bRefreshOrders(); bRefreshLotSelects();`
3. The end of `boot()`'s init sequence — add `bRefreshMachines();` next to `bRefreshShades(); bRefreshOrders();`

- [ ] **Step 3: Include it when saving**

In `submitBatch()` (index.html), the per-group `row` object currently is:
```js
    const row={ lots:grp, lotIds:grp.map(r=>r.lotId),
      orderId:g("b_order"), quality:q, shadeNo:g("b_shade"), shadeDate:g("b_shadeDate"),
      pcs:tot.pcs, mtr:tot.mtr, weight:tot.weight,
      status:"planned", notes:g("b_notes") };
```
Add `mcPin:g("b_mc"),` to it:
```js
    const row={ lots:grp, lotIds:grp.map(r=>r.lotId),
      orderId:g("b_order"), quality:q, shadeNo:g("b_shade"), shadeDate:g("b_shadeDate"),
      mcPin:g("b_mc"),
      pcs:tot.pcs, mtr:tot.mtr, weight:tot.weight,
      status:"planned", notes:g("b_notes") };
```
Note: when a batch is split into multiple sub-batches (the oversized-batch feature from the prior session), every split sibling gets the *same* pin — if the operator pinned JET-2 for a batch that then splits into two, both halves are pinned to JET-2 and will queue on it sequentially (this is intentional — the operator picked that machine for a reason; if that's wrong for a specific split they can edit that one batch's M/C No afterward via Admin, Task 7's Step 6).

Also reset it on success, alongside the other form-reset lines:
```js
  document.getElementById("b_lotBox").innerHTML=""; bLotCount(); bSyncTotals();
  ["b_notes","b_shadeDate"].forEach(id=>document.getElementById(id).value="");
```
add `document.getElementById("b_mc").value="";` to that line.

- [ ] **Step 4: Carry the pin into `batchesForSchedule()`**

In `mvp/static/app.js`, `batchesForSchedule()` currently builds each schedulable batch object without any machine-pin info. Add `mcPin:b.mcPin||""` to the pushed object:
```js
    out.push({key:b.id, batchId:b.id, order:b.orderId||b.id, cust:b.customer||"",
      qual:b.quality, shade:b.shadeNo||"", type:routeStep(q,+q.dyeStep||3).mc,
      meters:Math.round(meters), kg:Math.round(kg),
      dyeMins:q.dyeMins, finishMins:q.finishMins,
      pri:+b.pri||2, due:+b.due||7, urgent:!!b.urgent, redye:(b.status==="redye"),
      family:sh.family, tone:sh.tone, q:q, mcPin:b.mcPin||"",
      pcs:tot.pcs, inTime:b.inTime||"", outTime:b.outTime||"",
      notes:b.notes||"", operator:b.operator||"", lotIds:(b.lots||[]).map(r=>r.lotId).filter(Boolean).concat(b.lots?[]:(b.lotIds||[]))});
```

- [ ] **Step 5: Honor the pin in `computeSchedule()`**

The current dye-step eligibility line is:
```js
      const elig=DB.machines.filter(m=> m.type===st.mc && (!st.isDye || (m.capMax||0)>=b.kg));
      if(!elig.length){ b.unplanned=true; return; }
```
Replace the whole `steps.forEach(st=>{ ... })` body's eligibility block with a pin-aware version:
```js
    steps.forEach(st=>{
      const occ=H+st.time;
      let elig=DB.machines.filter(m=> m.type===st.mc && (!st.isDye || (m.capMax||0)>=b.kg));
      if(st.isDye && b.mcPin){
        const pinned=DB.machines.find(m=>m.id===b.mcPin);
        if(!pinned || pinned.type!==st.mc){
          b.pinWarning="M/C pin "+b.mcPin+" doesn't match this quality's dye machine ("+st.mc+") — auto-assigned instead";
        } else if((pinned.capMax||0) < b.kg){
          b.unplanned=true; b.unplannedReason=b.mcPin+" ("+pinned.capMax+" kg) is too small for this "+b.kg+" kg batch"; return;
        } else {
          elig=[pinned];
        }
      }
      if(!elig.length){ b.unplanned=true; b.unplannedReason=b.unplannedReason||"No "+st.mc+" machine can take this "+(st.isDye?b.kg+" kg ":"")+"batch"; return; }
```
(the rest of the function — `elig.forEach(m=>{...})` onward — is unchanged; `elig` now naturally contains just the pinned machine when applicable, so the existing "pick the one with earliest finish" loop still works, just over a 1-element array).

- [ ] **Step 6: Surface the pin (and any warning) in the UI**

In `mvp/static/admin.html`'s `SCHEMAS.batches`, add the field so it's visible/editable from Admin too — insert after `shadeNo`:
```js
      {k:"shadeNo",l:"Shade no.",sec:"Batch"},
      {k:"mcPin",l:"M/C No (pin)",sec:"Batch",t:"select",o:["",...DB.machines.map(m=>m.id)],help:"Leave blank to auto-assign. Pins only affect the dye step."},
```
Note: `o:[...]` is evaluated once when the module loads, before `DB` exists — this differs from every other `t:"select"` field in the schema, all of which use a static `o:` array. Follow the existing dynamic-options precedent instead: `qsel`/`csel`/`wsel` are resolved live inside `fieldInput()`. Add a matching `msel` (machine-select) branch there instead of a static `o:` array:
```js
  if(f.t==="msel") opts=[""].concat((DB.machines||[]).map(x=>x.id));
```
and use `{k:"mcPin",l:"M/C No (pin)",sec:"Batch",t:"msel",help:"Leave blank to auto-assign. Pins only affect the dye step."}` in the schema instead.

Also add an `mcPin` column to `SCHEMAS.batches.cols` so it's visible in the table listing, and surface `pinWarning`/`unplannedReason` in the Gantt hover card (`showGanttHover()` in `app.js`) and the "Batch master (generated)" table in `admin.html`'s `renderPlan()` — both already render `b.mcAssigned||'<span class="flag">unplanned</span>'`-style fallbacks, so append the reason there:
```js
// in renderPlan()'s batchCard row template, change:
//   '<td>'+(b.mcAssigned||'<span class="flag">unplanned</span>')+'</td>'
// to:
   '<td>'+(b.mcAssigned||'<span class="flag" title="'+esc(b.unplannedReason||"")+'">unplanned</span>')+(b.pinWarning?' <span class="flag" title="'+esc(b.pinWarning)+'">pin ignored</span>':'')+'</td>'
```

- [ ] **Step 7: Verify with a Node scheduler test**

This mirrors the verification style already used for `splitBatchRows` — load `app.js` in Node with a minimal `DB` fixture and call `computeSchedule()` directly.

```bash
cd mvp/static && node -e "
global.DB={
  settings:{widthDefault:56,minMeters:300,buffer:1.2,loadMin:35,unloadMin:25,stentorSetupMins:90},
  machines:[
    {id:'JET-1',type:'jet',capMax:250,wash:20},
    {id:'JET-2',type:'jet',capMax:400,wash:20},
    {id:'JIG-1',type:'jigger',capMax:200,wash:15}
  ],
  qualities:[{name:'Q1',gsm:115,width:56,maxBatch:400,dyeStep:1,step1_mc:'jet',step1_time:200}],
  shadeRecipes:[{quality:'Q1',shade:'Navy',family:'Blue',tone:8}],
  batches:[
    {id:'B-1',quality:'Q1',shadeNo:'Navy',lots:[{lotId:'L1',pcs:2,mtr:1000,weight:300,takas:[500,500]}],pcs:2,mtr:1000,weight:300,mcPin:'JET-2'},
    {id:'B-2',quality:'Q1',shadeNo:'Navy',lots:[{lotId:'L2',pcs:2,mtr:1000,weight:300,takas:[500,500]}],pcs:2,mtr:1000,weight:300,mcPin:'JET-1'}
  ]
};
const fs=require('fs'); eval(fs.readFileSync('app.js','utf8'));
const S=computeSchedule();
S.batches.forEach(b=>console.log(b.key, 'mcAssigned='+b.mcAssigned, 'unplanned='+!!b.unplanned, 'reason='+(b.unplannedReason||''), 'pinWarning='+(b.pinWarning||'')));
"
```
Expected: `B-1` gets `mcAssigned=JET-2` (pin honored, fits). `B-2` is pinned to `JET-1` (250 kg cap) for a 300 kg batch → `unplanned=true`, `reason='JET-1 (250 kg) is too small for this 300 kg batch'`. Confirm both lines match before moving on.

- [ ] **Step 8: Manual browser check**

Operations → Batch maker → pick a quality, pick a specific M/C from the new dropdown, create the batch → confirm the Gantt shows it on that exact machine. Then pick a machine deliberately too small for a large batch → confirm it shows `unplanned` with the capacity-mismatch tooltip instead of silently landing elsewhere.

---

### Task 8: Fix the pre-existing `saveModal()` dead-code bug

**Files:**
- Modify: `mvp/static/admin.html` — `saveModal()` (~line 530)

**Why this is in scope:** discovered while reading `admin.html` to place Task 7's `mcPin` field. `saveModal()`'s `sc.fields.forEach(...)` callback contains a block for `f.t==="lotqty"` that is dead/corrupted — it's a verbatim copy-paste of `fieldInput()`'s HTML-returning branches (`lotqty`, `batchTotal`, `lotsel`) pasted into the wrong function. It references an undefined variable `val` and uses bare `return` statements that only exit the `.forEach` iteration (not the enclosing function) after building nothing. Concretely: **saving a batch through Admin → Batch maker → Edit (or Add) currently throws `ReferenceError: val is not defined`** the moment it reaches the `lots` field (`t:"lotqty"`), because this file has no `val` in scope there. This has been silently broken until now — the day-to-day batch creation path (`index.html`'s dedicated Batch Maker, `submitBatch()`) doesn't go through `saveModal()` at all, so nobody hit it. Task 7 adds an `mcPin` field to the same `batches` schema, so this bug would otherwise make the admin-side edit path throw before ever reaching the new field.

**Interfaces:** none — this is a same-function bugfix, no signature changes.

- [ ] **Step 1: Read the current broken block**

Confirm the exact broken text still matches (it may have shifted a few lines from earlier edits in this plan):
```js
    if(f.t==="lotqty"){
    const rows=Array.isArray(val)?val:[], ids=(DB.lots||[]).map(l=>l.id);
    if(!ids.length) return '<div class="ro-field"><span class="muted">No lots yet - create them in Lot master first</span></div>';
    return '<div class="lotq-head"><span>Lot no.</span><span>Pcs</span><span>Meters</span><span>Weight (kg)</span><span></span></div>'
      +'<div id="lotBox">'+rows.map(r=>lotQRow(r,ids)).join("")+'</div>'
      +'<div class="taka-ctl"><button type="button" class="btn ghost sm" onclick="addLotRow()"><span class="material-symbols-rounded">add</span>Add lot</button><span class="taka-count" id="lotCount"></span></div>';
  }
  if(f.t==="batchTotal") return '<div class="ro-field" id="batchTotalBox"></div>';
  if(f.t==="lotsel"){ const b=document.getElementById("lotBox"); row.lotIds = b?[...b.querySelectorAll(".lot-sel")].map(s=>s.value):[]; return; }
```

- [ ] **Step 2: Replace with correct read-back logic**

This needs to actually read the rendered `#lotBox` rows back out (the same DOM the `lotqty` branch of `fieldInput()` rendered via `lotQRow()`), matching how `lotQRows()` already does it elsewhere in this same file (used by the *other*, non-schema batch-editing helpers). Replace the whole broken block with:
```js
    if(f.t==="lotqty"){
      row.lots = lotQRows();
      row.lotIds = row.lots.map(r=>r.lotId);
      row.pcs = row.lots.reduce((a,r)=>a+r.pcs,0);
      row.mtr = row.lots.reduce((a,r)=>a+r.mtr,0);
      row.weight = Math.round(row.lots.reduce((a,r)=>a+r.weight,0)*10)/10;
      return;
    }
    if(f.t==="batchTotal") return;   // derived/display-only, nothing to read back
```
(the stray `f.t==="lotsel"` branch is dead — no schema field uses `t:"lotsel"`, only `t:"lotqty"` — delete it rather than fix it, per YAGNI; if it's ever needed the working `lotqty` pattern above is the template to copy).

- [ ] **Step 3: Verify**

`node -e "new Function(require('fs').readFileSync('mvp/static/admin.html','utf8').match(/<script>([\s\S]*?)<\/script>\s*<\/body>/)[1])"` — expect no throw.

Manual: start the server, Admin → Batch maker → Add batch → pick a quality, add a lot row with pcs/meters/kg → Save → confirm it saves without a console error and the new batch appears in the list with the right totals. Then Edit that same batch, change the M/C No (Task 7), Save again → confirm no error and the change persists.

---

## Self-Review

**Spec coverage:**
- M/C No in Batch Maker → Task 7 (form field, scheduler pin logic, Admin visibility).
- Mass-import lots from the mill's real `.xlsx` → Task 5, column mapping verified against the actual uploaded file (475 rows, 118 qualities, exact header names confirmed by direct inspection, not guessed).
- Import button inside the Lot master table → Task 5 Step 2 (conditional toolbar button on `CUR==="lots"`).
- No taka-wise data in the source, avg-taka synthesis per the user's explicit instruction → Task 4 (`synthTakas`), used by Task 5.
- Quick-add for qualities → Task 6, deliberately positioned as the companion to Task 5's placeholder-quality creation.
- Weaver database → Tasks 1–2 (server plumbing + admin schema), consumed by Task 3 (lot field) and Task 5 (import match-or-create).

**Placeholder scan:** every task has concrete, complete code (no `TBD`/"add error handling"/"similar to Task N"). The two informational-fields lists in Task 3 are literal field arrays, not summarized.

**Type/name consistency check:**
- `synthTakas(totalMeters, pieceCount)` (Task 4) is called identically in Task 5 Step 4 as `synthTakas(balMt, balPc)`.
- `parseLotWorkbook(rows)` (Task 5 Step 4) returns `{rows, newQualities, newCustomers, newWeavers, skipped}` — `renderImportReport` (Step 5) and the Step 6 Node check both destructure exactly those five keys.
- Lot field names introduced in Task 3 (`srcLotNo`, `weaver`, `master`, `inwardPcs`, `inwardMeters`, `dispatchedPcs`, `dispatchedMeters`, `oldStockPcs`, `oldStockMeters`, `prodMeters`, `pendingProd`) are the exact keys populated by Task 5's parser output — cross-checked field-by-field against the mapping table.
- `mcPin` (Task 7) is introduced once and used with that exact name in the form (`b_mc` element → `row.mcPin`), `batchesForSchedule()`, `computeSchedule()`, and the Admin schema — no `mcAssigned`-vs-`mcPin` naming drift (`mcAssigned` already existed as the scheduler's *output* field for whichever machine actually got picked; `mcPin` is the new *input* — these are intentionally different fields, not a rename).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-weaver-import-mcno.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
