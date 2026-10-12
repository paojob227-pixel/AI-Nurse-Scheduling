2026-10-12 — Empty Manual draft conversion fix

- Approved AI drafts can fill an empty, never-published Manual draft while preserving its schedule ID.
- Populated Manual schedules, published schedules, and previously-published empty Manual schedules remain protected.
- Conversion changes the source to AI_GENERATED, revalidates, records the previous source/count in audit, and remains unpublished.
- Added conversion regression tests and updated PostgreSQL integration / browser E2E coverage for the empty-draft workflow.
- Updated frontend guidance; no schema migration required.

----------------

v0.10.0

- Added Phase 4.1 Clinical Pilot Preparation internal read-only module with pilot readiness checklist, KPI report, and audit-evidence verification
- Added clinical pilot documentation covering data verification, de-identification, ICU-rule freeze, and AI workflow acceptance
- KPI report includes AI generation time, solver status, validation errors/warnings, OT, workload fairness, Night distribution, and preference satisfaction
- Audit verification reports generated_by, validated_by, approved_by, published_by, and timestamps as verified evidence or explicit gaps; it never backfills records
- Verified 65 backend tests, isolated PostgreSQL pilot workflow integration 6/6, frontend tests 9/9, and production frontend build
- Hardened the integration-test safety guard: destructive fixtures now require a dedicated database name ending in `_integration_test`, never the locally running Pilot database
- No migration, solver, objective, constraint, approval, publish workflow, or production schedule data was modified

----------------

v0.10.1

- Added Expo React Native mobile foundation in `mobile/` for Expo Go
- Added read-only mobile Login, Dashboard, My Shift Today, and overlapping Senior RN display using the existing API
- Added editable LAN backend URL at Login and setup documentation for Expo Go; no schedule, solver, approval, or publish behavior was changed

----------------

v0.9.3

- Added the Phase 3.3 compatibility hard constraint: every staff member has at most one assignment per work date (`sum(x[staff,date,*]) <= 1`)
- Added one-shift-per-day dry-run counter and locked-assignment diagnostic; AM+PM and PM+N forced combinations are now infeasible
- Preserved the Manual Schedule schema, conversion API, publish workflow, and objective weights
- Completed Phase 3.3 execution verification: PostgreSQL integration passed 6/6 and Playwright E2E passed 2/2 for Generate → Validate → Submit → Approve → Convert → Manual Validate → Publish

----------------

v0.9.2

- Added Phase 3.3 PostgreSQL API integration-test harness for AI Preview → Validate → Submit → Head Nurse Approve → Convert → Manual Validate → Publish, plus the documented negative cases
- Added `_test` database safety guard and integration setup documentation; tests are skipped until an explicitly configured migrated PostgreSQL test database is available
- Added Playwright configuration and two browser E2E scenarios, with `pnpm test:e2e`; installed `@playwright/test` as a development dependency
- No business logic, CP-SAT solver, constraint, objective, schedule, approval, or publish behavior changed
- Execution verification against an isolated PostgreSQL `nurse_schedule_test` found a pre-existing compatibility defect: preview can contain multiple shifts for a staff/date while Manual Schedule conversion correctly rejects that representation; Phase 3.3 is not complete

----------------

v0.9.1

- Completed Phase 3.2 AI Schedule Explanation & Quality Evaluation
- Added read-only fairness, Night-distribution, preference, and per-staff explanation reports for existing AI Preview assignments
- Added `POST /api/v1/scheduler/preview/explanation` and Preview UI tabs; no solver, constraint, objective, schedule-table, approval, or publish behavior changed
- Added backend explanation tests and frontend explanation rendering tests

----------------

v0.9.0

- Completed Phase 3.1 ICU Simulation Benchmark with a repeatable 31-day, 40-staff ICU scenario (30 RN including 6 Senior RN, 5 PN, 5 NA)
- Added in-memory leave, unavailability, preference, and locked-assignment generation; no production table is read or written by the dataset generator
- Added `python -m app.simulation.benchmark_runner`, per-staff workload/N/D/DE/OT metrics, validator results, and generated `SIMULATION_BENCHMARK.md`
- Added dataset, snapshot-compatibility, benchmark-execution, and report-generation tests

----------------

v0.8.2

- Added deterministic 31-day ICU simulation dataset and in-memory CP-SAT benchmark runner
- Added benchmark metrics for solve status/time, validator safety, OT, workload, and Night distribution
- Baseline: `FEASIBLE` in 10.13 seconds with zero validation errors and zero OT
- Recorded Night-distribution imbalance as a future objective-quality refinement, not a safety failure

