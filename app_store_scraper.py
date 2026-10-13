
import requests

from google_play_scraper import search

from database import get_connection
from brand_profiles import is_whitelisted
from detection import calculate_risk


# --------------------------------------------------
# 1. DETERMINE THE RESULT STATUS
# --------------------------------------------------

def get_result_status(risk_score):
    """Convert a risk score into a readable status."""

    if risk_score >= 70:
        return "High Risk"

    if risk_score >= 35:
        return "Needs Review"

    if risk_score > 0:
        return "Low Risk"

    return "Safe"


# --------------------------------------------------
# 2. SAVE A SCAN RESULT
# --------------------------------------------------

def save_result(
    brand_id,
    platform,
    app_name,
    app_id,
    risk_score,
    reason,
    publisher="",
    description="",
    icon_url="",
):
    """Save an app scan result to the existing MySQL table."""

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO scan_results
            (
                brand_id,
                platform,
                app_name,
                publisher,
                app_id,
                description,
                icon_url,
                risk_score,
                status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        status = get_result_status(risk_score)

        # Preserve the app description and include detection
        # reasons so the reviewer can understand the result.
        saved_description = description or ""

        if reason:
            if saved_description:
                saved_description += "\n\n"
            saved_description += "Detection findings: " + reason

        cursor.execute(
            query,
            (
                brand_id,
                platform,
                app_name,
                publisher,
                app_id,
                saved_description,
                icon_url,
                risk_score,
                status,
            ),
        )

        connection.commit()

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 3. SCAN GOOGLE PLAY AND APPLE APP STORE
# --------------------------------------------------

def scan_brand(brand_id, brand_name, legal_entity):
    """
    Search both app stores for apps associated with a brand.

    Returns a list of scan results. Store errors are returned
    as error entries instead of crashing the entire scan.
    """

    results = []

    # --------------------------------------------------
    # GOOGLE PLAY STORE
    # --------------------------------------------------

    try:
        apps = search(
            brand_name,
            lang="en",
            country="in",
        )

        for app in apps[:10]:
            app_name = app.get("title", "") or ""
            app_id = app.get("appId", "") or ""
            publisher = app.get("developer", "") or ""
            icon_url = app.get("icon", "") or ""

            # Skip known official app IDs.
            if app_id and is_whitelisted("app_id", app_id):
                continue

            risk = calculate_risk(
                app_name=app_name,
                publisher=publisher,
                official_name=brand_name,
                official_publisher=legal_entity,
            )

            reason = "; ".join(risk.get("reasons", []))

            result = {
                "platform": "Google Play",
                "app_name": app_name,
                "app_id": app_id,
                "publisher": publisher,
                "description": "",
                "icon_url": icon_url,
                **risk,
            }

            save_result(
                brand_id=brand_id,
                platform="Google Play",
                app_name=app_name,
                app_id=app_id,
                risk_score=risk.get("risk_score", 0),
                reason=reason or "No suspicious indicators detected",
                publisher=publisher,
                description="",
                icon_url=icon_url,
            )

            results.append(result)

    except Exception as error:
        results.append({
            "platform": "Google Play",
            "error": str(error),
        })

    # --------------------------------------------------
    # APPLE APP STORE
    # --------------------------------------------------

    try:
        url = "https://itunes.apple.com/search"

        response = requests.get(
            url,
            params={
                "term": brand_name,
                "entity": "software",
                "country": "in",
                "limit": 10,
            },
            timeout=15,
        )

        response.raise_for_status()

        apps = response.json().get("results", [])

        for app in apps:
            app_name = app.get("trackName", "") or ""
            app_id = str(app.get("trackId", "") or "")
            publisher = app.get("sellerName", "") or ""
            description = app.get("description", "") or ""
            icon_url = app.get("artworkUrl512") or app.get(
                "artworkUrl100", ""
            )

            # Skip known official app IDs.
            if app_id and is_whitelisted("app_id", app_id):
                continue

            risk = calculate_risk(
                app_name=app_name,
                publisher=publisher,
                official_name=brand_name,
                official_publisher=legal_entity,
                description=description,
                app_id=app_id,
            )

            reason = "; ".join(risk.get("reasons", []))

            result = {
                "platform": "Apple App Store",
                "app_name": app_name,
                "app_id": app_id,
                "publisher": publisher,
                "description": description,
                "icon_url": icon_url,
                **risk,
            }

            save_result(
                brand_id=brand_id,
                platform="Apple App Store",
                app_name=app_name,
                app_id=app_id,
                risk_score=risk.get("risk_score", 0),
                reason=reason or "No suspicious indicators detected",
                publisher=publisher,
                description=description,
                icon_url=icon_url,
            )

            results.append(result)

    except Exception as error:
        results.append({
            "platform": "Apple App Store",
            "error": str(error),
        })

    return results
