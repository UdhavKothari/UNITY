/* ================= REL Dyeing ERP - shared engine (v2) ================= */
let DB = null;

const API = {
  async db(){ DB = await (await fetch("/api/db")).json(); return DB; },
  async _post(body){ const r = await fetch("/api",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}); return r.json(); },
  save(table,row){ return this._post({op:"upsert",table,row}); },
  del(table,id){ return this._post({op:"delete",table,id}); },
  batchStatus(id,to){ return this._post({op:"batchStatus",id,to}); },
  reset(){ return this._post({op:"reset"}); }
};

/* ---------- lookups ---------- */
const byName = (arr,n)=> arr.find(x=>x.name===n);
function colLetter(i){    // 0-based index -> A, B, ... Z, AA, AB, ... (spreadsheet-style)
  let n=i+1, s="";
  while(n>0){ const r=(n-1)%26; s=String.fromCharCode(65+r)+s; n=Math.floor((n-1)/26); }
  return s;
}
const Q = n => byName(DB.qualities,n);
/* ---- rebrands: qualities sharing a non-empty fabricGroup tag are the exact same physical fabric,
   just sold under different names. Each quality keeps its own GSM/route/maxBatch (no inheritance —
   simple tag, not a data hierarchy) but lots from either name can share one dye batch, and shade
   recipes/lookup are shared across the group so both names see the same shade list. ---- */
function fabricGroupNames(name){
  const q=byName(DB.qualities,name), names=new Set([name]);
  const tag=q&&q.fabricGroup;
  if(tag) (DB.qualities||[]).forEach(x=>{ if(x.fabricGroup===tag) names.add(x.name); });
  return names;
}
function sameFabric(a,b){
  if(!a || !b) return false;
  if(a===b) return true;
  const qa=byName(DB.qualities,a), qb=byName(DB.qualities,b);
  return !!(qa && qb && qa.fabricGroup && qb.fabricGroup && qa.fabricGroup===qb.fabricGroup);
}
const SH = (n,quality)=>{
  const a=DB.shadeRecipes||[];
  if(quality){
    const exact=a.find(x=>x.shade===n && x.quality===quality); if(exact) return exact;
    const grp=fabricGroupNames(quality);
    if(grp.size>1){ const g=a.find(x=>x.shade===n && grp.has(x.quality)); if(g) return g; }
  }
  return a.find(x=>x.shade===n);
};
const shadesForQuality = q => {
  const names=fabricGroupNames(q);
  return (DB.shadeRecipes||[]).filter(x=>names.has(x.quality));
};
const cfg = ()=> DB.settings;
const kgOf = (meters,gsm,widthIn)=> meters*((widthIn||cfg().widthDefault||56)*0.0254)*gsm/1000;

function shadeColor(shadeName,quality,alpha){
  if(alpha===undefined) alpha=1;
  const s=SH(shadeName,quality); if(!s) return "hsla(220,6%,70%,"+alpha+")";
  const map={Blue:212,Red:2,Yellow:44,Neutral:222,Green:140,Purple:280};
  const hue=(map[s.family]!==undefined)?map[s.family]:222;
  const sat= s.family==="Neutral" ? 6 : 62;
  const light= 86 - (s.tone||0)*5.4;
  return "hsla("+hue+","+sat+"%,"+light+"%,"+alpha+")";
}

/* ---------- batch split (multi-shade, kg + min-meters) ---------- */
function splitOrder(o){
  const q=Q(o.qual); if(!q) return [];
  const type=q.dyeType;
  const maxCap = q.maxBatch || Math.max.apply(null, DB.machines.filter(m=>m.type===type).map(m=>m.capMax||0).concat([1]));
  const minM = cfg().minMeters||300;
  const lines = o.lines || [{shade:o.shade,m:o.m}];
  const out=[];
  lines.forEach(function(ln,li){
    const totalKg=kgOf(ln.m,q.gsm,q.width);
    let n=Math.max(1,Math.ceil(totalKg/maxCap));
    while(n>1 && (ln.m/n)<minM) n--;
    for(let i=0;i<n;i++){
      const sh=SH(ln.shade,o.qual)||{family:"Neutral",tone:0};
      out.push({key:o.id+"-"+(li+1)+String.fromCharCode(65+i), order:o.id, cust:o.cust,
        qual:o.qual, shade:ln.shade, type:type, meters:Math.round(ln.m/n), kg:+(totalKg/n).toFixed(0),
        dyeMins:q.dyeMins, finishMins:q.finishMins, pri:o.pri, due:o.due,
        family:sh.family, tone:sh.tone, q:q});
    }
  });
  return out;
}

