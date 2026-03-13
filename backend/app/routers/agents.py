# -*- coding: utf-8 -*-
"""
OpenClaw Agent 管理路由
查看注册的 Agent、手动触发等
"""
from fastapi import APIRouter
from app.agents.orchestrator import orchestrator

router = APIRouter(prefix="/api/agents", tags=["OpenClaw Agents"])


@router.get("/")
async def list_agents():
    """列出所有注册的 OpenClaw Agent"""
    return {
        "framework": "OpenClaw",
        "agents": orchestrator.get_registered_agents(),
    }


@router.post("/run/{agent_name}")
async def run_agent(agent_name: str, kwargs: dict = {}):
    """手动触发指定 Agent"""
    result = await orchestrator.route_and_run(agent_name, **kwargs)
    return result
