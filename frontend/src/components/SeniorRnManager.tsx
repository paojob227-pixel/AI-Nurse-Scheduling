import { useState } from "react";

import { api } from "../api";
import "../senior-rn.css";

type Staff = { id: number; first_name: string; last_name: string; position: string; is_senior_rn: boolean; active: boolean };

function canBeSeniorRn(position: string): boolean {
  const normalized = position.trim().toUpperCase().replace("_", " ");
  return normalized === "RN" || normalized === "HEAD NURSE";
}

export default function SeniorRnManager({ staff, onUpdated }: { staff: Staff[]; onUpdated: () => void }): JSX.Element {
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);

  async function changeStatus(person: Staff, isSeniorRn: boolean): Promise<void> {
    setError(""); setSavingId(person.id);
    try { await api(`/staff/${person.id}/senior-rn`, { method: "PATCH", body: JSON.stringify({ is_senior_rn: isSeniorRn }) }); onUpdated(); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "ไม่สามารถบันทึกสถานะ Senior RN ได้"); }
    finally { setSavingId(null); }
  }

  return <section className="panel senior-rn-panel"><h2>Senior RN Management</h2><p className="muted">Head Nurse เป็น Senior RN อัตโนมัติ; อนุญาตให้กำหนดได้เฉพาะ RN</p>{error && <p className="error">{error}</p>}<table><thead><tr><th>บุคลากร</th><th>ตำแหน่ง</th><th>Senior RN</th></tr></thead><tbody>{staff.filter(person => person.active).map(person => { const eligible = canBeSeniorRn(person.position); return <tr key={person.id}><td>{person.first_name} {person.last_name}</td><td>{person.position}</td><td><label className="toggle-label"><input type="checkbox" checked={person.is_senior_rn} disabled={!eligible || savingId === person.id} onChange={event => changeStatus(person, event.target.checked)} />{person.position.trim().toUpperCase() === "HEAD NURSE" ? "อัตโนมัติ" : person.is_senior_rn ? "ใช่" : "ไม่ใช่"}</label></td></tr>; })}</tbody></table></section>;
}
