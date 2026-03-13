# -*- coding: utf-8 -*-
"""
NUS Campus Intelligent Assistant
Backend Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.routers import canvas, jobs, knowledge, agents, syllabus, schedule, userprefs, campus


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    await init_db()
    print("[App] Database initialized")
    print("[App] NUS Campus Intelligent Assistant started")
    print("[App] Powered by: OpenClaw + WaveSpeed AI")
    yield
    print("[App] Shutting down...")


app = FastAPI(
    title="NUS Campus Intelligent Assistant",
    description="Multi-Agent Campus Assistant powered by OpenClaw & WaveSpeed AI",
    version="1.0.0",
    lifespan=lifespan,
)

import os

# CORS — allow localhost for dev, plus any Railway/custom domain via env var
_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        *_extra_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(canvas.router)
app.include_router(jobs.router)
app.include_router(knowledge.router)
app.include_router(agents.router)
app.include_router(syllabus.router)
app.include_router(schedule.router)
app.include_router(userprefs.router)
app.include_router(campus.router)


@app.get("/")
async def root():
    return {
        "name": "NUS Campus Intelligent Assistant",
        "version": "1.0.0",
        "powered_by": ["OpenClaw (Multi-Agent Framework)", "WaveSpeed AI (LLM + Inference)"],
        "agents": ["canvas_agent", "job_agent", "knowledge_agent", "syllabus_agent"],
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
