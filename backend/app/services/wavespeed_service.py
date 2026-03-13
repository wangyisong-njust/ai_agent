# -*- coding: utf-8 -*-
"""
WaveSpeed AI Service
赞助商核心服务 - 统一的 LLM 调用入口

API 规范（原生格式，非 OpenAI 兼容）：
  Base URL: https://api.wavespeed.ai/api/v3
  LLM 端点: POST /wavespeed-ai/any-llm
  轮询结果: GET /predictions/{task_id}/result
  流式输出: 请求体加 "stream": true → SSE 流
  响应格式: data.outputs[0] 是文本内容
"""
import asyncio
import json
import httpx
from typing import AsyncGenerator
from app.config import get_settings

settings = get_settings()

LLM_ENDPOINT = f"{settings.wavespeed_base_url}/wavespeed-ai/any-llm"
VISION_ENDPOINT = f"{settings.wavespeed_base_url}/wavespeed-ai/any-llm/vision"
RESULT_ENDPOINT = f"{settings.wavespeed_base_url}/predictions/{{task_id}}/result"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.wavespeed_api_key}",
        "Content-Type": "application/json",
    }


async def chat_complete(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """
    同步模式调用 WaveSpeed LLM（enable_sync_mode=true，等待完整结果）
    messages 格式: [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    # 将 messages 转换为 WaveSpeed 格式：提取 system + 最后的 user prompt
    system_prompt = ""
    user_prompt = ""
    for msg in messages:
        if msg["role"] == "system":
            system_prompt = msg["content"]
        elif msg["role"] == "user":
            user_prompt = msg["content"]

    payload = {
        "model": settings.wavespeed_llm_model,
        "prompt": user_prompt,
        "system_prompt": system_prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "enable_sync_mode": True,
        "priority": "latency",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(LLM_ENDPOINT, headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") == 200:
        outputs = data.get("data", {}).get("outputs", [])
        return outputs[0] if outputs else ""
    raise RuntimeError(f"WaveSpeed API error: {data.get('message', 'Unknown error')}")


async def chat_complete_with_history(messages: list[dict], **kwargs) -> str:
    """
    支持多轮对话历史的版本：将 history 拼接进 user prompt
    """
    system_parts = []
    history_parts = []
    last_user = ""

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            system_parts.append(content)
        elif role == "user":
            last_user = content
            history_parts.append(f"User: {content}")
        elif role == "assistant":
            history_parts.append(f"Assistant: {content}")

    # 如果有历史，拼入 prompt
    if len(history_parts) > 2:
        context = "\n".join(history_parts[:-1])  # 不含最后一条 user
        prompt = f"Previous conversation:\n{context}\n\nUser: {last_user}"
    else:
        prompt = last_user

    system_prompt = "\n".join(system_parts)

    payload = {
        "model": settings.wavespeed_llm_model,
        "prompt": prompt,
        "system_prompt": system_prompt,
        "enable_sync_mode": True,
        "priority": "latency",
        **{k: v for k, v in kwargs.items() if k in ("temperature", "max_tokens")},
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(LLM_ENDPOINT, headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") == 200:
        outputs = data.get("data", {}).get("outputs", [])
        return outputs[0] if outputs else ""
    raise RuntimeError(f"WaveSpeed API error: {data.get('message')}")


async def chat_stream(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncGenerator[str, None]:
    """
    WaveSpeed LLM 流式输出
    WaveSpeed stream:true 实际是任务提交模式，不支持真正的 SSE token 流。
    改为 enable_sync_mode=true 获取完整结果，然后逐字 yield 模拟流式效果。
    """
    system_prompt = ""
    user_prompt = ""
    history_parts = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            system_prompt = content
        elif role == "user":
            history_parts.append(f"User: {content}")
            user_prompt = content
        elif role == "assistant":
            history_parts.append(f"Assistant: {content}")

    if len(history_parts) > 1:
        context = "\n".join(history_parts[:-1])
        final_prompt = f"Previous conversation:\n{context}\n\nUser: {user_prompt}"
    else:
        final_prompt = user_prompt

    payload = {
        "model": settings.wavespeed_llm_model,
        "prompt": final_prompt,
        "system_prompt": system_prompt,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "enable_sync_mode": True,
        "priority": "latency",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(LLM_ENDPOINT, headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") == 200:
        text = (data.get("data", {}).get("outputs") or [""])[0]
        # 按单词分块 yield，模拟流式打字效果
        import asyncio as _asyncio
        words = text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            if i % 5 == 0:
                await _asyncio.sleep(0)  # 让出事件循环，保持响应性
    else:
        raise RuntimeError(f"WaveSpeed API error: {data.get('message', 'Unknown error')}")


# ─────────────────────────────────────────────
# 业务层封装（供各 Agent 调用）
# ─────────────────────────────────────────────

import re as _re


def _extract_json(text: str) -> dict:
    """
    BUG-07 fix: 健壮的 JSON 提取
    1. 去除 markdown ```json ... ``` 包裹
    2. 先尝试直接 json.loads
    3. fallback 到非贪婪正则匹配第一个完整 JSON 对象
    """
    # 去除 markdown 代码块
    text = _re.sub(r'```(?:json)?\s*', '', text).strip()
    text = text.rstrip('`').strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 非贪婪匹配第一个 {...} 块
    match = _re.search(r'\{.*?\}', text, _re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


async def analyze_jd_resume(jd_text: str, resume_json: dict) -> dict:
    """JD 与简历匹配分析（Job Agent）"""
    import re

    prompt = f"""You are an expert career consultant. Analyze the match between this job description and candidate profile.

JOB DESCRIPTION:
{jd_text}

CANDIDATE PROFILE:
{json.dumps(resume_json, indent=2)}

Return a JSON object with:
{{
  "score": <0-100 integer match score>,
  "recommendation": <"apply" or "skip">,
  "top_reasons": [<3 short reason strings>],
  "cover_letter": "<personalized cover letter, 200 words>",
  "missing_skills": [<skill gap strings>]
}}

Only recommend "apply" if score >= 65. Return ONLY valid JSON, no extra text."""

    result = await chat_complete(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    # BUG-07 fix: 使用健壮的 JSON 提取函数
    parsed = _extract_json(result)
    if parsed:
        return parsed
    return {"score": 0, "recommendation": "skip", "top_reasons": [], "cover_letter": "", "missing_skills": []}


async def summarize_announcement(html_content: str, course_name: str) -> str:
    """总结 Canvas 公告（Canvas Agent）"""
    # 去除 HTML 标签
    import re
    clean = re.sub(r'<[^>]+>', ' ', html_content)
    clean = re.sub(r'\s+', ' ', clean).strip()[:2000]

    prompt = f"""Summarize this Canvas course announcement from "{course_name}" in 2-3 concise bullet points. Highlight any action items or deadlines.

Content: {clean}

Format:
• [key point]
• [key point]
• Action: [if any action required]"""

    return await chat_complete(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )


async def parse_resume(resume_text: str) -> dict:
    """解析简历文本为结构化 JSON（Job Agent）"""
    import re

    prompt = f"""Extract structured information from this resume. Return ONLY valid JSON, no explanation.

Resume text:
{resume_text[:4000]}

JSON format:
{{
  "name": "",
  "email": "",
  "phone": "",
  "linkedin": "",
  "summary": "",
  "education": [{{"degree": "", "school": "", "year": "", "gpa": ""}}],
  "experience": [{{"title": "", "company": "", "duration": "", "highlights": []}}],
  "skills": [],
  "languages": [],
  "projects": [{{"name": "", "description": "", "tech": []}}]
}}"""

    result = await chat_complete(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    # BUG-07 fix: 使用健壮的 JSON 提取函数
    return _extract_json(result)


async def analyze_image_with_prompt(image_url: str, prompt: str, system_prompt: str = "") -> str:
    """
    WaveSpeed Vision API 调用
    端点: POST /wavespeed-ai/any-llm/vision
    支持传入图片 URL，返回文本分析结果（同步模式）
    """
    payload = {
        "model": settings.wavespeed_llm_model,
        "prompt": prompt,
        "system_prompt": system_prompt,
        "images": [image_url],
        "enable_sync_mode": True,
        "priority": "latency",
        "max_tokens": 4096,
        "temperature": 0.1,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(VISION_ENDPOINT, headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") == 200:
        outputs = data.get("data", {}).get("outputs", [])
        return outputs[0] if outputs else ""
    raise RuntimeError(f"WaveSpeed Vision API error: {data.get('message', 'Unknown error')}")


async def extract_syllabus_events(image_url: str) -> list[dict]:
    """
    Syllabus Agent 专用：从课程大纲图片提取所有 deadline 和考试日期
    返回标准化的事件 JSON 数组
    """
    from datetime import datetime
    current_year = datetime.now().year

    system_prompt = "You are an academic calendar extraction assistant. Extract ALL deadlines, exam dates, and important project milestones from course syllabus images."

    prompt = f"""Please carefully read this course syllabus image.
Extract ALL assignment deadlines, exam dates, quiz dates, and important project milestones.

Current year is {current_year}. Use Singapore timezone (UTC+8).

You MUST output ONLY a valid JSON array. No explanations, no markdown, no extra text.

JSON format:
[
  {{
    "event_name": "Midterm Exam",
    "start_time": "{current_year}-03-25T14:00:00+08:00",
    "end_time": "{current_year}-03-25T16:00:00+08:00",
    "description": "Closed book exam covering chapters 1-5",
    "event_type": "exam"
  }},
  {{
    "event_name": "Assignment 1 Due",
    "start_time": "{current_year}-02-15T23:59:00+08:00",
    "end_time": "{current_year}-02-15T23:59:00+08:00",
    "description": "Submit via Canvas",
    "event_type": "deadline"
  }}
]

event_type must be one of: "exam", "deadline", "quiz", "project", "other"
If time is not specified, use 23:59:00 for deadlines and 09:00:00 for exams.
If only month/day is given (no year), use {current_year}.
Output ONLY the JSON array."""

    result = await analyze_image_with_prompt(image_url, prompt, system_prompt)

    # 提取 JSON 数组
    result = result.strip()
    result = _re.sub(r'```(?:json)?\s*', '', result).strip().rstrip('`').strip()

    try:
        events = json.loads(result)
        if isinstance(events, list):
            return events
    except json.JSONDecodeError:
        # 尝试找到 [...] 块
        match = _re.search(r'\[.*\]', result, _re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return []
