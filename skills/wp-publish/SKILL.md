# Skill: wp-publish

Publishing contract for the WordPress adapter (`lib/wp_publish.py`).

Each page is published via the WordPress REST API (`/wp-json/wp/v2`) using an
**Application Password** (WP Admin → Users → Profile → Application Passwords).

Per page it sets: title, HTML content (with internal links), slug, excerpt /
meta description, category, and an uploaded featured image.

Requirements on the target site:
- Pretty permalinks set to **Post name** (Settings → Permalinks), so every page's
  URL is `https://site/<slug>/` and the internal links resolve on first publish.
- REST API reachable over HTTPS.

The Yoast / Rank Math meta description is written when the plugin exposes that
field to REST; otherwise it falls back to the post excerpt.
