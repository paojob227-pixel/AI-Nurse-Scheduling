Hard Constraints

- คนลาห้ามลงเวร
- คนเดียวทำได้ 1 เวร/วัน
- Night ห้ามต่อ Morning
- ต้องมี RN อย่างน้อย 2 คน
- ต้องมี NA อย่างน้อย 1 คน
- จำกัด Night ไม่เกิน 8 ครั้ง/เดือน

Soft Constraints

- กระจาย Night ให้เท่ากัน
- กระจายวันหยุด
- Preference
- Fairness

Objective

Maximize fairness
Minimize OT
Balance workload

---

## Database readiness status

The database is prepared for the future scheduler according to ICU Rule Configuration v1.1. The scheduler implementation itself, including Google OR-Tools and constraint evaluation, has not been started.

Database inputs now available include Senior RN qualification, Incharge designation and exceptions, real-time coverage windows, shift duration/overnight metadata, department safety limits, shift preferences, and schedule audit logs.

## Manual validation status

The application now provides a read-only ICU v1.1 conflict validator for saved manual schedules. It reports safety and coverage errors or soft-preference warnings through `GET /api/v1/schedules/{id}/conflicts`. The Manual Schedule publish workflow runs the same validation, blocks any Error, permits Warning-only publication, and retains an immutable validation history. It does not select shifts, alter assignments, or use Google OR-Tools.
