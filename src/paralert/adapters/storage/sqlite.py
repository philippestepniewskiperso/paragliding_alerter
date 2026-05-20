import json
import sqlite3
from datetime import datetime, timezone

from paralert.domain.models import CheckResult, Settings, Summit
from paralert.domain.ports import CheckResultRepository, SettingsRepository, SummitRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    lat         REAL    NOT NULL,
    lon         REAL    NOT NULL,
    altitudes_m TEXT    NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS check_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at   TEXT    NOT NULL,
    summit_id    INTEGER NOT NULL REFERENCES summits(id) ON DELETE CASCADE,
    target_date  TEXT    NOT NULL,
    calm_hours   TEXT    NOT NULL,
    max_wind_kmh REAL    NOT NULL
);
"""

SETTINGS_DEFAULTS = {
    "ntfy_url": "https://ntfy.sh",
    "ntfy_topic": "paralert",
    "wind_calm_kmh": "15",
    "cron_expression": "0 6 * * *",
}


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)
        for key, value in SETTINGS_DEFAULTS.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))


def _row_to_summit(row: sqlite3.Row) -> Summit:
    return Summit(
        id=row["id"],
        name=row["name"],
        lat=row["lat"],
        lon=row["lon"],
        altitudes_m=tuple(json.loads(row["altitudes_m"])),
        enabled=bool(row["enabled"]),
    )


class SqliteSummitRepository(SummitRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def list(self, *, enabled_only: bool = False) -> list[Summit]:
        query = "SELECT * FROM summits"
        params: tuple = ()
        if enabled_only:
            query += " WHERE enabled = 1"
        with _connect(self._db_path) as conn:
            return [_row_to_summit(r) for r in conn.execute(query, params)]

    def get(self, id: int) -> Summit:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT * FROM summits WHERE id = ?", (id,)).fetchone()
        if row is None:
            raise KeyError(f"Summit {id} not found")
        return _row_to_summit(row)

    def add(self, summit: Summit) -> Summit:
        with _connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO summits (name, lat, lon, altitudes_m, enabled) VALUES (?, ?, ?, ?, ?)",
                (summit.name, summit.lat, summit.lon, json.dumps(list(summit.altitudes_m)), int(summit.enabled)),
            )
            row = conn.execute("SELECT * FROM summits WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_summit(row)

    def update(self, summit: Summit) -> Summit:
        with _connect(self._db_path) as conn:
            conn.execute(
                "UPDATE summits SET name=?, lat=?, lon=?, altitudes_m=?, enabled=? WHERE id=?",
                (summit.name, summit.lat, summit.lon, json.dumps(list(summit.altitudes_m)), int(summit.enabled), summit.id),
            )
            row = conn.execute("SELECT * FROM summits WHERE id = ?", (summit.id,)).fetchone()
        return _row_to_summit(row)

    def delete(self, id: int) -> None:
        with _connect(self._db_path) as conn:
            conn.execute("DELETE FROM summits WHERE id = ?", (id,))


class SqliteSettingsRepository(SettingsRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def get(self) -> Settings:
        with _connect(self._db_path) as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        data = {r["key"]: r["value"] for r in rows}
        return Settings(
            ntfy_url=data["ntfy_url"],
            ntfy_topic=data["ntfy_topic"],
            wind_calm_kmh=float(data["wind_calm_kmh"]),
            cron_expression=data["cron_expression"],
        )

    def save(self, settings: Settings) -> None:
        pairs = {
            "ntfy_url": settings.ntfy_url,
            "ntfy_topic": settings.ntfy_topic,
            "wind_calm_kmh": str(settings.wind_calm_kmh),
            "cron_expression": settings.cron_expression,
        }
        with _connect(self._db_path) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                pairs.items(),
            )


class SqliteCheckResultRepository(CheckResultRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def save(self, result: CheckResult) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO check_results (checked_at, summit_id, target_date, calm_hours, max_wind_kmh) VALUES (?, ?, ?, ?, ?)",
                (result.checked_at, result.summit_id, result.target_date, json.dumps(list(result.calm_hours)), result.max_wind_kmh),
            )

    def last_by_summit(self) -> list[CheckResult]:
        with _connect(self._db_path) as conn:
            rows = conn.execute("""
                SELECT cr.*
                FROM check_results cr
                INNER JOIN (
                    SELECT summit_id, MAX(checked_at) AS max_checked
                    FROM check_results
                    GROUP BY summit_id
                ) latest ON cr.summit_id = latest.summit_id AND cr.checked_at = latest.max_checked
                ORDER BY cr.summit_id
            """).fetchall()
        return [
            CheckResult(
                summit_id=r["summit_id"],
                target_date=r["target_date"],
                calm_hours=tuple(json.loads(r["calm_hours"])),
                max_wind_kmh=r["max_wind_kmh"],
                checked_at=r["checked_at"],
            )
            for r in rows
        ]
