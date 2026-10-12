import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { conflictReasonThai } from "./conflictText";
import "./ai-draft-preview.css";

export type PreviewAssignment = {
  staff_id: number;
  employee_code: string;
  staff_name: string;
  work_date: string;
  shift_type_id: number;
  shift_code: string;
  is_incharge: boolean;
};

export type PreviewWorkload = {
  staff_id: number;
  employee_code: string;
  staff_name: string;
  assigned_shift_count: number;
  working_minutes: number;
  workload_score: number;
  ot_minutes: number;
};

export type AiPreview = {
  solver_status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | "MODEL_INVALID";
  objective_value: number | null;
  solve_time_seconds: number;
  variable_count: number;
  constraint_count: number;
  diagnostics: { severity: "error" | "warning"; code: string; reason: string }[];
  assignments: PreviewAssignment[];
  summary: {
    total_staff: number;
    total_assignments: number;
    total_working_minutes: number;
    total_ot_minutes: number;
    objective_score: number;
    quality_score: number;
    fairness_score: number;
    preference_score: number;
    ot_score: number;
    staff_workloads: PreviewWorkload[];
  } | null;
  will_write_schedule: false;
  will_publish_schedule: false;
  notices: string[];
};

type PreviewValidation = {
  status: "passed" | "passed_with_warnings" | "failed";
  error_count: number;
  warning_count: number;
  conflicts: { severity: "error" | "warning"; code: string; work_date: string; shift: string; reason: string }[];
  will_write_schedule: false;
  will_publish_schedule: false;
};

type AiDraft = {
  id: number;
  status: "GENERATED" | "VALIDATED" | "APPROVED" | "REJECTED";
  validation_status: "not_validated" | "passed" | "passed_with_warnings" | "failed";
  approval_status: "not_submitted" | "pending" | "approved" | "rejected";
  rejection_reason: string | null;
  converted_schedule_id: number | null;
  converted_at: string | null;
};

type AiDraftConversion = { schedule_id: number; status: "draft"; source: "AI_GENERATED"; validation_ran: boolean; error_count: number; warning_count: number; will_publish_schedule: false };

type AiExplanation = {
  summary: { total_assignments: number; total_working_minutes: number; total_ot_minutes: number; message: string };
  fairness: { mean_workload_minutes: number; minimum_workload_minutes: number; maximum_workload_minutes: number; workload_difference_minutes: number; standard_deviation_minutes: number; status: "GOOD" | "ACCEPTABLE" | "IMBALANCED" };
  night_distribution: { total_night_assignments: number; mean_nights_per_rn: number; minimum_nights: number; maximum_nights: number; difference: number; status: "GOOD" | "ACCEPTABLE" | "WARNING"; staff: { staff_id: number; employee_code: string; night_count: number; difference_from_mean: number }[] };
  preference: { total_preferences: number; prefer_total: number; prefer_satisfied: number; prefer_satisfaction_percent: number; avoid_total: number; avoid_violations: number; overall_satisfied: number; overall_satisfaction_percent: number };
  staff_explanations: { staff_id: number; employee_code: string; staff_name: string; total_shifts: number; working_minutes: number; workload_score: number; night_count: number; ot_minutes: number; shift_counts: Record<string, number>; preference_total: number; prefer_satisfied: number; prefer_unsatisfied: number; avoid_violations: number; summary: string }[];
  will_write_schedule: false;
  will_publish_schedule: false;
};

type ExplanationTab = "overview" | "fairness" | "night" | "staff";

export function solverStatusMessage(status: AiPreview["solver_status"]): string {
  return {
    OPTIMAL: "พบตารางที่มีคะแนนดีที่สุดภายในเงื่อนไขที่กำหนด",
    FEASIBLE: "พบตารางที่ใช้งานได้ แต่อาจยังไม่ใช่คำตอบที่ดีที่สุด",
    INFEASIBLE: "ไม่สามารถสร้างตารางที่ผ่านกฎทั้งหมดได้",
    UNKNOWN: "ยังไม่พบตารางภายในเวลาที่กำหนด",
    MODEL_INVALID: "ข้อมูลหรือการตั้งค่ากฎยังไม่พร้อมสำหรับการสร้างตาราง",
  }[status];
}

