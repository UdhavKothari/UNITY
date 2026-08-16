/* REL-UNITY workflow builder — self-contained module hosted in a modal (Admin › Quality settings).
   Everything is scoped inside this IIFE; only window.openWorkflowsModal + window.WF (inline handlers)
   are exposed, so nothing collides with admin.html's own globals (e.g. its render()). */
(function(){
const WF_CSS = `
.wf-modalbox{width:min(1180px,96vw);max-width:96vw}
.wf-mb{padding:0}
.wf-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:14px 16px;border-bottom:1px solid var(--line)}
.wf-top .flowname{font-size:15px;font-weight:700;border:1px solid var(--line-2);border-radius:10px;padding:8px 11px;min-width:200px;background:var(--surface);color:var(--ink)}
.wf-top .flowname:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.wf-top select{border:1px solid var(--line-2);border-radius:10px;padding:8px 10px;background:var(--surface);color:var(--ink);font-size:13px;font-weight:600}
.wf-body{display:flex;min-height:460px;height:60vh}
.wf-palette{width:212px;flex:none;background:var(--surface-2);border-right:1px solid var(--line);display:flex;flex-direction:column}
.wf-palette .ph{padding:12px 14px 6px;font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.wf-palette .hint{padding:0 14px 10px;font-size:12px;color:var(--muted);line-height:1.5}
.wf-plist{overflow:auto;padding:4px 10px 12px;display:flex;flex-direction:column;gap:7px}
.wf-ptile{display:flex;align-items:center;gap:10px;padding:9px 10px;border:1px solid var(--line-2);border-radius:11px;background:var(--surface);text-align:left;width:100%;cursor:pointer;transition:box-shadow .12s,border-color .12s,transform .12s}
.wf-ptile:hover{box-shadow:var(--shadow-lift);border-color:var(--accent);transform:translateY(-1px)}
.wf-ptile .tile{width:34px;height:34px;flex:none;border-radius:9px;display:grid;place-items:center}
.wf-ptile .tile .material-symbols-rounded{font-size:20px}
.wf-ptile .nm{font-weight:600;font-size:13px;line-height:1.15}
.wf-ptile .mc{font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;color:var(--muted);text-transform:uppercase;margin-top:2px}
.wf-ptile.new{border-style:dashed;color:var(--accent);justify-content:center;font-weight:700}
.wf-m-jet .tile{background:var(--accent-soft);color:var(--accent)}
.wf-m-jigger .tile{background:#e9f3fb;color:#2f6ea8}
.wf-m-stentor .tile{background:#e6f4ee;color:var(--success)}
.wf-m-heatset .tile{background:#fdeede;color:var(--warning)}
.wf-m-input .tile{background:var(--surface-3);color:var(--ink-2)}
.wf-m-output .tile{background:var(--primary);color:#fff}
.wf-m-other .tile{background:var(--surface-3);color:var(--ink-2)}
.wf-stage{flex:1;position:relative;overflow:auto;background:radial-gradient(circle at 1px 1px,#dfe4ee 1px,transparent 0) 0 0/22px 22px}
.wf-canvas{position:relative;min-width:100%;min-height:100%}
svg.wf-wires{position:absolute;left:0;top:0;z-index:1;pointer-events:none;overflow:visible}
.wf-wire{fill:none;stroke:var(--line-2);stroke-width:2.5}
.wf-node{position:absolute;z-index:2;width:150px;background:var(--surface);border:1px solid var(--line-2);border-radius:13px;box-shadow:var(--shadow);padding:11px;transition:box-shadow .14s,border-color .14s,transform .14s}
.wf-node:hover{box-shadow:var(--shadow-lift);border-color:var(--accent);transform:translateY(-2px)}
.wf-node .nh{display:flex;align-items:center;gap:9px}
.wf-node .tile{width:38px;height:38px;flex:none;border-radius:10px;display:grid;place-items:center}
.wf-node .tile .material-symbols-rounded{font-size:22px}
.wf-node .nm{font-weight:700;font-size:13.5px;line-height:1.12}
.wf-node .mc{font-family:'IBM Plex Mono',monospace;font-size:9.5px;font-weight:600;color:var(--muted);text-transform:uppercase;margin-top:2px}
.wf-node .timerow{margin-top:9px;display:flex;align-items:center;gap:6px;background:var(--surface-2);border:1px solid var(--line);border-radius:9px;padding:4px 8px}
.wf-node .timerow .material-symbols-rounded{font-size:15px;color:var(--muted)}
.wf-node .timerow input{width:100%;border:none;background:transparent;font-family:'IBM Plex Mono',monospace;font-weight:600;font-size:13px;color:var(--ink);text-align:right}
.wf-node .timerow input:focus{outline:none}
.wf-node .timerow .u{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted)}
.wf-node .x{position:absolute;top:-9px;right:-9px;width:23px;height:23px;border-radius:50%;background:#fff;border:1px solid var(--line-2);color:var(--danger);display:none;place-items:center;box-shadow:var(--shadow);cursor:pointer}
.wf-node .x .material-symbols-rounded{font-size:15px}
.wf-node:hover .x{display:grid}
.wf-node .addin{position:absolute;left:-13px;top:50%;transform:translateY(-50%);width:25px;height:25px;border-radius:50%;background:#fff;border:1px dashed var(--accent);color:var(--accent);display:none;place-items:center;box-shadow:var(--shadow);cursor:pointer}
.wf-node .addin .material-symbols-rounded{font-size:16px}
.wf-node:hover .addin{display:grid}
.wf-node.io{width:126px;text-align:center}
.wf-node.io .nh{flex-direction:column;gap:7px}
.wf-node.input{border-style:dashed;background:var(--surface-2)}
.wf-node.output{border-color:var(--primary)}
.wf-node .badge{font-family:'IBM Plex Mono',monospace;font-size:9.5px;font-weight:600;color:var(--muted);text-transform:uppercase}
.wf-plus{position:absolute;z-index:2;width:28px;height:28px;border-radius:50%;background:var(--accent);color:#fff;display:grid;place-items:center;box-shadow:0 3px 10px rgba(58,99,196,.4);transform:translate(-50%,-50%);transition:transform .12s;border:2px solid #fff;cursor:pointer;line-height:0}
.wf-plus .material-symbols-rounded{font-size:18px}
.wf-plus:hover{transform:translate(-50%,-50%) scale(1.15)}
.wf-help{position:absolute;left:12px;bottom:12px;z-index:2;display:flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:7px 11px;font-size:12px;color:var(--ink-2);box-shadow:var(--shadow);max-width:70%}
.wf-help .material-symbols-rounded{font-size:17px;color:var(--accent)}
.wf-scrim{position:fixed;inset:0;background:rgba(24,35,59,.28);z-index:70;display:none;align-items:flex-end;justify-content:center}
.wf-scrim.on{display:flex}
.wf-sheet{width:min(720px,100%);background:var(--surface);border-radius:20px 20px 0 0;box-shadow:0 -8px 40px rgba(16,24,40,.2);padding:16px 16px 24px}
.wf-sheet h3{margin:2px 4px;font-size:16px}
.wf-sheet p{margin:0 4px 12px;color:var(--muted);font-size:13px}
.wf-pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:9px}
.wf-pick{display:flex;flex-direction:column;align-items:center;gap:7px;padding:15px 9px;border:1px solid var(--line-2);border-radius:13px;background:var(--surface);cursor:pointer;transition:box-shadow .12s,border-color .12s,transform .12s}
.wf-pick:hover{box-shadow:var(--shadow-lift);border-color:var(--accent);transform:translateY(-2px)}
.wf-pick .tile{width:44px;height:44px;border-radius:12px;display:grid;place-items:center}
.wf-pick .tile .material-symbols-rounded{font-size:25px}
.wf-pick .nm{font-weight:700;font-size:13.5px;text-align:center;line-height:1.12}
.wf-pick .mc{font-family:'IBM Plex Mono',monospace;font-size:9.5px;font-weight:600;color:var(--muted);text-transform:uppercase}
.wf-pick.new{border-style:dashed;color:var(--accent)}
.wf-pick.new .tile{background:var(--accent-soft);color:var(--accent)}
.wf-iconpick{display:flex;flex-wrap:wrap;gap:7px}
.wf-iconpick button{width:38px;height:38px;border-radius:10px;border:1px solid var(--line-2);display:grid;place-items:center;background:var(--surface);cursor:pointer}
.wf-iconpick button .material-symbols-rounded{font-size:21px;color:var(--ink-2)}
.wf-iconpick button.on{border-color:var(--accent);background:var(--accent-soft)}
.wf-iconpick button.on .material-symbols-rounded{color:var(--accent)}
.wf-seg{display:flex;gap:8px}
.wf-seg button{flex:1;border:1px solid var(--line-2);border-radius:10px;padding:8px;font-weight:600;font-size:13px;color:var(--ink-2);background:var(--surface);cursor:pointer}
.wf-seg button.on{border-color:var(--accent);background:var(--accent-soft);color:var(--accent)}
.wf-pv{display:flex;align-items:center;gap:10px;background:var(--surface-2);border:1px dashed var(--line-2);border-radius:12px;padding:10px 12px;margin-bottom:12px}
.wf-pv .tile{width:38px;height:38px;border-radius:10px;display:grid;place-items:center}
.wf-pv .id{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted)}
`;
function injectCss(){ if(document.getElementById("wf-css"))return; const s=document.createElement("style"); s.id="wf-css"; s.textContent=WF_CSS; document.head.appendChild(s); }

const MACHINE_META={jet:{name:"Jet"},jigger:{name:"Jigger"},stentor:{name:"Stentor"},heatset:{name:"Heat-set"},drum:{name:"Drum"},hydro:{name:"Hydro"},rope:{name:"Rope"}};
const ICON_CHOICES=["water_drop","waves","compress","local_fire_department","cleaning_services","science","mode_fan","cyclone","opacity","bolt","ac_unit","filter_alt"];
const PADX=44;
let uid=1; const nid=()=>"wn"+(uid++);
let PROCS=[], flow={id:"",name:"",fabricGroup:"",nodes:[],edges:[]}, sheetEdge=null, npIcon="water_drop", npPooled=0;

const P=id=>PROCS.find(p=>p.id===id);
const mcName=mk=>(MACHINE_META[mk]||{}).name||mk||"—";
const mcCls=mk=>MACHINE_META[mk]?("wf-m-"+mk):"wf-m-other";
const $=id=>document.getElementById(id);

function nodeMeta(n){
  if(n.kind==="input") return {name:n.label||"Greige",icon:"inventory_2",cls:"wf-m-input",mc:"RAW FABRIC"};
  if(n.kind==="output") return {name:"Finished fabric",icon:"verified",cls:"wf-m-output",mc:"DELIVER"};
  const p=P(n.proc)||{name:"?",icon:"help",machine:""};
  return {name:p.name,icon:p.icon,cls:mcCls(p.machine),mc:mcName(p.machine)};
}
function layout(){
  const nodes=flow.nodes,edges=flow.edges,adj={},indeg={};
  nodes.forEach(n=>{adj[n.id]=[];indeg[n.id]=0;});
  edges.forEach(e=>{ if(adj[e.from]){adj[e.from].push(e.to);indeg[e.to]=(indeg[e.to]||0)+1;} });
  const rank={},q=nodes.filter(n=>indeg[n.id]===0).map(n=>n.id); q.forEach(id=>rank[id]=0);
  const d={...indeg},queue=[...q];
  while(queue.length){ const id=queue.shift(); (adj[id]||[]).forEach(t=>{ rank[t]=Math.max(rank[t]??0,(rank[id]||0)+1); if(--d[t]===0) queue.push(t); }); }
  const maxR=Math.max(0,...Object.values(rank)); nodes.forEach(n=>{ if(n.kind==="output") rank[n.id]=maxR; });
  const maxR2=Math.max(0,...Object.values(rank)),cols={}; nodes.forEach(n=>{ (cols[rank[n.id]]=cols[rank[n.id]]||[]).push(n); });
  const COLW=200,NODEH=112,ROWG=36; let maxRows=0; Object.values(cols).forEach(c=>maxRows=Math.max(maxRows,c.length));
  const midY=PADX+(maxRows*NODEH+(maxRows-1)*ROWG)/2,pos={};
  for(let r=0;r<=maxR2;r++){ const c=cols[r]||[],h=c.length*NODEH+(c.length-1)*ROWG; let y=midY-h/2;
    c.forEach(n=>{ pos[n.id]={x:PADX+r*COLW,y:y,w:(n.kind==="proc"?150:126)}; y+=NODEH+ROWG; }); }
  return {pos};
}
function render(){
  const canvas=$("wf_canvas"),svg=$("wf_wires"); if(!canvas)return;
  [...canvas.querySelectorAll(".wf-node,.wf-plus")].forEach(el=>el.remove());
  const {pos}=layout(); let W=120,H=0;
  Object.values(pos).forEach(p=>{ W=Math.max(W,p.x+p.w+PADX); H=Math.max(H,p.y+130); });
  const CH=Math.max(H,420); canvas.style.width=W+"px"; canvas.style.height=CH+"px";
  svg.style.width=W+"px"; svg.style.height=CH+"px"; svg.setAttribute("viewBox","0 0 "+W+" "+CH); svg.setAttribute("preserveAspectRatio","none");
  const els={};
  flow.nodes.forEach(n=>{ const p=pos[n.id]; if(!p)return; const m=nodeMeta(n);
    const el=document.createElement("div"); el.className="wf-node "+(n.kind==="proc"?"":"io "+n.kind);
    el.style.left=p.x+"px"; el.style.top=p.y+"px";
    if(n.kind==="proc"){
      el.innerHTML='<button class="x" title="Remove" onclick="WF.delNode(\''+n.id+'\')"><span class="material-symbols-rounded">close</span></button>'
        +'<button class="addin" title="Join a second input" onclick="WF.addInput(\''+n.id+'\')"><span class="material-symbols-rounded">add</span></button>'
        +'<div class="nh"><div class="tile '+m.cls+'"><span class="material-symbols-rounded">'+m.icon+'</span></div>'
        +'<div><div class="nm">'+esc(m.name)+'</div><div class="mc">'+esc(m.mc)+'</div></div></div>'
        +'<div class="timerow"><span class="material-symbols-rounded">schedule</span><input type="number" min="0" value="'+(n.time||0)+'" onchange="WF.setTime(\''+n.id+'\',this.value)"><span class="u">min</span></div>';
    } else {
      el.innerHTML='<div class="nh"><div class="tile '+m.cls+'"><span class="material-symbols-rounded">'+m.icon+'</span></div>'
        +'<div class="nm">'+esc(m.name)+'</div><div class="badge">'+esc(m.mc)+'</div></div>';
    }
    canvas.appendChild(el); els[n.id]=el;
  });
  const geo=e=>{ const A=els[e.from],B=els[e.to]; if(!A||!B)return null; return {x1:A.offsetLeft+A.offsetWidth,y1:A.offsetTop+A.offsetHeight/2,x2:B.offsetLeft,y2:B.offsetTop+B.offsetHeight/2}; };
  let paths="";
  flow.edges.forEach(e=>{ const g=geo(e); if(!g)return; const dx=Math.max(38,(g.x2-g.x1)/2);
    paths+='<path class="wf-wire" d="M'+g.x1+','+g.y1+' C'+(g.x1+dx)+','+g.y1+' '+(g.x2-dx)+','+g.y2+' '+g.x2+','+g.y2+'"/>'; });
  svg.innerHTML=paths;
  flow.edges.forEach(e=>{ const g=geo(e); if(!g)return; const b=document.createElement("button"); b.className="wf-plus";
    b.style.left=((g.x1+g.x2)/2)+"px"; b.style.top=((g.y1+g.y2)/2)+"px"; b.title="Insert a process here";
    b.innerHTML='<span class="material-symbols-rounded">add</span>'; b.onclick=()=>openSheet(e); canvas.appendChild(b); });
}
function setTime(id,v){ const n=flow.nodes.find(x=>x.id===id); if(n) n.time=+v||0; }
function insertOnEdge(e,procId){ const p=P(procId),nn={id:nid(),kind:"proc",proc:procId,time:p?p.defTime:30};
  flow.nodes.push(nn); flow.edges=flow.edges.filter(z=>!(z.from===e.from&&z.to===e.to));
  flow.edges.push({from:e.from,to:nn.id},{from:nn.id,to:e.to}); render(); }
function appendProc(procId){ const out=flow.nodes.find(n=>n.kind==="output"),e=flow.edges.find(z=>z.to===out.id); if(e) insertOnEdge(e,procId); }
function delNode(id){ const n=flow.nodes.find(x=>x.id===id); if(!n||n.kind==="output")return;
  if(n.kind==="input"&&flow.nodes.filter(x=>x.kind==="input").length<=1){ toast("Keep at least one input"); return; }
  const ins=flow.edges.filter(e=>e.to===id).map(e=>e.from),outs=flow.edges.filter(e=>e.from===id).map(e=>e.to);
  flow.edges=flow.edges.filter(e=>e.from!==id&&e.to!==id);
  ins.forEach(a=>outs.forEach(b=>{ if(!flow.edges.some(e=>e.from===a&&e.to===b)) flow.edges.push({from:a,to:b}); }));
  flow.nodes=flow.nodes.filter(x=>x.id!==id); render(); }
function addInput(id){ const g={id:nid(),kind:"input",label:"Greige · 2"}; flow.nodes.push(g); flow.edges.push({from:g.id,to:id}); render(); toast("Second input added"); }

function openSheet(e){ sheetEdge=e; const g=$("wf_pickGrid"); g.innerHTML="";
  PROCS.forEach(p=>{ const b=document.createElement("button"); b.className="wf-pick";
    b.innerHTML='<div class="tile '+mcCls(p.machine)+'"><span class="material-symbols-rounded">'+p.icon+'</span></div><div class="nm">'+esc(p.name)+'</div><div class="mc">'+esc(mcName(p.machine))+' · '+(p.defTime||0)+'m</div>';
    b.onclick=()=>{ if(sheetEdge) insertOnEdge(sheetEdge,p.id); closeSheet(); }; g.appendChild(b); });
  const nb=document.createElement("button"); nb.className="wf-pick new"; nb.innerHTML='<div class="tile"><span class="material-symbols-rounded">add</span></div><div class="nm">New process type</div>';
  nb.onclick=()=>{ closeSheet(); openNp(); }; g.appendChild(nb);
  $("wf_sheet").classList.add("on"); }
function closeSheet(){ const s=$("wf_sheet"); if(s) s.classList.remove("on"); }

function buildPalette(){ const el=$("wf_palette"); if(!el)return; el.innerHTML="";
  PROCS.forEach(p=>{ const b=document.createElement("button"); b.className="wf-ptile";
    b.innerHTML='<div class="tile '+mcCls(p.machine)+'"><span class="material-symbols-rounded">'+p.icon+'</span></div><div><div class="nm">'+esc(p.name)+'</div><div class="mc">'+esc(mcName(p.machine))+' · '+(p.defTime||0)+' min</div></div>';
    b.onclick=()=>appendProc(p.id); el.appendChild(b); });
  if(canEdit("op_workflows")){ const nb=document.createElement("button"); nb.className="wf-ptile new"; nb.innerHTML='<span class="material-symbols-rounded">add</span> New process type'; nb.onclick=openNp; el.appendChild(nb); } }

/* new process type */
function openNp(){ const sel=$("wf_npMachine");
  sel.innerHTML=Object.keys(MACHINE_META).map(k=>'<option value="'+k+'">'+MACHINE_META[k].name+'</option>').join("");
  $("wf_npName").value=""; $("wf_npTime").value=45; $("wf_npLetter").value="T"; npPooled=0; npIcon="water_drop";
  document.querySelectorAll("#wf_npPool button").forEach((b,i)=>b.classList.toggle("on",i===0));
  const ic=$("wf_npIcons"); ic.innerHTML="";
  ICON_CHOICES.forEach(i=>{ const b=document.createElement("button"); b.className=(i===npIcon?"on":""); b.innerHTML='<span class="material-symbols-rounded">'+i+'</span>';
    b.onclick=()=>{ npIcon=i; [...ic.children].forEach(c=>c.classList.remove("on")); b.classList.add("on"); npSync(); }; ic.appendChild(b); });
  npSync(); $("wf_npModal").classList.add("on"); }
function closeNp(){ const m=$("wf_npModal"); if(m) m.classList.remove("on"); }
function npPool(p){ npPooled=p; document.querySelectorAll("#wf_npPool button").forEach((b,i)=>b.classList.toggle("on",i===p)); npSync(); }
function npSync(){ const name=$("wf_npName").value||"New process",mk=$("wf_npMachine").value;
  let L=($("wf_npLetter").value||"?").toUpperCase().slice(0,1); $("wf_npLetter").value=L;
  $("wf_npPvName").textContent=name;
  const pv=$("wf_npPv"); pv.querySelector(".tile").className="tile "+mcCls(mk); pv.querySelector(".material-symbols-rounded").textContent=npIcon;
  $("wf_npPvId").innerHTML=npPooled?("batch id · B"+L+"200/0826 (pooled)"):("batch id · B"+L+"05200/0826 (per machine)"); }
async function saveNp(){ const name=$("wf_npName").value.trim(); if(!name){ toast("Give the process a name"); return; }
  const row={name,machine:$("wf_npMachine").value,icon:npIcon,letter:($("wf_npLetter").value||"?").toUpperCase().slice(0,1),pooled:!!npPooled,defTime:+$("wf_npTime").value||30};
  const res=await API.save("processTypes",row); if(res&&res.error){ toast(res.error); return; }
  PROCS=(DB.processTypes||[]).slice(); buildPalette(); closeNp(); toast("“"+name+"” added"); }

/* fabric-group assignment + flow selector */
function syncAssign(){ const sel=$("wf_group"); if(!sel)return;
  sel.innerHTML='<option value="">— assign to a fabric group —</option>'
    +(DB.fabricGroups||[]).map(g=>'<option value="'+esc(g.id)+'"'+(g.id===flow.fabricGroup?" selected":"")+'>'+esc(g.name)+'</option>').join("")
    +'<option value="__new__">+ New fabric group…</option>'; }
async function onAssign(v){ if(v==="__new__"){ const name=prompt("New fabric group name:"); if(name){ const r=await API.save("fabricGroups",{name:name.trim()}); if(r&&r.row) flow.fabricGroup=r.row.id; } syncAssign(); return; } flow.fabricGroup=v; }
function syncFlows(){ const sel=$("wf_sel"); if(!sel)return;
  sel.innerHTML=(DB.workflows||[]).map(w=>'<option value="'+esc(w.id)+'"'+(w.id===flow.id?" selected":"")+'>'+esc(w.name||"(unnamed)")+'</option>').join("")+'<option value="__new__">+ New flow…</option>';
  if(!flow.id) sel.value="__new__"; }
function newFlow(){ const g=nid(),f=nid();
  flow={id:"",name:"New flow",fabricGroup:"",nodes:[{id:g,kind:"input"},{id:f,kind:"output"}],edges:[{from:g,to:f}]};
  if($("wf_name")) $("wf_name").value=flow.name; syncAssign(); render(); }
function loadFlow(id){ const w=(DB.workflows||[]).find(x=>x.id===id); if(!w){ newFlow(); return; }
  flow=JSON.parse(JSON.stringify(w)); flow.nodes=flow.nodes||[]; flow.edges=flow.edges||[];
  if($("wf_name")) $("wf_name").value=flow.name||""; syncAssign(); render(); }
async function saveFlow(){ if(!canEdit("op_workflows")){ toast("You can view but not edit workflows"); return; }
  flow.name=($("wf_name").value||"").trim()||"Untitled flow";
  const payload={name:flow.name,fabricGroup:flow.fabricGroup||"",nodes:flow.nodes,edges:flow.edges}; if(flow.id) payload.id=flow.id;
  const res=await API.save("workflows",payload); if(res&&res.error){ toast(res.error); return; }
  if(res.row&&res.row.id) flow.id=res.row.id; syncFlows(); toast("Flow saved"); }
async function delFlow(){ if(!flow.id){ newFlow(); return; } if(!canEdit("op_workflows")){ toast("You can view but not edit workflows"); return; }
  if(!confirm("Delete this flow?"))return; const res=await API._post({op:"delete",table:"workflows",id:flow.id});
  if(res&&res.error){ toast(res.error); return; } newFlow(); syncFlows(); toast("Flow deleted"); }

function shell(){ const canEd=canEdit("op_workflows");
  $("wf_app").innerHTML=
    '<div class="wf-top">'
    +'<select id="wf_sel" onchange="(this.value===\'__new__\')?WF.newFlow():WF.loadFlow(this.value)"></select>'
    +'<input class="flowname" id="wf_name" placeholder="Flow name" '+(canEd?"":"disabled")+'>'
    +'<select id="wf_group" onchange="WF.onAssign(this.value)" '+(canEd?"":"disabled")+'></select>'
    +'<span style="flex:1"></span>'
    +(canEd?'<button class="btn ghost" onclick="WF.delFlow()"><span class="material-symbols-rounded">delete</span></button>':'')
    +(canEd?'<button class="btn" onclick="WF.saveFlow()"><span class="material-symbols-rounded">check</span>Save flow</button>':'')
    +'</div>'
    +'<div class="wf-body">'
    +'<aside class="wf-palette"><div class="ph">Processes</div><div class="hint">Tap to add at the end, or the ＋ on any line to insert.</div><div class="wf-plist" id="wf_palette"></div></aside>'
    +'<section class="wf-stage"><div class="wf-canvas" id="wf_canvas"><svg class="wf-wires" id="wf_wires"></svg></div>'
    +'<div class="wf-help"><span class="material-symbols-rounded">touch_app</span> Fabric flows left → right into Finished fabric. Set the time on each machine; ＋ on a card’s left joins a second input.</div>'
    +'</section></div>';
}
function ensureSheets(){
  if(!$("wf_sheet")){ const d=document.createElement("div"); d.className="wf-scrim"; d.id="wf_sheet";
    d.innerHTML='<div class="wf-sheet" onclick="event.stopPropagation()"><h3>Add a process</h3><p>Pick what happens to the fabric at this step.</p><div class="wf-pgrid" id="wf_pickGrid"></div></div>';
    d.addEventListener("click",closeSheet); document.body.appendChild(d); }
  if(!$("wf_npModal")){ const d=document.createElement("div"); d.className="modal-bg"; d.id="wf_npModal";
    d.innerHTML='<div class="modal" style="width:500px;max-width:96vw" onclick="event.stopPropagation()">'
      +'<div class="m-h"><h3><span class="material-symbols-rounded">add_box</span>New process type</h3><button class="x" onclick="WF.closeNp()">&times;</button></div>'
      +'<div class="m-b"><div class="wf-pv" id="wf_npPv"><div class="tile wf-m-jet"><span class="material-symbols-rounded">water_drop</span></div><div><div class="nm" style="font-weight:700" id="wf_npPvName">New process</div><div class="id" id="wf_npPvId">batch id · BT05200/0826</div></div></div>'
      +'<label class="fld">Process name<input id="wf_npName" placeholder="e.g. Jet · Soaping" oninput="WF.npSync()"></label>'
      +'<div class="row" style="gap:12px"><label class="fld" style="flex:1">Runs on machine<select id="wf_npMachine" onchange="WF.npSync()"></select></label><label class="fld" style="flex:1">Default time (min)<input id="wf_npTime" type="number" value="45" min="0"></label></div>'
      +'<div class="row" style="gap:12px"><label class="fld" style="flex:1">Batch-id letter<input id="wf_npLetter" maxlength="1" value="T" oninput="WF.npSync()"></label><div class="fld" style="flex:1"><label>Numbering</label><div class="wf-seg" id="wf_npPool"><button class="on" onclick="WF.npPool(0)">Per machine</button><button onclick="WF.npPool(1)">Pooled</button></div></div></div>'
      +'<div class="fld"><label>Icon</label><div class="wf-iconpick" id="wf_npIcons"></div></div></div>'
      +'<div class="m-f"><button class="btn ghost" onclick="WF.closeNp()">Cancel</button><button class="btn" onclick="WF.saveNp()"><span class="material-symbols-rounded">check</span>Add process</button></div></div>';
    d.addEventListener("click",()=>closeNp()); document.body.appendChild(d); }
}
function openWorkflowsModal(){
  if(!can("op_workflows")){ toast("You don't have the Workflows permission"); return; }
  injectCss();
  let ov=$("wfModal"); if(ov) ov.remove();
  ov=document.createElement("div"); ov.id="wfModal"; ov.className="modal-bg on";
  ov.innerHTML='<div class="modal wf-modalbox" onclick="event.stopPropagation()">'
    +'<div class="m-h"><h3><span class="material-symbols-rounded">account_tree</span>Workflows</h3><button class="x" onclick="WF.close()">&times;</button></div>'
    +'<div class="m-b wf-mb"><div id="wf_app"></div></div></div>';
  ov.addEventListener("click",closeModal); document.body.appendChild(ov);
  ensureSheets();
  PROCS=(DB.processTypes||[]).slice();
  shell(); buildPalette();
  const first=(DB.workflows||[])[0]; if(first) loadFlow(first.id); else newFlow();
  syncFlows();
}
function closeModal(){ const m=$("wfModal"); if(m) m.remove(); closeSheet(); closeNp(); }

window.openWorkflowsModal=openWorkflowsModal;
window.WF={ newFlow, loadFlow, onAssign, delFlow, saveFlow, delNode, addInput, setTime, npSync, npPool, closeNp, saveNp, close:closeModal };
})();