/* ---------- lot totals (derived from taka lengths; never typed) ---------- */
function lotTotals(ids){
  let pcs=0, mtr=0;
  (ids||[]).forEach(id=>{
    const l=(DB.lots||[]).find(x=>x.id===id); if(!l) return;
    const t=(l.takas||[]).map(Number).filter(n=>!isNaN(n));
    pcs += t.length ? t.length : (+l.pcs||0);
    mtr += t.length ? t.reduce((a,b)=>a+b,0) : (+l.meters||0);
  });
  return {pcs:pcs, mtr:Math.round(mtr)};
}

/* ---------- takas cannot be cut: pick whole takas to cover a target ---------- */
function pickTakas(pool, target){
  const items=[...pool].map(Number).filter(n=>!isNaN(n)).sort((a,b)=>a-b);
  const sum=a=>a.reduce((x,y)=>x+y,0);
  const all=sum(items);
  if(!items.length || all<=target)                       // lot cannot cover it: take everything left
    return {takas:items.slice().sort((a,b)=>b-a), total:Math.round(all), pcs:items.length, short:all<target};
  // fewest takas first, then the least overshoot at that count.
  // layer[n] maps an achievable sum -> the index list that makes it (keeping the one that leaves most room to grow)
  let layer=new Map([[0,[]]]);
  for(let n=1;n<=items.length;n++){
    const next=new Map();
    layer.forEach((sel,s0)=>{
      for(let i=(sel.length?sel[sel.length-1]+1:0); i<items.length; i++){
        const s2=s0+items[i], prev=next.get(s2);
        if(!prev || i<prev[prev.length-1]) next.set(s2, sel.concat(i));
      }
    });
    let best=null;
    next.forEach((sel,s2)=>{ if(s2>=target && (best===null || s2<best[0])) best=[s2,sel]; });
    if(best) return {takas:best[1].map(i=>items[i]).sort((a,b)=>b-a),
                     total:Math.round(best[0]), pcs:best[1].length, short:false};
    layer=next;
  }
  return {takas:items.slice().sort((a,b)=>b-a), total:Math.round(all), pcs:items.length, short:false};
}

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

/* ---------- oversized batch: split lot rows into N machine-sized batches ---------- */
/* A batch heavier than the quality's max batch size can never run as one machine load.
   Split at the taka level (nothing gets cut) using best-fit-decreasing bin packing: largest
   taka first, into whichever batch-in-progress leaves the least spare room without going over
   capacityKg. capacityKg is a hard cap — a batch this produces never exceeds it (the only
   exception is a single taka heavier than capacityKg on its own, which no split can fix).
   A trailing batch left under the meters floor is folded back into another that has room. */
function splitBatchRows(rows, capacityKg, minMeters){
  const totalKg=(rows||[]).reduce((a,r)=>a+(+r.weight||0),0);
  if(!capacityKg || totalKg<=capacityKg) return [rows];

  let items=[];
  rows.forEach(r=>{
    const kgPerM=r.mtr>0 ? r.weight/r.mtr : 0;
    (r.takas&&r.takas.length ? r.takas : [r.mtr]).forEach(t=>
      items.push({lotId:r.lotId, taka:+t, kg:+(t*kgPerM).toFixed(2)}));
  });
  items.sort((a,b)=>b.kg-a.kg);

  const bins=[];
  items.forEach(it=>{
    let target=null, tightest=Infinity;
    bins.forEach(b=>{
      const remain=capacityKg-b.kg;
      if(remain>=it.kg && remain<tightest){ tightest=remain; target=b; }
    });
    if(!target){ target={kg:0,m:0,items:[]}; bins.push(target); }
    target.items.push(it); target.kg+=it.kg; target.m+=it.taka;
  });

  // fold any under-the-floor trailing batch into another bin that still has room
  for(let pass=0; pass<bins.length; pass++){
    let moved=false;
    for(let i=bins.length-1;i>=0;i--){
      if(bins.length<=1) break;
      const b=bins[i]; if(b.m>=(minMeters||0)) continue;
      const host=bins.find((h,hi)=>hi!==i && capacityKg-h.kg>=b.kg);
      if(host){ host.items=host.items.concat(b.items); host.kg+=b.kg; host.m+=b.m; bins.splice(i,1); moved=true; }
    }
    if(!moved) break;
  }

  return bins.filter(b=>b.items.length).map(bin=>{
    const byLot={};
    bin.items.forEach(it=>{
      const r=byLot[it.lotId] || (byLot[it.lotId]={lotId:it.lotId,pcs:0,mtr:0,weight:0,takas:[]});
      r.pcs++; r.mtr+=it.taka; r.weight+=it.kg; r.takas.push(it.taka);
    });
    return Object.keys(byLot).map(k=>{ const r=byLot[k];
      r.mtr=Math.round(r.mtr); r.weight=Math.round(r.weight*10)/10; return r; });
  });
}

