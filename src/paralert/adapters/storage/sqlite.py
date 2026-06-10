import json
import sqlite3

from paralert.domain.models import CalmSlot, CheckResult, Settings, SlotConfig, Summit, WindSlot
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
    calm_slots   TEXT    NOT NULL,
    max_wind_kmh REAL    NOT NULL,
    all_slots    TEXT    NOT NULL DEFAULT '[]'
);
"""

SETTINGS_DEFAULTS = {
    "ntfy_url": "https://ntfy.sh",
    "ntfy_topic": "paralert",
    "wind_calm_kmh": "15",
    "cron_expression": "0 6 * * *",
    "season_start": "04-15",
    "season_end": "11-15",
    "require_no_snow": "true",
    "only_off_peak": "false",
    "timezone": "Europe/Paris",
    "cloud_cover_max_pct": "50",
    "custom_slots": "[]",
}


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        for key, value in SETTINGS_DEFAULTS.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))


def _migrate(conn: sqlite3.Connection) -> None:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(check_results)").fetchall()]
    if "calm_hours" in cols:
        conn.execute("DROP TABLE check_results")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS check_results (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at   TEXT    NOT NULL,
                summit_id    INTEGER NOT NULL REFERENCES summits(id) ON DELETE CASCADE,
                target_date  TEXT    NOT NULL,
                calm_slots   TEXT    NOT NULL,
                max_wind_kmh REAL    NOT NULL,
                all_slots    TEXT    NOT NULL DEFAULT '[]'
            );
        """)
    if "all_slots" not in cols:
        conn.execute("ALTER TABLE check_results ADD COLUMN all_slots TEXT NOT NULL DEFAULT '[]'")
    summit_cols = [r[1] for r in conn.execute("PRAGMA table_info(summits)").fetchall()]
    if "custom_slots" not in summit_cols:
        conn.execute("ALTER TABLE summits ADD COLUMN custom_slots TEXT DEFAULT NULL")


def _row_to_summit(row: sqlite3.Row) -> Summit:
    raw_slots = row["custom_slots"]
    return Summit(
        id=row["id"],
        name=row["name"],
        lat=row["lat"],
        lon=row["lon"],
        altitudes_m=tuple(json.loads(row["altitudes_m"])),
        enabled=bool(row["enabled"]),
        custom_slots=_json_to_slot_configs(raw_slots) if raw_slots is not None else None,
    )


def _slot_configs_to_json(slots: tuple[SlotConfig, ...]) -> str:
    return json.dumps([{"start_hour": s.start_hour, "end_hour": s.end_hour} for s in slots])


def _json_to_slot_configs(raw: str) -> tuple[SlotConfig, ...]:
    return tuple(SlotConfig(start_hour=s["start_hour"], end_hour=s["end_hour"]) for s in json.loads(raw))


def _calm_slots_to_json(slots: tuple[CalmSlot, ...]) -> str:
    return json.dumps([
        {
            "start_hour": s.start_hour,
            "end_hour": s.end_hour,
            "is_calm": s.is_calm,
            "wind_by_altitude": [
                {"altitude_m": w.altitude_m, "mean_speed_kmh": w.mean_speed_kmh,
                 "max_speed_kmh": w.max_speed_kmh, "mean_direction_deg": w.mean_direction_deg}
                for w in s.wind_by_altitude
            ],
        }
        for s in slots
    ])


def _json_to_calm_slots(raw: str) -> tuple[CalmSlot, ...]:
    return tuple(
        CalmSlot(
            start_hour=s["start_hour"],
            end_hour=s["end_hour"],
            is_calm=s.get("is_calm", True),
            wind_by_altitude=tuple(
                WindSlot(altitude_m=w["altitude_m"], mean_speed_kmh=w["mean_speed_kmh"],
                         max_speed_kmh=w["max_speed_kmh"], mean_direction_deg=w["mean_direction_deg"])
                for w in s["wind_by_altitude"]
            ),
        )
        for s in json.loads(raw)
    )


