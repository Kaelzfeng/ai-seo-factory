# -*- coding: utf-8 -*-
"""lib/cms_adapter.py · Phase 6: CMS Adapter 抽象层

BaseCMSAdapter → WordPressCMSAdapter / MockCMSAdapter
所有方法返回统一结构。
"""


class BaseCMSAdapter:
    """CMS 适配器基类。"""

    def __init__(self, config: dict = None):
        self.config = config or {}

    def validate_config(self) -> dict:
        raise NotImplementedError

    def publish_draft(self, page_content, mapped_fields=None) -> dict:
        raise NotImplementedError

    def publish_now(self, page_content, mapped_fields=None) -> dict:
        raise NotImplementedError

    def update_content(self, remote_id, page_content, mapped_fields=None) -> dict:
        raise NotImplementedError

    def get_content(self, remote_id) -> dict:
        raise NotImplementedError

    def delete_content(self, remote_id) -> dict:
        raise NotImplementedError

    def health_check(self) -> dict:
        raise NotImplementedError


# ── Mock ─────────────────────────────────────────────


class MockCMSAdapter(BaseCMSAdapter):
    """测试用 mock adapter, 不发送真实请求。"""

    _counter = 0

    def validate_config(self) -> dict:
        return {"ok": True, "cms": "mock", "errors": []}

    def publish_draft(self, page_content, mapped_fields=None) -> dict:
        import time
        tid = f"mock-draft-{id(page_content)}"
        MockCMSAdapter._counter += 1
        return {
            "ok": True, "cms": "mock",
            "remote_id": tid, "remote_url": f"https://mock.local/{tid}",
            "status": "draft", "errors": [],
        }

    def publish_now(self, page_content, mapped_fields=None) -> dict:
        import time
        tid = f"mock-pub-{id(page_content)}"
        return {
            "ok": True, "cms": "mock",
            "remote_id": tid, "remote_url": f"https://mock.local/{tid}",
            "status": "published", "errors": [],
        }

    def update_content(self, remote_id, page_content, mapped_fields=None) -> dict:
        return {
            "ok": True, "cms": "mock",
            "remote_id": remote_id, "remote_url": f"https://mock.local/{remote_id}",
            "status": "updated", "errors": [],
        }

    def get_content(self, remote_id) -> dict:
        return {"ok": True, "cms": "mock", "remote_id": remote_id,
                "data": {"title": "Mock Content"}, "errors": []}

    def delete_content(self, remote_id) -> dict:
        return {"ok": True, "cms": "mock", "remote_id": remote_id,
                "status": "deleted", "errors": []}

    def health_check(self) -> dict:
        return {"ok": True, "cms": "mock", "status": "healthy"}


# ── WordPress ────────────────────────────────────────


