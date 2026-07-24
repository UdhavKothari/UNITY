const fs = require("fs"), vm = require("vm"), path = require("path");
const code = fs.readFileSync(path.join(__dirname, "..", "static", "app.js"), "utf8");
const ctx = { console };
vm.createContext(ctx);
vm.runInContext(code, ctx);
vm.runInContext(`DB = {
  lots: [{ id:"LOT-1", quality:"CP", customer:"REL", takas:[96,96,85,85,50], takaNos:[1,2,3,4,5] }],
  batches: [{ id:"B-1", lots:[{ lotId:"LOT-1", takas:[96], takaNos:[1] }] }]
};`, ctx);

vm.runInContext(`
const avail = lotTakaAvailability("LOT-1");
console.assert(avail.length === 5, "5 takas");
console.assert(avail[0].no === 1 && avail[0].used === true && avail[0].byBatch === "B-1", "taka 1 used by B-1");
console.assert(avail[2].no === 3 && avail[2].used === false, "taka 3 free");
console.assert(avail[2].meters === 85, "taka 3 is 85m");

const tot = takaSelectionTotals(DB.lots[0], [3,4]);
console.assert(tot.pcs === 2 && tot.mtr === 170, "selection 3+4 = 2pcs/170m");
console.assert(JSON.stringify(tot.takaNos) === "[3,4]", "takaNos preserved");
console.log("ok");
`, ctx);
