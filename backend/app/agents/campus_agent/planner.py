# -*- coding: utf-8 -*-
"""
Campus Route Planning Agent - Core Planner
Takes a natural language request and produces a structured itinerary.
"""
import json
import asyncio
from typing import AsyncGenerator, List, Dict, Optional
from datetime import datetime, date, timedelta

from app.agents.campus_agent.skills import (
    skill_get_calendar_events,
    skill_search_knowledge_base,
    skill_calculate_route_matrix,
    NUS_LOCATIONS,
    MOCK_SCHEDULE,
)
from app.services.wavespeed_service import chat_stream


async def _call_llm_sync(messages: List[Dict]) -> str:
    """Call WaveSpeed AI and return full text."""
    full = ""
    async for token in chat_stream(messages):
        full += token
    return full


def _detect_locations_from_request(request: str) -> List[str]:
    """Parse requested locations from natural language."""
    req_lower = request.lower()

    location_map = {
        "utown": ["utown", "university town", "utc", "rc"],
        "ea": ["ea", "engineering annex", "engineering block"],
        "yih": ["yih", "yusof ishak"],
        "kent_ridge_hall": ["kent ridge hall", "krh", "kent ridge"],
        "start": ["blk365", "blk 365", "clementi", "home", "start"],
    }

    found = []
    for loc_key, keywords in location_map.items():
        if any(kw in req_lower for kw in keywords):
            found.append(loc_key)

    # Default dormitory check-in route
    if not found or "start" not in found:
        return ["start", "utown", "ea", "yih", "kent_ridge_hall"]

    # Ensure start is first
    if "start" in found:
        found.remove("start")
        found = ["start"] + found

    # Ensure kent_ridge_hall is last if present
    if "kent_ridge_hall" in found and found[-1] != "kent_ridge_hall":
        found.remove("kent_ridge_hall")
        found.append("kent_ridge_hall")

    return found


