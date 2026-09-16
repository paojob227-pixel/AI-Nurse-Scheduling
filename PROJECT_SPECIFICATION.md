# AI Nurse Scheduling System

## Current delivery scope

The application supports monthly ICU scheduling through both a manual editor and an AI-assisted workflow powered by Google OR-Tools CP-SAT. Users can authenticate, maintain staff and reference data, submit or approve leave, record shift preferences (including all-day unavailability with an avoid preference at priority 5), create and validate schedules, generate AI previews, review auditable AI drafts, and publish an approved manual schedule.

## Roles

- `admin`: system settings, reference data, staff, ICU rules, validation, and schedule operations.
- `head_nurse`: schedule operations plus final AI-draft approval, rejection, and conversion into a manual draft.
- `nurse` / `nurse_assistant`: view schedules and personal shifts, submit leave, and maintain personal preferences.

## AI safety boundary

AI generation is decision support, not an automatic publishing mechanism. An AI preview is read-only. It must pass the ICU validator, be submitted, and be approved by a Head Nurse before it can be converted into a manual schedule draft. The converted draft must pass the standard manual validation gate before publication. AI never overwrites a manual or published schedule without the explicit draft-revision workflow and audit evidence.

## Main modules

- JWT authentication and role-based authorization
- Staff, department, shift, leave, and preference data
- Department-specific ICU rule configuration and real-time coverage windows
- Manual monthly scheduling, assignment locking, conflict validation, and publish history
- CP-SAT generation with hard constraints and fairness, preference, and OT objectives
- AI preview explanation, 0–10 quality scoring, human approval, conversion, and audit logging
- Read-only Expo mobile client for login, dashboard, personal shift, and daily ward schedule

## Operational limitations

The current deployment configuration is intended for demonstration and pilot preparation. It is not a certified production hospital system. Real staff data must be de-identified for testing, production hosting must include managed backups and organization-approved security controls, and every published schedule remains subject to accountable human review.
