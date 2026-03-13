# -*- coding: utf-8 -*-
"""
ICS 日历文件生成器
生成标准 .ics 文件，可直接导入 Windows 日历、Apple Calendar、Google Calendar 等所有主流日历
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from icalendar import Calendar, Event, Alarm, vText


# 事件类型 → 颜色标签（iCal COLOR 属性，部分客户端支持）
TYPE_COLORS = {
    "exam": "RED",
    "deadline": "ORANGE",
    "quiz": "YELLOW",
    "project": "GREEN",
    "assignment": "BLUE",
    "other": "GRAY",
}

TYPE_LABELS = {
    "exam": "📝 Exam",
    "deadline": "⏰ Deadline",
    "quiz": "✏️ Quiz",
    "project": "🚀 Project",
    "assignment": "📚 Assignment",
    "other": "📅 Event",
}


def build_ics(events: List[Dict]) -> bytes:
    """
    将事件列表生成 .ics 二进制内容

    每个 event dict 格式：
    {
        "title": str,
        "start": datetime,
        "end": datetime | None,
        "description": str,
        "event_type": str,   # exam/deadline/quiz/project/assignment/other
        "location": str | None,
        "url": str | None,
    }
    """
    cal = Calendar()
    cal.add("PRODID", "-//NUS Campus Assistant//OpenClaw//EN")
    cal.add("VERSION", "2.0")
    cal.add("CALSCALE", "GREGORIAN")
    cal.add("METHOD", "PUBLISH")
    cal.add("X-WR-CALNAME", "NUS Campus Schedule")
    cal.add("X-WR-TIMEZONE", "Asia/Singapore")

    for ev in events:
        vevent = Event()
        vevent.add("UID", str(uuid.uuid4()))

        label = TYPE_LABELS.get(ev.get("event_type", "other"), "📅 Event")
        vevent.add("SUMMARY", f"{label}: {ev['title']}")

        start: datetime = ev["start"]
        end: datetime = ev.get("end") or (start + timedelta(hours=1))

        # 确保有时区信息
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone(timedelta(hours=8)))  # SGT
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone(timedelta(hours=8)))

        vevent.add("DTSTART", start)
        vevent.add("DTEND", end)
        vevent.add("DTSTAMP", datetime.now(timezone.utc))

        desc_parts = [ev.get("description", "")]
        if ev.get("url"):
            desc_parts.append(f"URL: {ev['url']}")
        desc_parts.append("Synced by NUS Campus Assistant (OpenClaw + WaveSpeed AI)")
        vevent.add("DESCRIPTION", "\n".join(p for p in desc_parts if p))

        if ev.get("location"):
            vevent.add("LOCATION", ev["location"])

        # 颜色（支持的客户端会显示）
        color = TYPE_COLORS.get(ev.get("event_type", "other"), "GRAY")
        vevent.add("COLOR", color)

        # 提醒：提前 1 天邮件 + 提前 1 小时弹窗
        alarm_email = Alarm()
        alarm_email.add("ACTION", "EMAIL")
        alarm_email.add("DESCRIPTION", f"Reminder: {ev['title']}")
        alarm_email.add("TRIGGER", timedelta(days=-1))
        alarm_email.add("SUMMARY", f"[NUS] Due tomorrow: {ev['title']}")
        vevent.add_component(alarm_email)

        alarm_popup = Alarm()
        alarm_popup.add("ACTION", "DISPLAY")
        alarm_popup.add("DESCRIPTION", f"Due in 1 hour: {ev['title']}")
        alarm_popup.add("TRIGGER", timedelta(hours=-1))
        vevent.add_component(alarm_popup)

        cal.add_component(vevent)

    return cal.to_ical()
