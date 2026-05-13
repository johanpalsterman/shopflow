"""
routers/markers.py - ShopFlow v1.2.0
Marker location system - physical numbered markers in shop/garage/home
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_connection, get_cursor, dict_row, adapt_query, execute_insert
from auth_utils import get_current_user

router = APIRouter()


class MarkerCreate(BaseModel):
    marker_number: int
    label: str = ""
    x_pos: float = 0.5
    y_pos: float = 0.5
    zone_id: Optional[int] = None
    location_type: str = "shop"  # 'shop' | 'garage' | 'home'
    notes: str = ""


class MarkerUpdate(BaseModel):
    marker_number: Optional[int] = None
    label: Optional[str] = None
    x_pos: Optional[float] = None
    y_pos: Optional[float] = None
    zone_id: Optional[int] = None
    location_type: Optional[str] = None
    notes: Optional[str] = None


class MarkerProductLink(BaseModel):
    product_id: int
    quantity_note: str = ""


@router.get("/")
async def list_markers(user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("""
        SELECT m.id, m.tenant_id, m.marker_number, m.label, m.x_pos, m.y_pos,
               m.zone_id, m.location_type, m.notes, m.created_at,
               z.name as zone_name,
               COUNT(mp.id) as product_count
        FROM markers m
        LEFT JOIN zones z ON z.id = m.zone_id
        LEFT JOIN marker_products mp ON mp.marker_id = m.id
        WHERE m.tenant_id = ?
        GROUP BY m.id, m.tenant_id, m.marker_number, m.label, m.x_pos, m.y_pos,
                 m.zone_id, m.location_type, m.notes, m.created_at, z.name
        ORDER BY m.marker_number
    """), (user["tenant_id"],))
    rows = [dict_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


@router.get("/public/{store_slug}/")
async def public_list_markers(store_slug: str):
    """Public endpoint: all markers for map display (customer app)"""
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM tenants WHERE slug = ? AND active = TRUE"), (store_slug,))
    tenant = cur.fetchone()
    if not tenant:
        conn.close()
        raise HTTPException(status_code=404, detail="Store not found")
    tenant_id = dict_row(tenant)["id"]

    cur.execute(adapt_query("""
        SELECT m.id, m.marker_number, m.label, m.x_pos, m.y_pos,
               m.location_type, m.notes,
               z.name as zone_name, z.color as zone_color,
               COUNT(mp.id) as product_count
        FROM markers m
        LEFT JOIN zones z ON z.id = m.zone_id
        LEFT JOIN marker_products mp ON mp.marker_id = m.id
        WHERE m.tenant_id = ?
        GROUP BY m.id, m.marker_number, m.label, m.x_pos, m.y_pos,
                 m.location_type, m.notes, z.name, z.color
        ORDER BY m.marker_number
    """), (tenant_id,))
    rows = [dict_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


@router.get("/public/{store_slug}/{marker_number}")
async def public_marker_products(store_slug: str, marker_number: int):
    """Public endpoint: all products at a marker number (for customer app after scanning)"""
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM tenants WHERE slug = ? AND active = TRUE"), (store_slug,))
    tenant = cur.fetchone()
    if not tenant:
        conn.close()
        raise HTTPException(status_code=404, detail="Store not found")
    tenant_id = dict_row(tenant)["id"]

    cur.execute(adapt_query("""
        SELECT m.id, m.marker_number, m.label, m.x_pos, m.y_pos,
               m.location_type, m.notes,
               z.name as zone_name, z.color as zone_color
        FROM markers m
        LEFT JOIN zones z ON z.id = m.zone_id
        WHERE m.tenant_id = ? AND m.marker_number = ?
    """), (tenant_id, marker_number))
    marker = cur.fetchone()
    if not marker:
        conn.close()
        raise HTTPException(status_code=404, detail="Marker not found")
    marker_data = dict_row(marker)

    cur.execute(adapt_query("""
        SELECT p.id, p.name, p.description, p.price, p.aisle, p.shelf,
               p.position_notes, p.stock_status, p.image_url, p.category,
               z.name as zone_name, z.color as zone_color,
               mp.quantity_note
        FROM marker_products mp
        JOIN products p ON p.id = mp.product_id
        LEFT JOIN zones z ON z.id = p.zone_id
        WHERE mp.marker_id = ?
        ORDER BY p.name
    """), (marker_data["id"],))
    products = [dict_row(r) for r in cur.fetchall()]
    conn.close()

    marker_data["products"] = products
    return marker_data


@router.get("/{marker_id}")
async def get_marker(marker_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("""
        SELECT m.*, z.name as zone_name
        FROM markers m
        LEFT JOIN zones z ON z.id = m.zone_id
        WHERE m.id = ? AND m.tenant_id = ?
    """), (marker_id, user["tenant_id"]))
    marker = cur.fetchone()
    if not marker:
        conn.close()
        raise HTTPException(status_code=404, detail="Marker not found")
    marker_data = dict_row(marker)

    cur.execute(adapt_query("""
        SELECT p.id, p.name, p.description, p.price, p.aisle, p.shelf,
               p.position_notes, p.stock_status, p.category,
               z.name as zone_name, z.color as zone_color,
               mp.id as link_id, mp.quantity_note
        FROM marker_products mp
        JOIN products p ON p.id = mp.product_id
        LEFT JOIN zones z ON z.id = p.zone_id
        WHERE mp.marker_id = ?
        ORDER BY p.name
    """), (marker_id,))
    marker_data["products"] = [dict_row(r) for r in cur.fetchall()]
    conn.close()
    return marker_data


@router.post("/")
async def create_marker(data: MarkerCreate, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)

    # Check uniqueness of marker_number per tenant
    cur.execute(adapt_query(
        "SELECT id FROM markers WHERE tenant_id = ? AND marker_number = ?"
    ), (user["tenant_id"], data.marker_number))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Marker number already exists for this tenant")

    if data.zone_id:
        cur.execute(adapt_query("SELECT id FROM zones WHERE id = ? AND tenant_id = ?"),
                    (data.zone_id, user["tenant_id"]))
        if not cur.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Zone not found")

    marker_id = execute_insert(cur, """
        INSERT INTO markers (tenant_id, marker_number, label, x_pos, y_pos, zone_id, location_type, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user["tenant_id"], data.marker_number, data.label, data.x_pos, data.y_pos,
          data.zone_id, data.location_type, data.notes))
    conn.commit()
    conn.close()
    return {"id": marker_id, "message": "Marker created"}


