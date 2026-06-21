# -*- coding: utf-8 -*-
"""Small, draft-first WordPress REST API adapter.

This module intentionally exposes structured results instead of propagating
network exceptions into Flask handlers. Application Passwords are treated as
secrets and are removed from both returned errors and log messages.
"""

from __future__ import annotations

import logging
from urllib.parse import quote, urlsplit

import requests
from requests.auth import HTTPBasicAuth


logger = logging.getLogger(__name__)


class WordPressAdapter:
    """Create WordPress posts through ``/wp-json/wp/v2/posts``.

    Phase 9.3.4 is deliberately draft-only. Even if a caller supplies
    ``status="publish"``, the outbound payload remains a draft and the result
    contains a warning.
    """

    provider = "wordpress_real"

    def __init__(self, base_url, username, app_password, timeout=20):
        self.base_url = self._normalize_base_url(base_url)
        self.username = str(username or "")
        self._app_password = str(app_password or "")
        try:
            self.timeout = float(timeout)
        except (TypeError, ValueError):
            self.timeout = 20

        self.posts_endpoint = f"{self.base_url}/wp-json/wp/v2/posts"
        self.users_me_endpoint = f"{self.base_url}/wp-json/wp/v2/users/me"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.username, self._app_password)
        self.session.headers.update({"Accept": "application/json"})

    @staticmethod
    def _normalize_base_url(base_url):
        value = str(base_url or "").strip().rstrip("/")
        for suffix in ("/wp-json/wp/v2", "/wp-json"):
            if value.lower().endswith(suffix):
                value = value[:-len(suffix)].rstrip("/")
                break
        return value

    def sanitize_error(self, value):
        """Return an error string with all known forms of the secret masked."""
        text = str(value or "")
        secrets = {
            self._app_password,
            self._app_password.replace(" ", ""),
            quote(self._app_password, safe=""),
        }
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            text = text.replace(secret, "***")
        return text

    def _base_result(self, **overrides):
        result = {
            "ok": False,
            "provider": self.provider,
            "status": "failed",
            "post_id": None,
            "edit_url": "",
            "link": "",
            "warning": "",
            "error": "",
        }
        result.update(overrides)
        return result

    def _configuration_error(self):
        missing = []
        if not self.base_url:
            missing.append("WP_BASE_URL")
        if not self.username:
            missing.append("WP_USERNAME")
        if not self._app_password:
            missing.append("WP_APP_PASSWORD")
        if missing:
            return f"Missing WordPress configuration: {', '.join(missing)}"

        parsed = urlsplit(self.base_url)
        is_local_http = (
            parsed.scheme == "http"
            and (parsed.hostname in {"localhost", "127.0.0.1", "::1"})
        )
        if parsed.scheme != "https" and not is_local_http:
            return "WP_BASE_URL must use HTTPS (HTTP is allowed only for localhost)"
        if not parsed.netloc:
            return "WP_BASE_URL must be an absolute URL"
        return ""

    def _request(self, method, url, **kwargs):
        config_error = self._configuration_error()
        if config_error:
            return None, self._base_result(error=config_error)

        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                allow_redirects=False,
                **kwargs,
            )
        except requests.Timeout as exc:
            message = self.sanitize_error(exc) or "request timed out"
            message = f"WordPress request timed out: {message}"
            logger.warning("WordPress REST request failed: %s", message)
            return None, self._base_result(error=message)
        except requests.RequestException as exc:
            message = self.sanitize_error(exc) or "request failed"
            logger.warning("WordPress REST request failed: %s", message)
            return None, self._base_result(error=message)

        if not 200 <= response.status_code < 300:
            detail = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = payload.get("message") or payload.get("code") or ""
            except (TypeError, ValueError):
                detail = ""
            if not detail:
                detail = getattr(response, "text", "")[:500]
            message = self.sanitize_error(
                f"WordPress REST API returned HTTP {response.status_code}: {detail}"
            ).rstrip(": ")
            logger.warning("WordPress REST request failed: %s", message)
            return None, self._base_result(error=message)

        return response, None

    def test_connection(self):
        response, error = self._request(
            "GET", self.users_me_endpoint, params={"context": "edit"}
        )
        if error:
            return error
        try:
            payload = response.json()
        except (TypeError, ValueError):
            payload = {}
        return self._base_result(
            ok=True,
            status="connected",
            warning="",
            error="",
            username=payload.get("name") or payload.get("slug") or self.username,
        )

    def create_post(
        self,
        title,
        content,
        slug=None,
        excerpt=None,
        status="draft",
        categories=None,
        tags=None,
        dry_run=False,
    ):
        requested_status = str(status or "draft").lower()
        warning = ""
        if requested_status != "draft":
            warning = (
                f"Requested status '{requested_status}' was restricted to draft."
            )

        payload = {
            "title": title or "",
            "content": content or "",
            "status": "draft",
        }
        if slug:
            payload["slug"] = slug
        if excerpt:
            payload["excerpt"] = excerpt
        if categories:
            payload["categories"] = list(categories)
        if tags:
            payload["tags"] = list(tags)

        if dry_run:
            return self._base_result(
                ok=True,
                status="dry_run",
                warning=warning,
                error="",
                planned_payload=payload,
            )

        response, error = self._request("POST", self.posts_endpoint, json=payload)
        if error:
            error["warning"] = warning
            return error

        try:
            data = response.json()
        except (TypeError, ValueError):
            message = "WordPress REST API returned an invalid JSON response"
            logger.warning("WordPress REST request failed: %s", message)
            return self._base_result(error=message, warning=warning)

        post_id = data.get("id")
        if post_id is None:
            message = "WordPress REST API response did not include a post id"
            logger.warning("WordPress REST request failed: %s", message)
            return self._base_result(error=message, warning=warning)

        return self._base_result(
            ok=True,
            status="draft",
            post_id=post_id,
            edit_url=f"{self.base_url}/wp-admin/post.php?post={post_id}&action=edit",
            link=data.get("link", ""),
            warning=warning,
            error="",
        )

    def create_draft_post(self, title, content, **kwargs):
        kwargs["status"] = "draft"
        return self.create_post(title, content, **kwargs)
