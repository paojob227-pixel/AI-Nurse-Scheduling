# AI Scheduler Design — ICU Rule Configuration v1.1

**Status:** Phase 2.6 Approved AI Draft Conversion implemented. An approved AI draft can become a separately validated Manual Schedule draft, but it is never published automatically.

## Phase 1 foundation status

The read-only foundation and AI Hard Constraint Core are now implemented:

- `app.scheduler.contracts` defines typed input, snapshot, preflight, and dry-run output contracts.
- `app.scheduler.snapshot_loader` loads a department-month input snapshot without changing database state.
- `app.scheduler.assignment_model.AssignmentModelBuilder` creates deterministic Boolean variables `x[staff,date,shift]` and `incharge[staff,date,shift]` from a snapshot.
- Valid `schedule_details.locked` snapshot entries add a fixed CP-SAT constraint `x[staff,date,shift] == 1`.
- Invalid, duplicate, or conflicting locked entries are not added and are reported through structured `locked_assignment_issues` reasons.
- `leave_requests` are loaded into the snapshot with their status. Only `approved` leaves add `x[staff,date,shift] == 0` for every shift on each applicable leave date; pending, rejected, and cancelled leave does not constrain the model.
- Out-of-snapshot, inactive/missing-staff, invalid-range, invalid-status, and locked-on-leave data is reported through `approved_leave_issues`.
- Each configured real-time coverage window applies its mapped shifts to every date. Department `MIN_RN`, `MAX_RN`, and `MIN_SUPPORT` rules create RN lower/upper and PN/NA lower constraints.
- Missing ICU rules/windows and unmapped/unavailable shift IDs are reported through `coverage_issues`; invalid windows do not create constraints.
- Every `incharge` variable is constrained to an assignment; non-Senior RN incharge variables are fixed to `0`. Each valid coverage window/date requires its Senior RN minimum and at least one qualified Incharge.
- The dry-run adds real-time shift overlap constraints, rest-after-N/DE constraints using `REST_AFTER_NIGHT`, and same-day multiple-shift compatibility constraints. Continuous AM+PM and PM+N remain possible; gaps, D+DE by the same person, and overlapping pairs are forbidden.
- Incharge exceptions are not generated automatically. A supervisor-approved manual exception remains a Manual Scheduling workflow feature.
- `app.scheduler.solver.CpSatSchedulerSolver` minimizes the prepared weighted soft-cost expression and returns a read-only solve result; it does not return assignments or alter data.
- `POST /api/v1/scheduler/dry-run` is manager-only and reports snapshot counts, variable counts, fixed-constraint counts, and diagnostics with `will_write_schedule=false` and `will_publish_schedule=false`.

### Phase 2.3.1 Fairness Objective Foundation

- For every staff member, the model now creates `assigned_shift_count`, `working_minutes`, and scaled integer `workload_score` variables from `x[staff,date,shift]`.
- Base workload weights follow ICU v1.1: AM/PM/N = `1.0` (stored as `10`), D/DE = `1.5` (stored as `15`). Working minutes use `shift_types.duration_minutes`.
- Pairwise absolute workload differences and `total_workload_imbalance` are created as an explainable, prepared objective expression.
- The model deliberately does **not** call `Minimize` or `Solve` yet. Preference penalties, OT penalties, target weighting, and solver execution require later approval.

### Phase 2.3.2A Preference Objective Variables

- Each dated `staff_shift_preferences` entry creates a Boolean soft-penalty variable only when its staff/date/shift belongs to the snapshot.
- `prefer` has a penalty when its shift is not assigned; `avoid` has a penalty when its shift is assigned. Weights 1–5 form `preference_penalty_score`.
- These relations do not fix or prohibit any assignment `x`; preference remains a soft objective, never a hard safety rule.
- Invalid, outside-snapshot, unsupported-weight/type, and contradictory prefer/avoid inputs are reported in diagnostics and omitted from score terms.
- The preference score is prepared only. It is not passed to `Minimize`.

### Phase 2.3.2B OT Objective Variables

