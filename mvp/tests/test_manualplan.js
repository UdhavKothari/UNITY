const fs=require("fs"),vm=require("vm"),path=require("path");
const code=fs.readFileSync(path.join(__dirname,"..","static","app.js"),"utf8");
const ctx={console};
vm.createContext(ctx);
vm.runInContext(code,ctx);
vm.runInContext(`DB = {
  machines:[{id:"JET-2",type:"jet",capMax:400}],
  qualities:[{name:"CP",gsm:100,width:56,step3_mc:"jet",step3_time:120,dyeStep:3,step1_mc:"",step2_mc:"",step4_mc:""}],
  shadeRecipes:[], orders:[], lots:[], settings:{},
  batches:[
    {id:"B-1",machine:"JET-2",planDay:"2026-07-24",seq:2,quality:"CP",shadeNo:"0",lots:[{lotId:"L1",pcs:5,mtr:400,weight:200}]},
    {id:"B-2",machine:"JET-2",planDay:"2026-07-24",seq:1,quality:"CP",shadeNo:"0",lots:[{lotId:"L2",pcs:5,mtr:400,weight:200}]}
  ]};`,ctx);

vm.runInContext(`
const S=computeSchedule();
const blocks=S.tl["JET-2"].blocks.filter(b=>b.kind==="dye");
console.assert(blocks.length===2, "two dye blocks on JET-2");
console.assert(blocks[0].batch.key==="B-2", "seq1 (B-2) runs before seq2 (B-1)");
console.assert(blocks[0].batch.seq===1 && blocks[1].batch.seq===2, "blocks in seq order");
console.assert(blocks[0].start+blocks[0].mins<=blocks[1].start, "head-to-tail, no overlap on the machine");
console.assert(blocks[0].mins===180, "dye 120 + handling 60 = 180 min");
console.log("ok");
`,ctx);
