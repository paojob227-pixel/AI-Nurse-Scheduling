export type ConflictSeverity = "error" | "warning";

export type ScheduleConflict = {
  severity: ConflictSeverity;
  code: string;
  work_date: string;
  shift: string;
  staff_ids: number[];
  staff_names: string[];
  reason: string;
};

export type ConflictFilters = {
  severity: "all" | ConflictSeverity;
  workDate: string;
  shift: string;
};

export const defaultConflictFilters: ConflictFilters = {
  severity: "all",
  workDate: "",
  shift: "",
};

export function filterConflicts(
  conflicts: ScheduleConflict[],
  filters: ConflictFilters,
): ScheduleConflict[] {
  const normalizedShift = filters.shift.trim().toLowerCase();

  return conflicts.filter((conflict) => {
    const severityMatches =
      filters.severity === "all" || conflict.severity === filters.severity;
    const dateMatches = !filters.workDate || conflict.work_date === filters.workDate;
    const shiftMatches =
      !normalizedShift || conflict.shift.toLowerCase().includes(normalizedShift);

    return severityMatches && dateMatches && shiftMatches;
  });
}
