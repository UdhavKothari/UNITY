const fs=require("fs"),vm=require("vm"),path=require("path");
const code=fs.readFileSync(path.join(__dirname,"..","static","app.js"),"utf8");
const ctx={console};
vm.createContext(ctx);
vm.runInContext(code,ctx);
vm.runInContext(`DB = {batches:[
  {id:"B-1",machine:"JET-2",planDay:"2026-07-24",seq:2},
  {id:"B-2",machine:"JET-2",planDay:"2026-07-24",seq:1},
  {id:"B-3",machine:"JET-3",planDay:"2026-07-24",seq:1},
  {id:"B-4",machine:"JET-2",planDay:"2026-07-25",seq:1},
],lots:[],machines:[{id:"JET-2",type:"jet",capMax:400}]};`,ctx);

vm.runInContext(`
const p=planBatches("JET-2","2026-07-24");
console.assert(p.map(b=>b.id).join(",")==="B-2,B-1","sorted by seq");
console.assert(nextSeq("JET-2","2026-07-24")===3,"next seq 3");
console.assert(nextSeq("JET-9","2026-07-24")===1,"empty machine next seq 1");
const r=reorderPlan(p,1,0);           // move B-1 to front
console.assert(r.map(b=>b.id+":"+b.seq).join(",")==="B-1:1,B-2:2","reordered+renumbered");
console.assert(mpCapacityOk("JET-2",380)===true,"380<=400 ok");
console.assert(mpCapacityOk("JET-2",420)===false,"420>400 blocked");
console.log("ok");
`,ctx);
