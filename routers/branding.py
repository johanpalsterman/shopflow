"""
routers/branding.py - ShopFlow v1.1.0
Store white-label branding settings
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_connection, get_cursor, dict_row, adapt_query
from auth_utils import get_current_user

router = APIRouter()


class BrandingUpdate(BaseModel):
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    logo_url: Optional[str] = None
    welcome_message_nl: Optional[str] = None
    welcome_message_fr: Optional[str] = None
    store_tagline: Optional[str] = None
    show_powered_by: Optional[bool] = None
    language_default: Optional[str] = None


def get_branding(tenant_id: int) -> dict:
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("""
        SELECT key, value FROM app_settings
        WHERE tenant_id = ? AND key LIKE 'brand_%'
    """), (tenant_id,))
    rows = cur.fetchall()
    conn.close()

    defaults = {
        "primary_color": "#2563EB",
        "secondary_color": "#10B981",
        "logo_url": "",
        "welcome_message_nl": "Beschrijf uw probleem en wij begeleiden u stap voor stap.",
        "welcome_message_fr": "Décrivez votre problème et nous vous guidons étape par étape.",
        "store_tagline": "",
        "show_powered_by": "true",
        "language_default": "nl"
    }

    branding = {**defaults}
    for row in rows:
        r = dict_row(row)
        key = r["key"].replace("brand_", "")
        branding[key] = r["value"]

    return branding


@router.get("/")
async def get_store_branding(user=Depends(get_current_user)):
    return get_branding(user["tenant_id"])


@router.get("/public/{store_slug}")
async def get_public_branding(store_slug: str):
    """Public endpoint for customer app"""
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id, name FROM tenants WHERE slug = ? AND active = TRUE"), (store_slug,))
    tenant = cur.fetchone()
    conn.close()
    if not tenant:
        raise HTTPException(status_code=404, detail="Winkel niet gevonden")
    t = dict_row(tenant)
    branding = get_branding(t["id"])
    branding["store_name"] = t["name"]
    return branding


@router.put("/")
async def update_branding(data: BrandingUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Geen wijzigingen")

    conn = get_connection()
    cur = get_cursor(conn)
    tid = user["tenant_id"]

    for key, value in updates.items():
        db_key = f"brand_{key}"
        str_val = str(value)
        cur.execute(adapt_query("SELECT id FROM app_settings WHERE tenant_id = ? AND key = ?"), (tid, db_key))
        existing = cur.fetchone()
        if existing:
            cur.execute(adapt_query("UPDATE app_settings SET value = ? WHERE tenant_id = ? AND key = ?"),
                        (str_val, tid, db_key))
        else:
            cur.execute(adapt_query("INSERT INTO app_settings (tenant_id, key, value) VALUES (?, ?, ?)"),
                        (tid, db_key, str_val))

    conn.commit()
    conn.close()
    return {"message": "Branding bijgewerkt"}
