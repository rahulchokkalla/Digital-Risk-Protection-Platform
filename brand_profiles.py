
import re

from database import get_connection


# --------------------------------------------------
# 1. NORMALIZE BRAND NAMES
# --------------------------------------------------

def normalize_name(name):
    """Normalize a name for comparison."""

    if not name:
        return ""

    return re.sub(r"[^a-z0-9]", "", str(name).lower())


# --------------------------------------------------
# 2. CONVERT ASSETS INTO A LIST
# --------------------------------------------------

def _to_asset_values(value):
    """Accept a string or a list of asset values."""

    if not value:
        return []

    if isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = str(value).replace("\n", ",").split(",")

    return [
        str(item).strip()
        for item in values
        if item and str(item).strip()
    ]


# --------------------------------------------------
# 3. ADD A BRAND
# --------------------------------------------------

def add_brand(
    company_name,
    legal_entity,
    logo_url=None,
    social_handles=None,
    app_ids=None,
):
    """Add a brand using the existing database columns."""

    if not company_name or not str(company_name).strip():
        raise ValueError("Company name is required.")

    connection = None
    cursor = None

    social_values = _to_asset_values(social_handles)
    app_values = _to_asset_values(app_ids)

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO brand_profiles
            (
                company_name,
                legal_entity,
                official_logo_url,
                verified_social_handles,
                official_app_ids
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                str(company_name).strip(),
                legal_entity,
                logo_url,
                ",".join(social_values),
                ",".join(app_values),
            ),
        )

        brand_id = cursor.lastrowid

        # Also register official assets in the whitelist.
        for handle in social_values:
            cursor.execute(
                """
                INSERT IGNORE INTO whitelist_assets
                (brand_id, asset_type, asset_value)
                VALUES (%s, %s, %s)
                """,
                (brand_id, "social_handle", handle),
            )

        for app_id in app_values:
            cursor.execute(
                """
                INSERT IGNORE INTO whitelist_assets
                (brand_id, asset_type, asset_value)
                VALUES (%s, %s, %s)
                """,
                (brand_id, "app_id", app_id),
            )

        connection.commit()
        return brand_id

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
# 4. LIST BRANDS
# --------------------------------------------------

def list_brands():
    """Return all registered brands."""

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM brand_profiles ORDER BY brand_id DESC"
        )

        return cursor.fetchall()

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# --------------------------------------------------
# 5. ADD A TRUSTED ASSET
# --------------------------------------------------

def add_whitelist_asset(brand_id, asset_type, asset_value):
    """Add an official social handle, app ID, or other trusted asset."""

    if not asset_type or not str(asset_type).strip():
        raise ValueError("Asset type is required.")

    if not asset_value or not str(asset_value).strip():
        raise ValueError("Asset value is required.")

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT IGNORE INTO whitelist_assets
            (brand_id, asset_type, asset_value)
            VALUES (%s, %s, %s)
            """,
            (
                brand_id,
                str(asset_type).strip().lower(),
                str(asset_value).strip(),
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
# 6. CHECK TRUSTED ASSETS
# --------------------------------------------------

def is_whitelisted(asset_type, asset_value):
    """Return True if the asset is registered as trusted."""

    if not asset_type or not asset_value:
        return False

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM whitelist_assets
            WHERE asset_type = %s
              AND asset_value = %s
            """,
            (
                str(asset_type).strip().lower(),
                str(asset_value).strip(),
            ),
        )

        return cursor.fetchone()[0] > 0

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()
