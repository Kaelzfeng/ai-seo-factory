# -*- coding: utf-8 -*-
"""lib/security_headers.py · Phase 8: 安全响应头"""

def get_default_security_headers() -> dict:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }

def apply_security_headers(app):
    @app.after_request
    def _add_security_headers(response):
        for key, val in get_default_security_headers().items():
            response.headers.setdefault(key, val)
        if response.content_type and "application/json" in response.content_type:
            response.headers.setdefault("Cache-Control", "no-store")
        return response
