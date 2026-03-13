# -*- coding: utf-8 -*-
"""
OpenClaw Multi-Agent Orchestrator
统一管理四个 Agent 的协作与调度
OpenClaw 作为 Agent 框架的核心入口
"""
import asyncio
from typing import Dict, Any, Literal
from app.config import get_settings

settings = get_settings()

# Agent 注册表
AGENTS = {
    "canvas_agent": {
        "name": "NUS Canvas Sync Agent",
        "description": "Fetches Canvas LMS data and syncs to calendar",
        "module": "app.agents.canvas_agent.agent",
        "function": "run_canvas_sync",
    },
    "job_agent": {
        "name": "Job Application Agent",
        "description": "Analyzes JD vs resume and submits job applications",
        "module": "app.agents.job_agent.agent",
        "function": "run_job_analysis",
    },
    "knowledge_agent": {
        "name": "NUS Knowledge QA Agent",
        "description": "Answers NUS campus questions using RAG",
        "module": "app.agents.knowledge_agent.rag_service",
        "function": "answer_question",
    },
    "syllabus_agent": {
        "name": "Syllabus to Calendar Agent",
        "description": "Extracts deadlines and exam dates from syllabus images via WaveSpeed Vision and syncs to Google Calendar",
        "module": "app.agents.syllabus_agent.agent",
        "function": "run_syllabus_extract",
    },
}


class OpenClawOrchestrator:
    """
    OpenClaw 多 Agent 协作编排器
    负责：
    - Agent 路由（根据意图选择合适的 Agent）
    - 任务状态跟踪
    - 并发协调
    """

    def __init__(self):
        self.running_tasks: Dict[str, asyncio.Task] = {}

    async def route_and_run(
        self,
        agent_name: Literal["canvas_agent", "job_agent", "knowledge_agent", "syllabus_agent"],
        **kwargs
    ) -> Dict[str, Any]:
        """路由到指定 Agent 并执行"""
        if agent_name not in AGENTS:
            return {"error": f"Unknown agent: {agent_name}"}

        agent_info = AGENTS[agent_name]
        print(f"[OpenClaw] Dispatching to {agent_info['name']}...")

        # 动态导入 Agent 模块
        import importlib
        module = importlib.import_module(agent_info["module"])
        func = getattr(module, agent_info["function"])

        result = await func(**kwargs)
        return {"agent": agent_name, "result": result}

    async def run_parallel(self, tasks: list[Dict]) -> list[Dict]:
        """
        并发运行多个 Agent 任务
        tasks: [{"agent": str, "kwargs": dict}]
        """
        coroutines = [
            self.route_and_run(t["agent"], **t.get("kwargs", {}))
            for t in tasks
        ]
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        return [
            r if not isinstance(r, Exception) else {"error": str(r)}
            for r in results
        ]

    def get_registered_agents(self) -> list[Dict]:
        return [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in AGENTS.items()
        ]


# 单例 Orchestrator
orchestrator = OpenClawOrchestrator()
