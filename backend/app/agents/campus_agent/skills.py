# -*- coding: utf-8 -*-
"""
Campus Route Planning Agent - Skills
Three callable skills:
1. get_calendar_events - read schedule busy slots
2. search_knowledge_base - RAG for campus info
3. calculate_route_matrix - walking time between NUS locations
"""
import json
from typing import List, Dict, Optional
from datetime import datetime, date

# ── NUS Location Database ──────────────────────────────────────────────────
NUS_LOCATIONS = {
    "start": {
        "name": "Blk 365 Clementi Ave 2",
        "lat": 1.3143,
        "lng": 103.7653,
        "address": "365 Clementi Ave 2, Singapore 120365",
        "type": "origin",
    },
    "utown": {
        "name": "UTown Residential College",
        "lat": 1.3044,
        "lng": 103.7739,
        "address": "University Town, NUS, 138599",
        "type": "checkin_office",
        "hours": "Mon-Fri 9:00-17:00, Sat 9:00-13:00",
        "service": "UTown RC Room Key Collection",
        "duration_min": 20,
        "notes": "Bring IC, acceptance letter, and payment receipt"
    },
    "ea": {
        "name": "EA (Engineering Annex)",
        "lat": 1.2998,
        "lng": 103.7720,
        "address": "9 Engineering Drive 1, NUS, 117575",
        "type": "checkin_office",
        "hours": "Mon-Fri 8:30-17:30",
        "service": "Student Services & Matriculation Card",
        "duration_min": 15,
        "notes": "Bring passport photo for matric card"
    },
    "yih": {
        "name": "YIH (Yusof Ishak House)",
        "lat": 1.2977,
        "lng": 103.7735,
        "address": "20 Lower Kent Ridge Rd, NUS, 119080",
        "type": "checkin_office",
        "hours": "Mon-Fri 9:00-18:00",
        "service": "Student Welfare & NUS Card Top-up",
        "duration_min": 10,
        "notes": "Student card top-up and welfare registration"
    },
    "kent_ridge_hall": {
        "name": "Kent Ridge Hall",
        "lat": 1.2941,
        "lng": 103.7801,
        "address": "Kent Ridge Crescent, NUS, 119276",
        "type": "destination",
        "hours": "24/7",
        "service": "Dormitory Check-in Counter",
        "duration_min": 30,
        "notes": "Final check-in, room assignment, key collection"
    },
}

# ── Walking time matrix (minutes) ─────────────────────────────────────────
# Realistic NUS campus walking + bus times
ROUTE_MATRIX = {
    ("start", "utown"): {"walk_min": 35, "bus_min": 20, "mode": "bus", "bus_line": "95/96"},
    ("start", "ea"): {"walk_min": 45, "bus_min": 25, "mode": "bus", "bus_line": "95"},
    ("start", "yih"): {"walk_min": 50, "bus_min": 28, "mode": "bus", "bus_line": "95"},
    ("start", "kent_ridge_hall"): {"walk_min": 55, "bus_min": 30, "mode": "bus", "bus_line": "95"},
    ("utown", "ea"): {"walk_min": 20, "bus_min": 10, "mode": "internal_bus", "bus_line": "D2"},
    ("utown", "yih"): {"walk_min": 25, "bus_min": 12, "mode": "internal_bus", "bus_line": "D2"},
    ("utown", "kent_ridge_hall"): {"walk_min": 30, "bus_min": 15, "mode": "internal_bus", "bus_line": "D2"},
    ("ea", "yih"): {"walk_min": 8, "bus_min": 5, "mode": "walk", "bus_line": ""},
    ("ea", "kent_ridge_hall"): {"walk_min": 15, "bus_min": 8, "mode": "internal_bus", "bus_line": "D1"},
    ("yih", "kent_ridge_hall"): {"walk_min": 12, "bus_min": 7, "mode": "internal_bus", "bus_line": "D1"},
}

# ── Mock class schedule (conflicts) ─────────────────────────────────────
MOCK_SCHEDULE = [
    {
        "title": "CS3219 Software Engineering",
        "start": "14:00",
        "end": "16:00",
        "location": "COM3-01-10",
        "type": "lecture"
    },
]

