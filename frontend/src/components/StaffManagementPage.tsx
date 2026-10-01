import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import SeniorRnManager from "./SeniorRnManager";

type Department = { id: number; name: string; code: string };
type Staff = {
  id: number;
  employee_code: string;
  first_name: string;
  last_name: string;
  position: string;
  skill_level: string | null;
  is_senior_rn: boolean;
  employment_type: string;
  start_date: string | null;
  active: boolean;
  department_id: number | null;
  user_id: number | null;
};

const employmentLabels: Record<string, string> = {
  full_time: "ประจำ",
  part_time: "พาร์ตไทม์",
  contract: "สัญญาจ้าง",
};

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "เกิดข้อผิดพลาด กรุณาลองใหม่";
}

function StaffEditPanel({ staff, departments, saving, onCancel, onSave }: {
  staff: Staff;
  departments: Department[];
  saving: boolean;
  onCancel: () => void;
  onSave: (payload: Omit<Staff, "id" | "user_id">) => Promise<void>;
}): JSX.Element {
  const [position, setPosition] = useState(staff.position);
  const [isSeniorRn, setIsSeniorRn] = useState(staff.is_senior_rn);
  const positionCanBeSenior = position.trim().toUpperCase() === "RN" || position.trim().toUpperCase() === "HEAD NURSE";

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await onSave({
      employee_code: String(form.get("employee_code") ?? "").trim(),
      first_name: String(form.get("first_name") ?? "").trim(),
      last_name: String(form.get("last_name") ?? "").trim(),
      position: String(form.get("position") ?? "").trim(),
      skill_level: String(form.get("skill_level") ?? "").trim() || null,
      is_senior_rn: positionCanBeSenior && isSeniorRn,
      employment_type: String(form.get("employment_type") ?? "full_time"),
      start_date: String(form.get("start_date") ?? "") || null,
      active: staff.active,
      department_id: Number(form.get("department_id")) || null,
    });
  }

  return <section className="panel staff-edit-panel" role="dialog" aria-modal="true" aria-labelledby="staff-edit-title">
    <div className="section-heading">
      <div><p className="eyebrow">EDIT STAFF</p><h2 id="staff-edit-title">แก้ไขข้อมูลบุคลากร</h2><p className="muted">กำลังแก้ไข {staff.employee_code} — {staff.first_name} {staff.last_name}</p></div>
      <button type="button" className="secondary small" onClick={onCancel} disabled={saving}>ปิด</button>
    </div>
    <form className="staff-edit-grid" onSubmit={submit}>
      <label>รหัสพนักงาน<input name="employee_code" defaultValue={staff.employee_code} maxLength={30} required /></label>
      <label>ชื่อ<input name="first_name" defaultValue={staff.first_name} maxLength={100} required /></label>
      <label>นามสกุล<input name="last_name" defaultValue={staff.last_name} maxLength={100} required /></label>
      <label>ตำแหน่ง<input name="position" value={position} onChange={event => { setPosition(event.target.value); if (!["RN", "HEAD NURSE"].includes(event.target.value.trim().toUpperCase())) setIsSeniorRn(false); }} maxLength={50} required /></label>
      <label>แผนก<select name="department_id" defaultValue={staff.department_id ?? ""}><option value="">ไม่ระบุแผนก</option>{departments.map(department => <option key={department.id} value={department.id}>{department.code} — {department.name}</option>)}</select></label>
      <label>ระดับทักษะ<input name="skill_level" defaultValue={staff.skill_level ?? ""} maxLength={30} placeholder="เช่น Senior / Junior" /></label>
      <label>ประเภทการจ้าง<select name="employment_type" defaultValue={staff.employment_type || "full_time"}><option value="full_time">ประจำ</option><option value="part_time">พาร์ตไทม์</option><option value="contract">สัญญาจ้าง</option></select></label>
      <label>วันที่เริ่มงาน<input name="start_date" type="date" defaultValue={staff.start_date ?? ""} /></label>
      <label className="checkbox-label staff-senior-option"><input type="checkbox" checked={isSeniorRn} onChange={event => setIsSeniorRn(event.target.checked)} disabled={!positionCanBeSenior} />Senior RN</label>
      <div className="staff-edit-actions"><button type="button" className="secondary" onClick={onCancel} disabled={saving}>ยกเลิก</button><button disabled={saving}>{saving ? "กำลังบันทึก..." : "บันทึกการแก้ไข"}</button></div>
    </form>
    <p className="field-help">การแก้ไขข้อมูลไม่ลบประวัติเวรเดิม หากต้องการปิดบัญชีให้ใช้ปุ่ม “นำออก” ในรายการบุคลากร</p>
  </section>;
}

