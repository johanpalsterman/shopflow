"""
routers/qr.py - ShopFlow v1.1.0
QR code generation for zones and store app
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response
from database import get_connection, get_cursor, dict_row, adapt_query
from auth_utils import get_current_user
import os

router = APIRouter()

BASE_URL = os.environ.get("APP_BASE_URL", "https://shopflow.wishflow.eu")


def generate_qr_svg(url: str, size: int = 200) -> str:
    try:
        import qrcode
        import qrcode.image.svg
        import io

        factory = qrcode.image.svg.SvgPathImage
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(image_factory=factory)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode("utf-8")

    except ImportError:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" fill="white" stroke="#2563EB" stroke-width="2" rx="8"/>
  <rect x="20" y="20" width="60" height="60" fill="none" stroke="#1E293B" stroke-width="4"/>
  <rect x="30" y="30" width="40" height="40" fill="#1E293B"/>
  <rect x="{size-80}" y="20" width="60" height="60" fill="none" stroke="#1E293B" stroke-width="4"/>
  <rect x="{size-70}" y="30" width="40" height="40" fill="#1E293B"/>
  <rect x="20" y="{size-80}" width="60" height="60" fill="none" stroke="#1E293B" stroke-width="4"/>
  <rect x="30" y="{size-70}" width="40" height="40" fill="#1E293B"/>
  <text x="{size//2}" y="{size-20}" text-anchor="middle" font-family="monospace" font-size="8" fill="#64748B">{url[:40]}...</text>
  <text x="{size//2}" y="{size//2}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#2563EB">ShopFlow QR</text>
</svg>"""


