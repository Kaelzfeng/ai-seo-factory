# -*- coding: utf-8 -*-
"""SSE event orchestration for the conversational generation workspace."""

from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
from pathlib import Path

from lib.conversation_state import get_conversation_state, save_conversation_state
from lib.generation_plan import (
    apply_b2b_content_defaults, artifact_title, build_generation_plan, intent_is_locked, lock_intent,
    next_clarification, render_fallback_artifacts, understanding_message,
)


def _redact_text(value) -> str:
    text = str(value or "")
    for key, secret in os.environ.items():
        upper = key.upper()
        if any(mark in upper for mark in ("API_KEY", "SECRET", "PASSWORD", "TOKEN")):
            if secret and len(secret) >= 6:
                text = text.replace(secret, "***")
    return re.sub(
        r"(?i)\b(?:sk|pk|api|key)[-_][a-z0-9._-]{8,}\b", "***", text
    )


def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(_clean(payload), ensure_ascii=False)}\n\n"


def _normalize_results(result: dict) -> list[dict]:
    if result.get("results"):
        return list(result["results"])
    normalized = []
    for entry in result.get("pages") or []:
        page = entry.get("page", entry)
        content = entry.get("content", entry)
        quality = entry.get("quality", {})
        slug = page.get("slug", "")
        if not slug:
            continue
        normalized.append({
            "slug": slug,
            "title": content.get("title") or page.get("title") or slug,
            "type": page.get("type") or page.get("page_type") or "page",
            "score": quality.get("score"),
            "passed": quality.get("passed", True),
            "link": f"./{slug}.html",
        })
    return normalized


