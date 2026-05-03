"""
routers/products.py - ShopFlow v1.0.0
Product management + public search
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional
from database import get_connection, get_cursor, dict_row, adapt_query, execute_insert
from auth_utils import get_current_user

router = APIRouter()


class ProductCreate(BaseModel):
    name: str
    description: str = ""
    barcode: str = ""
    sku: str = ""
    price: float = 0.0
    category: str = ""
    tags: str = ""
    zone_id: Optional[int] = None
    aisle: str = ""
    shelf: str = ""
    position_notes: str = ""
    stock_status: str = "in_stock"
    image_url: str = ""


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    zone_id: Optional[int] = None
    aisle: Optional[str] = None
    shelf: Optional[str] = None
    position_notes: Optional[str] = None
    stock_status: Optional[str] = None
    image_url: Optional[str] = None


@router.get("/")
async def list_products(
    zone_id: Optional[int] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    user=Depends(get_current_user)
):
    conn = get_connection()
    cur = get_cursor(conn)

    query = """
        SELECT p.*, z.name as zone_name, z.color as zone_color
        FROM products p
        LEFT JOIN zones z ON z.id = p.zone_id
        WHERE p.tenant_id = ?
    """
    params = [user["tenant_id"]]

    if zone_id:
        query += " AND p.zone_id = ?"
        params.append(zone_id)
    if category:
        query += " AND p.category = ?"
        params.append(category)
    if search:
        query += " AND (p.name LIKE ? OR p.description LIKE ? OR p.barcode LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])

    query += " ORDER BY p.name"
    cur.execute(adapt_query(query), params)
    rows = [dict_row(r) for r in cur.fetchall()]
    conn.close()
    return rows


@router.get("/public/{store_slug}")
async def public_products(
    store_slug: str,
    names: str = Query("", description="Comma-separated product names to find")
):
    """Public endpoint for customer app - find products by name/keywords"""
    conn = get_connection()
    cur = get_cursor(conn)

    cur.execute(adapt_query("SELECT id FROM tenants WHERE slug = ? AND active = TRUE"), (store_slug,))
    tenant = cur.fetchone()
    if not tenant:
        conn.close()
        raise HTTPException(status_code=404, detail="Store not found")
    tenant_id = dict_row(tenant)["id"]

    name_list = [n.strip() for n in names.split(",") if n.strip()]

    if name_list:
        results = []
        for name in name_list:
            cur.execute(adapt_query("""
                SELECT p.name, p.description, p.price, p.aisle, p.shelf,
                       p.position_notes, p.stock_status, p.image_url,
                       z.name as zone_name, z.color as zone_color,
                       z.grid_x, z.grid_y, z.icon as zone_icon
                FROM products p
                LEFT JOIN zones z ON z.id = p.zone_id
                WHERE p.tenant_id = ?
                AND (p.name LIKE ? OR p.tags LIKE ? OR p.category LIKE ?)
                LIMIT 3
            """), (tenant_id, f"%{name}%", f"%{name}%", f"%{name}%"))
            rows = [dict_row(r) for r in cur.fetchall()]
            for r in rows:
                r["search_term"] = name
            results.extend(rows)
        conn.close()
        return results
    else:
        cur.execute(adapt_query("""
            SELECT p.name, p.category, p.aisle, p.shelf, z.name as zone_name
            FROM products p
            LEFT JOIN zones z ON z.id = p.zone_id
            WHERE p.tenant_id = ?
            ORDER BY p.category, p.name
        """), (tenant_id,))
        rows = [dict_row(r) for r in cur.fetchall()]
        conn.close()
        return rows


@router.get("/barcode/{barcode}")
async def lookup_barcode(barcode: str, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("""
        SELECT p.*, z.name as zone_name, z.color as zone_color
        FROM products p
        LEFT JOIN zones z ON z.id = p.zone_id
        WHERE p.tenant_id = ? AND p.barcode = ?
    """), (user["tenant_id"], barcode))
    product = cur.fetchone()
    conn.close()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return dict_row(product)


@router.post("/")
async def create_product(data: ProductCreate, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    if data.zone_id:
        cur.execute(adapt_query("SELECT id FROM zones WHERE id = ? AND tenant_id = ?"),
                    (data.zone_id, user["tenant_id"]))
        if not cur.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Zone not found")
    product_id = execute_insert(cur, """
        INSERT INTO products
        (tenant_id, zone_id, name, description, barcode, sku, price,
         category, tags, aisle, shelf, position_notes, stock_status, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user["tenant_id"], data.zone_id, data.name, data.description,
          data.barcode, data.sku, data.price, data.category, data.tags,
          data.aisle, data.shelf, data.position_notes,
          data.stock_status, data.image_url))
    conn.commit()
    conn.close()
    return {"id": product_id, "message": "Product created"}


@router.put("/{product_id}")
async def update_product(product_id: int, data: ProductUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in data.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM products WHERE id = ? AND tenant_id = ?"),
                (product_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    cur.execute(adapt_query(f"UPDATE products SET {set_clause} WHERE id = ?"),
                (*updates.values(), product_id))
    conn.commit()
    conn.close()
    return {"message": "Product updated"}


@router.delete("/{product_id}")
async def delete_product(product_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM products WHERE id = ? AND tenant_id = ?"),
                (product_id, user["tenant_id"]))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Product not found")
    cur.execute(adapt_query("DELETE FROM products WHERE id = ?"), (product_id,))
    conn.commit()
    conn.close()
    return {"message": "Product deleted"}
