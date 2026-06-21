# -*- coding: utf-8 -*-
"""Persist one conversational workspace state per project."""

from __future__ import annotations

import json


def _db():
    from models import _get_db
    return _get_db()


def _ensure_table(db) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS conversation_states (
               project_id INTEGER PRIMARY KEY,
               tenant_id INTEGER NOT NULL,
               state_json TEXT NOT NULL DEFAULT '{}',
               updated_at TEXT NOT NULL DEFAULT (datetime('now'))
           )"""
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_states_tenant "
        "ON conversation_states(tenant_id)"
    )
    db.commit()


def empty_state(project_id: int) -> dict:
    return {
        "ok": True,
        "project_id": project_id,
        "messages": [],
        "intent": {},
        "plan": {},
        "artifact": {
            "type": "website",
            "title": "",
            "preview": None,
            "pages": [],
        },
        "latest_job": None,
    }


def get_conversation_state(project_id: int, tenant_id: int) -> dict:
    db = _db()
    _ensure_table(db)
    row = db.execute(
        "SELECT state_json FROM conversation_states "
        "WHERE project_id = ? AND tenant_id = ?",
        (project_id, tenant_id),
    ).fetchone()
    if not row:
        return empty_state(project_id)
    try:
        state = json.loads(row["state_json"] or "{}")
    except (TypeError, ValueError):
        state = {}
    clean = empty_state(project_id)
    clean.update({key: state.get(key, clean[key]) for key in (
        "messages", "intent", "plan", "artifact", "latest_job"
    )})
    return clean


def save_conversation_state(project_id: int, tenant_id: int, state: dict) -> dict:
    db = _db()
    _ensure_table(db)
    payload = empty_state(project_id)
    payload.update({key: state.get(key, payload[key]) for key in (
        "messages", "intent", "plan", "artifact", "latest_job"
    )})
    payload["ok"] = True
    payload["project_id"] = project_id
    state_json = json.dumps(payload, ensure_ascii=False)
    db.execute(
        """INSERT INTO conversation_states (project_id, tenant_id, state_json)
           VALUES (?, ?, ?)
           ON CONFLICT(project_id) DO UPDATE SET
             tenant_id = excluded.tenant_id,
             state_json = excluded.state_json,
             updated_at = datetime('now')""",
        (project_id, tenant_id, state_json),
    )
    db.commit()
    return payload