- Per-staff `ot_minutes` is modelled as `max(0, working_minutes - OT_THRESHOLD × 60)`.
- `MONTHLY_HOURS` and `OT_THRESHOLD` are both required for diagnostics; the threshold must be positive and at least the monthly-hours baseline.
- `ot_penalty_score` is the sum of OT minutes and remains a soft metric only. It never caps workload or prohibits an assignment.
- The OT score is not passed to `Minimize`.

### Phase 2.3.3 Objective Composition

- `total_objective_cost` is an explainable, weighted integer expression composed from the existing penalty variables: fairness (`20`), preference (`10`), and OT (`10`).
- All components are penalties, therefore the weighted values are added: `20 × fairness_cost + 10 × preference_cost + 10 × ot_cost`. This preserves the intended meaning when the model minimizes the cost.
- The dry-run reports `objective_components`, `objective_weights`, and `total_objective_terms`; these reveal exactly which soft-cost components are ready for a future solve.
- This increment only builds the expression. It does **not** call `model.Minimize()`, `solver.Solve()`, generate assignments, modify `schedule_details`, or publish.

### Phase 2.4.1 CP-SAT Solver Dry Run

- The model calls `Minimize(total_objective_cost)` and executes CP-SAT with a 10-second dry-run limit.
- It reports `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN`, or `MODEL_INVALID`, along with objective value (when available), solve time, model variable/constraint counts, and structured diagnostics.
- Blocking preflight/model data errors return `MODEL_INVALID` without submitting a clinically unusable model to the solver.
- When CP-SAT proves infeasibility, the response adds explicit capacity diagnostics where detectable (for example insufficient available RN staff after approved leave) plus an overall infeasible-model reason.
- The result never contains generated assignments, and does not create schedules, modify `schedule_details`, or publish.

### Phase 2.4.2 Draft Preview API

- `POST /api/v1/scheduler/preview` solves the same in-memory model and extracts every selected `x[staff,date,shift]` assignment, including its Incharge designation.
- Preview entries include staff ID/code/name, date, shift ID/code, and `is_incharge`.
- The summary reports total assignments, total working minutes, total OT minutes, objective score, and each staff member's shift count, working minutes, workload score, and OT minutes.
- A preview is returned only for `OPTIMAL` or `FEASIBLE`. `INFEASIBLE`, `UNKNOWN`, and `MODEL_INVALID` return diagnostics with an empty assignment list and no summary.
- The API is read-only: it does not create a `Schedule`, modify `schedule_details`, modify a Manual Schedule, approve, or publish.

### Phase 2.4.3 Draft Preview UI

- The Manual Schedule page now provides a manager-only **Generate AI Draft** action when a department and month are selected.
- The UI calls the read-only preview endpoint and displays solver status, a monthly staff/date/shift grid, `★` Incharge markers, assignment/work-hours/OT/objective summary cards, and workload comparison.
- `OPTIMAL` and `FEASIBLE` display a preview only. `INFEASIBLE`, `UNKNOWN`, and `MODEL_INVALID` display diagnostics instead of a fictitious schedule.
- Preview Mode is intentionally visually distinct and has no edit, save, schedule-creation, approval, or publish action.

### Phase 2.4.4 AI Draft Validation

- `POST /api/v1/scheduler/preview/validate` accepts the displayed temporary assignments and validates them against the selected scheduler snapshot.
- `app.services.ai_preview_validation` adapts the temporary assignments into the existing `schedule_validator.validate_context` input. It does not implement a second ICU rule engine.
- The response uses the existing conflict fields and reports `passed`, `passed_with_warnings`, or `failed`, with separate Error/Warning counts.
- Preview UI provides **Validate AI Draft** and displays the result and conflict reasons. The result is informational only: it never creates `schedule_details`, changes a schedule, approves, or publishes.

### Phase 2.5 Human Approval Integration

- AI proposals are persisted in `ai_schedule_drafts` and `ai_schedule_draft_details`, separate from `schedules` and `schedule_details`.
- Each draft retains its solver metadata, assignments, validator conflict snapshot/counts, creator, submission, approval/rejection actor/timestamps, and rejection reason.
- Workflow is `GENERATED → VALIDATED → APPROVED` or `REJECTED`. A validation-failed draft remains auditable but cannot be submitted.
- Admin/Head Nurse may create and submit a draft; only Head Nurse may approve or reject it. UI exposes submit only after a passed/passed-with-warnings validation and exposes approval actions only to Head Nurse.
- Approval only records a decision. It does not create or overwrite a Manual Schedule, create `schedule_details`, invoke Publish, or bypass the existing Manual validation/publish gate.