def generate_qr_html(title: str, subtitle: str, url: str, color: str = "#2563EB") -> str:
    svg = generate_qr_svg(url)

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<title>QR - {title}</title>
<style>
  @media print {{ body {{ margin: 0; }} }}
  body {{ font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #F1F5F9; margin: 0; }}
  .card {{ background: white; border-radius: 16px; padding: 32px; text-align: center; max-width: 300px; box-shadow: 0 8px 30px rgba(0,0,0,.12); border-top: 8px solid {color}; }}
  .logo {{ font-size: 1.2rem; font-weight: 800; color: #1E293B; margin-bottom: 16px; }}
  .logo span {{ color: #67E8F9; }}
  .zone-title {{ font-size: 1.4rem; font-weight: 800; color: {color}; margin: 12px 0 4px; }}
  .subtitle {{ color: #64748B; font-size: .9rem; margin-bottom: 16px; }}
  .qr-wrap {{ background: white; padding: 12px; border-radius: 8px; display: inline-block; border: 1px solid #E2E8F0; }}
  .cta {{ margin-top: 16px; color: #374151; font-size: .85rem; }}
  .url {{ font-size: .7rem; color: #94A3B8; margin-top: 8px; word-break: break-all; }}
  .print-btn {{ margin-top: 16px; padding: 8px 20px; background: {color}; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: .9rem; }}
  @media print {{ .print-btn {{ display: none; }} }}
</style>
</head>
<body>
<div class="card">
  <div class="logo">Shop<span>Flow</span></div>
  <div class="zone-title">{title}</div>
  <div class="subtitle">{subtitle}</div>
  <div class="qr-wrap">{svg}</div>
  <div class="cta">📱 Scan voor hulp bij reparaties<br>en productlocaties</div>
  <div class="url">{url}</div>
  <button class="print-btn" onclick="window.print()">🖨️ Afdrukken</button>
</div>
</body>
</html>"""


@router.get("/store/{store_slug}")
async def qr_store(store_slug: str, format: str = Query("html", enum=["html", "svg"])):
    """QR code for the main store app"""
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT name FROM tenants WHERE slug = ? AND active = TRUE"), (store_slug,))
    tenant = cur.fetchone()
    conn.close()

    if not tenant:
        raise HTTPException(status_code=404, detail="Winkel niet gevonden")

    store_name = dict_row(tenant)["name"]
    url = f"{BASE_URL}/app?store={store_slug}"

    if format == "svg":
        return Response(content=generate_qr_svg(url), media_type="image/svg+xml")

    html = generate_qr_html(store_name, "Reparatiegids & winkelkaart", url)
    return Response(content=html, media_type="text/html")


@router.get("/zone/{zone_id}")
async def qr_zone(zone_id: int, user=Depends(get_current_user),
                  format: str = Query("html", enum=["html", "svg"])):
    """QR code for a specific zone"""
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("""
        SELECT z.name, z.color, z.description, t.slug
        FROM zones z JOIN tenants t ON t.id = z.tenant_id
        WHERE z.id = ? AND z.tenant_id = ?
    """), (zone_id, user["tenant_id"]))
    zone = cur.fetchone()
    conn.close()

    if not zone:
        raise HTTPException(status_code=404, detail="Zone niet gevonden")

    z = dict_row(zone)
    url = f"{BASE_URL}/app?store={z['slug']}&zone={zone_id}"

    if format == "svg":
        return Response(content=generate_qr_svg(url), media_type="image/svg+xml")

    html = generate_qr_html(
        z["name"],
        z.get("description") or "Scan voor producten in deze afdeling",
        url,
        z.get("color", "#2563EB")
    )
    return Response(content=html, media_type="text/html")


@router.get("/all-zones/{store_slug}")
async def qr_all_zones(store_slug: str, user=Depends(get_current_user)):
    """Printable page with QR codes for all zones"""
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT name FROM tenants WHERE id = ? AND slug = ?"),
                (user["tenant_id"], store_slug))
    tenant = cur.fetchone()
    if not tenant:
        conn.close()
        raise HTTPException(status_code=404, detail="Winkel niet gevonden")

    cur.execute(adapt_query("SELECT id, name, color, description FROM zones WHERE tenant_id = ? ORDER BY name"),
                (user["tenant_id"],))
    zones = [dict_row(r) for r in cur.fetchall()]
    conn.close()

    store_name = dict_row(tenant)["name"]

    cards_html = ""
    for z in zones:
        url = f"{BASE_URL}/app?store={store_slug}&zone={z['id']}"
        svg = generate_qr_svg(url, size=160)
        cards_html += f"""
        <div class="card" style="border-top-color:{z['color']}">
          <div class="zone-name" style="color:{z['color']}">{z['name']}</div>
          <div class="zone-desc">{z.get('description') or ''}</div>
          <div class="qr-wrap">{svg}</div>
          <div class="scan-text">📱 Scan voor reparatiegids</div>
        </div>"""

    return Response(content=f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<title>QR Codes - {store_name}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: #F1F5F9; padding: 24px; }}
  h1 {{ text-align: center; color: #1E293B; margin-bottom: 8px; }}
  .subtitle {{ text-align: center; color: #64748B; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; }}
  .card {{ background: white; border-radius: 12px; padding: 20px; text-align: center; border-top: 6px solid #2563EB; box-shadow: 0 4px 12px rgba(0,0,0,.08); }}
  .zone-name {{ font-size: 1.1rem; font-weight: 800; margin-bottom: 4px; }}
  .zone-desc {{ color: #64748B; font-size: .8rem; margin-bottom: 12px; min-height: 20px; }}
  .qr-wrap {{ background: white; padding: 8px; border-radius: 6px; display: inline-block; border: 1px solid #E2E8F0; }}
  .scan-text {{ margin-top: 10px; color: #374151; font-size: .8rem; }}
  .print-btn {{ display: block; margin: 20px auto; padding: 10px 28px; background: #2563EB; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; }}
  @media print {{ .print-btn {{ display: none; }} body {{ background: white; padding: 8px; }} }}
</style>
</head>
<body>
<h1>ShopFlow QR Codes</h1>
<div class="subtitle">{store_name} — Druk af en hang op in elke afdeling</div>
<button class="print-btn" onclick="window.print()">🖨️ Alles afdrukken</button>
<div class="grid">{cards_html}</div>
<button class="print-btn" onclick="window.print()">🖨️ Alles afdrukken</button>
</body>
</html>""", media_type="text/html")
