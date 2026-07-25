const fs=require("fs"),vm=require("vm"),path=require("path");
const code=fs.readFileSync(path.join(__dirname,"..","static","app.js"),"utf8");
const ctx={console};
vm.createContext(ctx);
vm.runInContext(code,ctx);
vm.runInContext(`DB = {batches:[
  {id:"B-1",machine:"JET-2",seq:2},
  {id:"B-2",machine:"JET-2",seq:1},
  {id:"B-3",machine:"JET-3",seq:1},
  {id:"B-4",machine:"JET-2",seq:3},
],lots:[],machines:[{id:"JET-2",type:"jet",capMax:400}]};`,ctx);

vm.runInContext(`
const p=planBatches("JET-2");
console.assert(p.map(b=>b.id).join(",")==="B-2,B-1,B-4","sorted by seq across the machine (no day dimension)");
console.assert(nextSeq("JET-2")===4,"next seq 4");
console.assert(nextSeq("JET-9")===1,"empty machine next seq 1");
const r=reorderPlan(p,2,0);           // move B-4 to front
console.assert(r.map(b=>b.id+":"+b.seq).join(",")==="B-4:1,B-2:2,B-1:3","reordered+renumbered");
console.assert(mpCapacityOk("JET-2",380)===true,"380<=400 ok");
console.assert(mpCapacityOk("JET-2",420)===false,"420>400 blocked");
console.log("ok");
`,ctx);
