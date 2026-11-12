"""Small, transactional database migrations for the media-processing tables."""
import logging
import re
import sqlite3

logger = logging.getLogger(__name__)


def migrate_media_geographic_columns(connection) -> bool:
    """Add camera calibration metadata and optional camera association to old DBs."""
    from sqlalchemy import inspect

    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        return False
    json_type = "JSONB" if dialect == "postgresql" else "JSON"
    additions = {
        "cameras": {
            "stream_url": "TEXT",
            "direction": "VARCHAR(100) NOT NULL DEFAULT 'unknown'",
            "stream_type": "VARCHAR(10)",
            "webcam_device_index": "INTEGER",
            "monitoring_status": "VARCHAR(20) NOT NULL DEFAULT 'stopped'",
            "last_frame_at": "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME",
            "monitoring_error": "TEXT",
            "monitoring_reconnect_count": "INTEGER NOT NULL DEFAULT 0",
            "calibration_homography": json_type,
            "calibration_origin_latitude": "FLOAT",
            "calibration_origin_longitude": "FLOAT",
            "calibration_image_width": "INTEGER",
            "calibration_image_height": "INTEGER",
            "calibration_point_count": "INTEGER",
            "calibration_updated_at": "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME",
        },
        "processing_jobs": {
            "camera_id": "VARCHAR(20) REFERENCES cameras(id) ON DELETE SET NULL",
        },
    }
    changed = False
    tables = set(inspect(connection).get_table_names())
    for table, columns in additions.items():
        if table not in tables:
            continue
        existing = {column["name"] for column in inspect(connection).get_columns(table)}
        for name, sql_type in columns.items():
            if name not in existing:
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")
                changed = True
    if dialect == "postgresql" and "cameras" in tables:
        stream_url_type = next((column["type"].__class__.__name__ for column in inspect(connection).get_columns("cameras") if column["name"] == "stream_url"), "")
        if stream_url_type.lower() != "text":
            connection.exec_driver_sql("ALTER TABLE cameras ALTER COLUMN stream_url TYPE TEXT")
            changed = True
    return changed


def migrate_phase6_analytics_alert_columns(connection) -> bool:
    """Add alert rule links and operator acknowledgement fields without resetting data."""
    from sqlalchemy import inspect

    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        return False
    tables = set(inspect(connection).get_table_names())
    if "alerts" not in tables:
        return False
    additions = {
        "rule_id": "INTEGER REFERENCES alert_rules(id) ON DELETE SET NULL",
        "source": "VARCHAR(30) NOT NULL DEFAULT 'legacy'",
        "tracking_id": "VARCHAR(100)",
        "registration_number": "VARCHAR(50)",
        "related_detection_id": "INTEGER REFERENCES media_detections(id) ON DELETE SET NULL",
        "related_live_event_id": "INTEGER REFERENCES live_detection_events(id) ON DELETE SET NULL",
        "dedupe_key": "VARCHAR(255)",
        "acknowledged_at": "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME",
    }
    existing = {column["name"] for column in inspect(connection).get_columns("alerts")}
    changed = False
    for name, sql_type in additions.items():
        if name not in existing:
            connection.exec_driver_sql(f"ALTER TABLE alerts ADD COLUMN {name} {sql_type}")
            changed = True
    for column_name in ("rule_id", "source", "tracking_id", "registration_number", "related_detection_id", "related_live_event_id", "dedupe_key"):
        connection.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS ix_alerts_{column_name} ON alerts ({column_name})")
    return changed


def migrate_phase7_query_indexes(connection) -> bool:
    """Add composite indexes for frequent filtered job and alert queries."""
    from sqlalchemy import inspect

    tables = set(inspect(connection).get_table_names())
    changed = False
    if "processing_jobs" in tables:
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_processing_jobs_status_camera_created "
            "ON processing_jobs (status, camera_id, created_at)"
        )
        changed = True
    if "alerts" in tables:
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_alerts_resolved_severity_created "
            "ON alerts (is_resolved, severity, created_at)"
        )
        changed = True
    return changed


def migrate_sqlite_media_plate_confidence(connection: sqlite3.Connection) -> bool:
    """Rebuild the legacy plate-results table when plate_confidence is NOT NULL.

    Existing DDL, indexes, triggers, column ordering, and rows are copied from
    sqlite_master/PRAGMA so this migration preserves schema details beyond the
    columns currently known to the application.
    """
    table = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='media_plate_results'"
    ).fetchone()
    if table is None:
        return False
    column_info = connection.execute("PRAGMA table_info(media_plate_results)").fetchall()
    nullable_columns = {"plate_confidence", "ocr_confidence"}
    columns_by_name = {column[1]: column for column in column_info}
    missing_columns = nullable_columns - columns_by_name.keys()
    if missing_columns:
        raise RuntimeError(f"media_plate_results is missing columns: {', '.join(sorted(missing_columns))}")
    columns_to_relax = [name for name in nullable_columns if columns_by_name[name][3]]
    if not columns_to_relax:
        return False

    original_ddl = table[0]
    temporary_table = "media_plate_results__nullable_migration"
    renamed_ddl, table_replacements = re.subn(
        r"(?i)(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)([`\"\[]?)media_plate_results([`\"\]]?)",
        rf"\g<1>\g<2>{temporary_table}\g<3>",
        original_ddl,
        count=1,
    )
    if table_replacements != 1:
        raise RuntimeError("Could not safely identify the media_plate_results table DDL")
    relaxed_ddl = renamed_ddl
    for column_name in columns_to_relax:
        relaxed_ddl, replacements = re.subn(
            rf"(?i)([`\"]?{column_name}[`\"]?\s+[^,\n]+?)\s+NOT\s+NULL\b",
            r"\1",
            relaxed_ddl,
            count=1,
        )
        if replacements != 1:
            raise RuntimeError(f"Could not safely make {column_name} nullable")

    columns = [column[1] for column in column_info]
    quoted_columns = ", ".join('"' + name.replace('"', '""') + '"' for name in columns)
    saved_objects = connection.execute(
        "SELECT type, sql FROM sqlite_master "
        "WHERE tbl_name='media_plate_results' AND type IN ('index', 'trigger') AND sql IS NOT NULL "
        "ORDER BY type, name"
    ).fetchall()
    transaction_state = getattr(connection, "in_transaction", None)
    if transaction_state is None:
        transaction_state = connection.driver_connection.in_transaction
    owns_transaction = not transaction_state
    try:
        if owns_transaction:
            connection.execute("BEGIN IMMEDIATE")
        connection.execute(f'DROP TABLE IF EXISTS "{temporary_table}"')
        connection.execute(relaxed_ddl)
        connection.execute(
            f'INSERT INTO "{temporary_table}" ({quoted_columns}) '
            f'SELECT {quoted_columns} FROM "media_plate_results"'
        )
        connection.execute('DROP TABLE "media_plate_results"')
        connection.execute(
            f'ALTER TABLE "{temporary_table}" RENAME TO "media_plate_results"'
        )
        for _kind, statement in saved_objects:
            connection.execute(statement)
        violations = connection.execute("PRAGMA foreign_key_check(media_plate_results)").fetchall()
        if violations:
            raise RuntimeError(f"Foreign key check failed after media plate migration: {violations}")
        if owns_transaction:
            connection.commit()
    except Exception:
        if owns_transaction:
            connection.rollback()
        raise

    logger.info("Migrated nullable plate/OCR confidence columns; preserved rows and schema objects.")
    return True
