# ICU Rule Configuration Document

**Version:** Draft v1.1
**Last Updated:** July 2026
**Status:** Reviewed & Updated (Addressed Logical Contradictions & Safety Constraints)

---

## 1. ICU Information

### ICU Name
ICU รวม

### ICU Type
Mixed ICU

### Number of Beds
ยังไม่กำหนด (TBD)

### Number of Patients (Average)
ยังไม่กำหนด (TBD)

### Hospital Type
ยังไม่กำหนด (TBD)

### Description
เป็นหอผู้ป่วยวิกฤตแบบรวม (Mixed ICU) รองรับผู้ป่วยวิกฤตหลายประเภท เช่น อายุรกรรม ศัลยกรรม และผู้ป่วยภาวะวิกฤต

ระบบจัดตารางเวรอัตโนมัติ (AI Scheduler) ต้องรองรับบุคลากร 3 กลุ่มหลัก:
- **RN** (Registered Nurse)
- **PN** (Practical Nurse)
- **NA** (Nursing Assistant)

โดยระบบต้องคำนึงถึงจำนวนบุคลากรขั้นต่ำในแต่ละช่วงเวลา สัดส่วนระดับทักษะ (Senior RN) กฎการทำงานต่อเนื่อง และเวลาพักตามมาตรฐานความปลอดภัย

---

## 2. Staffing Requirement

### Registered Nurse (RN)
- **Minimum:** 3 คน / ช่วงเวลา
- **Maximum:** 4 คน / ช่วงเวลา
- **Rule:**
  - ทุกช่วงเวลาต้องมี RN อย่างน้อย 3 คน
  - หากมีอัตรากำลังเพียงพอ สามารถจัดเพิ่มเป็น 4 คนได้

---

### Support Staff (PN / NA)
- **Positions:** PN (Practical Nurse) และ NA (Nursing Assistant)
- **Minimum:** 1 คน / ช่วงเวลา
- **Rule:**
  - PN และ NA สามารถปฏิบัติงานแทนกันได้ (Fungible Role)
  - ไม่บังคับว่าต้องมี PN และ NA พร้อมกันในเวรเดียว

**ตัวอย่างโครงสร้างอัตรากำลังที่ถูกต้อง:**
- `RN 3 คน` + `PN 1 คน`
- `RN 3 คน` + `NA 1 คน`
- `RN 4 คน` + `PN 1 คน` (กรณีมีคนเพียงพอ)

---

## 3. Shift Configuration & Coverage Logic

### 3.1 Shift Types Definition
ระบบรองรับประเภท Shift ทั้งหมด 5 รูปแบบ:

| Shift Code | Name | Working Hours | Duration | Category |
| :---: | :--- | :---: | :---: | :---: |
| **AM** | Morning Shift | 07:00 - 15:00 | 8 ชั่วโมง | Normal Shift |
| **PM** | Afternoon Shift | 15:00 - 23:00 | 8 ชั่วโมง | Normal Shift |
| **N** | Night Shift | 23:00 - 07:00 | 8 ชั่วโมง | Normal Shift |
| **D** | Day Shift | 07:00 - 19:00 | 12 ชั่วโมง | Extended Shift |
| **DE** | Day Night Shift | 19:00 - 07:00 | 12 ชั่วโมง | Extended Shift |

---

### 3.2 Real-Time Shift Coverage Logic
ระบบ AI ต้องคำนวณและตรวจสอบสัดส่วนอัตรากำลังตาม **ช่วงเวลาจริง (Time Windows)** ไม่ใช่การนับเพียงรหัสชื่อเวร:

| Time Window | Applicable Shifts | Minimum Staffing Requirement |
| :---: | :---: | :--- |
| **07:00 - 15:00** | AM, D | RN $\ge$ 3, Support (PN/NA) $\ge$ 1 |
| **15:00 - 19:00** | PM, D | RN $\ge$ 3, Support (PN/NA) $\ge$ 1 |
| **19:00 - 23:00** | PM, DE | RN $\ge$ 3, Support (PN/NA) $\ge$ 1 |
| **23:00 - 07:00** | N, DE | RN $\ge$ 3, Support (PN/NA) $\ge$ 1 |