### Phase 2.6 Approved AI Draft Conversion

- Only `APPROVED` AI drafts with approved approval status can convert. Generated, validated/pending, rejected, and already-converted drafts are blocked.
- Conversion creates a new `schedules` row with `status=draft`, `source=AI_GENERATED`, and copies staff/date/shift/Incharge values as generated `schedule_details`.
- Existing Manual Schedules are never overwritten: a conversion is rejected when that department/month already has a schedule.
- The conversion guards against draft data that the current Manual Schedule schema cannot represent (multiple assignments for a staff member on the same date).
- The new Manual draft is immediately revalidated through `schedule_validator`; its current validation counts/state are returned, and `AI_DRAFT_CONVERTED` is stored in the schedule audit log.
- Conversion never calls Publish. The existing Manual Schedule Validate → Publish workflow remains mandatory.

The next recommended work is an ICU simulation/integration test dataset and browser/API end-to-end tests using the full AI-assisted workflow; no further automatic-publish path should be introduced.

## Simulation benchmark baseline

`app.scheduler.simulation` now supplies a reproducible 31-day in-memory ICU scenario with 30 RN (6 Senior RN), 5 PN, 5 NA, leave, unavailable dates, preferences, and a lock. The baseline reached `FEASIBLE` in 10.13 seconds with zero ICU-validator errors, five soft warnings, and zero OT. See [SIMULATION_BENCHMARK.md](SIMULATION_BENCHMARK.md) for metrics and the identified Night-distribution refinement opportunity.

## 1. Purpose and architecture

The AI Scheduler will create a **draft** monthly schedule for one department. It is a decision-support tool: it does not publish a schedule, bypass the Manual Schedule publish gate, or replace nurse-supervisor review.

```text
PostgreSQL source data
        ↓
Scheduler input snapshot (department + month)
        ↓
CP-SAT feasibility model (hard constraints)
        ↓
Optimisation model (soft constraints / weighted score)
        ↓
Candidate draft assignments + explanation
        ↓
Existing ICU conflict validator
        ↓
Manual review, edit, validate, approve, publish
```

The existing `schedule_validator` remains the independent post-generation safety check. The solver and validator must use the same rule definitions, but the validator is the publish-time authority.

## 2. Input model

Each generation run is scoped to `{department_id, year, month}` and creates an immutable input snapshot for reproducibility.

| Input | Source | Required use |
|---|---|---|
| Staff | `staffs`, `users` | Active staff in the department; position, Senior RN, account role |
| Shift types | `shift_types` | Code, real start/end time, duration, overnight/category metadata |
| Coverage | `coverage_windows`, `coverage_window_shift_types` | Which shifts cover each real-time window and staffing minima/maxima |
| Department rules | `department_rule_settings` | MIN_RN, MAX_RN, MIN_SUPPORT, REST_AFTER_NIGHT, MONTHLY_HOURS, OT_THRESHOLD |
| Leave | approved `leave_requests` | Prohibited work dates |
| Availability | `availability` | `unavailable` and `preferred_off` become soft penalties |
| Preferences | `staff_shift_preferences` | `prefer` / `avoid` with weight 1–5 become soft penalties |
| Existing schedule | `schedules`, `schedule_details` | Locked assignments are fixed; prior published data may provide fairness baseline later |
| Incharge/exception data | `schedule_details` | Preserve locked/manual choices; generated normal Incharge must be Senior RN |

The input loader must reject a run with missing shift metadata, missing coverage mapping, invalid ICU rule values, or no eligible staff. It should return a clear preflight report rather than silently generate an unsafe result.

## 3. Decision variables and derived data

For every eligible staff member `s`, work date `d`, and shift type `t`:

```text
x[s,d,t] ∈ {0,1}    staff s is assigned shift t on date d
incharge[s,d,t] ∈ {0,1}    staff s is the Incharge for that assignment
```

Derived expressions include:

- coverage count by time window, position, and Senior RN qualification;
- staff work intervals using actual timestamps, including cross-midnight shifts;
- monthly minutes/hours, OT hours, count of N/DE duties, and workload score;
- consecutive worked days and consecutive night duties;
- preference and unavailable-date penalties.

Locked manual assignments are represented as fixed `x=1`; all conflicting alternatives are fixed to `0`.

## 4. Hard constraints — solver must never intentionally violate

1. **Approved leave:** no assignment on an approved leave date.
2. **No real-time overlap:** a staff member cannot receive shifts whose actual intervals overlap, including PM+DE and D+PM.
3. **Rest safety:** enforce the configured rest after N/DE and all real-time rest gaps.
4. **N/DE next-morning restriction:** no AM or D after a night-ending assignment without required rest.
5. **Coverage windows:** every configured window meets RN minimum, RN maximum, and PN/NA support minimum using the applicable shifts.
6. **Senior RN and Incharge:** each operating shift/window has the configured Senior RN coverage and a qualified Senior RN Incharge. A non-Senior exception is not generated automatically.
7. **D continuation:** any D assignment requires DE coverage that evening and the D/DE continuation cannot be the same person.
8. **Shift consistency:** each choice references an active departmental staff member and a valid working shift type.
9. **Locked assignments:** preserve all valid manual locks exactly; return infeasible if they prevent a safe solution.

The rule document allows some non-overlapping double shifts, such as AM+PM and PM+N. Therefore the canonical implementation is **interval-overlap and rest based**, not a blanket “one shift per calendar day” restriction. This removes the contradiction between the shorthand rule and the detailed ICU shift rules.

## 5. Soft constraints and penalties

Soft constraints are optimized only after feasibility. They never turn an unsafe schedule into an acceptable one.

| Soft constraint | Penalty direction |
|---|---|
| `avoid` preference | Penalize assigning the requested shift, scaled by preference weight |
| `prefer` preference | Penalize failing to assign the requested shift, scaled by preference weight |
| Unavailable / preferred-off date | Penalize any assignment on the requested date |
| Workload fairness | Penalize deviation from the eligible-staff workload target |
| Night fairness | Penalize deviation in N/DE distribution |
| Consecutive work days | Penalize days above 6 consecutive days |
| Consecutive night duties | Penalize N/DE duties above 3 consecutively |
| OT reduction | Penalize minutes above `MONTHLY_HOURS` and especially `OT_THRESHOLD` |
| Optional coverage | Penalize unnecessary staffing above the configured minimum while respecting maximums |

## 6. Objective function and scoring

Hard constraints are feasibility conditions, not tradeable score components. The source document’s 40/20/20/10/10 priority is represented as a reporting rubric and lexicographic optimization tiers:

1. **Safety and required coverage (40% + 20%):** zero hard violations is mandatory; no score can compensate for a violation.
2. **Fairness (20%):** minimize workload and N/DE distribution deviation.
3. **Preference / availability (10%):** minimize weighted request penalties.
4. **OT reduction (10%):** minimize OT minutes, with stronger penalty beyond threshold.

After the hard model is feasible, CP-SAT should minimize a scaled integer cost:

```text
total_cost =
  W_fairness × fairness_penalty
  + W_preference × preference_penalty
  + W_ot × overtime_penalty
  + W_consecutive × fatigue_penalty
```

Recommended first values: `W_fairness=20`, `W_preference=10`, `W_ot=10`, `W_consecutive=20`. Use lexicographic passes, or weights that are proven not to let a lower priority outweigh a higher priority. Coverage and rest penalties are excluded because they are hard constraints.

The response reports both `objective_cost` and explainable components: coverage=feasible, rest=feasible, fairness penalty, preference penalty, OT minutes, and warnings.

## 7. Generation flow

1. Authorize Admin/Head Nurse and select a department-month.
2. Load an input snapshot and run preflight data validation.
3. Apply locked assignments and construct work intervals/coverage mappings.
4. Add all hard constraints and solve for feasibility.
5. If feasible, add soft objective tiers and solve for the best candidate within a configured time limit.
6. Convert selected variables into draft schedule assignments only; mark generated assignments as generated and retain locks.
7. Execute the existing `schedule_validator` against the candidate.
8. Return candidate assignments, score breakdown, solver status, explanations, and validator results.
9. Require Manual Schedule review. Existing Validate → Publish workflow remains mandatory.