/* ---------- human labels: never show a bare id ---------- */
function orderLabel(id){
  const o=(DB.orders||[]).find(x=>x.id===id); if(!o) return id;
  const sh=(o.lines||[]).map(l=>l.shade+" "+l.m+"m").join(", ");
  return id+"  \u00b7  "+(o.cust||"")+"  \u00b7  "+(o.qual||"")+(sh?("  \u00b7  "+sh):"");
}
function lotLabel(id){
  const l=(DB.lots||[]).find(x=>x.id===id); if(!l) return id;
  const a=lotAllocation(id);
  const qty = a.used ? (a.remainingPcs+" pcs / "+a.remaining+" m left  (of "+a.totalPcs+" / "+a.total+" m)")
                     : (a.totalPcs+" pcs / "+a.total+" m");
  return id+"  \u00b7  "+(l.customer||"no customer")+"  \u00b7  "+(l.quality||"no quality")+"  \u00b7  "+qty;
}
function batchLabel(id){
  const b=(DB.batches||[]).find(x=>x.id===id); if(!b) return id;
  const t=batchTotals(b);
  return id+"  \u00b7  "+(b.quality||"")+(b.shadeNo?(" / "+b.shadeNo):"")+"  \u00b7  "+t.pcs+" pcs / "+t.mtr+" m";
}

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
      if(!map[r.lotId]) map[r.lotId]={pcs:0, mtr:0, by:[], pool:[]};
      const m=map[r.lotId];
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
function lotsAvailable(quality){
  return (DB.lots||[]).filter(l=> (!quality || l.quality===quality) && !lotAllocation(l.id).blocked );
}

/* ---------- searchable lot picker (250+ open lots — a plain <select> stops scaling fast) ---------- */
/* Renders as a text input + filtered dropdown instead of a giant <select>. The picked lot id
   lives in the root element's data-val (read it with lotPickVal()) — nothing else changes about
   how callers treat "the lot select": swap .value for lotPickVal(el), swap onchange for the
   onSelect callback passed to wireLotPicker. */
function lotPickerHTML(selId, extraCls){
  const label = selId ? lotLabel(selId) : "";
  return '<div class="lotpick'+(extraCls?(' '+extraCls):'')+'" data-val="'+esc(selId||"")+'">'
    +'<input class="lotpick-in" type="text" autocomplete="off" placeholder="Search lot no., customer, quality…" value="'+esc(label)+'">'
    +'<div class="lotpick-menu"></div></div>';
}
function lotPickVal(root){ return root ? (root.dataset.val||"") : ""; }
function lotPickerMatches(root, filterFn){
  const term=(root.querySelector(".lotpick-in").value||"").trim().toLowerCase();
  const cur=root.dataset.val;
  let ids=(DB.lots||[]).filter(l=> (!filterFn || filterFn(l) || l.id===cur)).map(l=>l.id);
  if(term) ids=ids.filter(id=> lotLabel(id).toLowerCase().indexOf(term)>=0);
  return ids.slice(0,60);                                 // type to narrow further past the cap
}
function wireLotPicker(root, opts){
  opts=opts||{};
  const inp=root.querySelector(".lotpick-in"), menu=root.querySelector(".lotpick-menu");
  let hi=-1;
  function close(){ menu.classList.remove("on"); menu.innerHTML=""; hi=-1; }
  function items(){ return [...menu.querySelectorAll(".lotpick-opt:not(.disabled)")]; }
  function setHi(i){ const list=items(); list.forEach(x=>x.classList.remove("hi"));
    hi=Math.max(0,Math.min(list.length-1,i)); if(list[hi]){ list[hi].classList.add("hi"); list[hi].scrollIntoView({block:"nearest"}); } }
  function paint(){
    const ids=lotPickerMatches(root, opts.filterFn);
    if(!ids.length){ menu.innerHTML='<div class="lotpick-empty">No matching lots</div>'; menu.classList.add("on"); hi=-1; return; }
    menu.innerHTML=ids.map(id=>{
      const a=lotAllocation(id), blocked=a.blocked && id!==root.dataset.val;
      return '<div class="lotpick-opt'+(blocked?' disabled':'')+'" data-id="'+esc(id)+'">'+esc(lotLabel(id))
        +(a.blocked?' <span class="flag">fully used</span>':a.used?' <span class="muted">part used</span>':'')+'</div>';
    }).join("");
    menu.classList.add("on"); hi=-1;
  }
  function pick(id){
    root.dataset.val=id; inp.value=lotLabel(id); close();
    if(opts.onSelect) opts.onSelect(id);
  }
  inp.addEventListener("focus", ()=>{ inp.value=""; paint(); });
  inp.addEventListener("input", paint);
  inp.addEventListener("keydown", e=>{
    if(e.key==="ArrowDown"){ e.preventDefault(); if(!menu.classList.contains("on")) paint(); else setHi(hi+1); }
    else if(e.key==="ArrowUp"){ e.preventDefault(); setHi(hi-1); }
    else if(e.key==="Enter"){ e.preventDefault(); const list=items(); if(list[hi]) pick(list[hi].dataset.id); }
    else if(e.key==="Escape"){ close(); inp.blur(); }
  });
  menu.addEventListener("mousedown", e=>{
    const o=e.target.closest(".lotpick-opt:not(.disabled)"); if(!o) return;
    e.preventDefault(); pick(o.dataset.id);               // preventDefault keeps the input focused so blur-close doesn't race the pick
  });
  inp.addEventListener("blur", ()=> setTimeout(()=>{ close(); inp.value = root.dataset.val ? lotLabel(root.dataset.val) : ""; }, 150));
}

