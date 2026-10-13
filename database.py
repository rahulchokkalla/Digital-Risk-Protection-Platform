import os
from pathlib import Path
import sqlite3
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE, override=True)

DB_TYPE = os.getenv("DB_TYPE", "auto").lower()
DB_FILE = BASE_DIR / os.getenv("DB_FILE", "shieldwatch.db")

try:
    import mysql.connector
except ImportError:
    mysql = None


class SQLiteCursorWrapper:
    """Cursor wrapper that translates MySQL dialect to SQLite."""

    def __init__(self, cursor, dictionary=False):
        self._cursor = cursor
        self._dictionary = dictionary

    def execute(self, sql, params=None):
        adapted = sql
        adapted = adapted.replace("INSERT IGNORE INTO", "INSERT OR IGNORE INTO")
        adapted = adapted.replace("AUTO_INCREMENT", "AUTOINCREMENT")
        adapted = adapted.replace("%s", "?")
        if params is None:
            return self._cursor.execute(adapted)
        return self._cursor.execute(adapted, params)

    def executemany(self, sql, seq_of_params):
        adapted = sql.replace("INSERT IGNORE INTO", "INSERT OR IGNORE INTO")
        adapted = adapted.replace("AUTO_INCREMENT", "AUTOINCREMENT")
        adapted = adapted.replace("%s", "?")
        return self._cursor.executemany(adapted, seq_of_params)

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return dict(row) if self._dictionary else row

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [dict(r) for r in rows] if self._dictionary else rows

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass


class SQLiteConnectionWrapper:
    """Connection wrapper for SQLite database file."""

    def __init__(self, conn):
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._is_closed = False

    def cursor(self, dictionary=False, **kwargs):
        return SQLiteCursorWrapper(self._conn.cursor(), dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._is_closed = True
        self._conn.close()

    def is_connected(self):
        return not self._is_closed


def _get_mysql_connection():
    if mysql is None:
        return None
    try:
        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "3306"))
        user = os.getenv("DB_USER", "root")
        password = os.getenv("DB_PASSWORD", "")
        database = os.getenv("DB_NAME", "digital_risk_db")
        return mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connection_timeout=5,
        )
    except Exception:
        return None


def get_connection():
    """Connect to MySQL if configured, or fall back to local server SQLite file."""
    if DB_TYPE == "mysql" or DB_TYPE == "auto":
        conn = _get_mysql_connection()
        if conn is not None:
            return conn
        if DB_TYPE == "mysql":
            # If explicitly requested MySQL, retry or raise
            raise ConnectionError(
                "Failed to connect to MySQL database. Verify DB_HOST, DB_USER, DB_PASSWORD."
            )

    # SQLite file stored on the server
    conn = sqlite3.connect(str(DB_FILE), check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return SQLiteConnectionWrapper(conn)


def create_tables():
    """Create all tables required by ShieldWatch."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Table 1: Brand profiles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brand_profiles (
                brand_id INTEGER PRIMARY KEY AUTO_INCREMENT,
                company_name VARCHAR(150) NOT NULL,
                legal_entity VARCHAR(200),
                official_logo_url VARCHAR(500),
                verified_social_handles TEXT,
                official_app_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 2: Trusted or official assets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whitelist_assets (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                brand_id INT NOT NULL,
                asset_type VARCHAR(50) NOT NULL,
                asset_value VARCHAR(500) NOT NULL,
                FOREIGN KEY (brand_id)
                    REFERENCES brand_profiles(brand_id)
                    ON DELETE CASCADE,
                UNIQUE (brand_id, asset_type, asset_value)
            )
        """)

        # Table 3: Application and monitoring scan results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                brand_id INT NOT NULL,
                platform VARCHAR(50) NOT NULL,
                app_name VARCHAR(250),
                publisher VARCHAR(250),
                app_id VARCHAR(300),
                description TEXT,
                icon_url TEXT,
                risk_score INT DEFAULT 0,
                status VARCHAR(50) DEFAULT 'Needs Review',
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (brand_id)
                    REFERENCES brand_profiles(brand_id)
                    ON DELETE CASCADE
            )
        """)

        connection.commit()
        print("All database tables verified and created successfully!")

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


def test_connection():
    """Check database availability."""
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        print("Database connection test succeeded!")
        return True
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    test_connection()
    create_tables()
