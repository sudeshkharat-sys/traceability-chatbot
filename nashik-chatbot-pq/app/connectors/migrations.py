"""
Database Migrations
Idempotent index migrations that run at startup using CREATE INDEX IF NOT EXISTS.
Safe to run on existing databases - skips already-existing indexes.
"""

import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Each tuple: (index_name, table_name, columns_sql)
PART_LABELER_INDEXES = [
    # raw_warranty_data
    ("idx_raw_warranty_user_month",   "raw_warranty_data", "user_id, manufac_yr_mon"),
    ("idx_raw_warranty_user_model",   "raw_warranty_data", "user_id, base_model"),
    ("idx_raw_warranty_user_mis",     "raw_warranty_data", "user_id, mis_bucket"),
    ("idx_raw_warranty_user_qtr",     "raw_warranty_data", "user_id, new_manufacturing_quater"),
    # raw_rpt_data
    ("idx_raw_rpt_user_month",        "raw_rpt_data",      "user_id, mfg_month"),
    ("idx_raw_rpt_user_model",        "raw_rpt_data",      "user_id, model"),
    ("idx_raw_rpt_user_category",     "raw_rpt_data",      "user_id, defect_category"),
    ("idx_raw_rpt_user_qtr",          "raw_rpt_data",      "user_id, mfg_quarter"),
    # raw_gnovac_data
    ("idx_raw_gnovac_user_month",     "raw_gnovac_data",   "user_id, mfg_month"),
    ("idx_raw_gnovac_user_model",     "raw_gnovac_data",   "user_id, model_code"),
    ("idx_raw_gnovac_user_pointer",   "raw_gnovac_data",   "user_id, pointer"),
    ("idx_raw_gnovac_user_qtr",       "raw_gnovac_data",   "user_id, mfg_quarter"),
    # raw_rfi_data
    ("idx_raw_rfi_user_month",        "raw_rfi_data",      "user_id, mfg_month"),
    ("idx_raw_rfi_user_model",        "raw_rfi_data",      "user_id, model_name"),
    ("idx_raw_rfi_user_severity",     "raw_rfi_data",      "user_id, severity_name"),
    ("idx_raw_rfi_user_qtr",          "raw_rfi_data",      "user_id, mfg_quarter"),
    # raw_esqa_data
    ("idx_raw_esqa_user_month",       "raw_esqa_data",     "user_id, mfg_month"),
    ("idx_raw_esqa_user_model",       "raw_esqa_data",     "user_id, vehicle_model"),
    ("idx_raw_esqa_user_category",    "raw_esqa_data",     "user_id, concern_category"),
    ("idx_raw_esqa_user_qtr",         "raw_esqa_data",     "user_id, mfg_quarter"),
]