/* ---------- batch totals (sum of the per-lot quantities) ---------- */
function batchTotals(b){
  const rows=(b&&b.lots)||[];
  if(rows.length) return {
    pcs: rows.reduce((a,r)=>a+(+r.pcs||0),0),
    mtr: Math.round(rows.reduce((a,r)=>a+(+r.mtr||0),0)),
    weight: Math.round(rows.reduce((a,r)=>a+(+r.weight||0),0)*10)/10 };
  return {pcs:+((b||{}).pcs)||0, mtr:+((b||{}).mtr)||0, weight:+((b||{}).weight)||0};
}

/* ---------- batches that drive the schedule (created in the Batch maker) ---------- */
function batchesForSchedule(){
  const out=[];
  (DB.batches||[]).forEach(b=>{
    if(b.status==="done") return;                              // a finished load has left the machine — frees it, rest pull forward
    const q=Q(b.quality); if(!q) return;                       // quality must exist to route it
    const sh=SH(b.shadeNo,b.quality)||{family:"Neutral",tone:0};
    const tot=batchTotals(b);
    const meters=tot.mtr;
    const kg=tot.weight || kgOf(meters,q.gsm,q.width);         // weighed kg wins; else derive from meters
    out.push({key:b.id, batchId:b.id, order:b.orderId||b.id, cust:b.customer||"",
      qual:b.quality, shade:b.shadeNo||"", type:routeStep(q,+q.dyeStep||3).mc,
      meters:Math.round(meters), kg:Math.round(kg),
      dyeMins:q.dyeMins, finishMins:q.finishMins,
      pri:+b.pri||2, due:+b.due||7, urgent:!!b.urgent, redye:(b.status==="redye"),
      status:b.status||"planned", startedAt:b.startedAt||"", startedBy:b.startedBy||"",
      completedAt:b.completedAt||"", completedBy:b.completedBy||"",
      family:sh.family, tone:sh.tone, q:q, mcPin:b.mcPin||"",
      pcs:tot.pcs, inTime:b.inTime||"", outTime:b.outTime||"",
      notes:b.notes||"", operator:b.operator||"", lotIds:(b.lots||[]).map(r=>r.lotId).filter(Boolean).concat(b.lots?[]:(b.lotIds||[]))});
  });
  return out;
}

/* ---------- routes: every quality is up to 4 machine steps ---------- */
function routeStep(q,i){ return {mc:(q["step"+i+"_mc"]||""), time:(+q["step"+i+"_time"]||0)}; }
function routeOf(q, meters){
  const out=[]; const dye=+q.dyeStep||3;
  for(let i=1;i<=4;i++){
    const mc=q["step"+i+"_mc"]||""; if(!mc) continue;
    let time=+q["step"+i+"_time"]||0;
    if(mc==="stentor"){                       // stentor runs at a speed, not a fixed batch time
      const sp=+q["step"+i+"_speed"]||0;
      if(sp>0) time=Math.round((+meters||0)/sp + (+cfg().stentorSetupMins||90));
    }
    if(!time) continue;
    out.push({idx:i, mc:mc, time:time, isDye:i===dye});
  }
  return out;
}

/* ---------- scheduler: walks each batch through its 4-step route ---------- */
function computeSchedule(){
  const BUF = cfg().buffer||1.2;
  const tl={}; DB.machines.forEach(m=> tl[m.id]={cursor:0,last:null,blocks:[],mc:m});
  let batches=batchesForSchedule();   // the Batch maker is the source of truth for scheduling
  // urgent first, then priority, due date, then shade family + tone for campaign grouping
  batches.sort((a,b)=> (b.urgent?1:0)-(a.urgent?1:0) || a.pri-b.pri || a.due-b.due
                     || String(a.family).localeCompare(b.family) || a.tone-b.tone);

  let washCount=0; const orderFinish={};
  batches.forEach(b=>{
    let t=0, steps=routeOf(b.q, b.meters);
    if(b.redye) steps=steps.filter(st=>st.idx>= (+b.q.dyeStep||3));   // redye goes straight back to the dye machine
    if(!steps.length){ b.unplanned=true; return; }
    const H = (+b.q.loadMin||cfg().loadMin||35) + (+b.q.unloadMin||cfg().unloadMin||25);
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
      if(st.isDye && best.needWash){ best.q.blocks.push({kind:"wash",start:Math.max(best.q.cursor,t),mins:best.m.wash||0}); washCount++; }
      best.q.blocks.push({kind: st.isDye?"dye":"pre", batch:b, start:best.start, mins:occ, step:st.idx, mcType:st.mc});
      best.q.cursor=best.fin; t=best.fin;
      if(st.isDye){ best.q.last={family:b.family,tone:b.tone}; b.mcAssigned=best.m.id; b.dyeStart=best.start; b.dyeEnd=best.fin; }
      else if(st.idx < (+b.q.dyeStep||3)) b.rfdReady=best.fin;
    });
    b.routeEnd=t;
    orderFinish[b.order]=Math.max(orderFinish[b.order]||0, t*BUF);
  });

  const maxMin=Math.max.apply(null,[60].concat(DB.machines.map(m=>tl[m.id].cursor)))+30;
  return {tl,batches,washCount,orderFinish,batchCount:batches.length,maxMin,BUF};
}

