"""Validate by default; --apply is the only command that writes Pilot data."""
import argparse
from app.database.database import SessionLocal
from app.pilot_import.service import import_dataset, load_workbooks, validate_dataset

parser = argparse.ArgumentParser(description="Validate or explicitly import an ICU Pilot dataset")
parser.add_argument("folder")
parser.add_argument("--year", type=int, required=True)
parser.add_argument("--month", type=int, required=True)
parser.add_argument("--department-id", type=int)
parser.add_argument("--apply", action="store_true", help="write only after complete validation succeeds")
args = parser.parse_args()
dataset = load_workbooks(args.folder)
if not args.apply:
    report = validate_dataset(dataset, args.year, args.month)
    print("VALID" if report.valid else "INVALID")
    for issue in report.issues: print(f"{issue.file}:{issue.row} {issue.field} — {issue.message}")
    raise SystemExit(0 if report.valid else 1)
if args.department_id is None: parser.error("--department-id is required with --apply")
with SessionLocal() as db:
    import_dataset(db, args.department_id, dataset, args.year, args.month)
print("IMPORT COMPLETED")
