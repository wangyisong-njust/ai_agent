# -*- coding: utf-8 -*-
"""
Google Calendar 自动推送
OAuth2 授权 + 批量创建事件，真正的 Agent 自动同步
"""
import json
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

import httpx

# Token 持久化路径
TOKEN_FILE = "data/gcal_token.json"
os.makedirs("data", exist_ok=True)

SCOPES = "https://www.googleapis.com/auth/calendar"
GCAL_API = "https://www.googleapis.com/calendar/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def _load_token() -> Optional[dict]:
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_token(token: dict):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f, indent=2)


def clear_token():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def is_authorized() -> bool:
    t = _load_token()
    return bool(t and t.get("refresh_token"))


def get_auth_url(client_id: str, redirect_uri: str) -> str:
    """生成 OAuth 授权 URL"""
    params = (
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={SCOPES}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return AUTH_URL + params


async def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """用授权码换 access_token + refresh_token"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        resp.raise_for_status()
        token = resp.json()
        _save_token(token)
        return token


async def _get_valid_access_token(client_id: str, client_secret: str) -> str:
    """获取有效的 access_token，必要时用 refresh_token 刷新"""
    token = _load_token()
    if not token:
        raise RuntimeError("Not authorized. Please connect Google Calendar first.")

    # 检查是否过期（提前 60s 刷新）
    expires_at = token.get("expires_at", 0)
    import time
    if time.time() < expires_at - 60 and token.get("access_token"):
        return token["access_token"]

    # 刷新
    if not token.get("refresh_token"):
        raise RuntimeError("No refresh token. Please re-authorize.")

    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data={
            "refresh_token": token["refresh_token"],
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        new_token = resp.json()
        import time as _time
        new_token["refresh_token"] = token["refresh_token"]  # refresh_token 不变
        new_token["expires_at"] = _time.time() + new_token.get("expires_in", 3600)
        _save_token(new_token)
        return new_token["access_token"]


def _event_to_gcal(ev: dict) -> dict:
    """把本地事件格式转成 Google Calendar API 格式"""
    from app.agents.schedule_agent.ics_builder import TYPE_LABELS, TYPE_COLORS

    label = TYPE_LABELS.get(ev.get("event_type", "other"), "📅 Event")
    title = f"{label}: {ev['title']}"

    start: datetime = ev["start"]
    end: datetime = ev.get("end") or (start + timedelta(hours=1))

    # 确保有时区
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone(timedelta(hours=8)))
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone(timedelta(hours=8)))

    desc_parts = [ev.get("description", "")]
    if ev.get("url"):
        desc_parts.append(f"URL: {ev['url']}")
    desc_parts.append("🤖 Auto-synced by NUS Campus Assistant")

    gcal_event = {
        "summary": title,
        "description": "\n".join(p for p in desc_parts if p),
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Singapore"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Singapore"},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},   # 1 day before
                {"method": "popup", "minutes": 60},          # 1 hour before
            ],
        },
    }

    # Color ID mapping (Google Calendar uses 1-11)
    color_map = {
        "exam": "11",       # Tomato (red)
        "deadline": "6",    # Tangerine (orange)
        "quiz": "5",        # Banana (yellow)
        "project": "2",     # Sage (green)
        "assignment": "9",  # Blueberry
        "other": "8",       # Graphite
    }
    color_id = color_map.get(ev.get("event_type", "other"), "8")
    gcal_event["colorId"] = color_id

    return gcal_event


async def push_events_to_gcal(
    events: List[dict],
    client_id: str,
    client_secret: str,
    calendar_id: str = "primary",
) -> Tuple[int, int, List[str]]:
    """
    批量推送事件到 Google Calendar。
    返回 (pushed_count, skipped_count, errors)
    """
    access_token = await _get_valid_access_token(client_id, client_secret)
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    pushed = 0
    skipped = 0
    errors = []

    async with httpx.AsyncClient(timeout=30) as client:
        for ev in events:
            try:
                gcal_ev = _event_to_gcal(ev)
                resp = await client.post(
                    f"{GCAL_API}/calendars/{calendar_id}/events",
                    headers=headers,
                    json=gcal_ev,
                )
                if resp.status_code in (200, 201):
                    pushed += 1
                else:
                    skipped += 1
                    errors.append(f"{ev['title']}: {resp.text[:100]}")
            except Exception as e:
                skipped += 1
                errors.append(f"{ev['title']}: {str(e)}")

    return pushed, skipped, errors
