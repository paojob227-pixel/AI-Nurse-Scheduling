# API specification

All business endpoints are prefixed with `/api/v1`. Interactive schema documentation is available from `/docs` while the backend is running.

| Area | Main endpoints |
|---|---|
| Authentication | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` |
| Reference data | `GET/POST /departments`, `GET/POST /shift-types`, `GET/POST/DELETE /holidays` |
| Staff | `GET/POST /staff`, `PUT/DELETE /staff/{id}` |
| Leave / availability | `GET/POST /leave-requests`, `PUT /leave-requests/{id}`, `GET/POST /availability` |
| Staff preferences | `GET/POST /staff-preferences`, `PUT/DELETE /staff-preferences/{id}` |
| Manual schedule | `GET/POST /schedules`, `PUT/DELETE /schedules/{id}/assignments`, `POST /schedules/{id}/publish` |
| Schedule validation | `GET /schedules/{id}/conflicts`, `GET /schedules/{id}/validation-history` |
| Operations | `GET /dashboard`, `GET/PUT /settings` |
| ICU rules | `GET/POST /departments/{id}/icu-rules`, `GET/PUT/DELETE /departments/{id}/icu-rules/{key}` |
| AI Scheduler foundation | `POST /scheduler/dry-run` |
| AI Scheduler preview | `POST /scheduler/preview` |
| AI Preview validation | `POST /scheduler/preview/validate` |
| AI Preview explanation | `POST /scheduler/preview/explanation` |
| AI Draft approval | `GET/POST /ai-schedule-drafts`, `POST /ai-schedule-drafts/{id}/submit`, `POST /ai-schedule-drafts/{id}/approve`, `POST /ai-schedule-drafts/{id}/reject` |

All except login and refresh require `Authorization: Bearer <access-token>`.

`POST /auth/refresh` accepts JSON body `{ "refresh_token": "..." }`. The token
is never sent in the URL query string, preventing it from being copied into
proxy and access logs.

`PATCH /staff/{id}/senior-rn` updates the Senior RN designation. Admin and Head Nurse may use it; the server allows RN staff, automatically retains Senior RN status for Head Nurse, and rejects PN/NA.

For a manual schedule assignment, send `staff_id`, `shift_type_id`, `work_date`, and optional `locked` to `PUT /schedules/{schedule_id}/assignments`. `work_date` must fall within the schedule's month.

ICU rule keys are `MIN_RN`, `MAX_RN`, `MIN_SUPPORT`, `REST_AFTER_NIGHT`, `MONTHLY_HOURS`, and `OT_THRESHOLD`. Their payload uses `{ "key": "MIN_RN", "value": 3 }` when creating and `{ "value": 3 }` when updating.

Staff shift preferences use `preference` value `prefer` or `avoid`. Weights `1` through `4` are soft constraints for the selected shift. An `avoid` request with weight `5` represents an all-day unavailable date: `shift_type_id` is stored as `null` and the scheduler must not assign any working shift on that date. Weight `5` is reserved for this all-day unavailable request.

`/availability` remains available only for legacy Pilot imports and existing data. It is no longer exposed as a separate user workflow; new all-day unavailable requests must use `POST /staff-preferences` with `preference: "avoid"` and `weight: 5`.

`GET /schedules/{id}/conflicts` validates the saved manual schedule against ICU v1.1 rules and returns read-only errors and warnings. It does not generate or alter a schedule.

`POST /schedules/{id}/publish` always runs ICU v1.1 validation first. It records an immutable validation-history snapshot. Any Error returns HTTP 422 and leaves the schedule in draft with `validation_state=blocked` and `approval_state=rejected`. Warnings do not block publication; successful publication is marked `approved_with_warnings` when warnings exist, otherwise `approved`.

`GET /schedules/{id}/validation-history` returns manager-only publish-validation attempts, including error/warning counts, outcome, timestamp, actor ID, and the recorded conflict snapshot.

`POST /scheduler/dry-run` is Admin/Head Nurse only. It loads a typed snapshot for `{ department_id, year, month }`, including `leave_requests`, ICU rules, real-time coverage windows, coverage-window shift mappings, and staff preferences. It builds Boolean `x[staff,date,shift]` and `incharge[staff,date,shift]` variables. Valid locked assignments add `x=1`; approved leave adds `x=0` for every shift on each leave date; `one_shift_per_day_constraint_count` reports the hard rule that each staff member can receive at most one shift on a work date. For every valid mapped coverage window/date, `MIN_RN`, `MAX_RN`, and `MIN_SUPPORT` add RN minimum/maximum and PN/NA minimum constraints. Senior RN/Incharge constraints enforce qualified Incharge coverage. Real-time shift overlap, N/DE rest, and incompatible/gapped multiple shifts are also constrained. The dry-run prepares fairness, preference, and OT soft-score variables; their weighted penalty expression is reported through `objective_components`, `objective_weights`, and `total_objective_terms`. It calls `Minimize(total_objective_cost)` and runs CP-SAT read-only for up to 10 seconds. The response includes `solver_status` (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN`, or `MODEL_INVALID`), objective value when available, solve time, model variable/constraint counts, and diagnostics. Pending, rejected, and cancelled leave does not create constraints. It never returns assignments, creates schedules, modifies `schedule_details`, or publishes.