---

### 3.3 Special Coverage Rules

#### DE Coverage Rule
- Shift DE (19:00 - 07:00) ครอบคลุมช่วงเวลากลางคืนทั้งหมด
- หากช่วงเวลา 23:00 - 07:00 มีอัตรากำลังจาก DE ครบตาม Minimum Requirement แล้ว **ไม่จำเป็นต้องเพิ่ม Shift N**

#### PM and DE Overlap Rule
- อนุญาตให้มีบุคลากรขึ้น PM (15:00 - 23:00) และ DE (19:00 - 07:00) พร้อมกันในวันเดียวกันได้ โดยช่วงเวลา 19:00 - 23:00 จะนับกำลังคนสมทบจากทั้งสองเวร

#### D Continuation Rule
- หากมีการจัดบุคลากรขึ้น Shift D (07:00 - 19:00) **ต้องมีบุคลากรขึ้น Shift DE (19:00 - 07:00) รับช่วงต่อเสมอ**
- **บังคับ:** D และ DE ในช่วงเวลาคาบเกี่ยวนี้ **ต้องเป็นคนละบุคคล** (ห้ามจัดคนเดียวกัน)

---

## 4. Position & Qualification Rules

### 4.1 RN Incharge Requirement
- ทุกช่วงเวลาการทำงาน (AM, PM, N, D, DE) ต้องมี **RN Incharge** อย่างน้อย 1 คนเสมอ

### 4.2 Incharge Qualification
- ผู้รับหน้าที่ Incharge ต้องมีคุณสมบัติเป็น **Senior RN** เท่านั้น (RN ทั่วไปไม่สามารถทำหน้าที่ Incharge ในสภาวะปกติได้)

### 4.3 Senior RN Requirement
- ทุก Shift / ช่วงเวลา ต้องมี Senior RN อย่างน้อย 1 คน เพื่อปฏิบัติหน้าที่ Incharge และควบคุมมาตรฐานการดูแลผู้ป่วย

### 4.4 Senior RN Coverage Detail
- **8-Hour Shifts (AM / PM / N):** ต้องมี Senior RN ปฏิบัติงานเต็มช่วงเวลา
- **12-Hour Shifts (D / DE):** Senior RN สามารถปฏิบัติงานเต็ม 12 ชั่วโมงได้
- **Multiple Shifts:** Senior RN 1 คน สามารถทำ 2 Shifts ในวันเดียวกันได้ (เช่น AM + PM) แต่ต้องไม่ละเมิด Rest Time Rule

### 4.5 Exception Rule (กรณีวิกฤตขาดแคลน)
หากเกิดเหตุสุดวิสัยและไม่มี Senior RN ในเวร:
1. อนุญาตให้ RN ทั่วไปทำหน้าที่ Incharge ชั่วคราวได้
2. ระบบต้องแสดง **Warning Alert** ในหน้าตาราง
3. ต้องได้รับการอนุมัติ Manual Approve จากหัวหน้าหอผู้ป่วย (Nurse Supervisor)
4. ระบบต้องบันทึก Audit Log เหตุการณ์ลงในระบบ

### 4.6 Skill & Support Roles Rules
- **Skill Level (MVP):** ยังไม่นำ Special Skills (เช่น Ventilator, CRRT, ECMO) มาเป็น Hard Constraint ในระยะ MVP
- **PN / NA Rule:** ไม่แบ่งระดับ Skill ใช้แทนกันได้ตามอัตราส่วน Support Staff
- **Trainee / Student Rule:** ไม่อนุญาตและไม่มีนักศึกษาฝึกงานในระบบ AI Scheduler

---

## 5. Work Restriction & Safety Rules