/* ---------- gantt / floor rendering ---------- */
const PXH=60; const px=min=> min/60*PXH;
let LAST_S=null;

/* plan t0 == "now"; label a plan-minute offset as a real wall-clock time */
function planClockLabel(min){
  const d=new Date(Date.now()+min*60000);
  return d.getHours().toString().padStart(2,"0")+":"+d.getMinutes().toString().padStart(2,"0");
}

function renderGantt(el,S,newKeys){
  newKeys=newKeys||[]; LAST_S=S;
  let html='<div class="axis"><div></div><div class="ticks" style="width:'+px(S.maxMin)+'px">';
  for(let h=0;h<=Math.ceil(S.maxMin/60);h+=2) html+='<span class="tk" style="left:'+px(h*60)+'px">'+planClockLabel(h*60)+'</span>';
  html+='</div></div>';
  DB.machines.forEach(m=>{
    const t=S.tl[m.id];
    html+='<div class="grow"><div class="glabel"><b>'+m.id+'</b><small>'+m.type+(m.plc?" - PLC":"")+'</small></div><div class="gtrack" style="width:'+px(S.maxMin)+'px">';
    t.blocks.forEach(b=>{
      const left=px(b.start), w=Math.max(16,px(b.mins));
      if(b.kind==="wash") html+='<div class="blk wash" style="left:'+left+'px;width:'+w+'px" title="Machine wash '+b.mins+'m">WASH</div>';
      else if(b.kind==="pre"){const bt=b.batch;
        html+='<div class="blk pre" data-bk="'+bt.key+'" style="left:'+left+'px;width:'+w+'px">'+bt.order+'<small>step '+b.step+' &middot; '+esc(b.mcType)+'</small></div>';}
      else{const bt=b.batch;const hot=newKeys.indexOf(bt.key)>=0?" newb":"";
        const run=(bt.status==="running")?" running":"";
        const marks=(bt.urgent?'<span class="material-symbols-rounded blk-ic">priority_high</span>':'')
                   +(bt.status==="running"?'<span class="material-symbols-rounded blk-ic">bolt</span>':'')
                   +(bt.notes?'<span class="material-symbols-rounded blk-ic">sticky_note_2</span>':'');
        html+='<div class="blk'+hot+run+(bt.urgent?' urgent':'')+'" data-bk="'+bt.key+'" style="left:'+left+'px;width:'+w+'px;background:'+shadeColor(bt.shade,bt.qual)+';color:'+(bt.tone>5?'#fff':'#20242c')+'"><div class="cap l" style="width:'+px((+bt.q.loadMin||cfg().loadMin||35))+'px"></div><div class="cap r" style="width:'+px((+bt.q.unloadMin||cfg().unloadMin||25))+'px"></div>'+marks+esc(bt.shade)+'<small>'+esc(bt.order)+' - '+bt.meters+'m</small></div>';}
    });
    html+='</div></div>';
  });
  // live now-line: plan t0 is "now", so it sits at the left edge and sweeps right between renders
  html+='<div class="nowline" id="nowline" style="left:calc(var(--glabel-w, 132px))"><span>now</span></div>';
  el.innerHTML=html;
  startNowLine(el,S);
  el.onmousemove=e=>{ const blk=e.target.closest('.blk[data-bk]'); if(blk) showGanttHover(blk,e); else hideGanttHover(); };
  el.onmouseleave=hideGanttHover;
}

/* live now-line: t0 == render time; the line sweeps right until the next replan re-anchors it */
let NOWLINE_TIMER=null, LAST_RENDER=Date.now();
function startNowLine(el,S){
  LAST_RENDER=Date.now();
  if(NOWLINE_TIMER){ clearInterval(NOWLINE_TIMER); NOWLINE_TIMER=null; }
  const place=()=>{
    const line=el.querySelector("#nowline"); const track=el.querySelector(".gtrack");
    if(!line||!track) return;
    const mins=(Date.now()-LAST_RENDER)/60000;
    // label column width: measured when layout exists (browser), else the CSS fallback 132px
    const labelW=track.parentElement ? (track.getBoundingClientRect().left - el.getBoundingClientRect().left) : 132;
    const x=(labelW||132)+px(Math.min(mins, S?S.maxMin:0));
    line.style.left=x+"px";
  };
  place();
  NOWLINE_TIMER=setInterval(place, 20000);   // sweep every 20s (real browser; harmless in jsdom)
}

