import { describe, expect, it } from "vitest";
import { filterConflicts, type ScheduleConflict } from "./conflictFilters";

const conflicts: ScheduleConflict[] = [
  { severity: "error", code: "APPROVED_LEAVE", work_date: "2026-08-04", shift: "D", staff_ids: [1], staff_names: ["A"], reason: "Approved leave" },
  { severity: "warning", code: "PREFERENCE", work_date: "2026-08-04", shift: "N", staff_ids: [2], staff_names: ["B"], reason: "Preference" },
  { severity: "error", code: "REST_AFTER_NIGHT", work_date: "2026-08-05", shift: "DE", staff_ids: [3], staff_names: ["C"], reason: "Rest required" },
];

describe("filterConflicts", () => {
  it("filters by severity", () => {
    expect(filterConflicts(conflicts, { severity: "error", workDate: "", shift: "" })).toHaveLength(2);
  });

  it("filters by exact work date", () => {
    expect(filterConflicts(conflicts, { severity: "all", workDate: "2026-08-04", shift: "" })).toHaveLength(2);
  });

  it("filters shifts case-insensitively", () => {
    expect(filterConflicts(conflicts, { severity: "all", workDate: "", shift: "de" })[0].code).toBe("REST_AFTER_NIGHT");
  });
});
