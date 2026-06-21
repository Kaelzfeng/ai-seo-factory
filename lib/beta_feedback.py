# -*- coding: utf-8 -*-
"""lib/beta_feedback.py · Phase 9.3: Beta 反馈收集

提供 create / list / summarize 三个接口。
使用 models._get_db() 获取连接，适配测试 monkeypatch。
"""

import json
import models


def create_beta_feedback(tenant_id, rating, message="", category=None,
                         page=None, meta=None, project_id=None, metadata=None):
    """创建一条 Beta 反馈记录。

    rating 会被 clamp 到 1-5 范围。
    page / meta / metadata 会合并写入 metadata_json。
    project_id 可选，关联到具体项目。
    返回新记录的 id。
    """
    db = models._get_db()

    # Clamp rating
    rating = max(1, min(5, int(rating or 3)))

    category = category or "other"
    message = message or ""

    # 合并 metadata (meta + metadata + page)
    merged_meta = {}
    if meta and isinstance(meta, dict):
        merged_meta.update(meta)
    if metadata and isinstance(metadata, dict):
        merged_meta.update(metadata)
    if page:
        merged_meta["page"] = page

    db.execute(
        "INSERT INTO beta_feedback (tenant_id, project_id, category, rating, message, metadata_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (tenant_id, project_id, category, rating, message, json.dumps(merged_meta)),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


def list_beta_feedback(tenant_id, limit=50, project_id=None):
    """返回当前 tenant 的反馈列表，按 created_at 倒序。可选按 project_id 过滤。"""
    db = models._get_db()
    sql = "SELECT * FROM beta_feedback WHERE tenant_id = ?"
    params = [tenant_id]
    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def summarize_beta_feedback(tenant_id, project_id=None):
    """汇总当前 tenant 的反馈统计。

    返回 dict:
        count        — 反馈总数
        avg_rating   — 平均评分
        by_category  — 按 category 分组计数
        categories   — by_category 的别名
        recent_items — 最近 5 条摘要
    """
    db = models._get_db()

    sql = "SELECT * FROM beta_feedback WHERE tenant_id = ?"
    params = [tenant_id]
    if project_id is not None:
        sql += " AND project_id = ?"
        params.append(project_id)

    rows = db.execute(sql, params).fetchall()
    items = [dict(r) for r in rows]

    count = len(items)
    avg_rating = (
        round(sum(it["rating"] for it in items) / count, 1) if count > 0 else 0.0
    )

    by_category = {}
    for it in items:
        cat = it.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + 1

    recent_items = []
    for it in items[:5]:
        recent_items.append({
            "id": it["id"],
            "rating": it["rating"],
            "category": it.get("category", "other"),
            "message": (it.get("message") or "")[:100],
            "created_at": it.get("created_at", ""),
        })

    return {
        "count": count,
        "avg_rating": avg_rating,
        "by_category": by_category,
        "categories": by_category,
        "recent_items": recent_items,
    }