----------------

v0.8.1

- Added AI Scheduler Phase 2.6 Approved AI Draft → Manual Schedule Draft conversion
- Added schedule `source` metadata (`MANUAL` / `AI_GENERATED`) and Alembic migration `20260802_05`
- Added Head Nurse conversion API, immediate Manual-validator recheck, and `AI_DRAFT_CONVERTED` audit logging
- Conversion never overwrites an existing month, auto-publishes, or bypasses Manual Schedule publish validation

----------------

v0.8.0

- Added AI Scheduler Phase 2.5 Human Approval Integration
- Added separate auditable AI draft/draft-detail storage and Alembic migration `20260802_04`
- Added submit, Head Nurse approve, and Head Nurse reject APIs plus guarded preview UI controls
- No Manual Schedule creation/overwrite, `schedule_details` write, automatic conversion, or publish added

----------------

v0.7.3

- Added AI Scheduler Phase 2.4.4 AI Draft Validation
- Added read-only preview-validation service reusing the Manual Schedule ICU validator and conflict format
- Added manager Preview UI validation action with passed/warning/failed display
- No schedule creation, `schedule_details` write, approval, validation-history write, or publish action added

----------------

v0.7.2

- Added AI Scheduler Phase 2.4.3 Draft Preview UI to the Manual Schedule page
- Added manager-only Generate AI Draft action, monthly read-only preview grid, Incharge markers, solver states, and workload/OT/objective summaries
- Added frontend tests for preview status and Incharge rendering; frontend production build passes
- No schedule creation, `schedule_details` write, approval, or publish action added

----------------

v0.7.1

- Added AI Scheduler Phase 2.4.2 Draft Preview API
- Added in-memory CP-SAT solution extraction for assignment, staff/date/shift, and Incharge data
- Added per-staff workload/OT and overall preview summary output
- No `Schedule` creation, `schedule_details` write, Manual Schedule change, approval, or publish added

----------------

v0.7.0

- Added AI Scheduler Phase 2.4.1 CP-SAT Solver Dry Run
- Added read-only `Minimize(total_objective_cost)` and CP-SAT status/objective/runtime/model-size output
- Added structured solver diagnostics, including detectable RN capacity shortages for infeasible models
- No schedule preview, schedule creation, database write, or publish added

----------------

v0.6.9

- Added AI Scheduler Phase 2.3.3 Objective Composition
- Added prepared weighted total cost from fairness (`20`), preference (`10`), and OT (`10`) penalties
- Added dry-run objective components, weights, and total objective-term diagnostics
- No `Minimize`, solver execution, schedule generation, database write, or publish added

----------------

v0.6.8

- Added AI Scheduler Phase 2.3.2B OT Objective Variables
- Added per-staff OT minutes and total OT penalty score from working minutes and ICU hour thresholds
- Added dry-run OT counters and monthly-hours/OT-threshold diagnostics
- OT remains a soft metric; no objective aggregation, `Minimize`, solver execution, database write, or publish added

----------------

v0.6.7

- Added AI Scheduler Phase 2.3.2A Preference Objective Variables
- Added weighted soft penalties for dated `prefer` and `avoid` staff shift preferences
- Added dry-run preference score-term counts and diagnostics
- Preference never fixes an assignment; no OT optimisation, objective aggregation, `Minimize`, solver execution, database write, or publish added

----------------

v0.6.6

- Added AI Scheduler Phase 2.3.1 Fairness Objective Foundation
- Added assigned-shift count, working-minutes, workload-score, pairwise imbalance, and total workload-imbalance CP-SAT variables
- Added workload shift-weight/duration diagnostics and dry-run fairness counters
- No `Minimize`, solver execution, preference/OT optimisation, schedule generation, database write, or publish added

----------------

v0.6.5

- Added AI Scheduler Phase 2.2.5 Senior RN/Incharge and Phase 2.2.6 Rest/Overlap hard constraints
- Added Senior RN coverage, qualified Incharge assignment/coverage, real-time overlap, N/DE rest, and multiple-shift compatibility constraints
- Added dry-run counters and diagnostics for Senior/Incharge and timing safety data
- No solver execution, optimisation, schedule generation, database write, or publish added

----------------

v0.6.4

- Added AI Scheduler Phase 2.2.4 Staffing + Coverage Constraints
- Added per-date real-time coverage constraints for RN minimum/maximum and PN/NA minimum using ICU rules and window shift mappings
- Added dry-run staffing/coverage counts and diagnostics for missing rules/windows and invalid mappings
- No Senior/Incharge, rest/overlap constraints, solve operation, database write, or publish added

