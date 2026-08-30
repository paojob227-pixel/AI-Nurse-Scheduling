import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../api";
import "../icu-rules.css";

type Department = { id: number; name: string; code: string };
type RuleKey = "MIN_RN" | "MAX_RN" | "MIN_SUPPORT" | "REST_AFTER_NIGHT" | "MONTHLY_HOURS" | "OT_THRESHOLD";
type IcuRule = { id: number; department_id: number; key: RuleKey; value: number; enabled: boolean };

const RULES: Array<{ key: RuleKey; label: string; description: string; unit: string; fallback: number }> = [
  { key: "MIN_RN", label: "RN ขั้นต่ำ", description: "จำนวน RN ขั้นต่ำต่อ coverage window", unit: "คน", fallback: 3 },
  { key: "MAX_RN", label: "RN สูงสุด", description: "จำนวน RN สูงสุดต่อ coverage window", unit: "คน", fallback: 4 },
  { key: "MIN_SUPPORT", label: "Support ขั้นต่ำ", description: "PN หรือ NA ขั้นต่ำต่อ coverage window", unit: "คน", fallback: 1 },
  { key: "REST_AFTER_NIGHT", label: "พักหลังเวรดึก", description: "เวลาพักขั้นต่ำหลัง N หรือ DE", unit: "ชั่วโมง", fallback: 8 },
  { key: "MONTHLY_HOURS", label: "ชั่วโมงมาตรฐานต่อเดือน", description: "ชั่วโมงทำงานมาตรฐานต่อบุคลากร", unit: "ชั่วโมง", fallback: 168 },
  { key: "OT_THRESHOLD", label: "เกณฑ์เริ่ม OT", description: "ชั่วโมงทำงานที่เกินค่านี้จะนับเป็น OT", unit: "ชั่วโมง", fallback: 168 },
];

function errorMessage(error: unknown): string { return error instanceof Error ? error.message : "ไม่สามารถบันทึก ICU rule ได้"; }

export default function IcuRulesPanel(): JSX.Element {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentId, setDepartmentId] = useState("");
  const [rules, setRules] = useState<IcuRule[]>([]);
  const [drafts, setDrafts] = useState<Partial<Record<RuleKey, number>>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const ruleByKey = useMemo(() => new Map(rules.map(rule => [rule.key, rule])), [rules]);

  const loadRules = useCallback(async (selectedDepartmentId: string) => {
    if (!selectedDepartmentId) { setRules([]); setDrafts({}); return; }
    setLoading(true); setError("");
    try {
      const loadedRules = await api<IcuRule[]>(`/departments/${selectedDepartmentId}/icu-rules`);
      setRules(loadedRules);
      setDrafts(Object.fromEntries(loadedRules.map(rule => [rule.key, rule.value])));
    } catch (requestError) { setError(errorMessage(requestError)); } finally { setLoading(false); }
  }, []);

  useEffect(() => { api<Department[]>("/departments").then(items => { setDepartments(items); if (items.length === 1) setDepartmentId(String(items[0].id)); }).catch(requestError => setError(errorMessage(requestError))); }, []);
  useEffect(() => { loadRules(departmentId); }, [departmentId, loadRules]);

  async function saveRule(key: RuleKey, fallback: number): Promise<void> {
    if (!departmentId) return;
    const value = drafts[key] ?? fallback;
    setError("");
    try {
      if (ruleByKey.has(key)) await api<IcuRule>(`/departments/${departmentId}/icu-rules/${key}`, { method: "PUT", body: JSON.stringify({ value }) });
      else await api<IcuRule>(`/departments/${departmentId}/icu-rules`, { method: "POST", body: JSON.stringify({ key, value }) });
      await loadRules(departmentId);
    } catch (requestError) { setError(errorMessage(requestError)); }
  }

  async function deleteRule(key: RuleKey): Promise<void> {
    if (!departmentId || !ruleByKey.has(key) || !window.confirm(`ลบ ICU rule ${key} ใช่หรือไม่?`)) return;
    setError("");
    try { await api(`/departments/${departmentId}/icu-rules/${key}`, { method: "DELETE" }); await loadRules(departmentId); } catch (requestError) { setError(errorMessage(requestError)); }
  }

  return <section className="panel icu-rules-panel"><div className="section-heading"><div><h2>ICU Rules</h2><p className="muted">ค่ากฎสำหรับตรวจสอบความปลอดภัยของตารางเวร ICU</p></div><label className="department-select">แผนก<select value={departmentId} onChange={event => setDepartmentId(event.target.value)}><option value="">เลือกแผนก</option>{departments.map(department => <option key={department.id} value={department.id}>{department.name}</option>)}</select></label></div>{error && <p className="error">{error}</p>}{!departmentId && <p className="muted">เลือกแผนกเพื่อดูและแก้ไข ICU rules</p>}{departmentId && <table className="rules-table"><thead><tr><th>Rule</th><th>รายละเอียด</th><th>ค่า</th><th /></tr></thead><tbody>{RULES.map(rule => { const exists = ruleByKey.has(rule.key); return <tr key={rule.key}><td><strong>{rule.label}</strong><small>{rule.key}</small></td><td>{rule.description}</td><td><div className="rule-value"><input aria-label={rule.key} type="number" min="0" value={drafts[rule.key] ?? rule.fallback} onChange={event => setDrafts(current => ({ ...current, [rule.key]: Number(event.target.value) }))} disabled={loading} /><span>{rule.unit}</span></div></td><td className="rule-actions"><button className="small" onClick={() => saveRule(rule.key, rule.fallback)} disabled={loading}>{exists ? "บันทึก" : "เพิ่ม"}</button>{exists && <button className="small secondary" onClick={() => deleteRule(rule.key)} disabled={loading}>ลบ</button>}</td></tr>; })}</tbody></table>}</section>;
}
