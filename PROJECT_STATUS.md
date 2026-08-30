# สถานะโครงการ: AI Nurse Scheduling System

อัปเดตล่าสุด: 9 สิงหาคม 2026

## สถานะใช้งานปัจจุบัน

ระบบเป็น **เว็บแอปจัดตารางเวร ICU แบบมี AI ช่วยตัดสินใจ** ไม่ใช่ระบบ Auto-publish โดย AI ทำหน้าที่สร้างตารางตัวอย่าง ตรวจเงื่อนไข และอธิบายผล ส่วน Head Nurse ยังเป็นผู้อนุมัติและเผยแพร่ตาม workflow ของโรงพยาบาล

### ผู้ใช้และสิทธิ์

| บทบาท | สิทธิ์หลัก |
|---|---|
| Admin | จัดการข้อมูลหลัก บุคลากร กฎ ICU และตารางเวร |
| Head Nurse | จัดการตาราง, สร้าง/ตรวจ/อนุมัติ AI Draft, เปิด Draft เพื่อแก้ไข และเผยแพร่ |
| Nurse | ดูตาราง ส่งคำขอลา และบันทึก preference/availability ของตน |
| Nurse Assistant | ดูตาราง ส่งคำขอลา และบันทึก preference/availability ของตน |

### Workflow ที่ใช้งานจริง

```text
ข้อมูลบุคลากร + เวร + วันลา + Availability + ICU Rules
                         ↓
                 AI Generate Preview
                         ↓
                Validate ด้วย ICU Validator
                         ↓
              Submit → Head Nurse Approve
                         ↓
       ส่ง AI Draft ลงตารางฉบับร่าง (แทน AI Draft เก่าได้)
                         ↓
        Manual Validate → Publish Validation Gate → Publish
```

- AI Preview ไม่เขียนข้อมูลตารางจริง
- AI Draft ที่อนุมัติแล้วส่งลงแทนได้เฉพาะ `AI_GENERATED` Draft เดิมเท่านั้น
- ตาราง Manual และตารางที่เผยแพร่แล้วจะไม่ถูก AI เขียนทับ
- หากต้องแก้ตารางที่เผยแพร่แล้ว ต้องเปิดเป็น Draft revision ก่อน และระบบบันทึก Audit Log

### กฎ ICU ที่สำคัญ

- หนึ่งคนมีได้ไม่เกินหนึ่งเวรต่อวัน
- Approved leave และ unavailable availability เป็น hard constraint
- `availability = ALL` หมายถึงไม่พร้อมทำงานทุกเวรในวันนั้น
- ตรวจ RN/PN/NA coverage, Senior RN, Incharge, overlap, rest หลัง N/DE และ D/DE continuation
- Preference เป็น soft constraint: AI พยายามทำตาม แต่ไม่บล็อกการจัดเวร
- Fairness, preference และ OT ใช้เป็น objective score
- Head Nurse เป็น Senior RN อัตโนมัติ และ AI/Manual Validator อนุญาตเฉพาะเวร `AM` หรือ `D` (สามารถลา/Off ได้)

## สิ่งที่ทำในวันนี้

### ความปลอดภัยและ UX

- เพิ่มการต่ออายุ JWT access token อัตโนมัติด้วย refresh token
- ปรับข้อความ Publish blocked ให้เป็นภาษาไทย พร้อมวัน เวร บุคลากร และสาเหตุที่ต้องแก้
- เพิ่มปุ่มกลับไปแก้ไขตารางจากผล Publish Validation
- เพิ่มข้อความอธิบาย Unavailable Date และ validation ของช่วงวันลา
- เพิ่มข้อความบอกชัดเจนว่า Manager เท่านั้นที่ตรวจ/เผยแพร่ได้ และตาราง Published ถูกล็อก

### Dashboard และข้อมูลเวรวันนี้

- หน้า Dashboard แสดงเวรของผู้ใช้ในวันนี้, เวลาเวร, Incharge และสถานะ Draft/Published
- Senior RN บน Dashboard คำนวณจากช่วงเวลาที่ทับซ้อนกัน ไม่จำกัดว่าต้องมี shift code เดียวกัน เช่น PM เห็น Senior ที่อยู่ D/DE ซึ่งครอบคลุมเวลาเดียวกัน

