# ICU Pilot Dataset Validation Report

Validated: 2026-08-03

Pilot period: August 2026

## Result

**PASS — safe to import only through the explicit `--apply` command.**

| File | Rows | Result |
| --- | ---: | --- |
| staff (2).xlsx | 17 | Valid employee codes, positions, Senior RN and active flags |
| shift (1).xlsx | 5 | Valid AM, PM, N, D and DE shift codes |
| icu_rules.xlsx | 6 | All ICU rule keys and values supported |
| leave.xlsx | 4 | Staff references, dates and leave statuses valid |
| availability (1).xlsx | 8 | Valid, including `PN001 / 2026-08-20 / ALL` |
| preferences (2).xlsx | 5 | Valid dates, shifts, preference values and weights |

`ALL` means the staff member is unavailable for every working shift on the stated date. The importer stores it as a null shift scope, and the scheduler converts it into an `x[staff, date, shift] = 0` hard constraint for every working shift.

## Safe import command

```powershell
cd backend
python -m app.pilot_import "C:\Users\paojo\Downloads" --year 2026 --month 8
# Only after reviewing a VALID result:
python -m app.pilot_import "C:\Users\paojo\Downloads" --year 2026 --month 8 --department-id <ICU_DEPARTMENT_ID> --apply
```

The validation command is read-only. The second command is the only path that writes Pilot data and runs the complete validation again inside the import flow.
