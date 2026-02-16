import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    return conn


def init_db():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    identifier TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    bot_id TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS agent_id TEXT REFERENCES agents(identifier)")
            cur.execute("ALTER TABLE suggestions ADD COLUMN IF NOT EXISTS agent_id TEXT")
            cur.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS agent_id TEXT")
            try:
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_votes_project_agent ON votes (project_id, agent_id)")
            except psycopg2.errors.DuplicateTable:
                pass
        print("[DB] Database schema initialized (agents table + agent_id columns)")
    finally:
        conn.close()


def execute(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    finally:
        conn.close()


def fetchone(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            result = cur.fetchone()
            return dict(result) if result else None
    finally:
        conn.close()


def fetchall(sql, params=None):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            results = cur.fetchall()
            return [dict(row) for row in results]
    finally:
        conn.close()
