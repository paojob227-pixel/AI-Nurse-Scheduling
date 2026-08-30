# AI Nurse Scheduling System

## Database Design

### Objective

ระบบ AI สำหรับจัดตารางเวรพยาบาลและผู้ช่วยพยาบาล
โดยสามารถจัดเวรอัตโนมัติ ลดภาระหัวหน้าหอผู้ป่วย และคำนึงถึงความยุติธรรมในการจัดเวร

---

# Main Modules

1. Authentication
2. Staff Management
3. Department Management
4. Shift Type Management
5. Leave Request
6. Shift Request
7. Schedule Management
8. AI Schedule Generator
9. Notification
10. Report

---

# Main Tables

- users
- staffs
- departments
- roles
- shift_types
- leave_requests
- shift_requests
- schedules
- schedule_details
- holidays
---

# users

ใช้เก็บบัญชีผู้ใช้

| Field | Type |
|--------|------|
| id | Integer |
| username | String |
| password | String |
| role | String |

---

# staffs

ใช้เก็บข้อมูลบุคลากร

| Field | Type |
|--------|------|
| id | Integer |
| employee_code | String |
| first_name | String |
| last_name | String |
| position | String |
| department_id | Integer |

---

# shift_types

ใช้เก็บประเภทเวร

| Field | Type |
|--------|------|
| id | Integer |
| name | String |
| start_time | Time |
| end_time | Time |