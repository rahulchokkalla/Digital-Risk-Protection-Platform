
from io import BytesIO

import requests
from PIL import Image, ImageChops, ImageStat


def compare_logos(official_url, profile_url):
    if not official_url or not profile_url:
        return None

    try:
        images = []

        for url in [official_url, profile_url]:
            response = requests.get(
                url,
                timeout=8,
                headers={"User-Agent": "DigitalRiskProtection/1.0"}
            )
            response.raise_for_status()

            image = Image.open(
                BytesIO(response.content)
            ).convert("RGB").resize((64, 64))

            images.append(image)

        difference = ImageChops.difference(
            images[0], images[1]
        )
        average_difference = sum(
            ImageStat.Stat(difference).mean
        ) / 3

        similarity = 1 - average_difference / 255
        return round(max(0, min(1, similarity)), 2)

    except Exception:
        # Missing or inaccessible images are unknown, not suspicious
        return None
