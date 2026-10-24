"""Tiny database layer: one API for MySQL (PyMySQL) and the SQLite fallback.

Rows come back as plain dicts, DECIMAL -> float, and columns ending in _on -> datetime.date.
"""
import sqlite3
from datetime import date, datetime
from decimal import Decimal

import config

try:
    import pymysql
    import pymysql.cursors
except ImportError:  # only needed for MySQL mode
    pymysql = None


def connect(with_database=True):
    if config.DB_ENGINE == "sqlite":
        conn = sqlite3.connect(config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    if pymysql is None:
        raise RuntimeError("PyMySQL is not installed. Run: pip install -r requirements.txt")
    kwargs = dict(
        host=config.MYSQL_HOST, port=config.MYSQL_PORT,
        user=config.MYSQL_USER, password=config.MYSQL_PASSWORD,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=True,
    )
    if with_database:
        kwargs["database"] = config.MYSQL_DB
    return pymysql.connect(**kwargs)


def _clean(row):
    out = {}
    for k, v in dict(row).items():
        if isinstance(v, Decimal):
            v = float(v)
        elif config.DB_ENGINE == "sqlite" and k.endswith("_on") and isinstance(v, str) and len(v) >= 10:
            v = date.fromisoformat(v[:10])
        elif isinstance(v, datetime) and k.endswith("_on"):
            v = v.date()
        out[k] = v
    return out


class DB:
    def __init__(self, conn):
        self.conn = conn
        self.sqlite = config.DB_ENGINE == "sqlite"

    def _sql(self, sql):
        return sql.replace("%s", "?") if self.sqlite else sql

    def _cur(self):
        return self.conn.cursor()

    def all(self, sql, params=()):
        cur = self._cur()
        cur.execute(self._sql(sql), tuple(params))
        rows = [_clean(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def one(self, sql, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql, params=(), default=0):
        row = self.one(sql, params)
        if not row:
            return default
        val = list(row.values())[0]
        return default if val is None else val

    def execute(self, sql, params=()):
        cur = self._cur()
        cur.execute(self._sql(sql), tuple(params))
        last = cur.lastrowid
        if self.sqlite:
            self.conn.commit()
        cur.close()
        return last

    def commit(self):
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
