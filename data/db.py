"""The one SQLite file of the app: where it is, how to open it, and its schema (created / upgraded in migrate)."""
import sqlite3
from contextlib import closing
from pathlib import Path

from app import config


def _add_missing_columns(c, table: str, columns: dict[str, str]):
    have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
    for name, decl in columns.items():
        if name not in have:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = str(path or config.data_dir() / "library.db")
        self.covers_dir = Path(self.path).parent / "covers"  # custom playlist covers
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def migrate(self):
        """Idempotent: creates missing tables and adds columns that older versions did not have."""
        with closing(self.connect()) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS tracks(
                id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE,
                title TEXT, artist TEXT, album TEXT, added REAL, fmt TEXT, duration REAL)""")
            # year / genre NULL = metadata not read yet (filled in by LibraryService backfill)
            _add_missing_columns(c, "tracks", {"year": "INTEGER", "genre": "TEXT"})
            c.execute("""CREATE TABLE IF NOT EXISTS play_stats(
                track_id INTEGER PRIMARY KEY, play_count INTEGER NOT NULL DEFAULT 0, last_played REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS playlists(
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created REAL)""")
            _add_missing_columns(c, "playlists", {"description": "TEXT NOT NULL DEFAULT ''",
                                                  "cover": "TEXT NOT NULL DEFAULT ''"})
            c.execute("""CREATE TABLE IF NOT EXISTS playlist_tracks(
                playlist_id INTEGER, track_id INTEGER, position INTEGER,
                PRIMARY KEY(playlist_id, track_id))""")
            c.commit()
