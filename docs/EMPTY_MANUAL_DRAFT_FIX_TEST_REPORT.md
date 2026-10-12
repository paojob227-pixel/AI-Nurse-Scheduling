# ผลตรวจแก้ปัญหา AI Draft ลงตาราง Manual ว่าง

วันที่: 12 ตุลาคม 2026

## สาเหตุ

ตารางเดือนนั้นถูกสร้างเป็น `MANUAL` และมีสถานะ `draft` โดยยังไม่มี `schedule_details` แต่ service เดิมปฏิเสธตาราง Manual ทุกกรณี จึงไม่สามารถนำ AI Draft ที่อนุมัติแล้วลงตารางว่างได้

## การแก้ไข

- อนุญาตให้ approved AI Draft เติมตาราง Manual ที่ status เป็น draft, ไม่มี assignment และไม่มี published_at
- คง schedule ID เดิม เปลี่ยน source เป็น AI_GENERATED คัดลอกรายการเวร แล้วตรวจ ICU validation ซ้ำ
- บันทึก audit AI_DRAFT_CONVERTED พร้อม previous_source และ previous_assignment_count
- ยังป้องกัน Manual ที่มี assignment และตาราง published; Manual ที่เคยเผยแพร่และถูกเปิดใหม่ยังถูกป้องกัน
- รองรับทั้ง convert และ convert-replace-draft; การแทนที่ AI draft เดิมยังทำงานตามเดิม
- คงการตรวจสิทธิ์ Head Nurse และการ Publish เป็นขั้นตอนแยก
- ปรับคำอธิบายหน้าเว็บและ API documentation ไม่เปลี่ยน schema

## การทดสอบ

- Backend ทั้งชุดรวม PostgreSQL integration: 76/76 ผ่าน ไม่มี skipped ในรอบสุดท้าย
- เพิ่ม regression tests 7 กรณี ใช้ SQLite in-memory แยกทั้งหมด และ mock เฉพาะ validator ในการทดสอบ service
- PostgreSQL integration ใช้ cluster ใหม่เฉพาะ localhost และฐานข้อมูลชื่อลงท้าย `_integration_test`; apply migrations ถึง repository head
- Integration ครอบคลุม generate/validate/submit/approve/fill empty Manual/validate/publish, การแปลงซ้ำ, Manual ที่มีข้อมูล, สิทธิ์ Nurse, rejected draft และ publish gate
- Browser E2E ครอบคลุมสิทธิ์ผู้ใช้ และการสร้าง Manual ว่างก่อน Generate → Validate → Submit → Approve → ส่ง AI ลงตารางเดิม → Publish
- Frontend Vitest: 10/10 ผ่าน; TypeScript และ Vite production build ผ่าน
- Browser Playwright: 2/2 ผ่าน
- Mobile TypeScript และ Expo dependency compatibility check ผ่าน

## ขอบเขต

ผลข้างต้นยืนยันระบบในเครื่องและฐานข้อมูลจำลอง ไม่ใช่การทดสอบข้อมูลจริงบน Render และไม่ได้เปลี่ยนตารางเวร Production

การนำขึ้น Render ใช้ clone แยกของ repository เดิม และสิทธิ์ Git ที่บันทึกในเครื่อง เนื่องจาก GitHub connector ไม่เห็น repository เป้าหมาย ตรวจเฉพาะ diff ของ fix ก่อน push และตรวจ asset เวอร์ชันออนไลน์หลัง deploy

เมื่อนำไฟล์ขึ้น repository ที่ Render เชื่อมอยู่และ deploy สำเร็จ ให้ลองส่ง approved AI Draft เดิมลงตารางว่างอีกครั้ง ไม่ต้องลบตารางเดิมและไม่ต้องรัน migration สำหรับ fix นี้