### Mobile App (Expo Go) — Phase 1

- เพิ่มแอป React Native ในโฟลเดอร์ `mobile/` ใช้ Expo Go ได้โดยไม่กระทบเว็บแอปเดิม
- รองรับ Login, Dashboard, เวรของฉันวันนี้ และรายชื่อ Senior RN ที่ครอบคลุมช่วงเวลาเวร
- กำหนด Backend URL ได้จากหน้า Login สำหรับใช้ผ่าน Wi-Fi เดียวกัน; ค่าเริ่มต้นเป็น `http://192.168.1.56:8001/api/v1`
- Mobile app เป็น read-only ใน Phase 1 เพื่อคง workflow Validate → Approval → Publish ของระบบ ICU

### Head Nurse และ AI Draft

- รวมกฎ `AM/D only` ของ Head Nurse เป็น business rule กลาง เพื่อไม่ให้ AI และ Manual Validator ใช้กฎคนละชุด
- เพิ่ม unit test ยืนยันว่า CP-SAT ห้าม Head Nurse ได้ PM/N/DE และอนุญาต AM/D
- ตรวจ AI Preview กับ Pilot data จริง: `FEASIBLE`, RN001 มีเฉพาะ `AM,D`, เวรต้องห้ามเป็น `0`
- เพิ่มปุ่มเปิด Published schedule กลับเป็น Draft revision พร้อม audit
- เพิ่มปุ่มล้างเฉพาะ PM/N/DE เก่าของ Head Nurse ใน Draft พร้อม audit; ระบบไม่แทนเวรแบบเดาสุ่ม
- เพิ่มปุ่ม `ส่ง AI Draft ลงตารางฉบับร่าง` หลัง Approve เพื่อแทน AI-generated Draft เก่าอย่างปลอดภัย

### Import และ Pilot Data

- รองรับตรวจและนำเข้าชุด Pilot data: staff, shift, ICU rules, leave, availability และ preference
- รองรับ `availability.shift_code = ALL` โดยบล็อกทุกเวรของบุคลากรในวันนั้น
- ใช้ employee code เป็น key และไม่จำเป็นต้องนำข้อมูลผู้ป่วยเข้าระบบ

### ผลการตรวจสอบล่าสุด

| รายการ | ผลลัพธ์ |
|---|---|
| Backend unit tests | ผ่าน 65 tests (ข้าม 6 integration tests เมื่อไม่มี test DB) |
| PostgreSQL pilot workflow integration | ผ่าน 6/6 ใน environment ทดสอบ; ปัจจุบัน test harness บังคับใช้ฐานชื่อ `_integration_test` เพื่อไม่ให้กระทบฐาน Pilot ที่เปิดในแอป |
| Frontend unit tests | ผ่าน 9 tests |
| Frontend production build | ผ่าน |
| AI Preview บน Pilot data | `FEASIBLE`; RN001 มีเฉพาะ AM/D |

### ข้อจำกัดที่ยังมี

- ฐานข้อมูลที่กำลังใช้เป็น Pilot/local development database ไม่ใช่ production hospital database
- การล้างเวร Head Nurse ที่ผิดกฎอาจทำให้ coverage ขาด จึงต้อง Generate AI Draft ใหม่และ Validate ก่อน publish
- ตารางที่เผยแพร่แล้วไม่ถูกแก้ไขโดยตรง เพื่อรักษา audit; ใช้ Draft revision แทน

## สรุปปัจจุบัน

ระบบอยู่ในสถานะ **Manual Scheduling MVP + ICU Rule Engine Foundation เสร็จสมบูรณ์ในระดับโค้ด** และ AI Scheduler มีครบตั้งแต่ **CP-SAT generation, preview, validation, human approval, conversion และ explanation/evaluation** แล้ว

ระบบ Manual รองรับการสร้าง แก้ไข ตรวจ conflict ตรวจสอบก่อนเผยแพร่ และเผยแพร่ตารางเวรได้ โดย Error จากกฎ ICU จะบล็อกการ publish ส่วน Warning จะถูกบันทึกพร้อมประวัติการอนุมัติ

