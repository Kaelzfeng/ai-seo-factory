"""可选配图：从 Pexels 取一张图。没配 key 就返回 None（demo 仍可跑）。"""
import os
import requests


def fetch_image(query: str):
    """返回 (bytes, filename, content_type) 或 None。"""
    key = os.getenv("PEXELS_API_KEY", "").strip()
    if not key:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": key}, timeout=20,
        )
        r.raise_for_status()
        photos = r.json().get("photos", [])
        if not photos:
            return None
        img = requests.get(photos[0]["src"]["large"], timeout=20)
        img.raise_for_status()
        slug = "".join(ch if ch.isalnum() else "-" for ch in query.lower())[:40].strip("-")
        return img.content, f"{slug or 'image'}.jpg", "image/jpeg"
    except Exception as e:
        print(f"   ⚠️ 配图获取失败（跳过）：{e}")
        return None