@router.put("/{marker_id}")
async def update_marker(marker_id: int, data: MarkerUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM markers WHERE id = ? AND tenant_id = ?"),
                (marker_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Marker not found")

    # Check uniqueness if marker_number is being updated
    if "marker_number" in updates:
        cur.execute(adapt_query(
            "SELECT id FROM markers WHERE tenant_id = ? AND marker_number = ? AND id != ?"
        ), (user["tenant_id"], updates["marker_number"], marker_id))
        if cur.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Marker number already exists")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    cur.execute(adapt_query(f"UPDATE markers SET {set_clause} WHERE id = ?"),
                (*updates.values(), marker_id))
    conn.commit()
    conn.close()
    return {"message": "Marker updated"}


@router.delete("/{marker_id}")
async def delete_marker(marker_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM markers WHERE id = ? AND tenant_id = ?"),
                (marker_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Marker not found")
    cur.execute(adapt_query("DELETE FROM marker_products WHERE marker_id = ?"), (marker_id,))
    cur.execute(adapt_query("DELETE FROM markers WHERE id = ?"), (marker_id,))
    conn.commit()
    conn.close()
    return {"message": "Marker deleted"}


@router.post("/{marker_id}/products")
async def link_product_to_marker(marker_id: int, data: MarkerProductLink, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM markers WHERE id = ? AND tenant_id = ?"),
                (marker_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Marker not found")
    cur.execute(adapt_query("SELECT id FROM products WHERE id = ? AND tenant_id = ?"),
                (data.product_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    # Avoid duplicate links
    cur.execute(adapt_query(
        "SELECT id FROM marker_products WHERE marker_id = ? AND product_id = ?"
    ), (marker_id, data.product_id))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Product already linked to this marker")

    link_id = execute_insert(cur, """
        INSERT INTO marker_products (marker_id, product_id, quantity_note)
        VALUES (?, ?, ?)
    """, (marker_id, data.product_id, data.quantity_note))
    conn.commit()
    conn.close()
    return {"id": link_id, "message": "Product linked to marker"}


@router.delete("/{marker_id}/products/{product_id}")
async def unlink_product_from_marker(marker_id: int, product_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM markers WHERE id = ? AND tenant_id = ?"),
                (marker_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Marker not found")
    cur.execute(adapt_query(
        "DELETE FROM marker_products WHERE marker_id = ? AND product_id = ?"
    ), (marker_id, product_id))
    conn.commit()
    conn.close()
    return {"message": "Product unlinked from marker"}