# ── NUS Dormitory Check-in Knowledge ─────────────────────────────────────
CHECKIN_KNOWLEDGE = """
## NUS Dormitory Check-in Procedure

### Step 1: UTown Residential College Registration
- **Location**: UTown RC Management Office, University Town
- **Hours**: Mon-Fri 9:00-17:00, Sat 9:00-13:00
- **What to bring**: NUS Student ID / IC, acceptance letter, payment receipt
- **Duration**: ~20 minutes
- **Purpose**: Register your residency and collect welcome pack

### Step 2: EA (Engineering Annex) - Matriculation Card
- **Location**: Student Service Centre, Engineering Annex Level 1
- **Hours**: Mon-Fri 8:30-17:30
- **What to bring**: Passport-sized photo (2 copies)
- **Duration**: ~15 minutes
- **Purpose**: Collect official NUS Matriculation Card (required for all campus access)

### Step 3: YIH (Yusof Ishak House) - Student Welfare
- **Location**: YIH Ground Floor, Student Union offices
- **Hours**: Mon-Fri 9:00-18:00
- **Duration**: ~10 minutes
- **Purpose**: Student welfare registration, NUS card top-up, CCA sign-up info

### Step 4: Kent Ridge Hall - Final Check-in
- **Location**: Kent Ridge Hall main counter
- **Hours**: 24/7 (counter: 8:00-22:00)
- **What to bring**: Completed UTown RC receipt + Matric Card
- **Duration**: ~30 minutes
- **Purpose**: Room key collection, dormitory orientation, rules briefing

### Important Notes
- Complete steps 1-3 before proceeding to Kent Ridge Hall
- Total estimated time: 3-4 hours
- Best to start before 10:00 AM to avoid queues
- UTown and KR Hall are far apart — use NUS internal shuttle
"""


def get_route_time(from_loc: str, to_loc: str) -> Dict:
    """Get travel time between two NUS locations."""
    key = (from_loc, to_loc)
    rev_key = (to_loc, from_loc)
    data = ROUTE_MATRIX.get(key) or ROUTE_MATRIX.get(rev_key)
    if not data:
        return {"walk_min": 20, "bus_min": 10, "mode": "walk", "bus_line": ""}
    return data


async def skill_get_calendar_events(target_date: Optional[str] = None) -> Dict:
    """
    Skill: Read calendar events for a given date.
    Returns busy time slots that may conflict with route planning.
    """
    today_str = target_date or date.today().strftime("%Y-%m-%d")
    return {
        "date": today_str,
        "events": MOCK_SCHEDULE,
        "busy_slots": [{"start": e["start"], "end": e["end"], "title": e["title"]} for e in MOCK_SCHEDULE],
        "source": "local_schedule"
    }


async def skill_search_knowledge_base(query: str) -> Dict:
    """
    Skill: Search RAG knowledge base for campus information.
    Falls back to built-in dormitory checkin knowledge.
    """
    query_lower = query.lower()
    relevant_sections = []

    # Extract relevant sections from built-in knowledge
    sections = CHECKIN_KNOWLEDGE.split("###")
    for section in sections:
        keywords = ["utown", "ea", "yih", "kent", "matric", "check-in", "checkin",
                    "dorm", "hall", "registration", "key", "card"]
        if any(kw in section.lower() for kw in keywords) or any(kw in query_lower for kw in keywords):
            relevant_sections.append(section.strip())

    # Try RAG if available
    rag_results = []
    try:
        from app.agents.knowledge_agent.vectorstore.chroma_client import query_similar
        rag_docs = query_similar(query, n_results=3)
        for doc in rag_docs:
            if doc.get("distance", 1.0) < 0.7:
                rag_results.append(doc.get("text", ""))
    except Exception:
        pass

    return {
        "query": query,
        "knowledge": "\n\n".join(relevant_sections[:3]) if relevant_sections else CHECKIN_KNOWLEDGE,
        "rag_results": rag_results[:2],
        "source": "rag+builtin"
    }


async def skill_calculate_route_matrix(locations: List[str]) -> Dict:
    """
    Skill: Calculate optimal route and time matrix between NUS locations.
    """
    route_segments = []
    total_travel_min = 0
    total_service_min = 0

    for i in range(len(locations) - 1):
        from_loc = locations[i]
        to_loc = locations[i + 1]
        travel = get_route_time(from_loc, to_loc)

        from_info = NUS_LOCATIONS.get(from_loc, {})
        to_info = NUS_LOCATIONS.get(to_loc, {})

        travel_min = travel["bus_min"] if travel["mode"] != "walk" else travel["walk_min"]
        service_min = to_info.get("duration_min", 0)

        route_segments.append({
            "from": from_loc,
            "from_name": from_info.get("name", from_loc),
            "to": to_loc,
            "to_name": to_info.get("name", to_loc),
            "travel_min": travel_min,
            "mode": travel["mode"],
            "bus_line": travel.get("bus_line", ""),
            "service_min": service_min,
            "service": to_info.get("service", ""),
            "hours": to_info.get("hours", ""),
            "notes": to_info.get("notes", ""),
        })

        total_travel_min += travel_min
        total_service_min += service_min

    return {
        "locations": locations,
        "segments": route_segments,
        "total_travel_min": total_travel_min,
        "total_service_min": total_service_min,
        "total_min": total_travel_min + total_service_min,
        "location_details": {k: NUS_LOCATIONS[k] for k in locations if k in NUS_LOCATIONS},
    }
