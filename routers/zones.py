"""
routers/zones.py - ShopFlow v1.0.0
Store zone management
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_connection, get_cursor, dict_row, adapt_query, execute_insert
from auth_utils import get_current_user

router = APIRouter()


class ZoneCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#3B82F6"
    grid_x: int = 0
    grid_y: int = 0
    grid_w: int = 2
    grid_h: int = 2
    icon: str = "box"


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    grid_x: Optional[int] = None
    grid_y: Optional[int] = None
    grid_w: Optional[int] = None
    grid_h: Optional[int] = None
    icon: Optional[str] = None


@router.get("/")
async def list_zones(user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("""
        SELECT z.id, z.tenant_id, z.name, z.description, z.color,
               z.grid_x, z.grid_y, z.grid_w, z.grid_h, z.icon, z.created_at,
               COUNT(p.id) as product_count
        FROM zones z
        LEFT JOIN products p ON p.zone_id = z.id
        WHERE z.tenant_id = ?
        GROUP BY z.id, z.tenant_id, z.name, z.description, z.color,
                 z.grid_x, z.grid_y, z.grid_w, z.grid_h, z.icon, z.created_at
        ORDER BY z.grid_y, z.grid_x
    """), (user["tenant_id"],))
    rows = [dict_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


@router.post("/")
async def create_zone(data: ZoneCreate, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    zone_id = execute_insert(cur, """
        INSERT INTO zones (tenant_id, name, description, color, grid_x, grid_y, grid_w, grid_h, icon)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user["tenant_id"], data.name, data.description, data.color,
          data.grid_x, data.grid_y, data.grid_w, data.grid_h, data.icon))
    conn.commit()
    conn.close()
    return {"id": zone_id, "message": "Zone created"}


@router.put("/{zone_id}")
async def update_zone(zone_id: int, data: ZoneUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM zones WHERE id = ? AND tenant_id = ?"),
                (zone_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Zone not found")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    cur.execute(adapt_query(f"UPDATE zones SET {set_clause} WHERE id = ?"),
                (*updates.values(), zone_id))
    conn.commit()
    conn.close()
    return {"message": "Zone updated"}


@router.delete("/{zone_id}")
async def delete_zone(zone_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM zones WHERE id = ? AND tenant_id = ?"),
                (zone_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Zone not found")
    cur.execute(adapt_query("UPDATE products SET zone_id = NULL WHERE zone_id = ?"), (zone_id,))
    cur.execute(adapt_query("DELETE FROM zones WHERE id = ?"), (zone_id,))
    conn.commit()
    conn.close()
    return {"message": "Zone deleted"}