class WordPressCMSAdapter(BaseCMSAdapter):
    """复用 lib/wp_publish.py 的 WordPress REST 适配器。"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._wp = None

    def _get_wp(self):
        if self._wp is None:
            from lib.cms_wordpress import WordPressAdapter
            site = (
                self.config.get("base_url")
                or self.config.get("wp_base_url")
                or self.config.get("wp_url")
                or self.config.get("site_url", "")
            )
            user = self.config.get("username") or self.config.get("wp_username", "")
            pw = self.config.get("app_password") or self.config.get("wp_app_password", "")
            if not site or not user or not pw:
                return None
            self._wp = WordPressAdapter(
                base_url=site,
                username=user,
                app_password=pw,
                timeout=self.config.get("timeout", 20),
            )
        return self._wp

    def validate_config(self) -> dict:
        missing = []
        if not any(self.config.get(key) for key in (
            "base_url", "wp_base_url", "wp_url", "site_url"
        )):
            missing.append("wp_url")
        if not (self.config.get("username") or self.config.get("wp_username")):
            missing.append("wp_username")
        if not (self.config.get("app_password") or self.config.get("wp_app_password")):
            missing.append("wp_app_password")
        if missing:
            return {"ok": False, "cms": "wordpress",
                    "errors": [f"Missing config: {', '.join(missing)}"]}
        return {"ok": True, "cms": "wordpress", "errors": []}

    def publish_draft(self, page_content, mapped_fields=None) -> dict:
        return self._publish(page_content, mapped_fields, status="draft")

    def publish_now(self, page_content, mapped_fields=None) -> dict:
        return self._publish(page_content, mapped_fields, status="publish")

    def _publish(self, page_content, mapped_fields=None, status="draft") -> dict:
        vc = self.validate_config()
        if not vc["ok"]:
            error = "; ".join(vc["errors"])
            return {
                "ok": False, "cms": "wordpress", "provider": "wordpress_real",
                "status": "failed", "post_id": None, "edit_url": "", "link": "",
                "warning": "", "error": error,
                "remote_id": "", "remote_url": "", "errors": vc["errors"],
            }

        wp = self._get_wp()
        if wp is None:
            return vc

        mf = mapped_fields or {}
        title = mf.get("title", getattr(page_content, "title", ""))
        html = mf.get("content", getattr(page_content, "gutenberg_html", ""))
        slug = mf.get("slug", getattr(page_content, "slug", ""))
        meta = mf.get("meta_description", getattr(page_content, "meta_description", ""))

        try:
            result = wp.create_post(
                title=title,
                content=html,
                slug=slug,
                excerpt=meta,
                status=status,
                categories=mf.get("categories"),
                tags=mf.get("tags"),
            )
            error = wp.sanitize_error(result.get("error", ""))
            post_id = result.get("post_id")
            link = result.get("link", "")
            return {
                "ok": result.get("ok", False),
                "cms": "wordpress",
                "provider": "wordpress_real",
                "remote_id": str(post_id) if post_id is not None else "",
                "remote_url": link,
                "post_id": post_id,
                "edit_url": result.get("edit_url", ""),
                "link": link,
                "status": result.get("status", "failed"),
                "warning": result.get("warning", ""),
                "error": error,
                "errors": [error] if error else [],
            }
        except Exception as e:
            error = wp.sanitize_error(e)
            return {
                "ok": False, "cms": "wordpress", "provider": "wordpress_real",
                "status": "failed", "post_id": None, "edit_url": "", "link": "",
                "warning": "", "error": error,
                "remote_id": "", "remote_url": "", "errors": [error],
            }

    def update_content(self, remote_id, page_content, mapped_fields=None) -> dict:
        return {"ok": False, "cms": "wordpress", "status": "failed",
                "errors": ["update_content not implemented for WordPress adapter"]}

    def get_content(self, remote_id) -> dict:
        return {"ok": False, "cms": "wordpress", "status": "failed",
                "errors": ["get_content not implemented"]}

    def delete_content(self, remote_id) -> dict:
        return {"ok": False, "cms": "wordpress", "status": "failed",
                "errors": ["delete_content not implemented"]}

    def health_check(self) -> dict:
        vc = self.validate_config()
        if not vc["ok"]:
            return {"ok": False, "cms": "wordpress", "status": "unhealthy", "errors": vc["errors"]}
        result = self._get_wp().test_connection()
        return {
            "ok": result["ok"], "cms": "wordpress",
            "provider": "wordpress_real",
            "status": "healthy" if result["ok"] else "unhealthy",
            "errors": [result["error"]] if result.get("error") else [],
        }


# ── Factory ──────────────────────────────────────────


_ADAPTERS = {
    "mock": MockCMSAdapter,
    "wordpress": WordPressCMSAdapter,
    "wordpress_real": WordPressCMSAdapter,
}


def get_cms_adapter(cms_type: str = "wordpress", config: dict = None) -> BaseCMSAdapter:
    cls = _ADAPTERS.get(cms_type, MockCMSAdapter)
    return cls(config)
