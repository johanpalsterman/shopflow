"""
routers/import_csv.py - ShopFlow v1.1.0
CSV bulk product import
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from database import get_connection, get_cursor, dict_row, adapt_query, execute_insert
from auth_utils import get_current_user
import io
import csv

router = APIRouter()

REQUIRED_COLS = {"name"}
OPTIONAL_COLS = {"barcode", "sku", "price", "category", "tags",
                 "aisle", "shelf", "position_notes", "description",
                 "zone_name", "stock_status"}


@router.post("/products")
async def import_products_csv(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """
    Import products from CSV.
    Required column: name
    Optional: barcode, sku, price, category, tags, aisle, shelf,
              position_notes, description, zone_name, stock_status
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Alleen CSV bestanden toegestaan")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]

    if "name" not in headers:
        raise HTTPException(status_code=400,
            detail="CSV moet een 'name' kolom bevatten")

    conn = get_connection()
    cur = get_cursor(conn)
    tid = user["tenant_id"]

    cur.execute(adapt_query("SELECT id, name FROM zones WHERE tenant_id = ?"), (tid,))
    zone_cache = {dict_row(r)["name"].lower(): dict_row(r)["id"]
                  for r in cur.fetchall()}

    imported = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items()}
        name = row.get("name", "").strip()
        if not name:
            skipped += 1
            continue

        zone_id = None
        zone_name = row.get("zone_name", "")
        if zone_name:
            zone_id = zone_cache.get(zone_name.lower())

        try:
            price = float(row.get("price", 0) or 0)
        except ValueError:
            price = 0.0

        try:
            execute_insert(cur, """
                INSERT INTO products
                (tenant_id, zone_id, name, description, barcode, sku, price,
                 category, tags, aisle, shelf, position_notes, stock_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tid, zone_id, name,
                row.get("description", ""),
                row.get("barcode", ""),
                row.get("sku", ""),
                price,
                row.get("category", ""),
                row.get("tags", ""),
                row.get("aisle", ""),
                row.get("shelf", ""),
                row.get("position_notes", ""),
                row.get("stock_status", "in_stock")
            ))
            imported += 1
        except Exception as e:
            errors.append(f"Rij {i}: {str(e)}")
            skipped += 1

    conn.commit()
    conn.close()

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:10],
        "message": f"{imported} producten geimporteerd, {skipped} overgeslagen"
    }


@router.get("/template")
async def download_template():
    """Return CSV template as text"""
    template = """name,barcode,price,category,tags,aisle,shelf,position_notes,description,zone_name,stock_status
Muurverf Wit 10L,5410123456789,24.99,Verf,"verf,muur,wit,schilderen",A1,2,Linker kant bij de verfmixer,Premium muurverf voor binnen,Afdeling Verf,in_stock
Kraan rubber pakking 15mm,5410987654321,1.99,Sanitair,"kraan,pakking,rubber,afdichting,waterleiding",B3,4,,Set van 5 pakkingen,Afdeling Sanitair,in_stock
Silicone kit wit 300ml,5410111222333,4.99,Afdichting,"kit,silicone,voeg,badkamer,keuken,wit",B2,1,Naast de kwasten,Neutrale silicone kit,Afdeling Sanitair,in_stock
"""
    from fastapi.responses import Response
    return Response(
        content=template,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=shopflow_import_template.csv"}
    )