### 5.1 Rest Time Rules (ข้อกำหนดเวลาพัก)
- **Rest Time After Shift:** หลังจบการทำงานทุกครั้ง ต้องมีเวลาพักต่อเนื่อง **ไม่อย่างนั้นจะไม่สามารถขึ้นเวรใหม่ได้**
- **Night Shift Rest Restriction:** หลังทำ Shift N (23:00 - 07:00) หรือ DE (19:00 - 07:00) ต้องมีเวลาพักอย่างน้อย **8 ชั่วโมง**
  - ❌ **ไม่อนุญาต:** N (23:00-07:00) ต่อ AM (07:00-15:00) ในวันเดียวกัน
  - ❌ **ไม่อนุญาต:** N (23:00-07:00) ต่อ D (07:00-19:00) ในวันเดียวกัน
  - ❌ **ไม่อนุญาต:** DE (19:00-07:00) ต่อ AM (07:00-15:00) ในวันเดียวกัน

### 5.2 Multiple Shift & Overlap Rules
- **PM + DE Same Person Rule (Resolved):** ❌ **ไม่อนุญาต** ให้บุคลากรคนเดียวกันขึ้น PM (15:00-23:00) ต่อด้วย DE (19:00-07:00) เนื่องจากเวลาทับซ้อนกัน 4 ชั่วโมง (19:00-23:00)
- **D Shift Restrictions:**
  - บุคลากรที่ทำ D (07:00-19:00) **ห้ามทำ PM (15:00-23:00)** ในวันเดียวกัน (เวลาทับซ้อน)
  - บุคลากรที่ทำ D (07:00-19:00) **ห้ามทำ DE (19:00-07:00)** ต่อในวันเดียวกัน
- **Shift Overlap Rule:** ห้ามมอบหมาย Shift ที่มีเวลาคาบเกี่ยวกันให้บุคลากรคนเดียวกัน
- **Shift Break Gap Rule:** หากทำ Multiple Shifts ในวันเดียวกัน **ห้ามมีช่วงว่าง (Gap) แล้วกลับมาทำใหม่**
  - ✅ **Allowed:** AM + PM (07:00-23:00), PM + N (15:00-07:00)
  - ❌ **Not Allowed:** AM $
ightarrow$ พัก $
ightarrow$ N, D $
ightarrow$ พัก $
ightarrow$ N

### 5.3 Fatigue & Workload Safety Limits (Recommended Safety Limits)
- **Max Consecutive Days:** แม้ไม่มีกฎหมายบังคับ แต่ AI Scheduler จะตั้งค่า **Soft Constraint ไม่เกิน 6 วันติดต่อกัน** (หากเกินจะเตือน Warning)
- **Max Consecutive Night Shifts:** ตั้งค่า **Soft Constraint ไม่เกิน 3 Night Shifts ติดต่อกัน** (N หรือ DE) เพื่อป้องกันความล้าของพยาบาล

### 5.4 Normal Working Hours & Overtime (OT)
- **Standard Workload:** 21 เวร / เดือน (168 ชั่วโมง / เดือน คำนวณจาก $21 	imes 8$ ชม.)
- **Overtime Rule:** ชั่วโมงที่เกิน 168 ชั่วโมง/เดือน จะถูกนับเป็น OT
- AI Scheduler สามารถจัด OT ได้โดยต้องแสดงผล คำนวณชั่วโมง OT และผ่านการอนุมัติจากหัวหน้า

---

## 6. Leave, Availability & Preferences

### 6.1 Leave Rules
- **Leave Types:** รองรับ Standard Leave (พักร้อน, กิจ, ป่วย) และ Custom Leave (ลาคลอด, อบรม, ประชุม)
- **Hard Constraint:** เมื่อ Leave ได้รับการอนุมัติแล้ว AI **ห้ามจัดเวรเด็ดขาด** (AM, PM, N, D, DE)
- **Leave Cancellation:** หากยกเลิกการลาหลัง Publish ตาราง ให้ใช้การปรับ Manual โดยหัวหน้า ระบบ AI จะไม่จัดตารางใหม่อัตโนมัติ

### 6.2 Availability & Preferences (Soft Constraints)
- **Unavailable Date:** บุคลากรระบุวันไม่สะดวก (ไม่ใช่วันลา) AI จะพยายามหลีกเลี่ยง
- **Shift Preference:** บุคลากรระบุ Preference (เช่น อยากขึ้น AM / ไม่ชอบ N)
- **Request Priority:** ใช้หลัก **First Come, First Served** เมื่อเกิดคำขอชนกัน
- **Availability Weight:** คำขอ Unavailable และ Preference ถือเป็น Soft Constraint หากจัดไม่ได้ ระบบจะใส่ Warning ให้หัวหน้าทราบ

