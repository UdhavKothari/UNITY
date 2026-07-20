# RAW PLAN — transcript of the handwritten design pages

Transcribed from `raw_plan/PXL_20260716_*.jpg` (10 pages). Kept close to the original wording; `[?]` marks uncertain handwriting, `~~struck~~` marks crossed-out text.

---

## Page 1 — INFO TABLES (`060533121`)

1. **Machine Master** — MC ID | MC Name | Type | Capacity (Min, Max) | Last Maintenance | Scheduled Maintenance | Company
2. **Machine Schedule** — MC ID/Name | Batch ID | Planned Start | Planned End | Actual Start | Actual End
3. **Order Master** — Order ID | Customer (ID) | Fabric | Quantity | Shade | Due Date | Priority | Shade Family | Quality | Planning | Inward Exp. | Received
4. **Customer Master** — Cust Name | Contact No. | Contact Name | Address | Cust ID
5. **Batch Master** — Batch ID | Order ID | Fabric | Shade | Shade Family | Qty | ~~Recipe ID~~ | Quality | **Taka No.** | Location Info → Area Name, Row, Column, Shelf
6. **Quality Master** — Quality Name | **Step 1 MC1 (Type) | Step 2 MC2 (Type) | Step 3 MC3 (Type) | Step 4 MC4 (Type)** | MC1 Max Batch | MC1 Time | MC2 Time | MC3 Time | MC4 Time
   > **Note: four machine steps per quality, not three.**
7. **Storage Area Master** — Area Name | Area Capacity | Shelf | Row | Column | Area Location X | Area Location Y | Floor No.
8. **Shade Master (Colours)** — Quality | Shade | Dye 1 | Dye 2 | Dye 3 | Program % (Dye 1) | Dye 2 | Dye 3
9. **Recipe Master** — Quality | Shade | Mixing Chemical 1 | Mixing Chem 2 | Mixing Chem 3 | 4 | 5 | 6 | M/C (Jigger, Jet Dye, Stenter) — plus Shade Family, Shade, Tone
10. **User Info** — Username | Pass | AUTH | ROLE
11. **Batch Master (detail)** — Batch code | Taka 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 … 30 | Shade (Fin. shade) | Quality; second row: MC1 Time Act | MC2 TA | MC3 TA | MC4

---

## Page 2 — INDIVIDUALS (roles) (`060543990`)

1. Security Office — Inwards & Weighing Tally
2. Order Inputs — PC Terminal (Office) → **Sales**
3. Operators — (JIGGER) → (JET) → (STENTOR)
4. Supervisors (Floor) — **JJS**
5. Inward Storage Manager
6. RFD Storage Manager
7. Store Manager
8. QC Manager
9. Maintenance Manager
10. Batcher
11. R&D Manager

---

## Page 3 — SALES INT (WebApp) + USER XP (`060554738`)

Header: *Software Working — SALES INT (WebApp)* — Input Fields: **Order Input Field | Customer Info Field**

**USER XP**

- **[Sales]** → Order Req. Form (Customer Info, Sh–, Qty, Quality) and Customer Info Form (Cust: ____ , update buttons). *Req: PC Terminal*
- **[Security Office]** → upload challan photo → (screen). *Req: PC Terminal + Hand Scanner*
- **[Operator]** — three screens, *Req: Phone + PC Terminal on floor*:
  - **JIGGER** — JIGGER-01 | Batch [____] [scan]
  - **JET** — JET-01 | Batch [____] [scan] | Instructions … | Program Name
  - **STENTOR** — ST-01 | Batch [____] [scan] | Instructions … | Programme Name

---

## Page 4 — USER XP continued (`060604817`)

- **[Supervisor]** — LAYOUT OF SHOP FLOOR with M/C Status Indicators. *Req: PC Terminal + Phone*
- **[Storage Manager]** — *Everything is logged, neat, clean & correctly placed.* *Req: Phone*
- **[QC Manager], [R&D]** → Enters Recipes, Colour Details. *Req: PC Terminal*
- **[Maintenance]** → Logs M/C Maintenance → Gets Periodic Notifications / M/C → Enters M/C Data. *Req: Phone*

---

## Page 5 — SOFTWARE LOGIC (`060615042`)

**Step 1 — Order Input**

| Tables Required | Affected |
|---|---|
| Order Master, Customer Master, Machine Master, Machine Schedule, Storage | ALL + QC Master |

Logic:
1. Splits into required batches of Max. Batch Limits / Machine.
2. Looks at Schedule Chart → creates Temporary Table.

Example: Order = 6000 m in 5 shades → splits into 1200 m × 5 batches.

**[INWARD SCAN LOGIC]**

Logic:
- Looks at Schedule Chart; creates Temporary Table for when each machine is free next.
- Takes decision based on **priority**:
  1. Next 8 hours is not full
  2. Urgent Order (1, 2, 3)
  3. Shade Family Match
  4. Lighter / Darker
  5. Due Date

Example temp table → `MC No. | Type | Free Next (estimated time) | Shade Family | Colour Tone`

Flow: POSCH[?] Table → "Next 8 hrs free?" → Yes → … ; No → wait 4 hrs → (shade family check) → Yes → …

> *Can we add between batches of same Shade Family based on colour tone?*

---

## Page 6 — Step 2, LOGIC TABLE [M/C selection] (`060628247`)

Info Req.: Order, Machine, Schedule, Storage, Dye.

