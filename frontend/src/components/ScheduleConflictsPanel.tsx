import { useMemo, useState } from "react";
import { api } from "../api";
import {
  defaultConflictFilters,
  filterConflicts,
  type ConflictFilters,
  type ScheduleConflict,
} from "./conflictFilters";
import { conflictReasonThai } from "./conflictText";
import "./schedule-conflicts.css";

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "เกิดข้อผิดพลาด";
}

type ValidationResult = {
  schedule_id: number;
  error_count: number;
  warning_count: number;
  conflicts: ScheduleConflict[];
};

function ConflictList({
  title,
  conflicts,
  severity,
}: {
  title: string;
  conflicts: ScheduleConflict[];
  severity: "error" | "warning";
}) {
  return (
    <section className={`conflict-list conflict-list-${severity}`}>
      <h3>{title} ({conflicts.length})</h3>
      {conflicts.length === 0 ? (
        <p className="conflict-empty">ไม่พบรายการ</p>
      ) : (
        <div className="conflict-table-wrap">
          <table className="conflict-table">
            <thead>
              <tr>
                <th>Severity</th>
                <th>Code</th>
                <th>วันที่</th>
                <th>Shift</th>
                <th>บุคลากร</th>
                <th>เหตุผล</th>
              </tr>
            </thead>
            <tbody>
              {conflicts.map((conflict, index) => (
                <tr key={`${conflict.code}-${conflict.work_date}-${conflict.shift}-${index}`}>
                  <td><span className={`severity severity-${conflict.severity}`}>{conflict.severity}</span></td>
                  <td><code>{conflict.code}</code></td>
                  <td>{conflict.work_date || "—"}</td>
                  <td>{conflict.shift || "—"}</td>
                  <td>{conflict.staff_names.length ? conflict.staff_names.join(", ") : "—"}</td>
                  <td>{conflictReasonThai(conflict)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function ScheduleConflictsPanel({ scheduleId }: { scheduleId: number }) {
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [filters, setFilters] = useState<ConflictFilters>(defaultConflictFilters);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const filtered = useMemo(
    () => filterConflicts(result?.conflicts ?? [], filters),
    [result, filters],
  );
  const errors = filtered.filter((conflict) => conflict.severity === "error");
  const warnings = filtered.filter((conflict) => conflict.severity === "warning");
  const shifts = useMemo(
    () => [...new Set((result?.conflicts ?? []).map((conflict) => conflict.shift).filter(Boolean))].sort(),
    [result],
  );

  async function validate() {
    setLoading(true);
    setError("");
    try {
      setResult(await api<ValidationResult>(`/schedules/${scheduleId}/conflicts`));
    } catch (requestError) {
      setError(messageFrom(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel schedule-conflicts-panel">
      <div className="conflicts-header">
        <div>
          <h2>ตรวจสอบความขัดแย้งของตารางเวร</h2>
          <p>ตรวจตาม ICU Rule Configuration โดยไม่แก้ไขตารางเวร</p>
        </div>
        <button onClick={validate} disabled={loading}>
          {loading ? "กำลังตรวจสอบ..." : "Validate Schedule"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <>
          <div className="conflict-summary" aria-label="Validation summary">
            <span className="summary-error">Error: {result.error_count}</span>
            <span className="summary-warning">Warning: {result.warning_count}</span>
          </div>
          <div className="conflict-filters">
            <label>Severity<select value={filters.severity} onChange={(event) => setFilters({ ...filters, severity: event.target.value as ConflictFilters["severity"] })}><option value="all">ทั้งหมด</option><option value="error">Error</option><option value="warning">Warning</option></select></label>
            <label>วันที่<input type="date" value={filters.workDate} onChange={(event) => setFilters({ ...filters, workDate: event.target.value })} /></label>
            <label>Shift<select value={filters.shift} onChange={(event) => setFilters({ ...filters, shift: event.target.value })}><option value="">ทั้งหมด</option>{shifts.map((shift) => <option key={shift} value={shift}>{shift}</option>)}</select></label>
            <button className="small" onClick={() => setFilters(defaultConflictFilters)}>ล้างตัวกรอง</button>
          </div>
          {(filters.severity === "all" || filters.severity === "error") && <ConflictList title="Errors" conflicts={errors} severity="error" />}
          {(filters.severity === "all" || filters.severity === "warning") && <ConflictList title="Warnings" conflicts={warnings} severity="warning" />}
        </>
      )}
    </section>
  );
}