/* ---------- gantt hover card: full batch detail ---------- */
function ganttHoverEl(){
  let h=document.getElementById("ganttHover");
  if(!h){ h=document.createElement("div"); h.id="ganttHover"; h.className="ghover"; document.body.appendChild(h); }
  return h;
}
function hideGanttHover(){ const h=document.getElementById("ganttHover"); if(h) h.classList.remove("on"); }
function showGanttHover(blk,e){
  const b=(LAST_S&&LAST_S.batches||[]).find(x=>x.key===blk.dataset.bk); if(!b) return;
  const h=ganttHoverEl();
  const row=(l,v)=>'<div class="gh-row"><span>'+l+'</span><b>'+(v===""||v==null?"&mdash;":esc(v))+'</b></div>';
  h.innerHTML='<div class="gh-head"><span class="swatch" style="background:'+shadeColor(b.shade,b.qual)+'"></span>'
      +'<b>'+esc(b.batchId||b.key)+'</b>'
      +(b.urgent?'<span class="pill maint">urgent</span>':'')
      +(b.redye?'<span class="pill wash">redye</span>':'')+'</div>'
    +row("Lot no.", (b.lotIds||[]).join(", "))
    +row("Pieces", b.pcs)
    +row("Meters", b.meters)
    +row("Quality", b.qual)
    +row("Shade no.", b.shade)
    +row("In time", b.inTime)
    +row("Out time", b.outTime)
    +row("Machine", b.mcAssigned)
    +(b.mcPin?row("M/C pin", b.mcPin):'')
    +(b.pinWarning?'<div class="gh-note"><span class="material-symbols-rounded">warning</span>'+esc(b.pinWarning)+'</div>':'')
    +(b.unplannedReason?'<div class="gh-note"><span class="material-symbols-rounded">error</span>'+esc(b.unplannedReason)+'</div>':'')
    +(b.notes?'<div class="gh-note"><span class="material-symbols-rounded">sticky_note_2</span>'+esc(b.notes)+'</div>':'');
  h.classList.add("on");
  const pad=14, w=h.offsetWidth||260, hh=h.offsetHeight||180;
  let x=e.clientX+pad, y=e.clientY+pad;
  if(x+w>window.innerWidth-8) x=e.clientX-w-pad;
  if(y+hh>window.innerHeight-8) y=Math.max(8,e.clientY-hh-pad);
  h.style.left=x+"px"; h.style.top=y+"px";
}
function renderLegend(el){
  const fams=[]; DB.shadeRecipes.forEach(s=>{ if(fams.indexOf(s.family)<0) fams.push(s.family); });
  el.innerHTML=fams.map(f=>{const ex=DB.shadeRecipes.filter(s=>s.family===f).sort((a,b)=>a.tone-b.tone);
    return '<span><span class="swatch" style="background:'+shadeColor(ex[0].shade,ex[0].quality)+'"></span><span class="swatch" style="background:'+shadeColor(ex[ex.length-1].shade,ex[ex.length-1].quality)+'"></span>'+f+' (light-to-dark)</span>';}).join("")
    +'<span><span class="swatch" style="background:repeating-linear-gradient(45deg,#c9ccd4,#c9ccd4 3px,#dfe2e8 3px,#dfe2e8 6px)"></span>Wash</span>'
    +'<span><span class="swatch" style="background:repeating-linear-gradient(45deg,#aebfe0,#aebfe0 3px,#cdd9ee 3px,#cdd9ee 6px)"></span>Pre-treatment</span>';
}
function mcIcon(type){ return {jet:"water_drop",jigger:"waves",drum:"cyclone",stentor:"compress",hydro:"mode_fan",rope:"timeline"}[type]||"precision_manufacturing"; }
function renderFloor(el,S,clockH){
  clockH=clockH||0; const nowMin=clockH*60;
  if(!DB.machines.length){ el.innerHTML='<div class="empty"><span class="material-symbols-rounded">precision_manufacturing</span><h3>No machines yet</h3><p>Add machines in the Admin console and the shop floor will appear here.</p></div>'; return; }
  let html="";
  DB.machines.forEach((m,i)=>{
    const t=S.tl[m.id];
    const cur=t.blocks.find(b=> nowMin>=b.start && nowMin<b.start+b.mins);
    let status="free",label="Idle",fillPct=0,fillBg="var(--surface-3)",vatCls=" idle";
    let info='<div class="mc-info"><b class="muted">Idle</b><div class="sub muted">No active batch</div></div>';
    if(cur){
      if(cur.kind==="wash"){status="wash";label="Wash";fillPct=100;vatCls="";
        fillBg="repeating-linear-gradient(-45deg,#8fb0e6,#8fb0e6 5px,#c9d7f4 5px,#c9d7f4 10px)";
        info='<div class="mc-info"><b>Machine wash</b><div class="sub">Resetting for a lighter shade</div></div>';}
      else if(cur.kind==="pre"){status="pre";label="Pre-treat";fillPct=60;vatCls="";
        fillBg="repeating-linear-gradient(45deg,#e7c98a,#e7c98a 5px,#f0dcae 5px,#f0dcae 10px)";
        info='<div class="mc-info"><b>'+esc(cur.batch.order)+'</b><div class="sub">Pre-treatment &middot; '+esc(m.type)+'</div></div>';}
      else{const b=cur.batch;status="run";label="Dyeing";vatCls="";
        fillPct=Math.max(6,Math.min(100,Math.round((b.kg/(m.capMax||b.kg))*100)));
        fillBg=shadeColor(b.shade,b.qual);
        info='<div class="mc-info"><b><span class="swatch" style="background:'+shadeColor(b.shade,b.qual)+'"></span>'+esc(b.shade)+'</b><div class="sub">'+esc(b.order)+' &middot; '+esc(b.qual)+'</div><div class="q">'+b.meters+' m &middot; '+b.kg+' kg</div></div>';}
    }
    const queue=t.blocks.filter(b=>b.start>=nowMin && b.kind==="dye").length;
    html+='<div class="mc rise" style="animation-delay:'+(i*35)+'ms">'
      +'<div class="mc-top"><div class="mc-ic"><span class="material-symbols-rounded">'+mcIcon(m.type)+'</span></div>'
      +'<div style="min-width:0;flex:1"><div class="mc-name">'+m.id+' <span class="pill '+status+'">'+label+'</span></div>'
      +'<div class="mc-type">'+esc(m.type)+(m.plc?" &middot; PLC":"")+' &middot; '+m.capMax+' kg</div></div></div>'
      +'<div class="mc-body"><div class="vat'+vatCls+'"><div class="fill" style="height:'+fillPct+'%;background:'+fillBg+'"></div>'
      +(fillPct?'<div class="pct">'+fillPct+'%</div>':'')+'</div>'+info+'</div>'
      +'<div class="mc-foot"><span class="lbl">Queue</span><span class="tnum" style="font-weight:600">'+queue+' <span class="muted" style="font-weight:400">waiting</span></span></div></div>';
  });
  el.innerHTML=html;
}