AI Scheduler สร้าง **AI Preview** ผ่าน CP-SAT ได้แบบ read-only แล้ว และรองรับ flow: Generate → Validate ด้วย ICU Validator เดิม → Submit → Head Nurse Approve/Reject → Convert เป็น Manual Schedule Draft. ระบบไม่ auto-publish และ Manual Validation/Publish Gate ยังคงเป็นขั้นบังคับเสมอ

## สถานะตาม Phase

| Phase | สถานะ | รายละเอียด |
|---|---|---|
| Phase 1 — ICU Rule Configuration | เสร็จ | Staffing, shift, Senior RN, leave, preference, coverage และ ICU rules |
| Phase 1.5 — Manual Workflow & AI Readiness | เสร็จในระดับโค้ด | Conflict validator/UI, publish gate, approval state, validation history |
| Phase 2.0 — AI Scheduler Design | เสร็จ | เอกสาร architecture, input, constraints, scoring และ CP-SAT mapping |
| Phase 2.1 — AI Scheduler Skeleton | เสร็จ | Typed contracts, snapshot loader, preflight, CP-SAT dependency และ dry-run API |
| Phase 2.2.1 — Assignment Model Foundation | เสร็จ | สร้าง CP-SAT variables `x` และ `incharge` จาก snapshot แบบ dry-run |
| Phase 2.2.2 — Fixed/Locked Assignment | เสร็จ | บังคับ valid locked assignment เป็น `x=1` และรายงาน lock conflict |
| Phase 2.2.3 — Approved Leave | เสร็จ | Approved leave บังคับทุก shift เป็น `x=0`; pending/rejected/cancelled ไม่บังคับ |
| Phase 2.2.4 — Staffing + Coverage | เสร็จ | RN min/max และ PN/NA min ตาม coverage window/mapping จริง |
| Phase 2.2.5 — Senior RN + Incharge | เสร็จ | Senior RN coverage และ Incharge ที่ต้องเป็น Senior RN |
| Phase 2.2.6 — Rest + Overlap | เสร็จ | N/DE rest, real-time overlap, multiple-shift compatibility และ one assignment per staff/date |
| Phase 2.3 — Objective Optimisation | เสร็จ | Fairness, preference, OT และ weighted objective composition พร้อมแล้ว |
| Phase 2.4.1 — Solver Feasibility Dry Run | เสร็จ | Minimize/Solve แบบ read-only พร้อม status, runtime, objective และ diagnostics |
| Phase 2.4.2 — Draft Preview API | เสร็จ | ส่ง solved assignment, Incharge และ workload/OT summary แบบ read-only |
| Phase 2.4.3 — Draft Preview UI | เสร็จ | Manager-only Preview Mode, ตารางรายเดือน, Incharge, solver status และ workload summary |
| Phase 2.4.4 — AI Draft Validation | เสร็จ | Reuse Manual ICU validator กับ preview และแสดง Error/Warning/Passed result แบบ read-only |
| Phase 2.5 — Human Approval Integration | เสร็จ | AI draft storage, submit, Head Nurse approve/reject และ audit โดยไม่แตะ Manual Schedule |
| Phase 2.6 — Approved Draft Conversion | เสร็จ | Head Nurse แปลง AI Draft ที่อนุมัติเป็น Manual Schedule draft, revalidate และ audit โดยไม่ publish |
| Phase 2.5–2.6 — Human Review + Publish | Manual workflow พร้อมแล้ว | ใช้ Validate → Approve → Publish ที่มีอยู่ |
| Phase 3.1 — Simulation Benchmark | เสร็จ | ชุดข้อมูล ICU จำลอง 31 วันแบบ repeatable, CP-SAT benchmark, validator evaluation และ Markdown report โดยไม่เขียนข้อมูล production |
| Phase 3.2 — AI Explanation & Evaluation | เสร็จ | รายงาน fairness, night distribution, preference และคำอธิบายรายบุคคลจาก AI Preview แบบ read-only |
| Phase 3.3 — AI Workflow Integration Testing | เสร็จ | PostgreSQL integration 6/6 และ Playwright E2E 2/2 ผ่าน: Generate → Validate → Submit → Approve → Convert → Manual Validate → Publish |
| Phase 3.4 — Draft Revision & AI Draft Replacement | เสร็จ | เปิด Published เป็น Draft revision พร้อม audit, ล้างเวร Head Nurse ที่ผิดกฎ และแทน AI-generated Draft เดิมด้วย AI Draft ที่อนุมัติแล้ว |
| Phase 4.1 — Clinical Pilot Preparation | เสร็จในระดับเทคนิค | เพิ่มโมดูล read-only สำหรับ readiness/KPI/audit verification, checklist การทดลองใช้ และ tests โดยไม่เขียน production schedule |