def _build_timeline(
    route_data: Dict,
    calendar_data: Dict,
    start_time: str = "09:00",
    start_date: Optional[str] = None,
) -> List[Dict]:
    """
    Build timeline cards from route data, inserting calendar events and detecting conflicts.
    """
    target_date = start_date or date.today().strftime("%Y-%m-%d")
    busy_slots = calendar_data.get("busy_slots", [])

    # Convert start time to minutes
    sh, sm = map(int, start_time.split(":"))
    current_min = sh * 60 + sm

    timeline = []

    def min_to_time(m: int) -> str:
        h = (m // 60) % 24
        mi = m % 60
        return f"{h:02d}:{mi:02d}"

    # First card: departure
    timeline.append({
        "id": "depart",
        "type": "depart",
        "time": min_to_time(current_min),
        "title": "Departure",
        "location": NUS_LOCATIONS["start"]["name"],
        "location_key": "start",
        "description": "Start from Blk 365 Clementi Ave 2. Take bus 95 or 96 towards NUS.",
        "duration_min": 0,
        "lat": NUS_LOCATIONS["start"]["lat"],
        "lng": NUS_LOCATIONS["start"]["lng"],
        "conflict": False,
    })

    for segment in route_data.get("segments", []):
        travel_min = segment["travel_min"]
        service_min = segment["service_min"]
        to_key = segment["to"]
        to_info = NUS_LOCATIONS.get(to_key, {})

        # Travel card
        arrive_min = current_min + travel_min

        # Check for class conflicts during travel
        travel_conflict = False
        for busy in busy_slots:
            bh, bm = map(int, busy["start"].split(":"))
            eh, em = map(int, busy["end"].split(":"))
            busy_start_min = bh * 60 + bm
            busy_end_min = eh * 60 + em
            if current_min < busy_end_min and arrive_min > busy_start_min:
                travel_conflict = True
                # Insert class card before conflict
                timeline.append({
                    "id": f"class_{busy['title'].replace(' ', '_')}",
                    "type": "class",
                    "time": busy["start"],
                    "end_time": busy["end"],
                    "title": busy["title"],
                    "location_key": None,
                    "location": "Campus Classroom",
                    "description": f"Scheduled class — must attend. Resume route after {busy['end']}.",
                    "duration_min": busy_end_min - busy_start_min,
                    "lat": 1.2980,
                    "lng": 103.7738,
                    "conflict": False,
                })
                # Resume after class
                if arrive_min < busy_end_min:
                    arrive_min = busy_end_min + 5  # 5min buffer

        # Transit card
        timeline.append({
            "id": f"transit_{segment['from']}_{to_key}",
            "type": "transit",
            "time": min_to_time(current_min),
            "end_time": min_to_time(arrive_min),
            "title": f"Travel to {segment['to_name']}",
            "location_key": to_key,
            "location": segment["from_name"],
            "description": (
                f"Take {segment['bus_line']} bus ({segment['mode']}). "
                f"~{travel_min} min to {segment['to_name']}."
            ) if segment["bus_line"] else f"Walk ~{travel_min} min to {segment['to_name']}.",
            "duration_min": travel_min,
            "lat": to_info.get("lat", 1.3),
            "lng": to_info.get("lng", 103.77),
            "conflict": travel_conflict,
        })

        current_min = arrive_min

        if service_min > 0:
            # Check office hours
            service_start_time = min_to_time(current_min)
            hours_str = to_info.get("hours", "")
            service_end_min = current_min + service_min

            # Check if service conflicts with class
            service_conflict = False
            for busy in busy_slots:
                bh, bm = map(int, busy["start"].split(":"))
                eh, em = map(int, busy["end"].split(":"))
                busy_start_min = bh * 60 + bm
                busy_end_min = eh * 60 + em
                if current_min < busy_end_min and service_end_min > busy_start_min:
                    service_conflict = True

            timeline.append({
                "id": f"service_{to_key}",
                "type": "service",
                "time": service_start_time,
                "end_time": min_to_time(service_end_min),
                "title": segment["service"],
                "location_key": to_key,
                "location": segment["to_name"],
                "description": to_info.get("notes", "") + (f" | Office hours: {hours_str}" if hours_str else ""),
                "duration_min": service_min,
                "lat": to_info.get("lat", 1.3),
                "lng": to_info.get("lng", 103.77),
                "conflict": service_conflict,
                "hours": hours_str,
            })

            current_min = service_end_min

    # Final arrival
    timeline.append({
        "id": "arrive",
        "type": "arrive",
        "time": min_to_time(current_min),
        "title": "All Done!",
        "location": NUS_LOCATIONS.get("kent_ridge_hall", {}).get("name", "Destination"),
        "location_key": "kent_ridge_hall",
        "description": "Dormitory check-in complete. Welcome to NUS!",
        "duration_min": 0,
        "lat": NUS_LOCATIONS.get("kent_ridge_hall", {}).get("lat", 1.294),
        "lng": NUS_LOCATIONS.get("kent_ridge_hall", {}).get("lng", 103.780),
        "conflict": False,
    })

    return timeline


async def plan_itinerary(request: str, start_time: str = "09:00") -> AsyncGenerator[str, None]:
    """
    Main agent loop: plan itinerary from natural language request.
    Yields SSE JSON chunks.
    """
    import json

    def _sse(data: Dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    yield _sse({"type": "step", "message": "🤔 Analyzing your request..."})
    await asyncio.sleep(0.1)

    # Step 1: Parse locations
    locations = _detect_locations_from_request(request)
    yield _sse({"type": "step", "message": f"📍 Identified {len(locations)} stops: {' → '.join(locations)}"})

    # Step 2: Get calendar events
    yield _sse({"type": "step", "message": "📅 Checking your calendar for conflicts..."})
    calendar_data = await skill_get_calendar_events()
    busy_count = len(calendar_data.get("busy_slots", []))
    if busy_count > 0:
        titles = [b["title"] for b in calendar_data["busy_slots"]]
        yield _sse({"type": "step", "message": f"⚠️ Found {busy_count} class(es) today: {', '.join(titles)}"})
    else:
        yield _sse({"type": "step", "message": "✅ No class conflicts found"})

    # Step 3: Search knowledge base
    yield _sse({"type": "step", "message": "📚 Looking up dormitory check-in procedures..."})
    knowledge = await skill_search_knowledge_base("NUS dormitory check-in procedure UTown EA YIH Kent Ridge Hall")

    # Step 4: Calculate route
    yield _sse({"type": "step", "message": "🗺️ Calculating optimal route..."})
    route_data = await skill_calculate_route_matrix(locations)

    total_min = route_data["total_min"]
    yield _sse({
        "type": "step",
        "message": f"✅ Route calculated: {route_data['total_travel_min']}min travel + {route_data['total_service_min']}min services = {total_min}min total"
    })

    # Step 5: Build timeline
    yield _sse({"type": "step", "message": "📋 Building your timeline..."})
    timeline = _build_timeline(route_data, calendar_data, start_time)

    # Step 6: LLM narrative
    yield _sse({"type": "step", "message": "✍️ Generating AI summary..."})

    knowledge_text = knowledge.get("knowledge", "")[:800]
    route_summary = json.dumps(route_data["segments"], ensure_ascii=False)[:600]
    conflict_info = ""
    if busy_count > 0:
        conflict_info = f"\nNote: There is a class ({calendar_data['busy_slots'][0]['title']}) from {calendar_data['busy_slots'][0]['start']} to {calendar_data['busy_slots'][0]['end']}. The route has been adjusted around it."

    messages = [
        {"role": "system", "content": (
            "You are a helpful NUS campus assistant. "
            "Generate a friendly, concise route planning summary in 3-4 sentences. "
            "Mention the key stops, estimated total time, and any important reminders. "
            "Be encouraging and practical."
        )},
        {"role": "user", "content": (
            f"User request: {request}\n\n"
            f"Planned stops: {' → '.join(locations)}\n"
            f"Total time: {total_min} minutes\n"
            f"Route details: {route_summary}\n"
            f"Key procedures:\n{knowledge_text}\n"
            f"{conflict_info}\n\n"
            "Please write a friendly 3-4 sentence summary of this campus route plan."
        )}
    ]

    narrative = await _call_llm_sync(messages)

    # Step 7: Yield final result
    yield _sse({
        "type": "result",
        "narrative": narrative,
        "timeline": timeline,
        "route": {
            "locations": [
                {
                    "key": k,
                    "name": NUS_LOCATIONS[k]["name"],
                    "lat": NUS_LOCATIONS[k]["lat"],
                    "lng": NUS_LOCATIONS[k]["lng"],
                    "type": NUS_LOCATIONS[k].get("type", "stop"),
                }
                for k in locations if k in NUS_LOCATIONS
            ],
            "segments": route_data["segments"],
            "total_min": total_min,
        },
        "skills_used": ["get_calendar_events", "search_knowledge_base", "calculate_route_matrix"],
    })

    yield _sse({"type": "done"})
