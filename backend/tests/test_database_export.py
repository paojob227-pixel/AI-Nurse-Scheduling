import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.database import Base
from app.models import Department, User
from app.services.database_export import export_database


class DatabaseExportTests(unittest.TestCase):
    def test_exports_registered_tables_and_excludes_password_hashes(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(Department(name="Intensive Care Unit", code="ICU"))
            db.add(User(username="admin", password_hash="must-not-leak", role="admin"))
            db.commit()

            exported = export_database(db)

        self.assertIn("departments", exported["tables"])
        self.assertIn("users", exported["tables"])
        self.assertEqual(exported["tables"]["departments"]["row_count"], 1)
        self.assertEqual(exported["tables"]["users"]["excluded_columns"], ["password_hash"])
        self.assertNotIn("password_hash", exported["tables"]["users"]["rows"][0])
        self.assertEqual(exported["tables"]["users"]["rows"][0]["username"], "admin")


if __name__ == "__main__":
    unittest.main()