# Add new columns to existing tables (idempotent via IF NOT EXISTS)
COLUMN_MIGRATIONS = [
    "ALTER TABLE layouts ADD COLUMN IF NOT EXISTS legend_position_x FLOAT",
    "ALTER TABLE layouts ADD COLUMN IF NOT EXISTS legend_position_y FLOAT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
    "ALTER TABLE box_connections ADD COLUMN IF NOT EXISTS from_station_id VARCHAR(50)",
    "ALTER TABLE box_connections ADD COLUMN IF NOT EXISTS to_station_id VARCHAR(50)",
    # station_documents table (created idempotently)
    """
    CREATE TABLE IF NOT EXISTS station_documents (
        id SERIAL PRIMARY KEY,
        user_id INTEGER,
        layout_id INTEGER REFERENCES layouts(id) ON DELETE SET NULL,
        station_id VARCHAR(100) NOT NULL,
        concern_id VARCHAR(255),
        doc_type VARCHAR(50) NOT NULL,
        filename VARCHAR(500) NOT NULL,
        file_path VARCHAR(1000),
        file_size INTEGER,
        mime_type VARCHAR(100),
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_station_docs_station_id ON station_documents (station_id)",
    "CREATE INDEX IF NOT EXISTS idx_station_docs_layout_id ON station_documents (layout_id)",
    "CREATE INDEX IF NOT EXISTS idx_station_docs_concern_id ON station_documents (concern_id)",
    # z3d global model library — one row per unique model name, file stored once on disk
    """
    CREATE TABLE IF NOT EXISTS z3d_model_library (
        id SERIAL PRIMARY KEY,
        name VARCHAR(500) NOT NULL UNIQUE,
        ext VARCHAR(20) NOT NULL DEFAULT 'glb',
        file_path VARCHAR(1000),
        file_size INTEGER,
        default_sx FLOAT NOT NULL DEFAULT 1,
        default_sy FLOAT NOT NULL DEFAULT 1,
        default_sz FLOAT NOT NULL DEFAULT 1,
        default_rx FLOAT NOT NULL DEFAULT 0,
        default_ry FLOAT NOT NULL DEFAULT 0,
        default_rz FLOAT NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    # z3d per-layout placements — just transforms, file comes from library
    """
    CREATE TABLE IF NOT EXISTS z3d_layout_placements (
        id SERIAL PRIMARY KEY,
        layout_id INTEGER NOT NULL REFERENCES layouts(id) ON DELETE CASCADE,
        model_name VARCHAR(500) NOT NULL,
        line_group_id VARCHAR(100),
        station_id VARCHAR(100),
        px FLOAT NOT NULL DEFAULT 0,
        py FLOAT NOT NULL DEFAULT 0,
        pz FLOAT NOT NULL DEFAULT 0,
        rx FLOAT NOT NULL DEFAULT 0,
        ry FLOAT NOT NULL DEFAULT 0,
        rz FLOAT NOT NULL DEFAULT 0,
        sx FLOAT NOT NULL DEFAULT 1,
        sy FLOAT NOT NULL DEFAULT 1,
        sz FLOAT NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_z3d_placements_layout_id ON z3d_layout_placements (layout_id)",
    # buyoff icon label
    "ALTER TABLE buyoff_icons ADD COLUMN IF NOT EXISTS name VARCHAR(255) DEFAULT ''",
    # canvas text labels stored as JSON array in the layout row
    "ALTER TABLE layouts ADD COLUMN IF NOT EXISTS text_labels TEXT DEFAULT '[]'",
    # canvas arrow elements stored as JSON array in the layout row
    "ALTER TABLE layouts ADD COLUMN IF NOT EXISTS canvas_arrows TEXT DEFAULT '[]'",
]


def run_column_migrations(session_factory) -> None:
    """
    Add new columns to existing tables using ALTER TABLE … ADD COLUMN IF NOT EXISTS.
    Safe to run on every startup — no-op if columns already exist.
    """
    applied = 0
    failed = 0
    for sql in COLUMN_MIGRATIONS:
        try:
            with session_factory() as session:
                session.execute(text(sql))
                session.commit()
            applied += 1
        except Exception as e:
            logger.warning(f"Column migration skipped [{sql[:60]}]: {e}")
            failed += 1
    logger.info(f"Column migrations complete: {applied} applied, {failed} skipped/failed")


def run_index_migrations(session_factory) -> None:
    """
    Create all missing indexes using CREATE INDEX IF NOT EXISTS.
    Each index is created in a separate transaction so one failure
    doesn't block the rest.
    """
    created = 0
    skipped = 0
    failed = 0
    for idx_name, table, cols in PART_LABELER_INDEXES:
        sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({cols})"
        try:
            with session_factory() as session:
                session.execute(text(sql))
                session.commit()
            created += 1
        except Exception as e:
            logger.warning(f"Index migration skipped [{idx_name}]: {e}")
            failed += 1
    logger.info(
        f"Index migrations complete: {created} applied, {failed} skipped/failed"
    )


# One-time data cleanup: a since-fixed bug in the Z-Stage 3D layout UI sent the
# rotation sliders' raw DEGREES (0-360) straight into rx/ry/rz columns that are
# supposed to hold RADIANS (same convention as THREE.Object3D.rotation and every
# other rx/ry/rz in these tables). A legitimate radian value from that slider
# can never exceed a full turn (2*pi ~= 6.2832), so any stored value bigger than
# that in magnitude is unambiguously one of these leftover bad values — convert
# it back by treating it as the degrees it always was. Idempotent: once fixed,
# a value is a small radian and the WHERE clause no longer matches it, so this
# is safe to run on every startup.
DATA_MIGRATIONS = [
    """
    UPDATE z3d_layout_placements
    SET rx = CASE WHEN ABS(rx) > 6.2832 THEN rx * 3.14159265358979 / 180 ELSE rx END,
        ry = CASE WHEN ABS(ry) > 6.2832 THEN ry * 3.14159265358979 / 180 ELSE ry END,
        rz = CASE WHEN ABS(rz) > 6.2832 THEN rz * 3.14159265358979 / 180 ELSE rz END
    WHERE ABS(rx) > 6.2832 OR ABS(ry) > 6.2832 OR ABS(rz) > 6.2832
    """,
    """
    UPDATE z3d_model_library
    SET default_rx = CASE WHEN ABS(default_rx) > 6.2832 THEN default_rx * 3.14159265358979 / 180 ELSE default_rx END,
        default_ry = CASE WHEN ABS(default_ry) > 6.2832 THEN default_ry * 3.14159265358979 / 180 ELSE default_ry END,
        default_rz = CASE WHEN ABS(default_rz) > 6.2832 THEN default_rz * 3.14159265358979 / 180 ELSE default_rz END
    WHERE ABS(default_rx) > 6.2832 OR ABS(default_ry) > 6.2832 OR ABS(default_rz) > 6.2832
    """,
]


def run_data_migrations(session_factory) -> None:
    """
    Run one-time idempotent data-cleanup UPDATEs. Safe to run on every
    startup — each statement's WHERE clause only matches rows still needing
    the fix, so it's a no-op once the data is clean.
    """
    fixed_rows = 0
    failed = 0
    for sql in DATA_MIGRATIONS:
        try:
            with session_factory() as session:
                result = session.execute(text(sql))
                session.commit()
                fixed_rows += result.rowcount or 0
        except Exception as e:
            logger.warning(f"Data migration skipped [{sql[:60].strip()}]: {e}")
            failed += 1
    if fixed_rows > 0:
        logger.info(f"Data migrations complete: {fixed_rows} row(s) fixed, {failed} skipped/failed")
    else:
        logger.info(f"Data migrations complete: nothing to fix, {failed} skipped/failed")
