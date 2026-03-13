# -*- coding: utf-8 -*-
import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from app.agents.knowledge_agent.rag_service import answer_question, get_knowledge_stats, invalidate_bm25_cache
from app.agents.knowledge_agent.vectorstore.chroma_client import get_collection_count

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge QA"])


# ── Agent Intent 检测 ──────────────────────────────────────────

AGENT_INTENTS = {
    "canvas_sync": [
        "canvas", "sync my", "my assignments", "my courses", "my schedule",
        "assignment", "同步", "我的作业", "我的课",
    ],
    "download_schedule": [
        "download ics", "download calendar", "export calendar", "local calendar",
        "add to calendar", "下载日历", "导出日历",
    ],
    "send_schedule_email": [
        "send email", "email reminder", "send me email", "send schedule",
        "发邮件", "邮件提醒", "email me",
    ],
    "job_search": [
        "find job", "search job", "apply job", "linkedin", "internship",
        "job agent", "找工作", "投简历", "apply for", "job opening",
        "software engineer", "data analyst", "full stack", "frontend", "backend",
    ],
    "upload_syllabus": [
        "syllabus", "course outline", "大纲", "课表", "exam date",
        "extract date", "upload course",
    ],
}


def detect_intent(question: str) -> str | None:
    q = question.lower()
    for intent, keywords in AGENT_INTENTS.items():
        if any(kw in q for kw in keywords):
            return intent
    return None


async def handle_agent_intent(intent: str, question: str) -> str:
    """
    根据 intent 调用对应 Agent，返回结果文本
    """
    if intent == "canvas_sync":
        return (
            "📚 **Canvas Sync Agent**\n\n"
            "To sync your Canvas data, go to the **Schedule Agent** page and enter your Canvas access token.\n\n"
            "**Steps:**\n"
            "1. Navigate to **Schedule Agent** in the sidebar\n"
            "2. Paste your Canvas Access Token (Canvas → Account → Settings → Approved Integrations → New Token)\n"
            "3. Click **Sync** — the agent will fetch all assignments and announcements and summarize them with WaveSpeed AI\n\n"
            "After syncing, you can download the `.ics` file to import into your local calendar, or send it to your email."
        )

    elif intent == "download_schedule":
        # 直接检查是否有事件
        try:
            from app.agents.schedule_agent.ics_builder import build_ics
            from app.routers.schedule import _get_all_events
            events = await _get_all_events()
            if events:
                return (
                    f"📅 **Schedule Export Ready**\n\n"
                    f"I found **{len(events)} events** in your schedule (Canvas assignments + Syllabus events).\n\n"
                    f"Go to the **Schedule Agent** page and click **Download .ics** to export all events to your local calendar.\n\n"
                    f"The `.ics` file includes:\n"
                    f"- ⏰ 24-hour email reminders\n"
                    f"- 🔔 1-hour popup reminders\n"
                    f"- 🎨 Color-coded by event type (Exam=Red, Deadline=Orange, etc.)"
                )
            else:
                return (
                    "📅 **No events yet**\n\n"
                    "Sync your Canvas or upload a syllabus first, then I can export your schedule to a `.ics` calendar file."
                )
        except Exception as e:
            return f"Could not check schedule: {str(e)}"

    elif intent == "send_schedule_email":
        try:
            from app.routers.schedule import _get_all_events
            events = await _get_all_events()
            if events:
                return (
                    f"📧 **Email Reminder**\n\n"
                    f"I can send your schedule ({len(events)} events) to your email with a `.ics` attachment.\n\n"
                    f"Go to the **Schedule Agent** page, enter your email address in the **Send Email** section, and click Send.\n\n"
                    f"The email includes:\n"
                    f"- Full event table with countdown timers\n"
                    f"- `.ics` attachment (importable into any calendar app)\n"
                    f"- Embedded reminders (24h + 1h before each event)"
                )
            else:
                return "No events to email yet. Sync Canvas or upload a syllabus first."
        except Exception:
            return "Go to the **Schedule Agent** page to send schedule emails."

    elif intent == "job_search":
        return (
            "💼 **Job Application Agent**\n\n"
            "The Job Agent can automatically search LinkedIn and apply to matching positions.\n\n"
            "**How it works:**\n"
            "1. Go to **Job Agent** in the sidebar\n"
            "2. Upload your PDF resume\n"
            "3. Enter job keywords (e.g. *Software Engineer Intern*)\n"
            "4. Provide your LinkedIn `li_at` cookie (for Google login users)\n"
            "5. Click **Launch Job Agent**\n\n"
            "The agent will:\n"
            "- 🔍 Search LinkedIn Easy Apply jobs\n"
            "- 🤖 Score each job with WaveSpeed AI (match vs your resume)\n"
            "- 📤 Auto-apply to jobs scoring above your threshold"
        )

    elif intent == "upload_syllabus":
        return (
            "📄 **Syllabus Vision Agent**\n\n"
            "Go to the **Schedule Agent** page and use the **Syllabus → Events** section.\n\n"
            "**Supported formats:** JPG, PNG, WEBP, PDF\n\n"
            "WaveSpeed Vision AI will extract all exam dates, deadlines, and project milestones from your syllabus photo or PDF, then add them to your schedule timeline."
        )

    return None


# ── WebSocket Chat ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    chat_history: list = []


@router.get("/stats")
async def knowledge_stats():
    return await get_knowledge_stats()


@router.post("/ingest")
async def trigger_ingestion():
    from app.agents.knowledge_agent.ingestion.nus_spider import run_ingestion

    async def _ingest_and_invalidate():
        await run_ingestion()
        invalidate_bm25_cache()

    asyncio.create_task(_ingest_and_invalidate())
    return {"status": "ingestion started in background"}


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket 流式问答
    支持：
    1. 普通 NUS 知识问答（RAG + WaveSpeed AI）
    2. Agent intent 检测 → 直接调用/引导对应 Agent
    """
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            question = payload.get("question", "")
            chat_history = payload.get("chat_history", [])

            if not question.strip():
                continue

            # 检测是否触发 Agent 能力
            intent = detect_intent(question)
            if intent:
                try:
                    agent_response = await handle_agent_intent(intent, question)
                    if agent_response:
                        await websocket.send_text(json.dumps({"type": "token", "content": agent_response}))
                        await websocket.send_text(json.dumps({"type": "done"}))
                        continue
                except Exception as e:
                    # agent 失败则 fallback 到普通 RAG
                    pass

            # 普通 RAG 问答 — 收集完整回答后一次性发送，避免 WS 消息拆包问题
            try:
                full_answer = ""
                async for token in answer_question(question, chat_history):
                    full_answer += token
                await websocket.send_text(json.dumps({"type": "token", "content": full_answer}))
                await websocket.send_text(json.dumps({"type": "done"}))
            except Exception as e:
                await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))
        except Exception:
            pass


@router.post("/chat")
async def http_chat(req: ChatRequest):
    """HTTP 版问答（非流式，用于测试）"""
    full_answer = ""
    intent = detect_intent(req.question)
    if intent:
        result = await handle_agent_intent(intent, req.question)
        if result:
            return {"answer": result, "question": req.question, "agent_used": intent}

    async for token in answer_question(req.question, req.chat_history):
        full_answer += token
    return {"answer": full_answer, "question": req.question}