export function formatPreviewCell(assignment: PreviewAssignment | undefined): string {
  if (!assignment) return "–";
  return `${assignment.shift_code}${assignment.is_incharge ? " ★" : ""}`;
}

export function validationStatusMessage(status: PreviewValidation["status"]): string {
  return { passed: "ICU Rules Passed — พร้อมสำหรับ Head Nurse Review", passed_with_warnings: "Passed with warnings — กรุณาตรวจ Warning ก่อน Review", failed: "Cannot approve — พบ Error ที่ต้องแก้ไข" }[status];
}

export function canSubmitForApproval(validation: PreviewValidation | null, draft: AiDraft | null): boolean {
  return (validation?.status === "passed" || validation?.status === "passed_with_warnings") && !draft;
}

export function canConvertApprovedDraft(draft: AiDraft | null, canApprove: boolean): boolean {
  return canApprove && draft?.status === "APPROVED" && draft.converted_schedule_id === null;
}

export function explanationStatusMessage(status: "GOOD" | "ACCEPTABLE" | "IMBALANCED" | "WARNING"): string {
  return { GOOD: "สมดุลดี", ACCEPTABLE: "ยอมรับได้", IMBALANCED: "ภาระงานต่างกันมาก", WARNING: "ควรทบทวนการกระจายเวรดึก" }[status];
}

export function qualityScoreLabel(score: number): string {
  if (score >= 9) return "ดีมาก";
  if (score >= 8) return "ดี";
  if (score >= 7) return "พอใช้";
  return "ควรตรวจทาน";
}

function hours(minutes: number): string { return `${(minutes / 60).toFixed(1)} ชม.`; }