## สิ่งที่ใช้งานได้แล้ว

### Manual Scheduling และ ICU Rule Engine

- Authentication ด้วย JWT และ role: `admin`, `head_nurse`, `nurse`, `nurse_assistant`
- จัดการ Staff, Department, Shift Type, Holiday, Leave และ Availability
- Senior RN: RN กำหนดได้, Head Nurse เป็น Senior RN อัตโนมัติ, PN/NA ถูกป้องกัน
- Head Nurse scheduling policy: AI และ Manual Validator อนุญาตเฉพาะเวร `AM` หรือ `D` (ลา/Off ได้ตามปกติ); Head Nurse ถูกนับเป็น Senior RN โดยอัตโนมัติ
- ICU Rules ต่อแผนก: `MIN_RN`, `MAX_RN`, `MIN_SUPPORT`, `REST_AFTER_NIGHT`, `MONTHLY_HOURS`, `OT_THRESHOLD`
- Staff preference และ unavailable date เป็น soft constraint
- ตารางเวรรายเดือนแบบ Manual พร้อมแก้ไข/ลบ assignment และ lock assignment
- ตารางที่เผยแพร่แล้วเปิดกลับเป็น Draft revision ได้เฉพาะ Admin/Head Nurse พร้อม Schedule Audit Log แล้วต้องตรวจและเผยแพร่ใหม่
- ICU conflict validator ตรวจ staffing, support, Senior RN, Incharge, leave, rest, overlap, D/DE, N/DE, coverage และ preference
- Conflict/Warning UI แยก severity พร้อม filter วันที่และ shift
- Publish validation gate:
  - Error → block publish, `validation_state=blocked`, `approval_state=rejected`
  - Warning only → publish ได้, `approval_state=approved_with_warnings`
  - บันทึก immutable validation history, ผู้ตรวจ, เวลา และจำนวน Error/Warning
  - แก้ไข draft แล้วต้อง validate ใหม่ก่อน publish

### AI Scheduler: Generation, Human Review และ Explanation

