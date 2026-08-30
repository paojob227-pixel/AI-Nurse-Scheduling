import { FormEvent, useCallback, useEffect, useState } from "react";

import { api, User } from "../api";
import "../preferences.css";

type Shift = { id: number; code: string; name: string; is_working_shift: boolean };
type Staff = { id: number; employee_code: string; first_name: string; last_name: string };
type Preference = { id: number; staff_id: number; work_date: string; shift_type_id: number; preference: "prefer" | "avoid"; weight: number; reason: string | null };
type Availability = { id: number; staff_id: number; date: string; shift_type_id: number | null; status: string; reason: string | null };

const isManager = (user: User) => user.role === "admin" || user.role === "head_nurse";
const errorMessage = (error: unknown) => error instanceof Error ? error.message : "ไม่สามารถบันทึกข้อมูลได้";

export default function MyPreferencePage({ user }: { user: User }): JSX.Element {
  const manager = isManager(user);
  const [staff, setStaff] = useState<Staff[]>([]); const [shifts, setShifts] = useState<Shift[]>([]); const [staffId, setStaffId] = useState("");
  const [preferences, setPreferences] = useState<Preference[]>([]); const [availability, setAvailability] = useState<Availability[]>([]); const [error, setError] = useState("");

  const load = useCallback(async (selectedStaffId: string) => {
    setError("");
    const query = manager && selectedStaffId ? `?staff_id=${selectedStaffId}` : "";
    try {
      const [preferenceItems, availabilityItems] = await Promise.all([api<Preference[]>(`/staff-preferences${query}`), api<Availability[]>(`/availability${query}`)]);
      setPreferences(preferenceItems); setAvailability(availabilityItems.filter(item => item.status === "unavailable"));
    } catch (requestError) { setError(errorMessage(requestError)); }
  }, [manager]);

  useEffect(() => { api<Shift[]>("/shift-types").then(items => setShifts(items.filter(item => item.is_working_shift))).catch(requestError => setError(errorMessage(requestError))); if (manager) api<Staff[]>("/staff").then(setStaff).catch(requestError => setError(errorMessage(requestError))); }, [manager]);
  useEffect(() => { load(staffId); }, [staffId, load]);

  async function submitPreference(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement);
    try { await api("/staff-preferences", { method: "POST", body: JSON.stringify({ staff_id: manager ? Number(staffId) : undefined, work_date: form.get("work_date"), shift_type_id: Number(form.get("shift_type_id")), preference: form.get("preference"), weight: Number(form.get("weight")), reason: form.get("reason") || null }) }); formElement.reset(); await load(staffId); } catch (requestError) { setError(errorMessage(requestError)); }
  }

  async function submitUnavailable(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault(); const formElement = event.currentTarget; const form = new FormData(formElement);
    try { await api("/availability", { method: "POST", body: JSON.stringify({ staff_id: manager ? Number(staffId) : undefined, date: form.get("date"), status: "unavailable", reason: form.get("reason") || null }) }); formElement.reset(); await load(staffId); } catch (requestError) { setError(errorMessage(requestError)); }
  }

  const canEdit = !manager || Boolean(staffId);
  const shiftName = (shiftTypeId: number) => shifts.find(shift => shift.id === shiftTypeId)?.code ?? `Shift #${shiftTypeId}`;
  return <><h1>My Preference</h1><p className="muted">หน้านี้ใช้บันทึกทั้ง “ความต้องการ” และ “วันที่ไม่สามารถทำงานได้” เพื่อให้ระบบจัดเวรได้เหมาะสมและปลอดภัย</p><section className="preference-guide"><article><span className="guide-badge soft">Soft</span><div><strong>Shift Preference</strong><p>เป็นความต้องการ เช่น อยากได้เวรเช้า หรืออยากหลีกเลี่ยงเวรดึก ระบบจะพยายามทำตาม แต่ยังอาจจัดเวรนั้นได้หากจำเป็นเพื่อให้ ICU มีคนครบ</p></div></article><article><span className="guide-badge hard">สำคัญ</span><div><strong>Unavailable Date</strong><p>คือวันที่หรือเวรที่ “ไม่สามารถทำงานได้” ระบบจะไม่จัดเวรในขอบเขตที่ระบุ จึงควรบันทึกเฉพาะกรณีที่ไม่ว่างจริง</p></div></article></section>{manager && <section className="panel preference-filter"><label>ดูข้อมูลบุคลากร<select value={staffId} onChange={event => setStaffId(event.target.value)}><option value="">ทั้งหมด</option>{staff.map(person => <option key={person.id} value={person.id}>{person.employee_code} — {person.first_name} {person.last_name}</option>)}</select></label><p className="field-help">Admin และ Head Nurse เลือกดูหรือบันทึกข้อมูลแทนบุคลากรแต่ละคนได้</p></section>}{error && <p className="error">{error}</p>}<div className="preference-grid"><section className="panel"><h2>Shift Preference <span className="section-tag soft">Soft constraint</span></h2><p className="section-description">เลือกวันที่และเวรที่ต้องการ/ต้องการหลีกเลี่ยง แล้วระบุระดับความสำคัญ 1–5 โดย 5 สำคัญที่สุด</p>{canEdit && <form className="form-grid" onSubmit={submitPreference}><input name="work_date" type="date" aria-label="วันที่ต้องการ" required /><select name="shift_type_id" aria-label="เวรที่ต้องการ" required><option value="">เลือกเวร</option>{shifts.map(shift => <option key={shift.id} value={shift.id}>{shift.code} — {shift.name}</option>)}</select><select name="preference" aria-label="รูปแบบความต้องการ"><option value="prefer">ต้องการเวรนี้</option><option value="avoid">ต้องการหลีกเลี่ยง</option></select><select name="weight" defaultValue="1" aria-label="ระดับความสำคัญ"><option value="1">ความสำคัญ 1 — น้อย</option><option value="2">ความสำคัญ 2</option><option value="3">ความสำคัญ 3 — ปานกลาง</option><option value="4">ความสำคัญ 4</option><option value="5">ความสำคัญ 5 — สูงสุด</option></select><input name="reason" placeholder="เหตุผลหรือหมายเหตุ (ไม่บังคับ)" /><button>บันทึกความต้องการ</button></form>}<table><thead><tr><th>วันที่</th><th>เวร</th><th>ความต้องการ</th><th>น้ำหนัก</th><th /></tr></thead><tbody>{preferences.map(item => <tr key={item.id}><td>{item.work_date}</td><td>{shiftName(item.shift_type_id)}</td><td>{item.preference === "prefer" ? "ต้องการ" : "หลีกเลี่ยง"}</td><td>{item.weight}/5</td><td>{canEdit && <button className="small secondary" onClick={async () => { try { await api(`/staff-preferences/${item.id}`, { method: "DELETE" }); load(staffId); } catch (requestError) { setError(errorMessage(requestError)); } }}>ลบ</button>}</td></tr>)}</tbody></table></section><section className="panel unavailable-panel"><h2>Unavailable Date <span className="section-tag hard">ห้ามจัดเวร</span></h2><p className="section-description"><strong>วันไม่สะดวก</strong> ที่บันทึกจากฟอร์มนี้จะบล็อกเวรทุกประเภทของวันนั้น (AM, PM, N, D และ DE) ระบบยังรองรับรายการที่บล็อกเฉพาะเวรจากข้อมูลนำเข้า</p>{canEdit && <form className="form-grid" onSubmit={submitUnavailable}><input name="date" type="date" aria-label="วันที่ไม่สะดวก" required /><input name="reason" placeholder="เหตุผล เช่น พบแพทย์ / มีธุระ (ไม่บังคับ)" /><button>บันทึกวันไม่สะดวก</button></form>}<table><thead><tr><th>วันที่</th><th>ผลต่อการจัดเวร</th><th>เหตุผล</th><th /></tr></thead><tbody>{availability.map(item => <tr key={item.id}><td>{item.date}</td><td><span className="blocked-label">{item.shift_type_id ? `บล็อก ${shiftName(item.shift_type_id)}` : "บล็อกทุกเวร"}</span></td><td>{item.reason ?? "–"}</td><td>{canEdit && <button className="small secondary" onClick={async () => { try { await api(`/availability/${item.id}`, { method: "DELETE" }); load(staffId); } catch (requestError) { setError(errorMessage(requestError)); } }}>ลบ</button>}</td></tr>)}</tbody></table></section></div></>;
}
