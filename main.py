
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from database import get_connection, create_tables, test_connection
from brand_profiles import (
    add_brand,
    list_brands,
    add_whitelist_asset,
)
from app_store_scraper import scan_brand
from social_monitor import scan_social_profile

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"


# --------------------------------------------------
# 1. CREATE FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="ShieldWatch - Digital Risk Protection",
    description=(
        "Monitor suspicious applications and potential "
        "social media brand impersonation."
    ),
    version="1.1.0",
)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# 3. REQUEST MODELS
# --------------------------------------------------

class BrandInput(BaseModel):
    company_name: str = Field(min_length=1, max_length=150)
    legal_entity: str = Field(min_length=1, max_length=200)
    official_logo_url: Optional[str] = None
    verified_social_handles: Optional[str] = None
    official_app_ids: Optional[str] = None


class WhitelistInput(BaseModel):
    brand_id: int = Field(gt=0)
    asset_type: str = Field(min_length=1, max_length=50)
    asset_value: str = Field(min_length=1, max_length=500)


class SocialInput(BaseModel):
    brand_id: int = Field(gt=0)
    platform: str = Field(min_length=1, max_length=50)
    handle: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=250)
    bio: Optional[str] = ""
    profile_url: Optional[str] = ""
    profile_image_url: Optional[str] = ""


# --------------------------------------------------
# 4. STARTUP
# --------------------------------------------------

@app.on_event("startup")
def startup():
    """Verify MySQL connectivity and ensure tables exist."""

    test_connection()
    create_tables()


# --------------------------------------------------
# 5. HOME AND HEALTH
# --------------------------------------------------

@app.get("/")
def home():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "message": "ShieldWatch API is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/api-status")
def api_status():
    return {
        "message": "ShieldWatch API is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    """Check API and database availability."""

    connection = None

    try:
        connection = get_connection()

        return {
            "status": "running",
            "database": "connected",
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="API is running, but the database is unavailable.",
        )

    finally:
        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 6. CREATE A BRAND
# --------------------------------------------------

@app.post("/brands")
def create_brand(brand: BrandInput):
    try:
        brand_id = add_brand(
            company_name=brand.company_name.strip(),
            legal_entity=brand.legal_entity.strip(),
            logo_url=brand.official_logo_url,
            social_handles=brand.verified_social_handles,
            app_ids=brand.official_app_ids,
        )

        return {
            "message": "Brand added successfully",
            "brand_id": brand_id,
        }

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to add brand. Check the backend logs.",
        )


# --------------------------------------------------
# 7. LIST BRANDS
# --------------------------------------------------

@app.get("/brands")
def get_brands():
    try:
        return list_brands()

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve brand profiles.",
        )


# --------------------------------------------------
# 8. ADD A TRUSTED ASSET
# --------------------------------------------------

@app.post("/whitelist")
def create_whitelist(asset: WhitelistInput):
    try:
        # Ensure the brand exists before adding an asset.
        brands = list_brands()

        brand_exists = any(
            int(brand["brand_id"]) == asset.brand_id
            for brand in brands
        )

        if not brand_exists:
            raise HTTPException(
                status_code=404,
                detail="Brand not found.",
            )

        add_whitelist_asset(
            asset.brand_id,
            asset.asset_type,
            asset.asset_value,
        )

        return {
            "message": "Asset added to whitelist",
            "brand_id": asset.brand_id,
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to add the trusted asset.",
        )


# --------------------------------------------------
# 9. SCAN APP STORES
# --------------------------------------------------

@app.post("/scan/apps/{brand_id}")
def scan_apps(brand_id: int):
    try:
        brands = list_brands()

        brand = next(
            (
                item for item in brands
                if int(item["brand_id"]) == brand_id
            ),
            None,
        )

        if brand is None:
            raise HTTPException(
                status_code=404,
                detail="Brand not found. Add the brand first.",
            )

        results = scan_brand(
            brand_id=brand_id,
            brand_name=brand["company_name"],
            legal_entity=brand["legal_entity"] or "",
        )

        errors = [
            result
            for result in results
            if result.get("error")
        ]

        return {
            "message": "App scan completed",
            "brand_id": brand_id,
            "total_results": len(results) - len(errors),
            "errors": errors,
            "results": results,
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="App scanning failed. Check the backend logs.",
        )


# --------------------------------------------------
# 10. SCAN A SOCIAL PROFILE
# --------------------------------------------------

@app.post("/scan/social")
def scan_social(social: SocialInput):
    try:
        brands = list_brands()

        brand = next(
            (
                item for item in brands
                if int(item["brand_id"]) == social.brand_id
            ),
            None,
        )

        if brand is None:
            raise HTTPException(
                status_code=404,
                detail="Brand not found. Add the brand first.",
            )

        result = scan_social_profile(
            brand_id=social.brand_id,
            platform=social.platform,
            display_name=social.display_name,
            handle=social.handle,
            bio=social.bio or "",
            profile_url=social.profile_url or "",
            brand_name=brand["company_name"],
            profile_image_url=social.profile_image_url or "",
        )

        return {
            "message": "Social profile scan completed",
            "result": result,
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Social scanning failed. Check the backend logs.",
        )


# --------------------------------------------------
# 11. GET STORED SCAN RESULTS
# --------------------------------------------------

@app.get("/scan-results")
def get_scan_results(brand_id: Optional[int] = None):
    """Return recent scan results, optionally for one brand."""

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        if brand_id is not None:
            if brand_id <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="brand_id must be positive.",
                )

            cursor.execute(
                """
                SELECT *
                FROM scan_results
                WHERE brand_id = %s
                ORDER BY scanned_at DESC, id DESC
                LIMIT 500
                """,
                (brand_id,),
            )

        else:
            cursor.execute(
                """
                SELECT *
                FROM scan_results
                ORDER BY scanned_at DESC, id DESC
                LIMIT 500
                """
            )

        return cursor.fetchall()

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve scan results.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 12. GET HIGHER-RISK ALERTS
# --------------------------------------------------

@app.get("/alerts")
def get_alerts(brand_id: Optional[int] = None):
    """Return results that need review or are high risk."""

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        if brand_id is not None:
            if brand_id <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="brand_id must be positive.",
                )

            cursor.execute(
                """
                SELECT *
                FROM scan_results
                WHERE risk_score >= 35
                  AND brand_id = %s
                ORDER BY risk_score DESC, scanned_at DESC
                LIMIT 500
                """,
                (brand_id,),
            )

        else:
            cursor.execute(
                """
                SELECT *
                FROM scan_results
                WHERE risk_score >= 35
                ORDER BY risk_score DESC, scanned_at DESC
                LIMIT 500
                """
            )

        return cursor.fetchall()

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve alerts.",
        )

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