----------------

v0.6.3

- Added AI Scheduler Phase 2.2.3 Approved Leave Constraint
- Added leave-request status to scheduler snapshots; only approved leave fixes every applicable `x[staff,date,shift] = 0`
- Added dry-run counts and diagnostics for approved leave constraints
- Added validation for leave outside the snapshot, ineligible staff, invalid date range/status, and lock-on-leave conflicts
- No staffing, coverage, Senior/Incharge, rest/overlap constraints, solve operation, database write, or publish added

----------------

v0.6.2

- Added AI Scheduler Phase 2.2.2 Fixed/Locked Assignment Constraint
- Valid locked schedule snapshot entries now fix `x[staff,date,shift] = 1` in the CP-SAT model
- Added dry-run diagnostics for out-of-model, duplicate, and conflicting locks
- No leave, staffing, coverage, Senior/Incharge, rest/overlap constraints, solve operation, database write, or publish added

----------------

v0.6.1

- Added AI Scheduler Phase 2.2.1 Assignment Model Foundation
- Added deterministic CP-SAT Boolean variables for `x[staff,date,shift]` and `incharge[staff,date,shift]`
- Added unit coverage for snapshot-to-model variable construction
- No constraints, objective, solve operation, generated assignments, database writes, or auto publish added

----------------

v0.6.0

- Added AI Scheduler Phase 1 foundation: typed contracts, read-only snapshot loader, CP-SAT solver boundary, and manager dry-run API
- Added Google OR-Tools CP-SAT dependency
- Added scheduler foundation tests and preflight diagnostics
- Dry-run does not generate schedules, modify `schedule_details`, apply optimization weights, or publish

----------------

v0.5.8

- Added AI Scheduler design specification based on ICU Rule Configuration v1.1
- Defined input contracts, hard/soft constraints, objective tiers, conflict handling, and CP-SAT mapping
- No AI Scheduler, OR-Tools dependency, or generation code was added

----------------

v0.5.7

- Added ICU v1.1 publish validation gate for Manual Schedule
- Blocked schedule publication when validation returns an Error; allowed Warning-only publication
- Added schedule validation and approval states, publisher metadata, and immutable validation history
- Added manager API for validation-history records and Manual Schedule Publish Validation UI
- Added unit coverage for publish-gate outcomes

----------------

v0.5.6

- Added a Manual Schedule conflict and warning display panel for Admin and Head Nurse
- Added Validate Schedule action using `GET /api/v1/schedules/{schedule_id}/conflicts`
- Added severity, date, and shift filters with separate Error and Warning results
- Added Vitest frontend coverage for conflict-result filtering
- Verified the frontend production build

----------------

v0.1.0

- Initial FastAPI
- SQLAlchemy
- Alembic
- Database Models

----------------

v0.2.0

- JWT Authentication
- CRUD Staff
- CRUD Shift

----------------

v0.3.0

- React Frontend
- Login Page
- Dashboard

----------------

v0.4.0

- Manual scheduling API and calendar UI
- Docker Compose deployment assets and safe database seed command
- Schedule assignment field standardized as `work_date`
- Frontend production build verified

----------------

v0.5.0

- Added ICU Rule Configuration v1.1 database-readiness migration
- Added Senior RN, Incharge, exception approval, coverage-window, preference, audit-log, and per-department rule data structures
- Added ICU default seed data for AM, PM, N, D, DE, and OFF shifts

----------------

v0.5.1

- Added ICU Rule Management CRUD API for MIN_RN, MAX_RN, MIN_SUPPORT, REST_AFTER_NIGHT, MONTHLY_HOURS, and OT_THRESHOLD
- Added service-layer range and cross-rule validation
- Added ICU rule unit tests and OpenAPI validation

----------------

v0.5.2

- Added Settings > ICU Rules frontend interface for admin and head_nurse
- Added department selection and CRUD actions for all six ICU rules
- Verified frontend production build

----------------

v0.5.3

- Added Senior RN Management UI within Staff Management
- Added server-enforced Senior RN eligibility and Head Nurse automatic designation
- Added Senior RN endpoint and qualification tests

----------------

v0.5.4

- Added My Preference UI for dated shift preferences and unavailable dates
- Added Staff Preference API with ownership and manager visibility controls
- Added soft-constraint preference validation and tests

----------------

v0.5.5

- Added read-only ICU v1.1 manual schedule conflict validator
- Added staffing, support, Senior RN, Incharge, leave, rest, overlap, D/DE, N/DE, coverage, and soft-preference checks
- Added schedule conflict API and validator unit tests
