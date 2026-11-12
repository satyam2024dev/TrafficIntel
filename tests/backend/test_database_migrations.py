"""Regression tests for schema-preserving SQLite media table migrations."""
import sqlite3
import unittest

from sqlalchemy import create_engine

from backend.app.database.migrations import migrate_media_geographic_columns, migrate_sqlite_media_plate_confidence, migrate_phase7_query_indexes


class MediaPlateConfidenceMigrationTests(unittest.TestCase):
    def test_phase7_indexes_are_created_idempotently_without_data_loss(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE processing_jobs (id INTEGER PRIMARY KEY, status TEXT, camera_id TEXT, created_at DATETIME)")
            connection.exec_driver_sql("CREATE TABLE alerts (id INTEGER PRIMARY KEY, is_resolved BOOLEAN, severity TEXT, created_at DATETIME)")
            connection.exec_driver_sql("INSERT INTO processing_jobs VALUES (1, 'completed', 'CAM1', '2026-01-01')")
            self.assertTrue(migrate_phase7_query_indexes(connection))
            self.assertTrue(migrate_phase7_query_indexes(connection))
            indexes = {row[1] for row in connection.exec_driver_sql("PRAGMA index_list(processing_jobs)").fetchall()}
            alert_indexes = {row[1] for row in connection.exec_driver_sql("PRAGMA index_list(alerts)").fetchall()}
            self.assertIn("ix_processing_jobs_status_camera_created", indexes)
            self.assertIn("ix_alerts_resolved_severity_created", alert_indexes)
            self.assertEqual(connection.exec_driver_sql("SELECT id FROM processing_jobs").scalar_one(), 1)
        engine.dispose()

    def test_migration_preserves_rows_foreign_keys_indexes_and_artifacts(self):
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
            CREATE TABLE processing_jobs (id INTEGER PRIMARY KEY);
            CREATE TABLE media_detections (id INTEGER PRIMARY KEY);
            INSERT INTO processing_jobs VALUES (7);
            INSERT INTO media_detections VALUES (11);
            CREATE TABLE media_plate_results (
                id INTEGER PRIMARY KEY,
                processing_job_id INTEGER NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
                detection_id INTEGER REFERENCES media_detections(id) ON DELETE SET NULL,
                frame_number INTEGER,
                timestamp FLOAT,
                plate_text VARCHAR(50) NOT NULL,
                ocr_confidence FLOAT NOT NULL,
                plate_confidence FLOAT NOT NULL,
                x1 FLOAT NOT NULL, y1 FLOAT NOT NULL, x2 FLOAT NOT NULL, y2 FLOAT NOT NULL,
                original_crop_path TEXT,
                enhanced_crop_path TEXT,
                enhancement_metadata JSON,
                created_at DATETIME NOT NULL
            );
            CREATE INDEX idx_media_plate_job ON media_plate_results(processing_job_id);
            CREATE INDEX idx_media_plate_detection ON media_plate_results(detection_id);
            CREATE INDEX idx_media_plate_created ON media_plate_results(created_at);
            INSERT INTO media_plate_results VALUES (
                3, 7, 11, 1, 0.5, 'KA01AB1234', 0.82, 0.76,
                1, 2, 30, 12, 'original.jpg', 'enhanced.jpg', '{"provider":"PaddleOCR"}', '2026-01-01'
            );
        """)

        self.assertTrue(migrate_sqlite_media_plate_confidence(db))
        columns = {row[1]: row for row in db.execute("PRAGMA table_info(media_plate_results)")}
        self.assertEqual(columns["plate_confidence"][3], 0, "plate_confidence must allow NULL")
        self.assertEqual(columns["ocr_confidence"][3], 0, "unavailable OCR confidence must allow NULL")
        row = db.execute(
            "SELECT id, processing_job_id, detection_id, plate_text, ocr_confidence, plate_confidence, "
            "original_crop_path, enhanced_crop_path, enhancement_metadata FROM media_plate_results WHERE id=3"
        ).fetchone()
        self.assertEqual(row, (3, 7, 11, "KA01AB1234", 0.82, 0.76, "original.jpg", "enhanced.jpg", '{"provider":"PaddleOCR"}'))
        db.execute(
            "INSERT INTO media_plate_results "
            "(id, processing_job_id, detection_id, plate_text, ocr_confidence, plate_confidence, x1, y1, x2, y2, created_at) "
            "VALUES (4, 7, 11, 'KA02CD3456', 0.91, NULL, 0, 0, 1, 1, '2026-01-02')"
        )
        db.execute(
            "INSERT INTO media_plate_results "
            "(id, processing_job_id, detection_id, plate_text, ocr_confidence, plate_confidence, x1, y1, x2, y2, created_at) "
            "VALUES (5, 7, 11, '', NULL, 0.61, 0, 0, 1, 1, '2026-01-03')"
        )
        indexes = {row[1] for row in db.execute("PRAGMA index_list(media_plate_results)")}
        self.assertTrue({"idx_media_plate_job", "idx_media_plate_detection", "idx_media_plate_created"}.issubset(indexes))
        foreign_keys = {(row[2], row[3], row[4], row[6]) for row in db.execute("PRAGMA foreign_key_list(media_plate_results)")}
        self.assertEqual(foreign_keys, {
            ("media_detections", "detection_id", "id", "SET NULL"),
            ("processing_jobs", "processing_job_id", "id", "CASCADE"),
        })
        self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertFalse(migrate_sqlite_media_plate_confidence(db), "Migration should be idempotent")
        db.close()

    def test_geographic_schema_migration_preserves_camera_and_job_rows(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE cameras (id VARCHAR(20) PRIMARY KEY, name VARCHAR(100) NOT NULL)")
            connection.exec_driver_sql("CREATE TABLE processing_jobs (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO cameras (id, name) VALUES ('C42', 'Existing camera')")
            connection.exec_driver_sql("INSERT INTO processing_jobs (id) VALUES (91)")
            self.assertTrue(migrate_media_geographic_columns(connection))
            self.assertFalse(migrate_media_geographic_columns(connection), "Geographic migration must be idempotent")
            camera_columns = {column["name"] for column in __import__("sqlalchemy").inspect(connection).get_columns("cameras")}
            job_columns = {column["name"] for column in __import__("sqlalchemy").inspect(connection).get_columns("processing_jobs")}
            self.assertTrue({"direction", "calibration_homography", "calibration_image_width"}.issubset(camera_columns))
            self.assertIn("camera_id", job_columns)
            self.assertEqual(connection.exec_driver_sql("SELECT name, direction FROM cameras WHERE id='C42'").one(), ("Existing camera", "unknown"))
            self.assertEqual(connection.exec_driver_sql("SELECT id, camera_id FROM processing_jobs WHERE id=91").one(), (91, None))
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_key_list(processing_jobs)").fetchall()
            self.assertTrue(any(row[2] == "cameras" and row[3] == "camera_id" for row in foreign_keys))
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
