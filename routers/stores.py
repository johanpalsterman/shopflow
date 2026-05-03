"""
routers/stores.py - ShopFlow v1.0.0
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_connection, get_cursor, dict_row, adapt_query
from auth_utils import get_current_user

router = APIRouter()


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    logo_url: Optional[str] = None


@router.get("/me")
async def get_my_store(user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("""
        SELECT id, name, slug, email, address, phone, logo_url, plan, active, created_at
        FROM tenants WHERE id = ?
    """), (user["tenant_id"],))
    store = cur.fetchone()
    conn.close()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return dict_row(store)


@router.put("/me")
async def update_my_store(data: StoreUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_connection()
    cur = get_cursor(conn)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    cur.execute(adapt_query(f"UPDATE tenants SET {set_clause} WHERE id = ?"),
                (*updates.values(), user["tenant_id"]))
    conn.commit()
    conn.close()
    return {"message": "Store updated"}


@router.get("/stats")
async def get_store_stats(user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    tid = user["tenant_id"]

    cur.execute(adapt_query("SELECT COUNT(*) as c FROM zones WHERE tenant_id = ?"), (tid,))
    zones = dict_row(cur.fetchone())["c"]

    cur.execute(adapt_query("SELECT COUNT(*) as c FROM products WHERE tenant_id = ?"), (tid,))
    products = dict_row(cur.fetchone())["c"]

    cur.execute(adapt_query("SELECT COUNT(*) as c FROM repair_sessions WHERE tenant_id = ?"), (tid,))
    repairs = dict_row(cur.fetchone())["c"]

    conn.close()
    return {"zones": zones, "products": products, "repair_sessions": repairs}