/* ---------- small ui utils ---------- */
function serverBanner(){
  var msg = "Cannot reach the server. This is a live app - open it through the running server, not as a file. "
    + "Start it with: python server.py (in the mvp folder), then go to http://localhost:8080/";
  var el = document.createElement("div");
  el.setAttribute("style","background:#fbe8e8;color:#8a2020;padding:14px 18px;text-align:center;font-weight:600;font-family:sans-serif");
  el.textContent = "[!] " + msg;
  document.body.insertBefore(el, document.body.firstChild);
}
/* ---------- auth (login gate + permissions) ---------- */
let CURRENT_USER=null;
async function apiMe(){ try{ const r=await fetch("/api/me"); if(r.status!==200) return null; return (await r.json()).user; }catch(e){ return "ERR"; } }
function can(page){ return !!(CURRENT_USER && CURRENT_USER.perms && CURRENT_USER.perms.indexOf(page)>=0); }

async function boot(initFn){
  const u=await apiMe();
  if(u==="ERR"){ serverBanner(); return; }
  if(!u){ showLogin(initFn); return; }
  CURRENT_USER=u;
  try{ await API.db(); initFn(); renderUserBox(); }catch(e){ console.error(e); serverBanner(); }
}

function showLogin(initFn){
  if(document.getElementById("loginOverlay")) return;
  const o=document.createElement("div"); o.id="loginOverlay";
  o.style.cssText="position:fixed;inset:0;z-index:200;display:flex;align-items:center;justify-content:center;background:#eef1f7;font-family:'Inter',system-ui,sans-serif;animation:riseIn .3s cubic-bezier(.16,1,.3,1) both";
  o.innerHTML='<form id="loginForm" style="width:352px;max-width:92vw;background:#fff;border:1px solid #e6eaf1;border-radius:16px;padding:30px;box-shadow:0 24px 60px rgba(16,24,40,.14)">'
    +'<div style="display:flex;align-items:center;gap:11px">'
    +'<div style="width:38px;height:38px;border-radius:11px;background:#1f2d4d;display:flex;align-items:center;justify-content:center;font-family:\'IBM Plex Mono\',monospace;font-weight:600;color:#fff;font-size:13px">RD</div>'
    +'<div><div style="font-weight:800;font-size:16px;color:#18233b;letter-spacing:-.02em">REL Dyeing ERP</div><div style="font-size:12.5px;color:#7a8598">Sign in to continue</div></div></div>'
    +'<label style="display:block;font-size:12.5px;font-weight:600;color:#48546b;margin-top:20px">Username'
    +'<input id="lg_u" autocomplete="username" style="width:100%;margin-top:6px;padding:11px;border:1px solid #dbe1ea;border-radius:10px;background:#fff;color:#18233b;font:inherit"></label>'
    +'<label style="display:block;font-size:12.5px;font-weight:600;color:#48546b;margin-top:13px">Password'
    +'<input id="lg_p" type="password" autocomplete="current-password" style="width:100%;margin-top:6px;padding:11px;border:1px solid #dbe1ea;border-radius:10px;background:#fff;color:#18233b;font:inherit"></label>'
    +'<div id="lg_err" style="color:#d64545;font-size:12px;margin-top:10px;min-height:16px"></div>'
    +'<button type="submit" style="width:100%;margin-top:6px;padding:12px;border:0;border-radius:10px;background:#1f2d4d;color:#fff;font-weight:600;font-size:14px;cursor:pointer">Sign in</button></form>';
  document.body.appendChild(o);
  o.querySelector("#loginForm").addEventListener("submit", async(e)=>{
    e.preventDefault(); const err=o.querySelector("#lg_err"); err.textContent="";
    const r=await fetch("/api",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({op:"login",username:o.querySelector("#lg_u").value,password:o.querySelector("#lg_p").value})});
    const j=await r.json().catch(()=>({}));
    if(r.status!==200){ err.textContent=j.error||"Login failed"; return; }
    CURRENT_USER=j.user; o.remove();
    try{ await API.db(); initFn(); renderUserBox(); }catch(e2){ console.error(e2); serverBanner(); }
  });
  setTimeout(()=>{const el=o.querySelector("#lg_u"); if(el)el.focus();},50);
}

