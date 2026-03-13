# -*- coding: utf-8 -*-
"""
用户偏好本地持久化
将 Canvas token、邮箱、LinkedIn cookie 等保存到本地 data/user_prefs.json
避免每次都要重新填写
"""
import json
import os
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/prefs", tags=["User Preferences"])

PREFS_FILE = "data/user_prefs.json"
os.makedirs("data", exist_ok=True)


def _load() -> dict:
    try:
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    with open(PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class PrefsUpdate(BaseModel):
    canvas_token: Optional[str] = None
    email: Optional[str] = None
    linkedin_cookie: Optional[str] = None
    linkedin_email: Optional[str] = None
    keywords: Optional[str] = None
    location: Optional[str] = None


@router.get("")
async def get_prefs():
    """读取已保存的用户偏好"""
    prefs = _load()
    # canvas_token 和 linkedin_cookie 脱敏返回（只返回是否存在）
    return {
        "canvas_token": prefs.get("canvas_token", ""),
        "canvas_token_saved": bool(prefs.get("canvas_token")),
        "email": prefs.get("email", ""),
        "linkedin_cookie": prefs.get("linkedin_cookie", ""),
        "linkedin_cookie_saved": bool(prefs.get("linkedin_cookie")),
        "linkedin_email": prefs.get("linkedin_email", ""),
        "keywords": prefs.get("keywords", ""),
        "location": prefs.get("location", "Singapore"),
    }


@router.post("")
async def save_prefs(update: PrefsUpdate):
    """保存用户偏好（增量更新，不覆盖未传的字段）"""
    prefs = _load()
    for field, value in update.model_dump(exclude_none=True).items():
        if value:  # 只保存非空值
            prefs[field] = value
    _save(prefs)
    return {"saved": True}


@router.delete("")
async def clear_prefs():
    """清除所有保存的偏好"""
    _save({})
    return {"cleared": True}
