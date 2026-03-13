---
name: nus-canvas-sync
description: Syncs NUS Canvas LMS data (courses, assignments, announcements) to Google Calendar
version: 1.0.0
user-invocable: true
agent: canvas_agent
powered_by: WaveSpeed AI
---

# NUS Canvas Sync Skill

## Description
This skill connects to the NUS Canvas LMS platform and:
1. Fetches all active courses for the current semester
2. Retrieves upcoming assignment deadlines
3. Collects teacher announcements
4. Summarizes announcements using WaveSpeed AI
5. Pushes assignment deadlines to Google Calendar with reminders

## Trigger Phrases
- "sync my Canvas"
- "update my schedule"
- "check my assignments"
- "what's due this week"
- "sync Canvas to calendar"

## Instructions
1. Request the user's Canvas Personal Access Token if not stored
2. Call the canvas_fetcher tool to fetch all course data from nus.instructure.com
3. For each announcement, use WaveSpeed AI to generate a 2-3 bullet summary
4. Save all data to the local database
5. If Google Calendar is authorized, push assignment events with 24-hour reminders
6. Return a summary: N courses, M assignments, K announcements synced

## Tools Used
- canvas_fetcher: Canvas API client (canvasapi library)
- wavespeed_service: WaveSpeed AI for announcement summarization
- gcal_pusher: Google Calendar API for event creation

## Output Format
```
✅ Canvas Sync Complete
- 5 courses synced
- 12 upcoming assignments pushed to calendar
- 3 new announcements summarized
```
