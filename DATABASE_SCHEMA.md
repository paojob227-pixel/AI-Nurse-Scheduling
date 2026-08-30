# Database schema

Alembic is the source of truth for schema changes. The current revision head is `20260802_03`.

| Table | Purpose |
|---|---|
| `users` | Accounts, password hashes, roles, and active status |
| `departments` | Care areas such as ICU |
| `staffs` | Employee profile, position, department, and optional user account |
| `shift_types` | Manual shift definitions |
| `availability` | Per-staff availability or preference by date |
| `leave_requests` | Leave periods and approval state |
| `holidays` | Named calendar holidays |
| `schedules` | One department-month schedule in draft or published state |
| `schedule_validation_history` | Immutable publish-validation outcome and conflict snapshot |
| `schedule_details` | Individual assignment, keyed by schedule, staff, and `work_date` |
| `system_settings` | Key/value ICU scheduling settings |
| `shift_requests` | Reserved model for a future shift-swap workflow |

`schedule_details.work_date` was introduced in revision `20260802_01`.

## ICU Rule Configuration v1.1 readiness

Revision `20260802_02` adds the data required before a future scheduler can enforce ICU v1.1 rules:

- `staffs.is_senior_rn` identifies staff qualified to act as RN Incharge.
- `schedule_details.is_incharge` records the assigned Incharge; exception fields record an approved non-Senior-RN exception.
- `shift_types.duration_minutes`, `category`, and `crosses_midnight` allow safe rest, overlap, and overtime calculations.
- `coverage_windows` and `coverage_window_shift_types` model the four real ICU coverage windows and the shifts that contribute to each one.
- `department_rule_settings` stores rest, night-limit, consecutive-work, and monthly-hour configuration per department.
- `staff_shift_preferences` stores dated preferred or avoided shifts as soft-constraint input.
- `schedule_audit_logs` retains manual edits and approved safety exceptions.

## Publish Validation Workflow

Revision `20260802_03` adds a publish gate for the Manual Scheduling workflow:

- `schedules.validation_state` records `pending`, `blocked`, `passed`, or `passed_with_warnings`.
- `schedules.approval_state` records `not_requested`, `rejected`, `approved`, or `approved_with_warnings`.
- `schedules` stores the last validation time, actor, error/warning counts, and publisher metadata.
- `schedule_validation_history` stores one immutable ICU v1.1 conflict snapshot for every publish attempt.

An Error blocks publication. Warnings are recorded but allow an authorized manager to publish.

Run `alembic upgrade head` on every environment before starting the API.