No automatic publish, notification, or overwrite of a published schedule is permitted.

## 8. Infeasibility and conflict handling

When the hard model is infeasible, the system returns no publishable schedule. It must provide a structured `generation_failed` result containing:

- solver status and configured time limit;
- preflight/data errors;
- the smallest practical diagnostic set: date, coverage window/shift, missing role, and affected locked assignment where identifiable;
- suggested manager actions, such as add an eligible RN, remove/change a lock, approve a documented Incharge exception manually, or revise an ICU rule.

Warnings alone are returned with the candidate as soft-constraint tradeoffs. The existing conflict validator remains responsible for the final Error/Warning representation and Publish gate behavior.

## 9. Google OR-Tools CP-SAT mapping

| Design concept | CP-SAT representation |
|---|---|
| Assignment | `BoolVar x[s,d,t]` |
| Fixed manual assignment | `model.Add(x == 1)` |
| Prohibited assignment | `model.Add(x == 0)` |
| Coverage window | sum of applicable `x` variables with `>= min` and `<= max` |
| Senior RN/support count | filtered sum by qualification/position |
| Overlap/rest | incompatible-pair `x[a] + x[b] <= 1` |
| Incharge | Boolean subset of assignment; exactly one qualified Incharge per required shift |
| Monthly hours/OT | integer linear sum of duration minutes and excess variables |
| Fairness deviation | target/deviation `IntVar` with absolute-value constraints |
| Preferences | reified penalty BoolVars scaled by preference weight |
| Objective | `model.Minimize(weighted_integer_cost)` after feasibility is established |

The implementation must use deterministic input ordering, record the solver version/parameters, and persist an input snapshot and result metadata before exposing a generated draft.

## 10. Implementation boundaries for the next coding phase

The first implementation increment should add only:

- `scheduler/` data loader and typed input/output contracts;
- a CP-SAT model with a minimal hard-constraint subset and no automatic publishing;
- a dry-run generation API that returns diagnostics and does not write assignments;
- unit tests that compare solver results with the existing conflict validator.

It must not introduce hidden rule logic that disagrees with the manual validator. Any new ICU rule first needs a configuration field, validator coverage, migration/documentation, and tests.

## 11. Simulation benchmark

Phase 3.1 provides a repeatable, in-memory research scenario in `app.simulation`: ICU รวม for August 2026 (31 days), 30 RNs including 6 Senior RNs, 5 PN, and 5 NA. It adds approved leave, unavailable dates, dated preferences (prefer AM/PM or avoid N), and a few locked assignments without accessing production schedule tables.

Run the evaluation from `backend/`:

```text
python -m app.simulation.benchmark_runner
```

The runner solves the existing model unchanged, validates the temporary assignments through the existing ICU validator, and writes `SIMULATION_BENCHMARK.md`. It reports solver status/time/objective, validation and coverage result, aggregate OT, and per-staff shift, hour, workload, N/D/DE, and OT metrics. The dataset is seeded and repeatable; a `FEASIBLE` solution can still vary slightly between runs because the existing solver uses a time limit.

## 12. Explanation and quality evaluation

Phase 3.2 adds a read-only explanation layer for an existing AI Preview. It reports workload fairness (mean, range, standard deviation, and status), N-shift distribution for RNs, preference satisfaction and avoid violations, plus a staff-level summary of shifts, hours, workload score, N count, OT, and observed soft-preference trade-offs.

The explanation is deliberately evidence-based: it describes qualification, counts, configured thresholds, and observable trade-offs. It does not claim to reconstruct unprovable CP-SAT causality, alter constraints/objective weights, run the solver again, write schedule data, approve, or publish.

## 13. Manual Schedule compatibility

The Manual Schedule representation permits one `ScheduleDetail` per staff member and work date. CP-SAT therefore applies the hard compatibility rule `sum(x[staff,date,*]) <= 1` for every staff/date before solving. This prevents adjacent assignments such as AM+PM and PM+N, avoids ICU fatigue risk from double shifts, and ensures an approved AI Draft can be converted without redesigning the Manual Schedule schema.