- [AI_SCHEDULER_DESIGN.md](AI_SCHEDULER_DESIGN.md) ระบุ architecture, input model, hard/soft constraints, objective, conflict handling และ CP-SAT mapping
- Google OR-Tools CP-SAT ติดตั้งใน backend แล้ว
- `app.scheduler.contracts` มี typed input/output contracts
- `app.scheduler.snapshot_loader` โหลด snapshot ของ `{department_id, year, month}` แบบ read-only
- `POST /api/v1/scheduler/dry-run` สำหรับ Admin/Head Nurse รายงาน snapshot summary และ preflight issues
- `CpSatSchedulerSolver` เรียก `Minimize(total_objective_cost)` และ `Solve` แบบ read-only; dry-run ไม่คืน assignment ส่วน Preview ส่ง assignment ชั่วคราวให้ผู้จัดเวรตรวจสอบ
- `AssignmentModelBuilder` สร้าง Boolean variables `x[staff,date,shift]` และ `incharge[staff,date,shift]` พร้อม AI Hard Constraint Core
- Locked assignment ที่ valid ถูกบังคับเป็น `x=1`; lock ที่ conflict หรืออยู่นอก snapshot จะแสดง infeasible reason ใน dry-run response
- Leave requests พร้อม status อยู่ใน snapshot; เฉพาะ approved leave เท่านั้นที่บังคับทุก `x` ของวันลาเป็น `0` และมี diagnostics สำหรับข้อมูลที่ใช้ไม่ได้
- Coverage windows พร้อมช่วงเวลาและ shift mappings อยู่ใน snapshot; ICU `MIN_RN`, `MAX_RN`, `MIN_SUPPORT` สร้าง staffing constraints สำหรับทุกวันและ window ที่ valid
- Incharge ต้องผูกกับ assignment และเป็น Senior RN; ทุก coverage window ต้องมี Senior RN ตามขั้นต่ำและ Incharge อย่างน้อยหนึ่งคน
- มี real-time rest/overlap constraints: ห้ามเวลาทับซ้อน, ต้องพักตาม `REST_AFTER_NIGHT` หลัง N/DE, และห้าม multiple shifts ที่มี gap หรือ D+DE ในคนเดียวกัน
- ทุก staff ถูกจำกัดด้วย hard constraint `sum(x[staff,date,*]) <= 1` จึงไม่สามารถได้ AM+PM หรือ PM+N ในวันเดียวกัน และ AI Draft แปลงเข้ากับ Manual Schedule ได้
- Fairness foundation คำนวณ assigned shift count, working minutes และ workload score จาก `x`; AM/PM/N มีน้ำหนัก 1.0 และ D/DE มีน้ำหนัก 1.5 พร้อม total workload imbalance expression
- Staff preferences สร้าง penalty variable/score แบบ soft: prefer ถูกปรับเมื่อไม่ได้เวร และ avoid ถูกปรับเมื่อได้เวร โดยไม่บังคับค่า assignment
- OT foundation คำนวณ `max(0, working_minutes - OT_THRESHOLD × 60)` ต่อบุคลากรและรวมเป็น OT penalty score โดยไม่บล็อก assignment
- Objective composition รวม penalty เป็น `total_objective_cost = 20×fairness + 10×preference + 10×OT` และ dry-run แสดง component/weight/term count เพื่อการอธิบายผลในอนาคต
- Solver dry run รายงาน `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN` หรือ `MODEL_INVALID` พร้อม objective, เวลา, ขนาดโมเดล และ diagnostics; กรณี infeasible มีการชี้ RN capacity shortage ที่ตรวจพบได้
- `POST /api/v1/scheduler/preview` ส่ง assignment preview ที่ CP-SAT เลือก พร้อม staff/date/shift/Incharge และ summary ของ workload/OT/objective โดยไม่บันทึกข้อมูล
- หน้า Manual Schedule มี Preview Mode สำหรับ Admin/Head Nurse: ปุ่ม Generate AI Draft, ตาราง preview รายเดือนแบบ read-only, `★` Incharge, summary และ diagnostics ตาม solver status
- AI Preview มีปุ่ม Validate AI Draft ซึ่ง reuse ICU validator เดียวกับ Manual Schedule และแสดง `passed`, `passed_with_warnings` หรือ `failed` พร้อม conflict format เดิม โดยไม่เขียนข้อมูล
- AI Draft ที่ผ่าน validation สามารถ Submit for Approval ได้; Head Nurse เท่านั้นที่ Approve/Reject ได้ พร้อมผู้กระทำ เวลา และเหตุผลการปฏิเสธ เก็บแยกใน `ai_schedule_drafts`/`ai_schedule_draft_details`
- Head Nurse สามารถ Convert เฉพาะ AI Draft ที่ Approved เป็น Manual Schedule `source=AI_GENERATED`; ระบบ copy Incharge, revalidate, audit และไม่ overwrite ตารางเดือนเดิม
- `POST /api/v1/scheduler/preview/explanation` และปุ่ม Explain AI Draft สร้างรายงาน fairness, night distribution, preference และคำอธิบายรายบุคคลจาก preview เดิม โดยไม่ solve ซ้ำหรือแก้ไขตาราง

## ข้อจำกัดของ AI ในปัจจุบัน

สิ่งต่อไปนี้ **ยังไม่ได้ทำโดยตั้งใจ**:

- ยังไม่มี PostgreSQL/browser end-to-end test ครบ workflow
- Night distribution เป็น diagnostic เท่านั้น ยังไม่ได้เป็น objective เพิ่มเติม
- Explanation อธิบายข้อมูลและ trade-off ที่ตรวจสอบได้จาก preview; ไม่อ้างว่าเป็นเหตุผลเชิงสาเหตุภายใน CP-SAT ที่พิสูจน์ไม่ได้
- ไม่มี auto-publish; การเขียน `schedule_details` เกิดขึ้นได้เฉพาะเมื่อ Head Nurse อนุมัติและสั่ง Convert เป็น Manual Schedule Draft แล้วเท่านั้น