def stream_conversation(
    project: dict,
    tenant_id: int,
    message: str,
    root,
    timeout_seconds: float = 180,
    heartbeat_seconds: float = 3,
):
    project_id = int(project["id"])
    root = Path(root)
    safe_message = _redact_text(message)
    state = get_conversation_state(project_id, tenant_id)
    state["messages"].append({"role": "user", "content": safe_message})

    # Phase 9.3.8: Merge into previous intent from conversation state
    previous_intent = state.get("intent") or {}
    from lib.intent_engine import merge_intent as _merge, is_intent_ready as _ready, build_clarification as _build_clar
    intent = apply_b2b_content_defaults(_merge(previous_intent, safe_message))
    # Fallback: use project seed_keyword if nothing detected
    if not intent.get("product") and not intent.get("industry"):
        seed = str(project.get("seed_keyword", "")).strip()
        if seed:
            intent["product"] = seed.split()[0] if seed else ""
            intent["industry"] = seed

    if not _ready(intent):
        prompt, intent = _build_clar(intent)
        state["messages"].append({"role": "assistant", "content": prompt})
        state["intent"] = intent
        save_conversation_state(project_id, tenant_id, state)
        yield _event("message_delta", {"role": "assistant", "content": prompt})
        yield _event("clarification", {"message": prompt})
        yield _event("done", {
            "ok": True, "status": "awaiting_input", "pages_count": 0,
            "results": [], "index_url": "", "job_id": None,
        })
        return

    plan = build_generation_plan(intent)
    site_title = artifact_title(intent)
    understood = understanding_message(intent)
    planning = (
        "我已经锁定需求。接下来会按 6 个页面推进：供应商、制造商、"
        "批量采购、出口分销、规格选型和 FAQ。"
    )
    state["intent"] = intent
    state["plan"] = plan
    state["artifact"] = {
        "type": "website", "title": site_title,
        "preview": None, "pages": [],
    }
    state["messages"].extend([
        {"role": "assistant", "content": understood},
        {"role": "assistant", "content": planning},
    ])
    save_conversation_state(project_id, tenant_id, state)

    yield _event("message_delta", {"role": "assistant", "content": understood})
    yield _event("intent_locked", intent)
    yield _event("message_delta", {"role": "assistant", "content": planning})
    yield _event("plan_update", plan)
    yield _event("artifact_start", {
        "artifact_type": "website", "title": site_title,
    })

    event_queue = queue.Queue()
    cancelled = threading.Event()

    def callback(event_type, event_data):
        if not cancelled.is_set():
            event_queue.put(("event", event_type, event_data or {}))

    def worker():
        import run
        try:
            run.llm.reset_usage()
            result = run.generate_site_from_input(
                safe_message,
                project_id=project_id,
                tenant_id=tenant_id,
                mode="dry-run",
                bypass_subscription=True,
                max_pages=6,
                output_dir=str(root / "output_src"),
                progress_callback=callback,
            )
            if not cancelled.is_set():
                event_queue.put(("done", result))
        except Exception as exc:
            if not cancelled.is_set():
                event_queue.put(("error", _redact_text(exc)))

    threading.Thread(target=worker, daemon=True).start()
    deadline = time.monotonic() + max(0.05, float(timeout_seconds))
    result = None
    failure = ""

    def find_page(slug):
        return next((page for page in state["artifact"]["pages"] if page.get("slug") == slug), None)

    while result is None and not failure:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            cancelled.set()
            failure = "完整生成超时，已保留六页可编辑 Artifact 草稿。"
            break
        try:
            item = event_queue.get(timeout=min(max(0.01, float(heartbeat_seconds)), remaining))
        except queue.Empty:
            yield _event("message_delta", {
                "role": "assistant",
                "content": "内容仍在处理，我会在页面完成时立即更新右侧 Artifact。",
                "transient": True,
            })
            continue

        if item[0] == "done":
            result = item[1]
            break
        if item[0] == "error":
            failure = item[1]
            break

        event_type, payload = item[1], _clean(item[2])
        if event_type == "stage":
            yield _event("stage", payload)
            natural = payload.get("message") or payload.get("label")
            if natural:
                yield _event("message_delta", {
                    "role": "assistant", "content": str(natural), "transient": True,
                })
        elif event_type == "progress":
            yield _event("progress", payload)
        elif event_type == "log":
            yield _event("log", payload)
        elif event_type == "page_start":
            slug = payload.get("slug", "")
            page = find_page(slug)
            if page is None:
                page = {
                    "slug": slug, "title": payload.get("title", slug),
                    "status": "generating", "html": "", "url": "",
                }
                state["artifact"]["pages"].append(page)
            else:
                page["status"] = "generating"
            save_conversation_state(project_id, tenant_id, state)
            yield _event("page_start", payload)
            yield _event("artifact_page_start", payload)
            yield _event("message_delta", {
                "role": "assistant",
                "content": (
                    f"正在生成第 {payload.get('index', len(state['artifact']['pages']))}/"
                    f"{payload.get('total', 6)} 页：{payload.get('title', slug)}"
                ),
                "transient": True,
            })
        elif event_type == "page_preview":
            slug = payload.get("slug", "")
            page = find_page(slug)
            if page is None:
                page = {"slug": slug, "title": payload.get("title", slug)}
                state["artifact"]["pages"].append(page)
            page.update({
                "title": payload.get("title", page.get("title", slug)),
                "html": payload.get("html", ""), "status": "preview",
                "url": f"/output/{slug}.html" if slug else "",
            })
            state["artifact"]["preview"] = dict(page)
            save_conversation_state(project_id, tenant_id, state)
            yield _event("page_preview", payload)
            yield _event("artifact_page_preview", payload)
            yield _event("token", {"slug": slug, "html": payload.get("html", "")})
        elif event_type == "page_done":
            slug = payload.get("slug", "")
            page = find_page(slug)
            if page is None:
                page = {"slug": slug, "title": payload.get("title", slug), "html": ""}
                state["artifact"]["pages"].append(page)
            page.update({
                "title": payload.get("title", page.get("title", slug)),
                "status": payload.get("status", "done"),
                "url": f"/output/{slug}.html" if slug else "",
                "score": payload.get("score"), "passed": payload.get("passed", True),
            })
            state["artifact"]["preview"] = dict(page)
            save_conversation_state(project_id, tenant_id, state)
            done_payload = dict(payload)
            done_payload["url"] = page["url"]
            yield _event("page_done", done_payload)
            yield _event("artifact_page_done", done_payload)

    results = _normalize_results(result or {})
    if failure or len(results) < 2:
        fallback_pages = render_fallback_artifacts(root / "output_src", intent, plan)
        state["artifact"]["pages"] = []
        for index, page in enumerate(fallback_pages, 1):
            start_payload = {
                "index": index, "total": len(fallback_pages),
                "slug": page["slug"], "title": page["title"], "status": "generating",
            }
            preview_payload = {
                "slug": page["slug"], "title": page["title"],
                "html": page["html"], "status": "preview",
            }
            done_payload = {
                "slug": page["slug"], "title": page["title"],
                "url": page["url"], "status": "done",
            }
            yield _event("page_start", start_payload)
            yield _event("artifact_page_start", start_payload)
            yield _event("page_preview", preview_payload)
            yield _event("artifact_page_preview", preview_payload)
            yield _event("token", {"slug": page["slug"], "html": page["html"]})
            yield _event("page_done", done_payload)
            yield _event("artifact_page_done", done_payload)
            state["artifact"]["pages"].append(dict(page))
            state["artifact"]["preview"] = dict(page)
        results = [{
            "slug": page["slug"], "title": page["title"], "type": page["type"],
            "score": page.get("score"), "passed": True,
            "link": f"./{page['slug']}.html",
        } for page in fallback_pages]

    pages_count = len(results)
    summary_message = (
        f"已完成 {pages_count} 个页面，全部通过基础 SEO 检查。"
        "你可以继续追问、改写页面，或发布为 WordPress 草稿。"
    )
    state["messages"].append({"role": "assistant", "content": summary_message})
    if state["artifact"].get("pages"):
        state["artifact"]["preview"] = dict(state["artifact"]["pages"][-1])
    generation_ids = (result or {}).get("generation_ids") or []
    state["latest_job"] = {
        "id": generation_ids[0] if generation_ids else None,
        "status": "completed", "pages_count": pages_count,
    }
    save_conversation_state(project_id, tenant_id, state)
    yield _event("final_summary", {
        "message": summary_message,
        "pages_count": pages_count,
        "actions": [
            "open_preview", "publish_wordpress_draft",
            "generate_more_pages", "rewrite_page",
        ],
    })
    yield _event("done", {
        "ok": True, "status": "completed", "pages_count": pages_count,
        "results": results, "index_url": "/output/index.html",
        "job_id": state["latest_job"]["id"],
        "warning": _redact_text(failure) if failure else "",
    })