async function logout(){ try{ await fetch("/api",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({op:"logout"})}); }catch(e){} location.reload(); }

function renderUserBox(){
  const box=document.getElementById("userbox"); if(!box||!CURRENT_USER)return;
  box.innerHTML='<span id="hdrClock" class="hdr-clock" title="Current time (t) — the schedule is shown relative to now"></span>'
    +'<button class="btn ghost sm" onclick="openChangePw()" title="Click to change your password">'+esc(CURRENT_USER.username)+' &middot; '+esc(CURRENT_USER.role)+'</button>'
    +'<button class="btn ghost sm" onclick="logout()"><span class="material-symbols-rounded" style="font-size:16px">logout</span>Log out</button>';
  startClock();
}
let _clockTimer=null;
function startClock(){
  const upd=()=>{ const el=document.getElementById("hdrClock"); if(!el) return;
    const d=new Date(), p=n=>String(n).padStart(2,"0");
    el.innerHTML='<span class="material-symbols-rounded">schedule</span>'+p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds()); };
  upd(); if(_clockTimer) clearInterval(_clockTimer); _clockTimer=setInterval(upd,1000);
}
function openChangePw(){
  const ex=document.getElementById("cpwOverlay"); if(ex)ex.remove();
  const o=document.createElement("div"); o.id="cpwOverlay"; o.className="modal-bg on";
  o.innerHTML='<div class="modal" style="width:420px"><div class="m-h"><h3>Change password</h3><button class="x" onclick="this.closest(\'.modal-bg\').remove()">&times;</button></div>'
   +'<div class="m-b"><label class="fld">Current password<input id="cp_old" type="password"></label>'
   +'<label class="fld">New password (min 6 characters)<input id="cp_new" type="password"></label>'
   +'<div id="cp_err" style="color:#f0938a;font-size:12px;min-height:16px"></div></div>'
   +'<div class="m-f"><button class="btn ghost" onclick="this.closest(\'.modal-bg\').remove()">Cancel</button><button class="btn" onclick="submitChangePw()">Update password</button></div></div>';
  document.body.appendChild(o);
}
async function submitChangePw(){
  const err=document.getElementById("cp_err"); err.textContent="";
  const r=await fetch("/api",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({op:"changePassword",oldPassword:document.getElementById("cp_old").value,newPassword:document.getElementById("cp_new").value})});
  const j=await r.json().catch(()=>({}));
  if(r.status!==200){ err.textContent=j.error||"Failed"; return; }
  document.getElementById("cpwOverlay").remove(); toast("Password changed");
}
function toast(msg){ let t=document.getElementById("toast"); if(!t){t=document.createElement("div");t.id="toast";document.body.appendChild(t);} t.textContent=msg; t.classList.add("on"); clearTimeout(t._t); t._t=setTimeout(()=>t.classList.remove("on"),2200); }
const esc = s => String(s===undefined||s===null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
