import os
import asyncpg

pool = None


async def init_pool():
    global pool
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")
    pool = await asyncpg.create_pool(database_url)


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None


async def init_db():
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS votes CASCADE")
        await conn.execute("DROP TABLE IF EXISTS suggestions CASCADE")
        await conn.execute("DROP TABLE IF EXISTS projects CASCADE")
        await conn.execute("DROP TABLE IF EXISTS agents CASCADE")

        await conn.execute("""
            CREATE TABLE agents (
                identifier TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                bot_id TEXT,
                connected BOOLEAN NOT NULL DEFAULT FALSE,
                last_active_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
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

        await conn.execute("""
            CREATE TABLE suggestions (
                id SERIAL PRIMARY KEY,
                project_id INT REFERENCES projects(id),
                suggestion TEXT NOT NULL,
                agent_id TEXT,
                read_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE votes (
                id SERIAL PRIMARY KEY,
                project_id INT REFERENCES projects(id),
                agent_id TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(project_id, agent_id)
            )
        """)
    print("[DB] Database schema initialized (all tables created fresh)")


async def execute(sql, params=None):
    async with pool.acquire() as conn:
        if params:
            await conn.execute(sql, *params)
        else:
            await conn.execute(sql)


async def fetchone(sql, params=None):
    async with pool.acquire() as conn:
        if params:
            row = await conn.fetchrow(sql, *params)
        else:
            row = await conn.fetchrow(sql)
        return dict(row) if row else None


async def fetchall(sql, params=None):
    async with pool.acquire() as conn:
        if params:
            rows = await conn.fetch(sql, *params)
        else:
            rows = await conn.fetch(sql)
        return [dict(row) for row in rows]