export default function StaffManagementPage({ manager }: { manager: boolean }): JSX.Element {
  const [staff, setStaff] = useState<Staff[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editing, setEditing] = useState<Staff | null>(null);
  const [saving, setSaving] = useState(false);
  const [selectedRemovalIds, setSelectedRemovalIds] = useState<number[]>([]);
  const [selectedRestoreIds, setSelectedRestoreIds] = useState<number[]>([]);
  const [pendingRemoval, setPendingRemoval] = useState<Staff[] | null>(null);
  const [pendingRestore, setPendingRestore] = useState<Staff[] | null>(null);
  const [removing, setRemoving] = useState(false);
  const [restoring, setRestoring] = useState(false);

  const load = useCallback(async () => {
    try {
      const [staffItems, departmentItems] = await Promise.all([
        api<Staff[]>("/staff?active_only=false"),
        api<Department[]>("/departments"),
      ]);
      setStaff(staffItems);
      setDepartments(departmentItems);
      setError("");
    } catch (requestError) { setError(messageFrom(requestError)); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const activeStaff = useMemo(() => staff.filter(person => person.active), [staff]);
  const removedStaff = useMemo(() => staff.filter(person => !person.active), [staff]);
  const departmentName = (departmentId: number | null) => departments.find(item => item.id === departmentId)?.code ?? "–";

  async function createStaff(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setError(""); setNotice("");
    try {
      await api("/staff", { method: "POST", body: JSON.stringify({
        employee_code: form.get("employee_code"), first_name: form.get("first_name"), last_name: form.get("last_name"),
        position: form.get("position"), skill_level: form.get("skill_level") || null,
        is_senior_rn: form.get("is_senior_rn") === "on", employment_type: form.get("employment_type") || "full_time",
        start_date: form.get("start_date") || null, department_id: Number(form.get("department_id")) || null,
        username: form.get("username") || undefined, password: form.get("password") || undefined, role: form.get("role") || "nurse",
      }) });
      formElement.reset(); setNotice("เพิ่มบุคลากรเรียบร้อยแล้ว"); await load();
    } catch (requestError) { setError(messageFrom(requestError)); }
  }

  async function saveStaff(payload: Omit<Staff, "id" | "user_id">): Promise<void> {
    if (!editing) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await api(`/staff/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
      const savedName = `${payload.first_name} ${payload.last_name}`;
      setEditing(null); setNotice(`บันทึกข้อมูล ${savedName} เรียบร้อยแล้ว`); await load();
    } catch (requestError) { setError(messageFrom(requestError)); }
    finally { setSaving(false); }
  }

  function toggleSelected(staffId: number, kind: "remove" | "restore"): void {
    const setter = kind === "remove" ? setSelectedRemovalIds : setSelectedRestoreIds;
    setter(current => current.includes(staffId) ? current.filter(id => id !== staffId) : [...current, staffId]);
  }

  async function confirmRemoval(): Promise<void> {
    if (!pendingRemoval) return;
    setRemoving(true); setError(""); setNotice("");
    try {
      await Promise.all(pendingRemoval.map(person => api(`/staff/${person.id}`, { method: "DELETE" })));
      setSelectedRemovalIds([]); setPendingRemoval(null); setNotice("นำบุคลากรที่เลือกออกจากระบบแล้ว"); await load();
    } catch (requestError) { setError(messageFrom(requestError)); }
    finally { setRemoving(false); }
  }

  async function confirmRestore(): Promise<void> {
    if (!pendingRestore) return;
    setRestoring(true); setError(""); setNotice("");
    try {
      await Promise.all(pendingRestore.map(person => api(`/staff/${person.id}/restore`, { method: "POST" })));
      setSelectedRestoreIds([]); setPendingRestore(null); setNotice("นำบุคลากรที่เลือกกลับเข้าระบบแล้ว"); await load();
    } catch (requestError) { setError(messageFrom(requestError)); }
    finally { setRestoring(false); }
  }

  function StaffTable({ items, removed = false }: { items: Staff[]; removed?: boolean }): JSX.Element {
    return <div className="staff-table-wrap"><table className="staff-table"><thead><tr>{manager && <th>เลือก</th>}<th>รหัส</th><th>ชื่อ-นามสกุล</th><th>ตำแหน่ง</th><th>แผนก</th><th>การจ้าง</th><th>Senior RN</th><th>สถานะ</th>{manager && <th>จัดการ</th>}</tr></thead><tbody>{items.map(person => <tr key={person.id}>{manager && <td><input type="checkbox" aria-label={`${removed ? "เลือกนำกลับ" : "เลือกนำออก"} ${person.employee_code}`} checked={(removed ? selectedRestoreIds : selectedRemovalIds).includes(person.id)} onChange={() => toggleSelected(person.id, removed ? "restore" : "remove")} /></td>}<td>{person.employee_code}</td><td>{person.first_name} {person.last_name}</td><td>{person.position}</td><td>{departmentName(person.department_id)}</td><td>{employmentLabels[person.employment_type] ?? person.employment_type}</td><td>{person.is_senior_rn ? "ใช่" : "–"}</td><td><span className={`status-chip ${removed ? "inactive" : "active"}`}>{removed ? "นำออกแล้ว" : "ใช้งาน"}</span></td>{manager && <td><button type="button" className="small staff-edit-button" onClick={() => { setEditing(person); setError(""); setNotice(""); window.scrollTo({ top: 0, behavior: "smooth" }); }}>แก้ไข</button></td>}</tr>)}</tbody></table></div>;
  }

  return <>
    <h1>บุคลากร</h1>
    <p className="muted">ดู เพิ่ม และแก้ไขข้อมูลบุคลากร โดยประวัติตารางเวรเดิมจะยังคงอยู่</p>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="notice" role="status">{notice}</p>}
    {manager && editing && <StaffEditPanel key={editing.id} staff={editing} departments={departments} saving={saving} onCancel={() => setEditing(null)} onSave={saveStaff} />}
    {manager && <details className="panel"><summary>เพิ่มบุคลากรใหม่</summary><form className="form-grid staff-create-form" onSubmit={createStaff}>
      <input name="employee_code" placeholder="รหัสพนักงาน" required /><input name="first_name" placeholder="ชื่อ" required /><input name="last_name" placeholder="นามสกุล" required /><input name="position" placeholder="ตำแหน่ง เช่น RN" required />
      <select name="department_id"><option value="">ไม่ระบุแผนก</option>{departments.map(department => <option key={department.id} value={department.id}>{department.code} — {department.name}</option>)}</select>
      <input name="skill_level" placeholder="ระดับทักษะ (ไม่บังคับ)" /><select name="employment_type" defaultValue="full_time"><option value="full_time">ประจำ</option><option value="part_time">พาร์ตไทม์</option><option value="contract">สัญญาจ้าง</option></select><input name="start_date" type="date" aria-label="วันที่เริ่มงาน" />
      <select name="role"><option value="nurse">Nurse</option><option value="nurse_assistant">Nurse Assistant</option><option value="head_nurse">Head Nurse</option></select><label className="checkbox-label"><input name="is_senior_rn" type="checkbox" />Senior RN (สำหรับ RN เท่านั้น)</label><input name="username" placeholder="ชื่อเข้าใช้ (เว้นว่าง = รหัสพนักงาน)" /><input name="password" type="password" placeholder="รหัสผ่าน (เว้นว่าง = รหัสตั้งต้น)" /><button>บันทึกบุคลากรใหม่</button>
    </form></details>}
    {manager && <div className="toolbar"><button className="secondary" disabled={!selectedRemovalIds.length} onClick={() => { const selected = activeStaff.filter(person => selectedRemovalIds.includes(person.id)); if (selected.length) setPendingRemoval(selected); }}>นำบุคลากรที่เลือกออก ({selectedRemovalIds.length})</button><small>กด “แก้ไข” ท้ายแถวเพื่อปรับข้อมูลของบุคลากรแต่ละคน</small></div>}
    {pendingRemoval && <section className="panel" role="alertdialog" aria-label="ยืนยันการนำบุคลากรออก"><h2>ยืนยันการนำบุคลากรออก</h2><p>บัญชีและการจัดเวรในอนาคตจะถูกปิดใช้งาน แต่ประวัติเวรเดิมจะไม่ถูกลบ</p><ul>{pendingRemoval.map(person => <li key={person.id}>{person.employee_code} — {person.first_name} {person.last_name}</li>)}</ul><div className="toolbar"><button className="secondary" disabled={removing} onClick={() => setPendingRemoval(null)}>ยกเลิก</button><button disabled={removing} onClick={confirmRemoval}>{removing ? "กำลังนำออก..." : "ยืนยันนำออก"}</button></div></section>}
    <section className="panel"><h2>บุคลากรที่กำลังทำงาน ({activeStaff.length})</h2>{activeStaff.length ? <StaffTable items={activeStaff} /> : <p className="muted">ยังไม่มีบุคลากรที่กำลังทำงาน</p>}</section>
    {manager && <section className="panel"><h2>รายชื่อที่นำออกแล้ว ({removedStaff.length})</h2><p className="muted">รายชื่อส่วนนี้ไม่ถูกนำไปจัดเวร และไม่สามารถเข้าสู่ระบบได้จนกว่าจะนำกลับ</p><div className="toolbar"><button className="secondary" disabled={!selectedRestoreIds.length} onClick={() => { const selected = removedStaff.filter(person => selectedRestoreIds.includes(person.id)); if (selected.length) setPendingRestore(selected); }}>นำรายชื่อที่เลือกกลับเข้าระบบ ({selectedRestoreIds.length})</button></div>
      {pendingRestore && <section className="panel" role="alertdialog" aria-label="ยืนยันการนำบุคลากรกลับเข้าระบบ"><h2>ยืนยันการนำบุคลากรกลับเข้าระบบ</h2><p>บัญชีจะกลับมาใช้งานได้ และบุคลากรจะกลับเข้าสู่การจัดเวรครั้งถัดไป</p><ul>{pendingRestore.map(person => <li key={person.id}>{person.employee_code} — {person.first_name} {person.last_name}</li>)}</ul><div className="toolbar"><button className="secondary" disabled={restoring} onClick={() => setPendingRestore(null)}>ยกเลิก</button><button disabled={restoring} onClick={confirmRestore}>{restoring ? "กำลังนำกลับ..." : "ยืนยันนำกลับเข้าระบบ"}</button></div></section>}
      {removedStaff.length ? <StaffTable items={removedStaff} removed /> : <p className="muted">ยังไม่มีรายชื่อที่นำออก</p>}
    </section>}
    {manager && <SeniorRnManager staff={staff} onUpdated={load} />}
  </>;
}
