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
            cur.execute("DROP TABLE IF EXISTS votes CASCADE")
            cur.execute("DROP TABLE IF EXISTS suggestions CASCADE")
            cur.execute("DROP TABLE IF EXISTS projects CASCADE")
            cur.execute("DROP TABLE IF EXISTS agents CASCADE")

            cur.execute("""
                CREATE TABLE agents (
                    identifier TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    bot_id TEXT,
                    connected BOOLEAN NOT NULL DEFAULT FALSE,
                    last_active_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE projects (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    script TEXT DEFAULT '',
                    agent_id TEXT REFERENCES agents(identifier),
                    grid_x INT NOT NULL,
                    grid_z INT NOT NULL,
                    upvotes INT DEFAULT 0,
                    last_built_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP,
                    UNIQUE(grid_x, grid_z)
                )
            """)

            cur.execute("""
                CREATE TABLE suggestions (
                    id SERIAL PRIMARY KEY,
                    project_id INT REFERENCES projects(id),
                    suggestion TEXT NOT NULL,
                    agent_id TEXT,
                    read_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)

            cur.execute("""
                CREATE TABLE votes (
                    id SERIAL PRIMARY KEY,
                    project_id INT REFERENCES projects(id),
                    agent_id TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE(project_id, agent_id)
                )
            """)
        print("[DB] Database schema initialized (all tables created fresh)")
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
