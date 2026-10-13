
import re
from rapidfuzz import fuzz

from database import get_connection
from brand_profiles import normalize_name


# --------------------------------------------------
# 1. SUSPICIOUS SOCIAL PROFILE INDICATORS
# --------------------------------------------------

SUSPICIOUS_WORDS = [
    "giveaway",
    "free gift",
    "free money",
    "verify account",
    "claim reward",
    "login now",
    "account suspended",
    "customer care",
    "customer support",
    "help desk",
]


# --------------------------------------------------
# 2. CHECK WHETHER A PROFILE IS OFFICIALLY WHITELISTED
# --------------------------------------------------

def is_social_whitelisted(brand_id, handle, profile_url=""):
    """
    Check trusted social assets for this specific brand.

    Supports both 'social_handle' and legacy 'social'
    asset types to remain compatible with older data.
    """

    if not handle and not profile_url:
        return False

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT asset_value
            FROM whitelist_assets
            WHERE brand_id = %s
              AND asset_type IN ('social_handle', 'social')
            """,
            (brand_id,),
        )

        trusted_values = cursor.fetchall()

        candidates = {
            str(value).strip().rstrip("/").lower()
            for value in (handle, profile_url)
            if value
        }

        for row in trusted_values:
            trusted = str(row[0]).strip().rstrip("/").lower()

            if trusted and trusted in candidates:
                return True

        return False

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 3. CALCULATE SOCIAL PROFILE RISK
# --------------------------------------------------

def scan_social_profile(
    brand_id,
    platform,
    display_name,
    handle,
    bio="",
    profile_url="",
    brand_name="",
    profile_image_url="",
):
    """
    Screen a social profile for possible brand impersonation.

    This function uses text-based indicators only.
    It does not independently verify account ownership
    or image similarity.
    """

    display_name = str(display_name or "").strip()
    handle = str(handle or "").strip()
    bio = str(bio or "").strip()
    profile_url = str(profile_url or "").strip()
    brand_name = str(brand_name or "").strip()
    platform = str(platform or "Social Media").strip()

    risk_score = 0
    reasons = []

    normalized_name = normalize_name(display_name)
    normalized_brand = normalize_name(brand_name)
    normalized_handle = normalize_name(handle.lstrip("@"))

    # --------------------------------------------------
    # SIGNAL 1: CHECK THE BRAND-SPECIFIC WHITELIST
    # --------------------------------------------------

    whitelisted = is_social_whitelisted(
        brand_id,
        handle,
        profile_url,
    )

    if whitelisted:
        risk_score = 0
        reasons.append("Profile matches a trusted asset for this brand")

    else:
        # --------------------------------------------------
        # SIGNAL 2: DISPLAY NAME SIMILARITY
        # --------------------------------------------------

        name_score = 0

        if normalized_name and normalized_brand:
            name_score = max(
                fuzz.ratio(normalized_name, normalized_brand),
                fuzz.partial_ratio(
                    normalized_name,
                    normalized_brand,
                ),
                fuzz.token_set_ratio(
                    display_name,
                    brand_name,
                ),
            )

        if (
            normalized_name
            and normalized_brand
            and normalized_name != normalized_brand
            and name_score >= 80
        ):
            risk_score += 30
            reasons.append(
                f"Display name resembles the brand "
                f"({name_score:.0f}% similarity)"
            )

        # --------------------------------------------------
        # SIGNAL 3: BRAND NAME IN HANDLE
        # --------------------------------------------------

        if (
            normalized_handle
            and normalized_brand
            and normalized_brand in normalized_handle
            and normalized_handle != normalized_brand
        ):
            risk_score += 20
            reasons.append("Handle contains the brand name")

        # --------------------------------------------------
        # SIGNAL 4: SUSPICIOUS BIO WORDING
        # --------------------------------------------------

        bio_lower = bio.lower()

        found_words = [
            word
            for word in SUSPICIOUS_WORDS
            if word in bio_lower
        ]

        if found_words:
            risk_score += min(15 * len(found_words), 30)
            reasons.append(
                "Suspicious bio wording: "
                + ", ".join(found_words)
            )

        # --------------------------------------------------
        # SIGNAL 5: EXTERNAL LINKS
        # --------------------------------------------------

        if re.search(r"https?://|www\.", bio_lower):
            risk_score += 10
            reasons.append("External link found in profile bio")

        # --------------------------------------------------
        # SIGNAL 6: BRAND NAME AND SUPPORT-STYLE HANDLE
        # --------------------------------------------------

        support_terms = (
            "support",
            "customer care",
            "helpdesk",
            "help desk",
            "official",
            "security",
        )

        handle_lower = handle.lower()

        if (
            normalized_brand
            and normalized_brand in normalized_handle
            and any(term in handle_lower for term in support_terms)
        ):
            risk_score += 15
            reasons.append(
                "Brand-related handle uses support or official wording"
            )

        # Keep scores within the permitted range.
        risk_score = min(risk_score, 100)

    # --------------------------------------------------
    # 4. DETERMINE STATUS
    # --------------------------------------------------

    if risk_score >= 70:
        status = "High Risk"
    elif risk_score >= 35:
        status = "Needs Review"
    elif risk_score > 0:
        status = "Low Risk"
    else:
        status = "Safe"

    if not reasons:
        reasons.append("No suspicious indicators detected")

    # --------------------------------------------------
    # 5. SAVE THE RESULT
    # --------------------------------------------------

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

        findings = "; ".join(reasons)

        cursor.execute(
            query,
            (
                brand_id,
                platform,
                display_name,
                handle,
                handle,
                findings,
                profile_image_url,
                risk_score,
                status,
            ),
        )

        connection.commit()

        return {
            "brand_id": brand_id,
            "platform": platform,
            "display_name": display_name,
            "handle": handle,
            "profile_url": profile_url,
            "profile_image_url": profile_image_url,
            "name_similarity": round(
                name_score if not whitelisted else 100,
                2,
            ) if brand_name and display_name else 0,
            "risk_score": risk_score,
            "status": status,
            "reasons": reasons,
            "whitelisted": whitelisted,
            "message": "Social profile scan completed",
        }

    except Exception:
        if connection is not None and connection.is_connected():
            connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
