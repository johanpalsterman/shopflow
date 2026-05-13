"""
database.py - ShopFlow v1.0.0
SQLite for dev (no DATABASE_URL), PostgreSQL when DATABASE_URL is set
"""
import sqlite3
import os

DB_PATH = os.environ.get("SQLITE_PATH", "shopflow.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgresql"))


def get_connection():
    if USE_POSTGRES:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def get_cursor(conn):
    if USE_POSTGRES:
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        return conn.cursor()


def dict_row(row):
    if row is None:
        return None
    return dict(row)


def adapt_query(sql):
    """Convert SQLite-style query to the current backend's dialect"""
    if not USE_POSTGRES:
        return sql
    result = sql.replace("?", "%s")
    result = result.replace("datetime('now', '-7 days')", "NOW() - INTERVAL '7 days'")
    result = result.replace("datetime('now', '-14 days')", "NOW() - INTERVAL '14 days'")
    result = result.replace("datetime('now', '-30 days')", "NOW() - INTERVAL '30 days'")
    return result


def execute_insert(cur, sql, params):
    """Execute an INSERT and return the new row's id"""
    if USE_POSTGRES:
        sql_ret = adapt_query(sql.rstrip().rstrip(";")) + " RETURNING id"
        cur.execute(sql_ret, params)
        return cur.fetchone()["id"]
    else:
        cur.execute(sql, params)
        return cur.lastrowid


def init_db():
    conn = get_connection()
    cur = get_cursor(conn)

    if USE_POSTGRES:
        auto = "SERIAL PRIMARY KEY"
        ts = "TIMESTAMP DEFAULT NOW()"
        bool_t = "BOOLEAN DEFAULT FALSE"
    else:
        auto = "INTEGER PRIMARY KEY AUTOINCREMENT"
        ts = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        bool_t = "INTEGER DEFAULT 0"

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS tenants (
            id {auto},
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            logo_url TEXT,
            google_client_id TEXT,
            google_client_secret TEXT,
            active {bool_t},
            plan TEXT DEFAULT 'starter',
            created_at {ts}
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS store_users (
            id {auto},
            tenant_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            role TEXT DEFAULT 'admin',
            google_id TEXT,
            active {bool_t},
            created_at {ts},
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS zones (
            id {auto},
            tenant_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            color TEXT DEFAULT '#3B82F6',
            grid_x INTEGER DEFAULT 0,
            grid_y INTEGER DEFAULT 0,
            grid_w INTEGER DEFAULT 2,
            grid_h INTEGER DEFAULT 2,
            icon TEXT DEFAULT 'box',
            created_at {ts},
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS products (
            id {auto},
            tenant_id INTEGER NOT NULL,
            zone_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            barcode TEXT,
            sku TEXT,
            price REAL DEFAULT 0.0,
            category TEXT,
            tags TEXT,
            stock_status TEXT DEFAULT 'in_stock',
            image_url TEXT,
            aisle TEXT,
            shelf TEXT,
            position_notes TEXT,
            created_at {ts},
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (zone_id) REFERENCES zones(id)
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS repair_sessions (
            id {auto},
            tenant_id INTEGER NOT NULL,
            session_token TEXT,
            problem_description TEXT NOT NULL,
            ai_guide TEXT,
            products_needed TEXT,
            status TEXT DEFAULT 'active',
            created_at {ts},
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS app_settings (
            id {auto},
            tenant_id INTEGER,
            key TEXT NOT NULL,
            value TEXT,
            updated_at {ts}
        )
    """)

    # v1.2.0: Marker system
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS markers (
            id {auto},
            tenant_id INTEGER NOT NULL,
            marker_number INTEGER NOT NULL,
            label TEXT,
            x_pos REAL DEFAULT 0.5,
            y_pos REAL DEFAULT 0.5,
            zone_id INTEGER,
            location_type TEXT DEFAULT 'shop',
            notes TEXT,
            created_at {ts},
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (zone_id) REFERENCES zones(id)
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS marker_products (
            id {auto},
            marker_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity_note TEXT DEFAULT '',
            created_at {ts},
            FOREIGN KEY (marker_id) REFERENCES markers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Add marker_id column to products if it doesn't exist yet
    try:
        cur.execute("ALTER TABLE products ADD COLUMN marker_id INTEGER")
        conn.commit()
    except Exception:
        pass  # Column already exists

    conn.commit()
    cur.close()
    conn.close()
    print("[ShopFlow] Database initialized")
