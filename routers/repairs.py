"""
routers/repairs.py - ShopFlow v1.0.0
AI Repair Guide via AWS Bedrock (Claude 3.5 Sonnet)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_connection, get_cursor, dict_row, adapt_query, execute_insert
import json
import os
import uuid

router = APIRouter()

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
BEDROCK_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"
AI_ENABLED = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)


class RepairRequest(BaseModel):
    store_slug: str
    problem_description: str
    session_token: Optional[str] = None


def get_ai_guide(problem: str, available_products: list) -> dict:
    """Generate repair guide via AWS Bedrock"""
    if not AI_ENABLED:
        return _fallback_guide(problem)

    try:
        import boto3
        client = boto3.client(
            "bedrock-runtime",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

        products_str = json.dumps(available_products[:50], ensure_ascii=False)

        prompt = f"""Je bent een doe-het-zelf herstelexpert. Een klant heeft dit probleem:

"{problem}"

De winkel heeft de volgende producten beschikbaar (JSON):
{products_str}

Geef een gestructureerde herstelgids in het NEDERLANDS. Antwoord ALLEEN met een JSON object in dit formaat:
{{
  "title": "Titel van de reparatie",
  "difficulty": "Gemakkelijk|Gemiddeld|Moeilijk",
  "estimated_time": "bijv. 30 minuten",
  "summary": "Korte beschrijving van wat er gedaan moet worden",
  "tools_needed": ["gereedschap 1", "gereedschap 2"],
  "steps": [
    {{"step": 1, "title": "Stap titel", "description": "Gedetailleerde uitleg", "tip": "optionele tip"}}
  ],
  "products_needed": [
    {{"name": "productnaam zoals in de catalogus", "purpose": "waarvoor nodig", "quantity": "hoeveelheid"}}
  ],
  "safety_warning": "Veiligheidswaarschuwing indien van toepassing",
  "success_tips": ["tip 1", "tip 2"]
}}"""

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        })

        response = client.invoke_model(modelId=BEDROCK_MODEL, body=body)
        result = json.loads(response["body"].read())
        text = result["content"][0]["text"]

        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip().rstrip("```").strip()

        return json.loads(text)

    except Exception as e:
        print(f"[ShopFlow AI] Bedrock error: {e}")
        return _fallback_guide(problem)


def _fallback_guide(problem: str) -> dict:
    """Fallback when AI is unavailable"""
    return {
        "title": f"Herstelgids: {problem[:50]}",
        "difficulty": "Gemiddeld",
        "estimated_time": "Onbekend",
        "summary": "Beschrijf uw probleem gedetailleerder voor een volledige AI-gids. Configureer AWS Bedrock voor AI-functionaliteit.",
        "tools_needed": ["Schroevendraaier", "Multimeter"],
        "steps": [
            {"step": 1, "title": "Probleem identificeren", "description": "Inspecteer het defecte onderdeel zorgvuldig.", "tip": "Zet altijd de stroom af voor je begint."},
            {"step": 2, "title": "Benodigdheden verzamelen", "description": "Haal de nodige producten uit de winkel.", "tip": "Vraag winkelmedewerkers om hulp."},
            {"step": 3, "title": "Reparatie uitvoeren", "description": "Volg de fabrikantsinstructies.", "tip": "Neem foto's tijdens het demonteren."}
        ],
        "products_needed": [],
        "safety_warning": "Zorg altijd voor uw eigen veiligheid.",
        "success_tips": ["Neem de tijd", "Raadpleeg instructies"]
    }


@router.post("/generate")
async def generate_repair_guide(data: RepairRequest):
    """Generate AI repair guide and match products from store"""
    conn = get_connection()
    cur = get_cursor(conn)

    cur.execute(adapt_query("SELECT id FROM tenants WHERE slug = ? AND active = TRUE"), (data.store_slug,))
    tenant = cur.fetchone()
    if not tenant:
        conn.close()
        raise HTTPException(status_code=404, detail="Store not found")
    tenant_id = dict_row(tenant)["id"]

    cur.execute(adapt_query("""
        SELECT p.name, p.description, p.category, p.tags, p.price,
               p.aisle, p.shelf, p.position_notes, p.stock_status,
               z.name as zone_name, z.grid_x, z.grid_y, z.color as zone_color, z.icon as zone_icon
        FROM products p
        LEFT JOIN zones z ON z.id = p.zone_id
        WHERE p.tenant_id = ?
    """), (tenant_id,))
    available_products = [dict_row(r) for r in cur.fetchall()]

    guide = get_ai_guide(data.problem_description, available_products)

    products_to_find = []
    for needed in guide.get("products_needed", []):
        name = needed.get("name", "")
        matches = [p for p in available_products
                   if name.lower() in p["name"].lower()
                   or (p.get("tags") and name.lower() in p["tags"].lower())
                   or (p.get("category") and name.lower() in p["category"].lower())]

        if matches:
            best = matches[0]
            products_to_find.append({
                **needed,
                "found_in_store": True,
                "store_name": best["name"],
                "zone": best.get("zone_name", "Onbekend"),
                "aisle": best.get("aisle", ""),
                "shelf": best.get("shelf", ""),
                "position_notes": best.get("position_notes", ""),
                "price": best.get("price", 0),
                "zone_color": best.get("zone_color", "#3B82F6"),
                "zone_icon": best.get("zone_icon", "box"),
                "grid_x": best.get("grid_x", 0),
                "grid_y": best.get("grid_y", 0)
            })
        else:
            products_to_find.append({
                **needed,
                "found_in_store": False,
                "zone": None,
                "aisle": None
            })

    guide["products_to_find"] = products_to_find

    session_token = data.session_token or str(uuid.uuid4())
    session_id = execute_insert(cur, """
        INSERT INTO repair_sessions (tenant_id, session_token, problem_description, ai_guide, products_needed, status)
        VALUES (?, ?, ?, ?, ?, 'active')
    """, (tenant_id, session_token, data.problem_description,
          json.dumps(guide), json.dumps(products_to_find)))
    conn.commit()
    conn.close()

    return {
        "session_id": session_id,
        "session_token": session_token,
        "guide": guide
    }


@router.get("/session/{session_token}")
async def get_session(session_token: str, store_slug: str):
    conn = get_connection()
    cur = get_cursor(conn)
    cur.execute(adapt_query("SELECT id FROM tenants WHERE slug = ?"), (store_slug,))
    tenant = cur.fetchone()
    if not tenant:
        conn.close()
        raise HTTPException(status_code=404, detail="Store not found")
    tenant_id = dict_row(tenant)["id"]
    cur.execute(adapt_query("""
        SELECT * FROM repair_sessions WHERE session_token = ? AND tenant_id = ?
    """), (session_token, tenant_id))
    session = cur.fetchone()
    conn.close()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    s = dict_row(session)
    s["ai_guide"] = json.loads(s["ai_guide"]) if s.get("ai_guide") else {}
    s["products_needed"] = json.loads(s["products_needed"]) if s.get("products_needed") else []
    return s