### 6.3 Shift Swap Rule
- บุคลากรสามารถขอแลกเวรได้ แต่ระบบต้อง Validate กฎความปลอดภัยทั้งหมด (Position, Rest Rule, Incharge Requirement, Staffing Minimum) ก่อนอนุมัติ

---

## 7. Fairness & Workload Rules

### 7.1 Monthly Shift & Night Distribution
- AI ต้องกระจายจำนวนเวรต่อเดือนให้ใกล้เคียงกันมากที่สุด (Target Target Gap $\le \pm 1-2$ เวร)
- ไม่บังคับให้ Night / D / DE เท่ากันเป๊ะ แต่ให้กระจายตามความเหมาะสมและ Availability

### 7.2 Workload Score Calculation Formula
ระบบคำนวณ Workload Score เพื่อวัดความหนักเบาของงานรายบุคคล:

$$	ext{Workload Score} = \sum (	ext{Shift Base Weight}) + \sum (	ext{Combination Weight})$$

#### Base Weights:
- **AM Shift:** +1.0
- **PM Shift:** +1.0
- **N Shift:** +1.0
- **D Shift (12h):** +1.5
- **DE Shift (12h):** +1.5
- **OT Shift:** +1.0

#### Combination Extra Weights:
- **PM + N (Double Shift):** +2.0 Extra

---

## 8. AI Scheduler Objective & Priority Rules

### 8.1 Priority Order Engine

```
[Priority 1] Staffing Requirement (Min Staff & Coverage)
      ↓
[Priority 2] Hard Constraint Rules (Rest Time, Leave, Overlap, Restriction)
      ↓
[Priority 3] Senior RN & Incharge Qualification
      ↓
[Priority 4] Workload Fairness & Distribution
      ↓
[Priority 5] Staff Preferences & Availability (Soft Constraints)
      ↓
[Priority 6] Overtime (OT) Minimization
```

### 8.2 Objective Function Weight Score
คะแนนการตัดสินใจเลือกตารางที่ดีที่สุดของ AI (Total Score = 100%):

- **Staffing Coverage:** 40%
- **Rest Time & Hard Safety Rules:** 20%
- **Workload Fairness:** 20%
- **Staff Preferences:** 10%
- **OT Reduction:** 10%

### 8.3 Conflict Resolution & AI Recommendation
เมื่อเกิดสภาวะจัดตารางไม่ได้ (Unsatisfiable Scenario) AI จะ:
1. สร้างตารางที่สมบูรณ์ที่สุดเท่าที่เป็นไปได้
2. แสดง Alert Warning แจ้งจุดที่มีปัญหา
3. ระบบวิเคราะห์และแนะนำบุคลากรที่เหมาะสมที่สุดพร้อมเหตุผล (เช่น *แนะนำ RN001 เพราะชั่วโมงยังไม่ครบ พักผ่อนเพียงพอ ไม่ติดลา*)

---

## 9. Data Model & Output Requirements

### 9.1 Data Model Integration
- **Preference Data:** เก็บข้อมูล Wishlist ของพยาบาล
- **Leave Data:** Hard Constraint จากระบบ HR
- **Schedule Audit Log:** บันทึกทุกการแก้ไข Manual หลัง AI Generate (ผู้แก้, เวลา, ค่าก่อน/หลังแก้)

### 9.2 Output & View Specifications
- **Main View:** Monthly Interactive Calendar Grid
- **Reports:**
  - Conflict & Warning Report
  - Workload & Fairness Summary (Individual & Manager Dashboard)
- **Export Format:** `.xlsx` (Excel), `.pdf` (PDF Report)
- **Publish Workflow:** `AI Generate` $
ightarrow$ `Nurse Supervisor Review` $
ightarrow$ `Approve` $
ightarrow$ `Publish` $
ightarrow$ `Notification (Line/Email/Mobile)`
