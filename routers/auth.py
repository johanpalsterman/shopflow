"""
routers/auth.py - ShopFlow v1.0.0
Authentication: local + Google OAuth
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection, get_cursor, dict_row, adapt_query, execute_insert
from auth_utils import hash_password, verify_password, create_token
import re
import os

router = APIRouter()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


class StoreRegister(BaseModel):
    store_name: str
    email: str
    password: str
    address: str = ""
    phone: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str
    store_slug: str = ""


class GoogleTokenRequest(BaseModel):
    google_token: str
    store_slug: str = ""


@router.post("/register")
async def register_store(data: StoreRegister):
    if len(data.password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")

    slug = slugify(data.store_name)
    conn = get_connection()
    cur = get_cursor(conn)

    cur.execute(adapt_query("SELECT id FROM tenants WHERE email = ?"), (data.email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    base_slug = slug
    i = 1
    while True:
        cur.execute(adapt_query("SELECT id FROM tenants WHERE slug = ?"), (slug,))
        if not cur.fetchone():
            break
        slug = f"{base_slug}-{i}"
        i += 1

    pw_hash = hash_password(data.password)

    tenant_id = execute_insert(cur, """
        INSERT INTO tenants (name, slug, email, password_hash, address, phone, active)
        VALUES (?, ?, ?, ?, ?, ?, TRUE)
    """, (data.store_name, slug, data.email, pw_hash, data.address, data.phone))

    execute_insert(cur, """
        INSERT INTO store_users (tenant_id, email, password_hash, name, role, active)
        VALUES (?, ?, ?, ?, 'admin', TRUE)
    """, (tenant_id, data.email, pw_hash, data.store_name))

    conn.commit()
    conn.close()

    token = create_token(None, tenant_id, "admin", data.email)

    return {
        "token": token,
        "tenant_id": tenant_id,
        "store_slug": slug,
        "store_name": data.store_name,
        "email": data.email,
        "role": "admin"
    }


@router.post("/login")
async def login(data: LoginRequest):
    conn = get_connection()
    cur = get_cursor(conn)

    tenant_id = None
    if data.store_slug:
        cur.execute(adapt_query("SELECT id FROM tenants WHERE slug = ?"), (data.store_slug,))
        tenant = cur.fetchone()
        if not tenant:
            conn.close()
            raise HTTPException(status_code=404, detail="Store not found")
        tenant_id = dict_row(tenant)["id"]
        cur.execute(adapt_query("""
            SELECT id, password_hash, name, role FROM store_users
            WHERE tenant_id = ? AND email = ? AND active = TRUE
        """), (tenant_id, data.email))
    else:
        cur.execute(adapt_query("""
            SELECT su.id, su.password_hash, su.name, su.role, su.tenant_id
            FROM store_users su
            JOIN tenants t ON t.id = su.tenant_id
            WHERE su.email = ? AND su.active = TRUE
        """), (data.email,))

    user = cur.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = dict_row(user)

    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    tid = user.get("tenant_id", tenant_id)
    token = create_token(user["id"], tid, user["role"], data.email)

    return {
        "token": token,
        "tenant_id": tid,
        "email": data.email,
        "name": user.get("name", ""),
        "role": user["role"]
    }


@router.get("/stores")
async def list_stores():
    """Public endpoint: list active stores for customer login"""
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute("SELECT name, slug FROM tenants WHERE active = TRUE ORDER BY name")
    rows = [dict_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


@router.post("/google")
async def google_login(data: GoogleTokenRequest):
    """Exchange Google token for ShopFlow JWT"""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {data.google_token}"}
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google token")
            guser = resp.json()

        email = guser.get("email")
        google_id = guser.get("sub")

        conn = get_connection()
        cur = get_cursor(conn)

        tenant_id = None
        if data.store_slug:
            cur.execute(adapt_query("SELECT id FROM tenants WHERE slug = ?"), (data.store_slug,))
            tenant = cur.fetchone()
            if not tenant:
                conn.close()
                raise HTTPException(status_code=404, detail="Store not found")
            tenant_id = dict_row(tenant)["id"]
        else:
            cur.execute(adapt_query("SELECT tenant_id FROM store_users WHERE google_id = ? OR email = ?"), (google_id, email))
            u = cur.fetchone()
            if not u:
                conn.close()
                raise HTTPException(status_code=404, detail="No account found. Register your store first.")
            tenant_id = dict_row(u)["tenant_id"]

        cur.execute(adapt_query("""
            SELECT id, role FROM store_users WHERE tenant_id = ? AND (google_id = ? OR email = ?)
        """), (tenant_id, google_id, email))
        user = cur.fetchone()

        if not user:
            user_id = execute_insert(cur, """
                INSERT INTO store_users (tenant_id, email, password_hash, name, role, google_id, active)
                VALUES (?, ?, '', ?, 'admin', ?, TRUE)
            """, (tenant_id, email, guser.get("name", email), google_id))
            role = "admin"
        else:
            user = dict_row(user)
            user_id = user["id"]
            role = user["role"]
            cur.execute(adapt_query("UPDATE store_users SET google_id = ? WHERE id = ?"), (google_id, user_id))

        conn.commit()
        conn.close()

        token = create_token(user_id, tenant_id, role, email)
        return {"token": token, "tenant_id": tenant_id, "email": email, "role": role}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google auth error: {str(e)}")
