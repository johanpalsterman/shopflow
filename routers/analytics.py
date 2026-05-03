"""
routers/analytics.py - ShopFlow v1.1.0
Store analytics: top repairs, missing products, usage trends
"""
from fastapi import APIRouter, Depends
from database import get_connection, get_cursor, dict_row, adapt_query, USE_POSTGRES
from auth_utils import get_current_user
import json

router = APIRouter()


def _date_filter(days: int) -> str:
    if USE_POSTGRES:
        return f"NOW() - INTERVAL '{days} days'"
    return f"datetime('now', '-{days} days')"


@router.get("/summary")
async def analytics_summary(user=Depends(get_current_user)):
    """Full analytics summary for the admin dashboard"""
    conn = get_connection()
    cur = get_cursor(conn)
    tid = user["tenant_id"]

    cur.execute(adapt_query("SELECT COUNT(*) as c FROM repair_sessions WHERE tenant_id = ?"), (tid,))
    total_sessions = dict_row(cur.fetchone())["c"]

    cur.execute(adapt_query(f"""
        SELECT COUNT(*) as c FROM repair_sessions
        WHERE tenant_id = ?
        AND created_at >= {_date_filter(7)}
    """), (tid,))
    week_sessions = dict_row(cur.fetchone())["c"]

    cur.execute(adapt_query(f"""
        SELECT COUNT(*) as c FROM repair_sessions
        WHERE tenant_id = ?
        AND created_at >= {_date_filter(30)}
    """), (tid,))
    month_sessions = dict_row(cur.fetchone())["c"]

    cur.execute(adapt_query("SELECT COUNT(*) as c FROM products WHERE tenant_id = ?"), (tid,))
    total_products = dict_row(cur.fetchone())["c"]

    cur.execute(adapt_query("SELECT COUNT(*) as c FROM products WHERE tenant_id = ? AND zone_id IS NULL"), (tid,))
    unzoned = dict_row(cur.fetchone())["c"]

    cur.execute(adapt_query("SELECT COUNT(*) as c FROM products WHERE tenant_id = ? AND (tags = '' OR tags IS NULL)"), (tid,))
    untagged = dict_row(cur.fetchone())["c"]

    cur.execute(adapt_query("""
        SELECT z.name, z.color, COUNT(p.id) as product_count
        FROM zones z
        LEFT JOIN products p ON p.zone_id = z.id
        WHERE z.tenant_id = ?
        GROUP BY z.id, z.name, z.color
        ORDER BY product_count DESC
        LIMIT 5
    """), (tid,))
    top_zones = [dict_row(r) for r in cur.fetchall()]

    cur.execute(adapt_query(f"""
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM repair_sessions
        WHERE tenant_id = ?
        AND created_at >= {_date_filter(14)}
        GROUP BY DATE(created_at)
        ORDER BY day
    """), (tid,))
    daily_trend = [dict_row(r) for r in cur.fetchall()]

    cur.execute(adapt_query("""
        SELECT products_needed FROM repair_sessions
        WHERE tenant_id = ?
        AND products_needed IS NOT NULL
        AND products_needed != '[]'
        ORDER BY created_at DESC
        LIMIT 100
    """), (tid,))
    sessions = cur.fetchall()
    conn.close()

    missing_counts = {}
    found_counts = {}

    for s in sessions:
        try:
            prods = json.loads(dict_row(s)["products_needed"])
            for p in prods:
                name = p.get("name", "").strip()
                if not name:
                    continue
                if not p.get("found_in_store", True):
                    missing_counts[name] = missing_counts.get(name, 0) + 1
                else:
                    found_counts[name] = found_counts.get(name, 0) + 1
        except Exception:
            pass

    top_missing = sorted(missing_counts.items(), key=lambda x: -x[1])[:10]
    top_found = sorted(found_counts.items(), key=lambda x: -x[1])[:10]

    health_score = 100
    if total_products == 0:
        health_score = 0
    else:
        health_score -= int((unzoned / total_products) * 30)
        health_score -= int((untagged / total_products) * 40)
    health_score = max(0, min(100, health_score))

    return {
        "sessions": {
            "total": total_sessions,
            "this_week": week_sessions,
            "this_month": month_sessions,
            "daily_trend": daily_trend
        },
        "catalog": {
            "total_products": total_products,
            "unzoned_products": unzoned,
            "untagged_products": untagged,
            "health_score": health_score,
            "top_zones": top_zones
        },
        "ai_insights": {
            "top_missing_products": [{"name": n, "count": c} for n, c in top_missing],
            "top_found_products": [{"name": n, "count": c} for n, c in top_found],
        }
    }


@router.get("/catalog-health")
async def catalog_health(user=Depends(get_current_user)):
    """Products that need attention"""
    conn = get_connection()
    cur = get_cursor(conn)
    tid = user["tenant_id"]

    cur.execute(adapt_query("""
        SELECT p.id, p.name, p.barcode, p.category, p.tags,
               p.zone_id, z.name as zone_name
        FROM products p
        LEFT JOIN zones z ON z.id = p.zone_id
        WHERE p.tenant_id = ?
        ORDER BY p.name
    """), (tid,))
    products = [dict_row(r) for r in cur.fetchall()]
    conn.close()

    issues = []
    for p in products:
        p_issues = []
        if not p.get("zone_id"):
            p_issues.append("Geen zone toegewezen")
        if not p.get("tags"):
            p_issues.append("Geen tags (AI vindt dit product minder goed)")
        if not p.get("barcode"):
            p_issues.append("Geen barcode")
        if p_issues:
            issues.append({**p, "issues": p_issues})

    return {
        "products_with_issues": len(issues),
        "total_products": len(products),
        "items": issues[:50]
    }
