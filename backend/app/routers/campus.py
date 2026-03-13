# -*- coding: utf-8 -*-
"""
Campus Route Planning Agent - API Router
POST /api/campus/plan  -> SSE stream of planning steps + final result
GET  /api/campus/locations -> all NUS POI locations
"""
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.agents.campus_agent.skills import NUS_LOCATIONS
from app.agents.campus_agent.planner import plan_itinerary

router = APIRouter(prefix="/api/campus", tags=["Campus Agent"])


class PlanRequest(BaseModel):
    request: str
    start_time: Optional[str] = "09:00"


@router.get("/locations")
async def get_locations():
    """Return all NUS POI locations for map rendering."""
    return {"locations": NUS_LOCATIONS}


@router.post("/plan")
async def plan_route(req: PlanRequest):
    """
    Stream the campus route planning process as SSE.
    Each chunk is: data: {...json...}\\n\\n
    Final chunk type='result' contains: narrative, timeline, route
    """
    async def stream():
        try:
            async for chunk in plan_itinerary(req.request, req.start_time):
                yield chunk
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