## API สำคัญ

| Endpoint | หน้าที่ |
|---|---|
| `GET /api/v1/schedules/{id}/conflicts` | ตรวจ Error/Warning ของตาราง Manual |
| `POST /api/v1/schedules/{id}/publish` | ตรวจ ICU rules และ publish เมื่อไม่มี Error |
| `GET /api/v1/schedules/{id}/validation-history` | ดูประวัติ validation ก่อน publish |
| `POST /api/v1/scheduler/dry-run` | โหลด AI input snapshot แบบไม่แก้ไขข้อมูล |
| `POST /api/v1/scheduler/preview/explanation` | อธิบาย fairness, night, preference และ staff summary ของ AI Preview แบบ read-only |

## สถานะคุณภาพล่าสุด

| รายการ | สถานะ |
|---|---|
| Backend unit tests | ผ่าน (57 tests; integration tests skip เมื่อไม่ตั้ง test DB) |
| PostgreSQL integration tests | ผ่าน 6/6 กับ isolated `nurse_schedule_test` |
| Frontend unit tests | ผ่าน (9 tests) |
| Playwright E2E tests | ผ่าน 2/2 ด้วย Chromium และ isolated frontend/backend/test DB |
| Frontend production build | ผ่าน |
| FastAPI OpenAPI | ผ่าน (41 paths รวม AI Preview Explanation) |
| Alembic migration | `20260802_05` เป็น head |
| Full browser → API → PostgreSQL integration test | ยังไม่ทำ |

## งานถัดไปที่แนะนำ

1. ทดสอบ Manual Scheduling, conflict และ publish workflow ด้วยข้อมูล ICU จริงใน test environment
2. เตรียม Phase 4 Clinical Pilot: import ข้อมูลอ้างอิงที่ de-identify แล้ว, ยืนยัน ICU rules กับหัวหน้าหอ และเตรียม UAT

### Phase 4.1 — Pilot Dataset Validation (พร้อมใช้งาน)

- มีตัวตรวจสอบ Pilot workbooks ทั้งชุดก่อนเขียนฐานข้อมูล และคำสั่ง import ต้องระบุ `--apply` อย่างชัดเจน
- ใช้ `employee_code` เป็นคีย์ ไม่ต้องนำเข้าชื่อจริงหรือข้อมูลผู้ป่วย
- รองรับ Availability `ALL` เพื่อบล็อกทุกเวรของวันนั้น และ Availability แบบระบุเวรเพื่อบล็อกเฉพาะเวร
- CP-SAT นำ Availability สถานะ `unavailable` ไปเป็น hard constraint พร้อม diagnostic ที่อธิบายได้
3. Phase 3.1 simulation benchmark พร้อมใช้ผ่าน `python -m app.simulation.benchmark_runner`; ผลรอบล่าสุดอยู่ใน `SIMULATION_BENCHMARK.md` และอาจต่างกันเล็กน้อยเมื่อ solver หมดเวลาที่กำหนด
4. เปรียบเทียบ AI Preview กับตาราง Manual baseline และบันทึก KPI: conflict, เวลาจัดเวร, OT, night distribution และความพึงพอใจ
5. ใช้ Phase 3.2 explanation/evaluation ตรวจผลกับข้อมูลจำลองและข้อมูล ICU test environment
6. พิจารณาเพิ่ม Night-distribution objective หลังประเมิน benchmark และยอมรับเกณฑ์กับหัวหน้าหอแล้ว
7. คง Manual Validate → Publish workflow เป็นขั้นตอนบังคับหลัง AI generate

## เอกสารอ้างอิง

- [ICU Rule Configuration v1.1](docs/ICU_RULE_CONFIGURATION.md)
- [AI Scheduler Design](AI_SCHEDULER_DESIGN.md)
- [API Specification](API_SPEC.md)
- [งานถัดไป](NEXT_TASK.md)
