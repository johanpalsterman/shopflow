"""
ShopFlow v1.2.0 - Store Navigation & AI Repair Guide Platform
WishFlow Suite - Johan's Projects

v1.1.0: CSV import, QR codes, analytics, NL/FR, branding
v1.2.0: Marker location system, garage support, employee location page
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
import os

from database import init_db
from routers import auth, stores, zones, products, repairs
from routers import import_csv, qr, analytics, branding
from routers import markers

APP_VERSION = "1.2.0"
APP_NAME = "ShopFlow"

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Store Navigation & AI Repair Guide Platform"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheMiddleware)


@app.on_event("startup")
async def startup_event():
    init_db()
    print(f"[ShopFlow {APP_VERSION}] Started - DB initialized")


# v1.0.0 routers
app.include_router(auth.router,     prefix="/api/auth",     tags=["auth"])
app.include_router(stores.router,   prefix="/api/stores",   tags=["stores"])
app.include_router(zones.router,    prefix="/api/zones",    tags=["zones"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(repairs.router,  prefix="/api/repairs",  tags=["repairs"])

# v1.1.0 routers
app.include_router(import_csv.router, prefix="/api/import",    tags=["import"])
app.include_router(qr.router,         prefix="/api/qr",        tags=["qr"])
app.include_router(analytics.router,  prefix="/api/analytics", tags=["analytics"])
app.include_router(branding.router,   prefix="/api/branding",  tags=["branding"])

# v1.2.0 routers
app.include_router(markers.router,    prefix="/api/markers",   tags=["markers"])


# Health endpoint
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "module": APP_NAME,
        "suite": "WishFlow",
        "features": ["csv-import", "qr-codes", "analytics", "bilingual", "branding", "markers"]
    }


@app.get("/api/version")
async def version():
    return {"version": APP_VERSION, "module": APP_NAME}


# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Page routes
@app.get("/")
async def root():
    return FileResponse("static/index.html", media_type="text/html")


@app.get("/admin")
async def admin_page():
    return FileResponse("static/admin.html", media_type="text/html")


@app.get("/app")
async def customer_app():
    return FileResponse("static/app.html", media_type="text/html")


@app.get("/scan")
async def scan_page():
    return FileResponse("static/scan.html", media_type="text/html")


@app.get("/location")
async def location_page():
    return FileResponse("static/location.html", media_type="text/html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