class SqliteSummitRepository(SummitRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def list(self, *, enabled_only: bool = False) -> list[Summit]:
        query = "SELECT * FROM summits" + (" WHERE enabled = 1" if enabled_only else "")
        with _connect(self._db_path) as conn:
            return [_row_to_summit(r) for r in conn.execute(query)]

    def get(self, id: int) -> Summit:
        with _connect(self._db_path) as conn:
            row = conn.execute("SELECT * FROM summits WHERE id = ?", (id,)).fetchone()
        if row is None:
            raise KeyError(f"Summit {id} not found")
        return _row_to_summit(row)

    def add(self, summit: Summit) -> Summit:
        raw_slots = _slot_configs_to_json(summit.custom_slots) if summit.custom_slots is not None else None
        with _connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO summits (name, lat, lon, altitudes_m, enabled, custom_slots) VALUES (?, ?, ?, ?, ?, ?)",
                (summit.name, summit.lat, summit.lon, json.dumps(list(summit.altitudes_m)), int(summit.enabled), raw_slots),
            )
            row = conn.execute("SELECT * FROM summits WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_summit(row)

    def update(self, summit: Summit) -> Summit:
        raw_slots = _slot_configs_to_json(summit.custom_slots) if summit.custom_slots is not None else None
        with _connect(self._db_path) as conn:
            conn.execute(
                "UPDATE summits SET name=?, lat=?, lon=?, altitudes_m=?, enabled=?, custom_slots=? WHERE id=?",
                (summit.name, summit.lat, summit.lon, json.dumps(list(summit.altitudes_m)), int(summit.enabled), raw_slots, summit.id),
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
            season_start=data.get("season_start", "04-15"),
            season_end=data.get("season_end", "11-15"),
            require_no_snow=data.get("require_no_snow", "true").lower() == "true",
            only_off_peak=data.get("only_off_peak", "false").lower() == "true",
            timezone=data.get("timezone", "Europe/Paris"),
            cloud_cover_max_pct=float(data.get("cloud_cover_max_pct", "50")),
            custom_slots=_json_to_slot_configs(data.get("custom_slots", "[]")),
        )

    def save(self, settings: Settings) -> None:
        pairs = {
            "ntfy_url": settings.ntfy_url,
            "ntfy_topic": settings.ntfy_topic,
            "wind_calm_kmh": str(settings.wind_calm_kmh),
            "cron_expression": settings.cron_expression,
            "season_start": settings.season_start,
            "season_end": settings.season_end,
            "require_no_snow": str(settings.require_no_snow).lower(),
            "only_off_peak": str(settings.only_off_peak).lower(),
            "timezone": settings.timezone,
            "cloud_cover_max_pct": str(settings.cloud_cover_max_pct),
            "custom_slots": _slot_configs_to_json(settings.custom_slots),
        }
        with _connect(self._db_path) as conn:
            conn.executemany("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", pairs.items())


class SqliteCheckResultRepository(CheckResultRepository):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def save(self, result: CheckResult) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO check_results (checked_at, summit_id, target_date, calm_slots, max_wind_kmh, all_slots) VALUES (?, ?, ?, ?, ?, ?)",
                (result.checked_at, result.summit_id, result.target_date, _calm_slots_to_json(result.calm_slots), result.max_wind_kmh, _calm_slots_to_json(result.all_slots)),
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
                INNER JOIN summits s ON cr.summit_id = s.id AND s.enabled = 1
                ORDER BY cr.summit_id, cr.target_date
            """).fetchall()
        return [
            CheckResult(
                summit_id=r["summit_id"],
                target_date=r["target_date"],
                calm_slots=_json_to_calm_slots(r["calm_slots"]),
                max_wind_kmh=r["max_wind_kmh"],
                checked_at=r["checked_at"],
                all_slots=_json_to_calm_slots(r["all_slots"]),
            )
            for r in rows
        ]