export default function AiDraftPreview({ departmentId, year, month, canApprove, onConverted }: { departmentId: number; year: number; month: number; canApprove: boolean; onConverted: () => void }) {
  const [preview, setPreview] = useState<AiPreview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [validation, setValidation] = useState<PreviewValidation | null>(null);
  const [validating, setValidating] = useState(false);
  const [draft, setDraft] = useState<AiDraft | null>(null);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [conversion, setConversion] = useState<AiDraftConversion | null>(null);
  const [explanation, setExplanation] = useState<AiExplanation | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explanationTab, setExplanationTab] = useState<ExplanationTab>("overview");
  const days = useMemo(() => Array.from({ length: new Date(year, month, 0).getDate() }, (_, index) => index + 1), [year, month]);

  useEffect(() => { setPreview(null); setValidation(null); setDraft(null); setConversion(null); setExplanation(null); setExplanationTab("overview"); setRejectionReason(""); setError(""); }, [departmentId, year, month]);

  async function generate(): Promise<void> {
    setLoading(true); setError("");
    try {
      setPreview(await api<AiPreview>("/scheduler/preview", { method: "POST", body: JSON.stringify({ department_id: departmentId, year, month }) })); setValidation(null); setDraft(null); setConversion(null); setExplanation(null); setExplanationTab("overview"); setRejectionReason("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "ไม่สามารถสร้าง AI Preview ได้");
    } finally { setLoading(false); }
  }

  async function convertToManualDraft(): Promise<void> {
    if (!draft) return;
    setApprovalLoading(true); setError("");
    try {
      const result = await api<AiDraftConversion>(`/ai-schedule-drafts/${draft.id}/convert-replace-draft`, { method: "POST" });
      setConversion(result);
      setDraft({ ...draft, converted_schedule_id: result.schedule_id, converted_at: new Date().toISOString() });
      onConverted();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "ไม่สามารถแปลง AI Draft เป็น Manual Schedule ได้"); } finally { setApprovalLoading(false); }
  }

  async function submitForApproval(): Promise<void> {
    if (!preview || !preview.summary) return;
    setApprovalLoading(true); setError("");
    try {
      const assignments = preview.assignments.map(item => ({ staff_id: item.staff_id, shift_type_id: item.shift_type_id, work_date: item.work_date, is_incharge: item.is_incharge }));
      const generated = await api<AiDraft>("/ai-schedule-drafts", { method: "POST", body: JSON.stringify({ department_id: departmentId, year, month, assignments, solver_status: preview.solver_status, objective_score: preview.summary.objective_score }) });
      setDraft(await api<AiDraft>(`/ai-schedule-drafts/${generated.id}/submit`, { method: "POST" }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "ไม่สามารถส่ง AI Draft เพื่ออนุมัติได้"); } finally { setApprovalLoading(false); }
  }

  async function decide(action: "approve" | "reject"): Promise<void> {
    if (!draft) return;
    if (action === "reject" && !rejectionReason.trim()) { setError("กรุณาระบุเหตุผลที่ปฏิเสธ"); return; }
    setApprovalLoading(true); setError("");
    try {
      setDraft(await api<AiDraft>(`/ai-schedule-drafts/${draft.id}/${action}`, { method: "POST", body: action === "reject" ? JSON.stringify({ reason: rejectionReason.trim() }) : undefined }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "ไม่สามารถบันทึกการตัดสินใจได้"); } finally { setApprovalLoading(false); }
  }

  async function validateDraft(): Promise<void> {
    if (!preview) return;
    setValidating(true); setError("");
    try {
      setValidation(await api<PreviewValidation>("/scheduler/preview/validate", { method: "POST", body: JSON.stringify({ department_id: departmentId, year, month, assignments: preview.assignments.map(item => ({ staff_id: item.staff_id, shift_type_id: item.shift_type_id, work_date: item.work_date, is_incharge: item.is_incharge })) }) }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "ไม่สามารถตรวจ AI Draft ได้"); } finally { setValidating(false); }
  }

  async function explainDraft(): Promise<void> {
    if (!preview) return;
    setExplaining(true); setError("");
    try {
      setExplanation(await api<AiExplanation>("/scheduler/preview/explanation", { method: "POST", body: JSON.stringify({ department_id: departmentId, year, month, assignments: preview.assignments.map(item => ({ staff_id: item.staff_id, shift_type_id: item.shift_type_id, work_date: item.work_date, is_incharge: item.is_incharge })) }) }));
      setExplanationTab("overview");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "ไม่สามารถอธิบาย AI Draft ได้"); } finally { setExplaining(false); }
  }

  const assignments = new Map((preview?.assignments ?? []).map(item => [`${item.staff_id}:${item.work_date}`, item]));
  return <section className="panel ai-preview-panel">
    <div className="ai-preview-heading"><div><h2>AI Generated Preview</h2><p className="muted">ผลลัพธ์ชั่วคราวจาก AI — ยังไม่บันทึก ไม่สร้างตารางจริง และไม่เผยแพร่</p></div><button onClick={generate} disabled={loading}>{loading ? "กำลังสร้าง AI Draft..." : "Generate AI Draft"}</button></div>
    {error && <p className="error">{error}</p>}
    {preview && <>
      <div className={`ai-solver-status ai-solver-${preview.solver_status.toLowerCase()}`}><strong>{preview.solver_status}</strong><span>{solverStatusMessage(preview.solver_status)}</span></div>
      {(preview.solver_status === "OPTIMAL" || preview.solver_status === "FEASIBLE") && preview.summary ? <>
        <div className="cards ai-summary-cards"><article><span>Total Assignment</span><strong>{preview.summary.total_assignments}</strong></article><article><span>Working Hours</span><strong>{hours(preview.summary.total_working_minutes)}</strong></article><article><span>OT</span><strong>{hours(preview.summary.total_ot_minutes)}</strong></article><article className="ai-quality-card"><span>คะแนนคุณภาพตาราง</span><strong>{preview.summary.quality_score.toFixed(1)}<small>/10</small></strong><em>{qualityScoreLabel(preview.summary.quality_score)}</em></article></div>
        <div className="ai-quality-breakdown"><span>ความสมดุล {preview.summary.fairness_score.toFixed(1)}/10</span><span>Preference {preview.summary.preference_score.toFixed(1)}/10</span><span>ลด OT {preview.summary.ot_score.toFixed(1)}/10</span><small>คะแนนนี้ช่วยให้อ่านง่ายขึ้น ส่วน Error/Warning ด้านความปลอดภัยต้องตรวจแยกก่อนอนุมัติ</small></div>
        <div className="schedule-wrap ai-preview-grid"><table className="schedule"><thead><tr><th>บุคลากร</th>{days.map(day => <th key={day}>{day}</th>)}</tr></thead><tbody>{preview.summary.staff_workloads.map(person => <tr key={person.staff_id}><th>{person.employee_code}<br /><span>{person.staff_name}</span></th>{days.map(day => { const workDate = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`; const assignment = assignments.get(`${person.staff_id}:${workDate}`); return <td key={day} className={assignment?.is_incharge ? "ai-incharge" : ""}>{formatPreviewCell(assignment)}</td>; })}</tr>)}</tbody></table></div>
        <p className="muted ai-legend">★ Incharge · ตารางนี้เป็น AI Preview เท่านั้น และไม่สามารถแก้ไขจากหน้านี้ได้</p>
        <div className="ai-validation-actions"><button className="secondary" onClick={validateDraft} disabled={validating}>{validating ? "กำลังตรวจ AI Draft..." : "Validate AI Draft"}</button><span className="muted">ตรวจซ้ำด้วย ICU validator เดียวกับตาราง Manual โดยไม่บันทึกข้อมูล</span></div>
        {validation && <div className={`ai-validation-result ai-validation-${validation.status}`}><strong>{validationStatusMessage(validation.status)}</strong><span>Error {validation.error_count} · Warning {validation.warning_count}</span>{validation.conflicts.length > 0 && <ul>{validation.conflicts.map((item, index) => <li key={`${item.code}-${index}`}><strong>{item.code}</strong> ({item.work_date} · {item.shift}): {conflictReasonThai(item)}</li>)}</ul>}</div>}
        <div className="ai-approval-panel"><h3>Human Approval</h3>{canSubmitForApproval(validation, draft) && <button onClick={submitForApproval} disabled={approvalLoading}>{approvalLoading ? "กำลังส่ง..." : "Submit for Approval"}</button>}{draft && <><p className="muted">AI Draft #{draft.id} · {draft.status} · {draft.approval_status}</p>{draft.status === "VALIDATED" && draft.approval_status === "pending" && canApprove && <div className="ai-approval-actions"><button onClick={() => decide("approve")} disabled={approvalLoading}>Approve Draft</button><input value={rejectionReason} onChange={event => setRejectionReason(event.target.value)} placeholder="เหตุผลเมื่อปฏิเสธ" /><button className="secondary" onClick={() => decide("reject")} disabled={approvalLoading}>Reject Draft</button></div>}{draft.status === "APPROVED" && <><p className="ai-approved">Approved by Head Nurse — พร้อมส่งลงตารางฉบับร่าง</p>{canConvertApprovedDraft(draft, canApprove) && <button onClick={convertToManualDraft} disabled={approvalLoading}>{approvalLoading ? "กำลังส่งตาราง..." : "ส่ง AI Draft ลงตารางฉบับร่าง"}</button>}<p className="muted">ส่งลงตารางเดือนใหม่หรือตาราง Manual ที่ยังว่างและไม่เคยเผยแพร่ได้ รวมถึงแทนที่ AI Draft เดิมที่ยังไม่เผยแพร่ ตาราง Manual ที่มีเวรอยู่แล้วและตารางที่เผยแพร่แล้วจะไม่ถูกเขียนทับ</p></>}{draft.status === "REJECTED" && <p className="error">Rejected: {draft.rejection_reason}</p>}</>}</div>
        {conversion && <div className="ai-conversion-result"><strong>Manual Schedule Draft #{conversion.schedule_id} ถูกสร้างแล้ว</strong><span>ตรวจ ICU Rules ซ้ำแล้ว: Error {conversion.error_count} · Warning {conversion.warning_count} · ยังไม่เผยแพร่</span></div>}
        <h3>Workload Comparison</h3><div className="schedule-wrap"><table className="ai-workload-table"><thead><tr><th>บุคลากร</th><th>จำนวนเวร</th><th>ชั่วโมงทำงาน</th><th>Workload score</th><th>OT</th></tr></thead><tbody>{preview.summary.staff_workloads.map(item => <tr key={item.staff_id}><td>{item.employee_code} · {item.staff_name}</td><td>{item.assigned_shift_count}</td><td>{hours(item.working_minutes)}</td><td>{item.workload_score}</td><td>{hours(item.ot_minutes)}</td></tr>)}</tbody></table></div>
        <div className="ai-explanation-actions"><button className="secondary" onClick={explainDraft} disabled={explaining}>{explaining ? "กำลังวิเคราะห์..." : "Explain AI Draft"}</button><span className="muted">สรุป fairness, เวรดึก และ preference จาก AI Preview โดยไม่เปลี่ยนตาราง</span></div>
        {explanation && <section className="ai-explanation-panel"><h3>AI Schedule Explanation</h3><p className="muted">{explanation.summary.message}</p><div className="ai-explanation-tabs"><button className={explanationTab === "overview" ? "active" : "secondary"} onClick={() => setExplanationTab("overview")}>Overview</button><button className={explanationTab === "fairness" ? "active" : "secondary"} onClick={() => setExplanationTab("fairness")}>Fairness</button><button className={explanationTab === "night" ? "active" : "secondary"} onClick={() => setExplanationTab("night")}>Night Distribution</button><button className={explanationTab === "staff" ? "active" : "secondary"} onClick={() => setExplanationTab("staff")}>Staff Explanation</button></div>
          {explanationTab === "overview" && <div className="ai-explanation-overview"><p><strong>Assignments:</strong> {explanation.summary.total_assignments} · <strong>Hours:</strong> {hours(explanation.summary.total_working_minutes)} · <strong>OT:</strong> {hours(explanation.summary.total_ot_minutes)}</p><p><strong>Preference:</strong> Prefer สำเร็จ {explanation.preference.prefer_satisfaction_percent.toFixed(0)}% · Avoid ถูกละเมิด {explanation.preference.avoid_violations} ครั้ง</p></div>}
          {explanationTab === "fairness" && <div className="ai-explanation-overview"><p><strong>{explanationStatusMessage(explanation.fairness.status)}</strong></p><p>เฉลี่ย {hours(explanation.fairness.mean_workload_minutes)} · ต่ำสุด {hours(explanation.fairness.minimum_workload_minutes)} · สูงสุด {hours(explanation.fairness.maximum_workload_minutes)} · ต่างกัน {hours(explanation.fairness.workload_difference_minutes)} · SD {hours(explanation.fairness.standard_deviation_minutes)}</p></div>}
          {explanationTab === "night" && <div className="schedule-wrap"><p><strong>{explanationStatusMessage(explanation.night_distribution.status)}</strong> · N รวม {explanation.night_distribution.total_night_assignments} · เฉลี่ย {explanation.night_distribution.mean_nights_per_rn.toFixed(1)} ต่อ RN · ช่วง {explanation.night_distribution.minimum_nights}–{explanation.night_distribution.maximum_nights}</p><table className="ai-workload-table"><thead><tr><th>RN</th><th>N</th><th>ต่างจากเฉลี่ย</th></tr></thead><tbody>{explanation.night_distribution.staff.map(item => <tr key={item.staff_id}><td>{item.employee_code}</td><td>{item.night_count}</td><td>{item.difference_from_mean.toFixed(1)}</td></tr>)}</tbody></table></div>}
          {explanationTab === "staff" && <div className="schedule-wrap"><table className="ai-workload-table"><thead><tr><th>บุคลากร</th><th>เวร</th><th>N</th><th>Preference</th><th>คำอธิบาย</th></tr></thead><tbody>{explanation.staff_explanations.map(item => <tr key={item.staff_id}><td>{item.employee_code} · {item.staff_name}</td><td>{Object.entries(item.shift_counts).map(([shift, count]) => `${shift}: ${count}`).join(", ") || "–"}</td><td>{item.night_count}</td><td>Prefer ✓ {item.prefer_satisfied} · Prefer ✕ {item.prefer_unsatisfied} · Avoid ✕ {item.avoid_violations}</td><td>{item.summary}</td></tr>)}</tbody></table></div>}
        </section>}
      </> : <div className="ai-diagnostics"><h3>Diagnostics</h3>{preview.diagnostics.length ? <ul>{preview.diagnostics.map((item, index) => <li key={`${item.code}-${index}`}><strong>{item.code}</strong>: {item.reason}</li>)}</ul> : <p className="muted">ไม่มี diagnostic เพิ่มเติมจาก solver</p>}</div>}
    </>}
  </section>;
}
