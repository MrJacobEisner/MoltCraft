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
