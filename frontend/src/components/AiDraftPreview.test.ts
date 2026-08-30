import { describe, expect, it } from "vitest";
import { canConvertApprovedDraft, canSubmitForApproval, explanationStatusMessage, formatPreviewCell, qualityScoreLabel, solverStatusMessage, validationStatusMessage } from "./AiDraftPreview";

describe("AI draft preview helpers", () => {
  it("renders a read-only incharge indicator in a preview cell", () => {
    expect(formatPreviewCell({ staff_id: 1, employee_code: "RN001", staff_name: "RN One", work_date: "2026-08-01", shift_type_id: 3, shift_code: "N", is_incharge: true })).toBe("N ★");
    expect(formatPreviewCell(undefined)).toBe("–");
  });

  it("explains every solver state without promising a schedule", () => {
    expect(solverStatusMessage("OPTIMAL")).toContain("ดีที่สุด");
    expect(solverStatusMessage("FEASIBLE")).toContain("ใช้งานได้");
    expect(solverStatusMessage("INFEASIBLE")).toContain("ไม่สามารถ");
    expect(solverStatusMessage("UNKNOWN")).toContain("ยังไม่พบ");
    expect(solverStatusMessage("MODEL_INVALID")).toContain("ไม่พร้อม");
  });

  it("keeps validation outcomes distinct for a human reviewer", () => {
    expect(validationStatusMessage("passed")).toContain("Passed");
    expect(validationStatusMessage("passed_with_warnings")).toContain("warnings");
    expect(validationStatusMessage("failed")).toContain("Cannot approve");
  });

  it("permits approval submission only after successful validation", () => {
    expect(canSubmitForApproval(null, null)).toBe(false);
    expect(canSubmitForApproval({ status: "failed", error_count: 1, warning_count: 0, conflicts: [], will_write_schedule: false, will_publish_schedule: false }, null)).toBe(false);
    expect(canSubmitForApproval({ status: "passed_with_warnings", error_count: 0, warning_count: 1, conflicts: [], will_write_schedule: false, will_publish_schedule: false }, null)).toBe(true);
    expect(canSubmitForApproval({ status: "passed", error_count: 0, warning_count: 0, conflicts: [], will_write_schedule: false, will_publish_schedule: false }, { id: 1, status: "VALIDATED", validation_status: "passed", approval_status: "pending", rejection_reason: null, converted_schedule_id: null, converted_at: null })).toBe(false);
  });

  it("only exposes conversion for a Head Nurse-approved unconverted draft", () => {
    const approved = { id: 1, status: "APPROVED" as const, validation_status: "passed" as const, approval_status: "approved" as const, rejection_reason: null, converted_schedule_id: null, converted_at: null };
    expect(canConvertApprovedDraft(approved, true)).toBe(true);
    expect(canConvertApprovedDraft(approved, false)).toBe(false);
    expect(canConvertApprovedDraft({ ...approved, converted_schedule_id: 9 }, true)).toBe(false);
  });

  it("labels explanation quality states without promising that the AI changed the schedule", () => {
    expect(explanationStatusMessage("GOOD")).toContain("ดี");
    expect(explanationStatusMessage("IMBALANCED")).toContain("ต่างกัน");
    expect(explanationStatusMessage("WARNING")).toContain("เวรดึก");
  });

  it("labels the user-facing ten-point quality score", () => {
    expect(qualityScoreLabel(9.2)).toBe("ดีมาก");
    expect(qualityScoreLabel(8.4)).toBe("ดี");
    expect(qualityScoreLabel(7.5)).toBe("พอใช้");
    expect(qualityScoreLabel(6.9)).toBe("ควรตรวจทาน");
  });
});
