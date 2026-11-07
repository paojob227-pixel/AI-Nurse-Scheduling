import { FormEvent, useCallback, useEffect, useState } from "react";

import { api, User } from "../api";
import "../preferences.css";

type Shift = { id: number; code: string; name: string; is_working_shift: boolean };
type Staff = { id: number; employee_code: string; first_name: string; last_name: string };
type Preference = {
  id: number;
  staff_id: number;
  work_date: string;
  shift_type_id: number | null;
  preference: "prefer" | "avoid";
  weight: number;
  reason: string | null;
};

const isManager = (user: User) => user.role === "admin" || user.role === "head_nurse";
const errorMessage = (error: unknown) => {
  const message = error instanceof Error ? error.message : "ไม่สามารถบันทึกข้อมูลได้";
  if (message === "This identical preference already exists" || message === "An all-day unavailable preference already exists for this date") {
    return "วันนี้บันทึกว่าไม่พร้อมขึ้นเวรไว้แล้ว";
  }
  return message;
};

export default function MyPreferencePage({ user }: { user: User }): JSX.Element {
  const manager = isManager(user);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [staffId, setStaffId] = useState("");
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [error, setError] = useState("");
  const [selectedPreference, setSelectedPreference] = useState<"prefer" | "avoid">("prefer");
  const [selectedWeight, setSelectedWeight] = useState(1);
  const [selectedShiftId, setSelectedShiftId] = useState("");

  const load = useCallback(async (selectedStaffId: string) => {
    setError("");
    const query = manager && selectedStaffId ? `?staff_id=${selectedStaffId}` : "";
    try {
      setPreferences(await api<Preference[]>(`/staff-preferences${query}`));
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }, [manager]);

  useEffect(() => {
    api<Shift[]>("/shift-types")
      .then(items => setShifts(items.filter(item => item.is_working_shift)))
      .catch(requestError => setError(errorMessage(requestError)));
    if (manager) {
      api<Staff[]>("/staff").then(setStaff).catch(requestError => setError(errorMessage(requestError)));
    }
  }, [manager]);

  useEffect(() => {
    load(staffId);
  }, [staffId, load]);

  async function submitPreference(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const preference = String(form.get("preference"));
    const weight = Number(form.get("weight"));
    const isUnavailable = preference === "avoid" && weight === 5;
    try {
      await api("/staff-preferences", {
        method: "POST",
        body: JSON.stringify({
          staff_id: manager ? Number(staffId) : undefined,
          work_date: form.get("work_date"),
          shift_type_id: isUnavailable ? null : Number(form.get("shift_type_id")),
          preference,
          weight,
          reason: form.get("reason") || null,
        }),
      });
      formElement.reset();
      setSelectedPreference("prefer");
      setSelectedWeight(1);
      setSelectedShiftId("");
      await load(staffId);
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  async function deletePreference(preferenceId: number): Promise<void> {
    try {
      await api(`/staff-preferences/${preferenceId}`, { method: "DELETE" });
      await load(staffId);
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }

  const canEdit = !manager || Boolean(staffId);
  const isUnavailableRequest = selectedPreference === "avoid" && selectedWeight === 5;
  const shiftName = (shiftTypeId: number | null) => shiftTypeId === null
    ? "ทุกเวร"
    : shifts.find(shift => shift.id === shiftTypeId)?.code ?? `Shift #${shiftTypeId}`;

  return <>
    <h1>บันทึกความต้องการ</h1>
    <p className="muted">บันทึกความต้องการก่อนจัดตารางเวร โดย “หลีกเลี่ยง” ความสำคัญ 5 จะเป็นวันไม่พร้อมขึ้นเวร</p>

    <section className="preference-guide">
      <article>
        <span className="guide-badge soft">Soft</span>
        <div>
          <strong>ความสำคัญ 1–4</strong>
          <p>ระบบจะพยายามทำตามความต้องการของเวรที่เลือก แต่ยังอาจจัดเวรนั้นได้หากจำเป็นเพื่อให้ ICU มีคนครบ</p>
        </div>
      </article>
      <article>
        <span className="guide-badge hard">ห้ามจัดเวร</span>
        <div>
          <strong>หลีกเลี่ยง + ความสำคัญ 5</strong>
          <p>ระบบจะถือว่าคุณไม่พร้อมทำงานตลอดวัน และจะไม่จัดเวร AM, PM, N, D หรือ DE ในวันนั้น</p>
        </div>
      </article>
    </section>

    {manager && <section className="panel preference-filter">
      <label>ดูข้อมูลบุคลากร
        <select value={staffId} onChange={event => setStaffId(event.target.value)}>
          <option value="">ทั้งหมด</option>
          {staff.map(person => <option key={person.id} value={person.id}>{person.employee_code} — {person.first_name} {person.last_name}</option>)}
        </select>
      </label>
      <p className="field-help">Admin และ Head Nurse เลือกดูหรือบันทึกข้อมูลแทนบุคลากรแต่ละคนได้</p>
    </section>}

    {error && <p className="error">{error}</p>}

    <div className="preference-grid">
      <section className="panel">
        <h2>บันทึกความต้องการ</h2>
        <p className="section-description">เลือกวันที่ ความต้องการ และระดับความสำคัญ หากเลือก <strong>หลีกเลี่ยง + ความสำคัญ 5</strong> ระบบจะบล็อกทุกเวรของวันนั้นโดยอัตโนมัติ</p>
        {canEdit && <form className="form-grid" onSubmit={submitPreference}>
          <input name="work_date" type="date" aria-label="วันที่ต้องการ" required />
          <select name="shift_type_id" aria-label="เวรที่ต้องการ" value={isUnavailableRequest ? "" : selectedShiftId} onChange={event => setSelectedShiftId(event.target.value)} required={!isUnavailableRequest} disabled={isUnavailableRequest}>
            <option value="">{isUnavailableRequest ? "บล็อกทุกเวรโดยอัตโนมัติ" : "เลือกเวร"}</option>
            {shifts.map(shift => <option key={shift.id} value={shift.id}>{shift.code} — {shift.name}</option>)}
          </select>
          <select
            name="preference"
            aria-label="รูปแบบความต้องการ"
            value={selectedPreference}
            onChange={event => {
              const preference = event.target.value as "prefer" | "avoid";
              setSelectedPreference(preference);
              if (preference === "prefer" && selectedWeight === 5) setSelectedWeight(4);
            }}
          >
            <option value="prefer">ต้องการเวรนี้</option>
            <option value="avoid">ต้องการหลีกเลี่ยง</option>
          </select>
          <select name="weight" value={selectedWeight} onChange={event => setSelectedWeight(Number(event.target.value))} aria-label="ระดับความสำคัญ">
            <option value="1">ความสำคัญ 1 — น้อย</option>
            <option value="2">ความสำคัญ 2</option>
            <option value="3">ความสำคัญ 3 — ปานกลาง</option>
            <option value="4">ความสำคัญ 4</option>
            <option value="5" disabled={selectedPreference !== "avoid"}>ความสำคัญ 5 — ห้ามจัดเวรทั้งวัน (ใช้กับ “หลีกเลี่ยง”)</option>
          </select>
          <input name="reason" placeholder="เหตุผลหรือหมายเหตุ (ไม่บังคับ)" />
          <button>บันทึกความต้องการ</button>
        </form>}

        <table>
          <thead><tr><th>วันที่</th><th>เวร</th><th>ความต้องการ</th><th>ระดับ</th><th /></tr></thead>
          <tbody>{preferences.map(item => {
            const isUnavailable = item.preference === "avoid" && item.weight === 5;
            return <tr key={item.id}>
              <td>{item.work_date}</td>
              <td>{isUnavailable ? "ทุกเวร" : shiftName(item.shift_type_id)}</td>
              <td>{isUnavailable ? <span className="blocked-label">ไม่พร้อมขึ้นเวร</span> : item.preference === "prefer" ? "ต้องการ" : "หลีกเลี่ยง"}</td>
              <td>{item.weight}/5</td>
              <td>{canEdit && <button className="small secondary" onClick={() => void deletePreference(item.id)}>ลบ</button>}</td>
            </tr>;
          })}</tbody>
        </table>
      </section>
    </div>
  </>;
}
