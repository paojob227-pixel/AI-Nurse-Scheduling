# ICU Schedule Mobile (Expo Go)

แอปมือถือ React Native สำหรับระบบ ICU Schedule เดิม โดยเริ่มจาก Login, ภาพรวม, เวรของฉันวันนี้ และรายชื่อ Senior RN ในช่วงเวลาที่เกี่ยวข้อง

## เริ่มใช้งานด้วย Expo Go

1. ติดตั้ง **Expo Go** บน Android หรือ iPhone
2. ให้โทรศัพท์และคอมพิวเตอร์อยู่ใน Wi-Fi เดียวกัน ตัวเปิดระบบจะเลือก IPv4 ของอะแดปเตอร์ Wi-Fi และส่งให้ Expo โดยอัตโนมัติ
3. เปิด Backend ให้รับการเชื่อมต่อในเครือข่าย (ตัวอย่าง IP เครื่องพัฒนา: `10.199.204.145`):

   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```

4. เปิด Metro/Expo:

   ```powershell
   cd mobile
   npx.cmd expo start --lan
   ```

5. เปิด Expo Go แล้วสแกน QR code ที่แสดงใน Terminal

## การตั้งค่า Backend

ค่าเริ่มต้นในหน้า Login จะอ่าน IP เดียวกับ Metro/QR โดยอัตโนมัติ เช่น `http://192.168.1.10:8001/api/v1` และยังสามารถแก้ไขจากช่อง **ที่อยู่ Backend** ได้ก่อนเข้าสู่ระบบ

> ห้ามใส่ `127.0.0.1` หรือ `localhost` บนมือถือ เพราะจะหมายถึงโทรศัพท์เอง ไม่ใช่คอมพิวเตอร์ที่รัน Backend

โปรเจกต์ใช้ Expo SDK 54 ดังนั้น Expo Go บน Android ต้องเป็นรุ่นที่รองรับ SDK 54 หาก Play Store ติดตั้งรุ่นใหม่กว่านี้ ให้ติดตั้งรุ่นที่ตรงจาก `https://expo.dev/go` หรืออัปเกรด SDK ของโปรเจกต์ก่อน

## ขอบเขต Phase 1

- อ่านข้อมูลเท่านั้น: Login, Dashboard, เวรวันนี้ และ Senior RN
- Token เก็บไว้ในหน่วยความจำของแอป; ออกจากแอปแล้วต้อง Login ใหม่
- ยังไม่อนุญาตให้สร้าง/แก้/เผยแพร่ตารางจากมือถือ เพื่อคง Manual Validate → Approval → Publish workflow เดิม
