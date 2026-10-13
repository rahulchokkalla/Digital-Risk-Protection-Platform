
def calculate_social_risk(
    profile_result,
    logo_similarity=None
):
    # Preserve trusted-account protection
    if profile_result.get("status") == "Official":
        return {
            "status": "Official",
            "risk_score": 0,
            "risk_level": "Low",
            "reasons": profile_result.get("reasons", [])
        }

    score = profile_result.get("risk_score", 0)
    reasons = list(profile_result.get("reasons", []))

    if logo_similarity is not None:
        if logo_similarity >= 0.90:
            score += 25
            reasons.append("Profile image closely resembles the official logo")
        elif logo_similarity >= 0.75:
            score += 10
            reasons.append("Profile image may resemble the official logo")

    score = min(score, 100)

    if score >= 60:
        status, level = "Suspicious", "High"
    elif score >= 30:
        status, level = "Needs Review", "Medium"
    else:
        status, level = "No Strong Warning", "Low"

    return {
        "status": status,
        "risk_score": score,
        "risk_level": level,
        "logo_similarity": logo_similarity,
        "reasons": reasons or ["No obvious warning signs found"]
    }
