
import re
import unicodedata

from rapidfuzz import fuzz


# --------------------------------------------------
# 1. SUSPICIOUS WORDS
# --------------------------------------------------

SUSPICIOUS_WORDS = re.compile(
    r"\b("
    r"free money|verify account|urgent|claim reward|"
    r"password|free gift|support|login now|"
    r"account suspended|confirm identity|"
    r"claim now|limited offer"
    r")\b",
    re.IGNORECASE,
)


# --------------------------------------------------
# 2. NORMALIZE TEXT
# --------------------------------------------------

def normalize_name(name):
    """Normalize names and remove invisible Unicode characters."""

    if not name:
        return ""

    name = unicodedata.normalize("NFKC", str(name))

    name = "".join(
        char
        for char in name
        if unicodedata.category(char) != "Cf"
    )

    return re.sub(r"[^a-z0-9]", "", name.lower())


# --------------------------------------------------
# 3. NORMALIZE PUBLISHER NAMES
# --------------------------------------------------

def normalize_publisher(name):
    """
    Normalize publisher names while ignoring common
    legal suffixes such as Inc., LLC, and Ltd.
    """

    normalized = normalize_name(name)

    if not normalized:
        return ""

    suffixes = (
        "incorporated",
        "corporation",
        "limited",
        "inc",
        "llc",
        "ltd",
        "corp",
        "plc",
    )

    changed = True

    while changed:
        changed = False

        for suffix in suffixes:
            if (
                normalized.endswith(suffix)
                and len(normalized) > len(suffix)
            ):
                normalized = normalized[:-len(suffix)]
                changed = True
                break

    return normalized


# --------------------------------------------------
# 4. CALCULATE IMPERSONATION RISK
# --------------------------------------------------

def calculate_risk(
    app_name,
    publisher,
    official_name,
    official_publisher,
    description=None,
    app_id=None,
):
    """
    Estimate the risk that an app may be impersonating
    a legitimate brand.

    Returns a risk score, similarity scores, and reasons.

    This is a screening tool, not proof of fraud.
    """

    app_name = str(app_name or "").strip()
    publisher = str(publisher or "").strip()
    official_name = str(official_name or "").strip()
    official_publisher = str(official_publisher or "").strip()
    description = str(description or "")
    app_id = str(app_id or "").strip()

    # Normalize values for comparison.
    app_clean = normalize_name(app_name)
    official_clean = normalize_name(official_name)

    publisher_clean = normalize_publisher(publisher)
    official_publisher_clean = normalize_publisher(
        official_publisher
    )

    # Calculate name similarity.
    if app_clean and official_clean:
        name_score = max(
            fuzz.ratio(app_clean, official_clean),
            fuzz.token_sort_ratio(app_clean, official_clean),
            fuzz.partial_ratio(app_clean, official_clean),
            fuzz.token_set_ratio(app_clean, official_clean),
        )
    else:
        name_score = 0

    # Calculate publisher similarity.
    if publisher_clean and official_publisher_clean:
        publisher_score = fuzz.ratio(
            publisher_clean,
            official_publisher_clean,
        )
    else:
        publisher_score = 0

    risk = 0
    reasons = []

    # --------------------------------------------------
    # SIGNAL 1: LOOK-ALIKE APP NAME
    # --------------------------------------------------

    if (
        app_clean
        and official_clean
        and app_clean != official_clean
        and name_score >= 80
    ):
        risk += 35
        reasons.append(
            f"App name resembles the official brand "
            f"({name_score:.0f}% similarity)"
        )

    # --------------------------------------------------
    # SIGNAL 2: PUBLISHER MISMATCH
    # --------------------------------------------------

    publisher_mismatch = (
        bool(publisher_clean)
        and bool(official_publisher_clean)
        and publisher_clean != official_publisher_clean
    )

    if (
        app_clean
        and official_clean
        and name_score >= 80
        and publisher_mismatch
    ):
        risk += 35
        reasons.append(
            "Publisher differs from the official publisher"
        )

    # --------------------------------------------------
    # SIGNAL 3: SUSPICIOUS DESCRIPTION OR APP NAME
    # --------------------------------------------------

    text_to_check = f"{app_name} {description}"

    suspicious_matches = sorted(
        {
            match.group(0).lower()
            for match in SUSPICIOUS_WORDS.finditer(text_to_check)
        }
    )

    if suspicious_matches:
        risk += min(15 * len(suspicious_matches), 30)

        reasons.append(
            "Suspicious wording: "
            + ", ".join(suspicious_matches)
        )

    # --------------------------------------------------
    # SIGNAL 4: EMPTY OR MISSING INFORMATION
    # --------------------------------------------------

    if not app_name:
        reasons.append("App name is missing")

    if not publisher:
        reasons.append("Publisher information is missing")

    # Missing information alone does not prove impersonation.
    # It is reported for review but adds no risk points.

    # --------------------------------------------------
    # SIGNAL 5: FINAL RISK SCORE
    # --------------------------------------------------

    risk_score = min(risk, 100)

    if risk_score >= 70:
        status = "High Risk"
    elif risk_score >= 35:
        status = "Needs Review"
    else:
        status = "Low Risk"

    return {
        "risk_score": risk_score,
        "name_similarity": round(name_score, 2),
        "publisher_similarity": round(publisher_score, 2),
        "status": status,
        "reasons": reasons,
    }