Flowchart:
- **Start** → *Check if everything is in stock?*
  - **No** → ALERT STORE MANAGER → NOTIFY SALES TEAM / ORDER PUNCH PC → CHANGE DELIVERY DATE (+3 DAYS) → END
  - **Yes** → *M/C Available 8 hrs?*
    - **No** → "Scheduled +3 Days, Order Logged"
    - **Yes** → *Shade Family Check* → Darker / Lighter → *Schedule Batch Available?*
      - **No** → "Scheduled +3 Days, Order Logged"
      - **Yes** → "Scheduled +2 Days, Order Logged" → END

Notes:
1. Sort by M/C Type ← JIG / JET / STEN ← Shade Families
2. Estimated Time (T+) All M/C's + 20% → Delivery Time Given

---

## Page 7 — SOFTWARE WORKING, Steps 1–6 (`060654569`)

**Step 1 — Order Input**
- *Inputs:* Customer Name, Fabric Quality, Quantity, Shade, Delivery Date, Priority
- *Working:* Logs order → gives Shade Family → makes Batch Draft; allocates space inside shed
- *Output:* Order Logged; **ORDER ID SLIP** → Order ID, Qty, Batch Nos Allocated
- *Physical action:* Printed slip to be placed on allotted space

**Step 2 — Goods Inward**
- *Inputs:* Delivery Challan No., Quantity, Item Name (Quality), Due Date, Order ID
- *Working:* Looks at current M/C's → looks for empty M/C's → looks at Recipe → creates Route → maps
- *Output:* Creates Shikar[?] Slip; **Creates Lot with Taka No.**
- *Physical action:* Movers move to Inward Shed

**Step 3 — Storing Goods**
- *Input:* Taka No. entry in / good of gate slip / storage shed
- *Working:* Machine allocates Taka No. to the specific storage location; creates Batching possibilities
- *Output:* PC Terminal displays allocated space; adds to 24 hr / 48 hr flow
- *Physical action:* Taka moved to specified location

**Step 4 — Batching**
- *Input:* Taka No.
- *Output:* Prints **Program Slip**; Lights/Screen placed on M/C, displays M/C code
- *Working:* updates as soon as 24 hr mask is hit → starts to update schedule
- *Physical action:* Batched Taka is transported to Machine

**Step 5 — Jigger**
- *Inputs:* Production Slip, Operator ID, Chemical Slip
- *Working:* Operator scans ID; looks at Program set in the PLC; loading of fabric into M/C
- *Output:* gets updated in PC display; Loading → On; PLC Automation
- *Physical action:* Green light for operator to load fabric

**Step 6 — Jet Dyeing**
- *Inputs:* (NFC card), Operator ID
- *Working:* Updates automatically as PLC Automation has kicked in; records IN & OUT time and looks for expected time
- *Physical action:* Off-loads fabric; turns on Jigger for scouring; operator checks anything

---

## Page 8 — SOFTWARE WORKING, Steps 7–10 (`060707210`)

**Step 7 — Hydroextractor**
- *Input:* Batch ID, Operator ID
- *Working:* updates batch progress in PC Terminal in office
- *Output:* N/A — *Physical action:* operator places inside hydroextractor

**Step 8 — Rope Opener** — same as Hydro-Extractor

**Step 9 — Stentor** — same as Stentor / Rope-Opener

**Step 10 — QC**
- *Input:* Order ID, Taka No., Metrics set by QC
- *Working:* updates, keeps track — constant tracking
- *Output:* Pass / Fail (N/A) — keeps inward track
- *Physical action:* QC checks / Test → Input into software

---

## Page 9 — SLIPS (`060714453`)

**Order Slip** — office use only. Used twice only (Inward = Outward). Will have both input shape & output shape.

**Production Slip** — *travels with the **lot** (stuck on trolley)*
- Stuck to container / trolley; trolley will have a lid
- Goods to not be stored in different trolley
- Small but long strip — can be cut & pasted onto trolley / knotted on stitching
- Guidelines / SOP checklist
- 1 → Dye Required sticker printed with Batch ID on it
- 1, 2, 3 → for JIGGER, JET DYE, STENTOR, Finishing M/C's
- Fields: Batch ID | Inward Fabric | Machines (Date In / Out) | Temp | pH | Guidelines
- Photo of fabric can also be printed on the back for crosschecks by operator

**Chemical Slip** — Batch ID | MC No. | Shade | Dye | Program Name | Exposure[?] | Program Time

**Production Slip (detail)** — Batch ID | Inward Fabric | Taka Information | M/C No. required steps (Scour, Batch ID) | MC No. required steps (Dye, Batch ID) | MC No. required steps (Stentor, Batch ID) | Dye Info (colour of Roll / shade) — with **QR codes** per step
- Stuck to container / trolley → Trolley = Batch ID
- Different processes will have different departments
- Departments can complete their work, remove & store the slip for physical evidence

---

## Page 10 — INFO TABLES (2) (`060723419`)

- **Operator Master** — ID / Name | Contact | Machine Auth 1 | 2 | 3 | Batches logged … | No. of batches | (Batch ID)
- **QC Master** — Batch ID | Taka No. | metrics set by QC score … | cracking | date/batch | Pass / Fail
- **Storage Master (store/stock)** — Item | Supplier | Contact (→ Phone No., → Name) | Last 5 rates | Current stock | Next 24 hr req. | Procurement size

---

## Things the raw plan already anticipated (worth re-reading before each feature)

- **Four machine steps per quality** (MC1–MC4) — stentor sits after dyeing.
- **Lot with Taka No.** created at goods-inward; the Production Slip *travels with the lot* on the trolley.
- **Machine maintenance**: Last Maintenance + Scheduled Maintenance columns already in Machine Master.
- **Urgent order priority (1, 2, 3)** is step 2 of the inward-scan priority cascade.
- **Actual Start / Actual End** on Machine Schedule — the hook for real-time tracking later.
- QR codes per process step on the Production Slip — the hook for scanning-based live location.
