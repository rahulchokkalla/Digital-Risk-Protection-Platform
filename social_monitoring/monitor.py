
import re

SUSPICIOUS_WORDS = [
    "claim prize",
    "free money",
    "send password",
    "verify your account",
    "urgent payment",
    "giveaway winner"
]


def normalize(value):
    value = str(value or "").lower()
    return re.sub(r"[^a-z0-9]", "", value)


def check_profile(profile, official_name, trusted_handles=None):
    trusted_handles = trusted_handles or []

    handle = str(profile.get("handle", "")).strip().lower()
    trusted = {
        str(item).strip().lower()
        for item in trusted_handles
    }

    # Trusted official handles are never flagged
    if handle and handle in trusted:
        return {
            "status": "Official",
            "risk_score": 0,
            "risk_level": "Low",
            "reasons": ["Handle matches the trusted whitelist"]
        }

    display_name = profile.get("display_name", "")
    bio = profile.get("bio", "")
    name = normalize(official_name)
    display = normalize(display_name)
    text = (str(display_name) + " " + str(bio)).lower()

    score = 0
    reasons = []

    if name and display and name in display:
        score += 30
        reasons.append("Profile uses the brand name")

    if any(word in text for word in SUSPICIOUS_WORDS):
        score += 40
        reasons.append("Suspicious wording found")

    if any(word in handle for word in ["support", "help", "verify"]):
        score += 15
        reasons.append("Handle resembles a support account")

    score = min(score, 100)

    if score >= 60:
        status = "Suspicious"
        level = "High"
    elif score >= 30:
        status = "Needs Review"
        level = "Medium"
    else:
        status = "No Strong Warning"
        level = "Low"

    return {
        "status": status,
        "risk_score": score,
        "risk_level": level,
        "reasons": reasons or ["No obvious warning signs found"]
    }
