---
name: nus-syllabus-calendar
description: Extracts deadlines and exam dates from a syllabus photo using WaveSpeed Vision AI and syncs to Google Calendar
version: 1.0.0
user-invocable: true
agent: syllabus_agent
powered_by: WaveSpeed AI Vision
---

# Syllabus to Calendar Skill

## Description
This skill automates the academic calendar setup process:
1. Accepts a photo/image of a paper or digital course syllabus
2. Uses WaveSpeed AI Vision to extract ALL deadlines, exam dates, quiz dates, and project milestones
3. Presents extracted events as a confirmation card for user review
4. On user confirmation, pushes all events to Google Calendar with appropriate reminders

## Trigger Phrases
- "Upload a syllabus photo"
- "Help me add these dues to my calendar"
- "Extract deadlines from this syllabus"
- "Scan my course schedule"
- "Add exam dates to Google Calendar"

## Thinking Process (displayed to user)
1. [Thinking: Analyzing syllabus image...]
2. [Action: Calling WaveSpeed Vision API...]
3. [Action: Extracted N events from image]
4. [Waiting: User confirmation on event card]
5. [Action: Pushing to Google Calendar via API]
6. [Done: Successfully synced N events]

## Tools Used
- wavespeed_vision: WaveSpeed AI Vision endpoint (/wavespeed-ai/any-llm/vision)
- gcal_pusher: Google Calendar API for event creation (reused from canvas_agent)
- SyllabusEvent DB: Stores extracted events with confirmation status

## Event Types & Calendar Colors
- exam → Red (colorId 11)
- deadline → Blue (colorId 4)
- quiz → Yellow (colorId 5)
- project → Green (colorId 2)
- other → Graphite (colorId 8)

## Output Format
Confirmation card showing:
- Event name
- Date & time
- Type badge (Exam / Deadline / Quiz / Project)
- Description
User clicks "Confirm & Sync All" to push to Google Calendar.