`POST /scheduler/preview` is Admin/Head Nurse only and uses the same `{ department_id, year, month }` request. For an `OPTIMAL` or `FEASIBLE` solve, it returns the selected in-memory assignments with staff/date/shift/Incharge data and a workload/OT/objective summary. For `INFEASIBLE`, `UNKNOWN`, or `MODEL_INVALID`, `assignments` is empty and `summary` is `null`, with structured diagnostics. This endpoint never creates a schedule, writes `schedule_details`, changes a Manual Schedule, approves, or publishes.

`POST /scheduler/preview/validate` is Admin/Head Nurse only. It accepts the selected preview assignments (`staff_id`, `shift_type_id`, `work_date`, `is_incharge`) together with department/month. It adapts that temporary data to the same ICU validator used by Manual Schedule and returns `passed`, `passed_with_warnings`, or `failed` with existing conflict fields and Error/Warning counts. It is read-only: no Schedule, `schedule_details`, approval state, validation history, or publish state is changed.

`POST /scheduler/preview/explanation` is Admin/Head Nurse only. It accepts the same department/month and temporary preview assignments as preview validation. It returns a read-only quality report: workload mean/min/max/difference/standard deviation and status, N-shift distribution per RN and status, preference satisfaction/avoid-violation counts, and a staff summary containing shift counts, hours, workload score, N count, OT, and observed soft-preference trade-offs. It does not rerun or change CP-SAT, create a Schedule, write `schedule_details`, approve, or publish.

AI Draft approval endpoints are manager-only except `approve`, `reject`, and `convert`, which require `head_nurse`. `POST /ai-schedule-drafts` stores an auditable copy of a preview in separate AI-draft tables and revalidates it using the existing ICU validator. It starts as `GENERATED`; a validation-failed draft cannot proceed. `POST /{id}/submit` transitions a passing draft to `VALIDATED` and pending approval. Head Nurse then uses `POST /{id}/approve` or `POST /{id}/reject` (with a required reason).

`POST /ai-schedule-drafts/{id}/convert` only accepts an `APPROVED` unconverted draft. It creates a new `Schedule` with `status=draft` and `source=AI_GENERATED`, or fills an existing empty Manual draft that has never been published. The existing schedule ID is retained when filling an empty draft. It copies generated assignments/Incharge data, reruns the existing ICU validator, and writes an `AI_DRAFT_CONVERTED` audit event including the previous source/count when adopting an empty Manual draft. Populated Manual schedules and published schedules remain protected. Conversion never publishes; the standard publish gate still applies.

`POST /ai-schedule-drafts/{id}/convert-replace-draft` requires Head Nurse and an approved, unconverted AI draft. It supports the same new/empty Manual draft cases, and additionally replaces an existing AI-generated draft with an `AI_DRAFT_REPLACED` audit event. It does not overwrite populated Manual schedules or published schedules. A Manual draft with a previous `published_at` is also protected, even if its assignments were cleared.
