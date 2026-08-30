# ICU Clinical Pilot Checklist

เอกสารนี้ใช้เตรียมการทดลองใช้ AI Nurse Scheduling กับข้อมูล ICU โดยระบบยังคงเป็น decision-support: **ห้าม Auto-publish** และต้องผ่าน Human Approval กับ Manual Publish Gate ทุกครั้ง

## 1. Data verification

- [ ] ใช้ Pilot dataset ที่ผ่าน import validation แล้ว: staff, shift, ICU rules, leave, availability และ preference
- [ ] `employee_code` และ `shift_code` ทุกค่าอ้างอิงข้อมูลหลักที่มีอยู่จริง
- [ ] ช่วงวันที่อยู่ในเดือน Pilot ที่กำหนด และไม่มีข้อมูลนอกขอบเขตโดยไม่ตั้งใจ
- [ ] Approved leave, unavailable (รวม `ALL`) และ locked assignment ได้รับการตรวจทานโดย Head Nurse
- [ ] รัน Pilot Readiness Report ใน isolated test database และตรวจ Solver/Validator KPI

## 2. De-identification and privacy

- [ ] ไม่ใช้ชื่อผู้ป่วย, HN, เลขโรงพยาบาล, diagnosis หรือข้อมูลผู้ป่วยใด ๆ
- [ ] ใช้ `employee_code` สำหรับการเชื่อมข้อมูล; ลดชื่อบุคลากรให้น้อยที่สุดเท่าที่จำเป็นต่อการทดสอบ
- [ ] ได้รับอนุญาตจากหน่วยงาน/ผู้ควบคุมข้อมูลก่อนส่งออกหรือแชร์ผลรายงาน
- [ ] เก็บไฟล์ Pilot และผล benchmark ในพื้นที่ที่จำกัดสิทธิ์เข้าถึง

## 3. ICU rule freeze

- [ ] Head Nurse ยืนยันค่า MIN_RN, MAX_RN, MIN_SUPPORT, REST_AFTER_NIGHT, MONTHLY_HOURS และ OT_THRESHOLD
- [ ] ยืนยัน coverage windows และ mapping ของ AM/PM/N/D/DE
- [ ] ยืนยัน Senior RN/Incharge และนโยบาย Head Nurse (ขึ้นได้เฉพาะ AM/D)
- [ ] บันทึกวันที่/ผู้อนุมัติการ freeze กฎ และไม่เปลี่ยนกฎระหว่างเปรียบเทียบ AI กับ Manual baseline

## 4. AI workflow acceptance

- [ ] Admin/Head Nurse ทดสอบ Generate → Validate → Submit → Approve → Convert → Manual Validate → Publish บน database เฉพาะที่ลงท้าย `_integration_test` และไม่ใช่ฐาน Pilot ที่เปิดในแอป
- [ ] ยืนยันว่า AI Preview และ KPI report เป็น read-only และไม่สร้าง/แก้ไข production schedule
- [ ] ยืนยัน Error บล็อก Publish และ Warning สามารถบันทึกพร้อมเหตุผลได้
- [ ] ตรวจ audit evidence: generated_by, validated_by, approved_by, published_by และ timestamps
- [ ] เตรียมขั้นตอน Draft revision/rollback ก่อนเริ่ม Pilot

## 5. Clinical acceptance still required

ความพร้อมเชิงเทคนิคไม่ใช่การอนุมัติใช้งานจริง ต้องได้รับการยอมรับจาก Head Nurse, ผู้รับผิดชอบข้อมูล และหน่วยงานที่เกี่ยวข้องก่อนใช้ตารางในงานบริการจริง
