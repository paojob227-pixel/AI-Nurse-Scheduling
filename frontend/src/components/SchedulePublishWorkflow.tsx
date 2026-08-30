import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { ScheduleConflict } from "./conflictFilters";
import { conflictReasonThai } from "./conflictText";
import "./schedule-publish.css";

type ValidationHistory = {
  id: number;
  error_count: number;
  warning_count: number;
  outcome: string;
  created_at: string;
};

type Props = {
  schedule: {
    id: number;
    status: string;
    validation_state: string;
    approval_state: string;
    last_error_count: number;
    last_warning_count: number;
  };
  onPublished: () => void;
  onEdit: () => void;
};

type ValidationResult = {
  error_count: number;
  warning_count: number;
  conflicts: ScheduleConflict[];
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "เกิดข้อผิดพลาด";
}

function stateLabel(value: string): string {
  const labels: Record<string, string> = {
    pending: "รอตรวจสอบ",
    blocked: "ไม่ผ่านการตรวจสอบ",
    passed: "ผ่านการตรวจสอบ",
    passed_with_warnings: "ผ่านพร้อมคำเตือน",
    not_requested: "ยังไม่อนุมัติ",
    rejected: "ไม่อนุมัติ",
    approved: "อนุมัติแล้ว",
    approved_with_warnings: "อนุมัติพร้อมคำเตือน",
    published: "เผยแพร่แล้ว",
    published_with_warnings: "เผยแพร่พร้อมคำเตือน",
  };
  return labels[value] ?? value;
}

function conflictTitle(conflict: ScheduleConflict): string {
  const labels: Record<string, string> = {
    STAFFING_SHORTAGE: "จำนวนบุคลากรในเวรไม่ครบตามเกณฑ์",
    MIN_RN: "จำนวนพยาบาลวิชาชีพ (RN) ไม่ครบตามเกณฑ์",
    MAX_RN: "จำนวนพยาบาลวิชาชีพ (RN) เกินเกณฑ์",
    MIN_SUPPORT: "จำนวน PN/NA ไม่ครบตามเกณฑ์",
    SENIOR_RN_REQUIRED: "เวรนี้ไม่มี Senior RN",
    INCHARGE_REQUIRED: "เวรนี้ยังไม่ได้กำหนด Incharge",
    APPROVED_LEAVE: "มีบุคลากรถูกลงเวรในวันที่ลาซึ่งอนุมัติแล้ว",
    REST_AFTER_NIGHT: "เวลาพักหลังเวรดึกไม่เพียงพอ",
    SHIFT_OVERLAP: "บุคลากรถูกลงเวรที่เวลาทับซ้อนกัน",
    ONE_SHIFT_PER_DAY: "บุคลากรหนึ่งคนมีมากกว่าหนึ่งเวรในวันเดียวกัน",
    D_DE_CONTINUATION: "มีเวร D แต่ไม่มีเวร DE สำหรับดูแลต่อเนื่อง",
    N_DE_TO_MORNING: "จัดเวรเช้าต่อจากเวรดึก/DE ซึ่งไม่ปลอดภัย",
    HEAD_NURSE_MORNING_ONLY: "Head Nurse ต้องอยู่เวร AM หรือ D เท่านั้น",
  };
  return labels[conflict.code] ?? "พบข้อมูลตารางเวรที่ไม่เป็นไปตามกฎ ICU";
}

function conflictLocation(conflict: ScheduleConflict): string {
  return [conflict.work_date && `วันที่ ${conflict.work_date}`, conflict.shift && `เวร ${conflict.shift}`]
    .filter(Boolean)
    .join(" · ");
}

export default function SchedulePublishWorkflow({ schedule, onPublished, onEdit }: Props) {
  const [history, setHistory] = useState<ValidationHistory[]>([]);
  const [blockingIssues, setBlockingIssues] = useState<ScheduleConflict[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await api<ValidationHistory[]>(`/schedules/${schedule.id}/validation-history`));
    } catch (requestError) {
      setError(errorMessage(requestError));
    }
  }, [schedule.id]);

  const loadBlockingIssues = useCallback(async () => {
    try {
      const result = await api<ValidationResult>(`/schedules/${schedule.id}/conflicts`);
      setBlockingIssues(result.conflicts.filter((conflict) => conflict.severity === "error"));
    } catch {
      // The publish response is still shown if diagnostics cannot be loaded.
    }
  }, [schedule.id]);

  useEffect(() => { loadHistory(); }, [loadHistory]);
  useEffect(() => {
    if (schedule.last_error_count > 0) loadBlockingIssues();
    else setBlockingIssues([]);
  }, [schedule.last_error_count, loadBlockingIssues]);

  async function publish() {
    setLoading(true);
    setError("");
    try {
      await api(`/schedules/${schedule.id}/publish`, { method: "POST" });
      await loadHistory();
      onPublished();
    } catch (requestError) {
      setError(errorMessage(requestError));
      await loadBlockingIssues();
      await loadHistory();
      onPublished();
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel schedule-publish-panel">
      <div className="publish-heading">
        <div><h2>Publish Validation</h2><p>การเผยแพร่จะถูกบล็อกเมื่อพบ Error แต่เผยแพร่ได้เมื่อมี Warning เท่านั้น</p></div>
        {schedule.status === "draft" && <button onClick={publish} disabled={loading}>{loading ? "กำลังตรวจสอบ..." : "ตรวจสอบและเผยแพร่ตาราง"}</button>}
      </div>
      <div className="publish-states">
        <span>Validation: <strong>{stateLabel(schedule.validation_state)}</strong></span>
        <span>Approval: <strong>{stateLabel(schedule.approval_state)}</strong></span>
        <span className="summary-error">Error ล่าสุด: {schedule.last_error_count}</span>
        <span className="summary-warning">Warning ล่าสุด: {schedule.last_warning_count}</span>
      </div>
      {error && (
        <div className="publish-blocked" role="alert">
          <strong>ยังไม่สามารถเผยแพร่ตารางได้ กรุณาแก้ไขรายการต่อไปนี้</strong>
          <p>{blockingIssues.length > 0
            ? `พบข้อผิดพลาด ${blockingIssues.length} รายการ ข้อผิดพลาดเหล่านี้ทำให้ตารางเผยแพร่ไม่ได้`
            : error}</p>
          {blockingIssues.length > 0 && (
            <ul>
              {blockingIssues.map((conflict, index) => (
                <li key={`${conflict.code}-${conflict.work_date}-${conflict.shift}-${index}`}>
                  <strong>{conflictTitle(conflict)}</strong>
                  {conflictLocation(conflict) && ` (${conflictLocation(conflict)})`}
                  {conflict.staff_names.length > 0 && ` — ${conflict.staff_names.join(", ")}`}
                  {conflict.reason && <span className="publish-blocked-reason">: {conflictReasonThai(conflict)}</span>}
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="secondary publish-edit-button" onClick={onEdit}>กลับไปแก้ไขตาราง</button>
        </div>
      )}
      <h3>Validation History</h3>
      {history.length === 0 ? <p className="muted">ยังไม่มีประวัติการตรวจสอบเพื่อเผยแพร่</p> : <table className="publish-history"><thead><tr><th>เวลา</th><th>ผลลัพธ์</th><th>Error</th><th>Warning</th></tr></thead><tbody>{history.map((item) => <tr key={item.id}><td>{new Date(item.created_at).toLocaleString("th-TH")}</td><td>{stateLabel(item.outcome)}</td><td>{item.error_count}</td><td>{item.warning_count}</td></tr>)}</tbody></table>}
    </section>
  );
}
