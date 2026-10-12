# งานถัดไป: AI Nurse Scheduling System

อัปเดต: 12 ตุลาคม 2026

## แก้ไขล่าสุด: ส่ง AI ลงตาราง Manual ที่ยังว่าง

รองรับตารางฉบับร่าง Manual ที่ไม่มี assignment และไม่เคยเผยแพร่ โดยใช้ schedule ID เดิม ตรวจ validation ซ้ำ และเก็บ audit ก่อนเผยแพร่ตาม workflow ปกติ ตาราง Manual ที่มีข้อมูลและตารางเผยแพร่ยังถูกป้องกัน

เตรียมนำขึ้น Render ผ่าน repository เดิมโดยใช้สิทธิ์ Git ที่บันทึกในเครื่อง และตรวจเวอร์ชันออนไลน์หลัง deploy

## สถานะปัจจุบัน

ระบบ Manual Scheduling, ICU Rule Engine, AI CP-SAT Scheduler, AI Preview, Validation, Human Approval, Draft conversion/replacement และ Publish Gate ทำงานครบในระดับ Pilot แล้ว

AI เป็น **decision-support**: ห้าม auto-publish และต้องคง Manual Validate → Publish workflow เสมอ

## ลำดับงานที่ควรทำต่อ

### Phase 4.1 — Clinical Pilot Preparation

เสร็จในระดับเทคนิคแล้ว: มี `app.pilot_preparation` สำหรับสร้าง readiness report, KPI และตรวจ audit แบบ read-only รวมทั้ง [Clinical Pilot Checklist](docs/CLINICAL_PILOT_CHECKLIST.md)

สิ่งที่ต้องยืนยันกับหน่วยงานก่อนเริ่ม Pilot:

1. ยืนยัน Pilot dataset แบบ de-identified กับ Head Nurse/ผู้ควบคุมข้อมูล
2. Freeze ค่า ICU Rules ก่อนทดลอง เช่น MIN_RN, MIN_SUPPORT, REST_AFTER_NIGHT, OT_THRESHOLD
3. สร้าง baseline ตาราง Manual ของเดือนเดียวกัน เพื่อเปรียบเทียบกับ AI
4. ลงนามยอมรับ KPI: เวลาในการจัดตาราง, errors, warnings, OT, fairness, night distribution และ preference satisfaction

### Phase 4.2 — User Acceptance Test

1. ให้ Head Nurse ทดลอง Generate → Validate → Approve → ส่งลง Draft → Publish
2. ให้ Nurse/NA ทดลองดูเวร ส่ง leave, preference และ unavailable date
3. เก็บ feedback เรื่องความเข้าใจคำอธิบาย AI, ความง่ายในการใช้งาน และความยอมรับของตาราง

### Phase 4.2.1 — Mobile UAT (Expo Go)

เสร็จในระดับ Mobile Phase 1: มีแอป Expo Go แบบ read-only ใน `mobile/` สำหรับ Login, Dashboard, เวรวันนี้ และ Senior RN

ก่อนใช้งานจริง ให้ทดสอบกับโทรศัพท์บน Wi-Fi ของหน่วยงาน และกำหนดค่า Backend URL/Firewall ให้เข้าถึงได้เฉพาะเครือข่ายที่อนุญาต

งานถัดไปหลัง UAT คือกำหนดสิทธิ์และ UX สำหรับ mobile self-service เช่น ดูตารางรายเดือน, ส่ง leave และ preference โดยยังไม่เปิดการ Publish จากมือถือ

### Phase 4.3 — Production Readiness

1. ย้ายจาก local Pilot database ไป PostgreSQL environment ที่ดูแลจริง พร้อม backup/restore
2. เปลี่ยนรหัสผ่านทดสอบร่วมกันเป็นบัญชีรายบุคคล และเพิ่มเปลี่ยนรหัสผ่าน/บังคับ password policy
3. ตั้งค่า `JWT_SECRET_KEY`, `STAFF_INITIAL_PASSWORD`, CORS และ Docker environment ให้ปลอดภัย
4. รัน PostgreSQL integration tests และ Playwright E2E กับ environment แยก `_test` ก่อน deploy
5. เพิ่ม monitoring, error logging และแผน rollback สำหรับ Draft revision

## สิ่งที่ไม่ควรทำในตอนนี้

- ห้าม auto-publish ตารางจาก AI
- ห้ามเพิ่ม objective/constraint ใหม่โดยไม่ยืนยันกับ Head Nurse และทดสอบ benchmark
- ห้ามใช้ข้อมูลระบุตัวตนผู้ป่วยใน Pilot dataset
- ห้ามให้ AI เขียนทับ Manual หรือ Published schedule โดยไม่มี approval และ audit
