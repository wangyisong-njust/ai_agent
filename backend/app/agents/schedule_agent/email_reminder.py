# -*- coding: utf-8 -*-
"""
邮件提醒发送器
将 .ics 日历文件作为附件发送给用户，同时包含所有事件的 HTML 摘要
支持 Gmail SMTP（已在 .env 配置）
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from app.config import get_settings

settings = get_settings()

SGT = timezone(timedelta(hours=8))

TYPE_EMOJI = {
    "exam": "📝", "deadline": "⏰", "quiz": "✏️",
    "project": "🚀", "assignment": "📚", "other": "📅",
}
TYPE_COLOR = {
    "exam": "#ef4444", "deadline": "#f97316", "quiz": "#eab308",
    "project": "#22c55e", "assignment": "#3b82f6", "other": "#6b7280",
}


def _format_dt(dt: datetime | None) -> str:
    if not dt:
        return "TBD"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    sgt = dt.astimezone(SGT)
    return sgt.strftime("%a, %d %b %Y  %H:%M SGT")


def _days_until(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    days = (dt.astimezone(SGT).date() - datetime.now(SGT).date()).days
    if days < 0:
        return "<span style='color:#6b7280'>Past</span>"
    if days == 0:
        return "<span style='color:#ef4444;font-weight:bold'>Due TODAY</span>"
    if days == 1:
        return "<span style='color:#f97316;font-weight:bold'>Due TOMORROW</span>"
    if days <= 7:
        return f"<span style='color:#f97316'>{days} days left</span>"
    return f"<span style='color:#6b7280'>{days} days left</span>"


def build_email_html(events: List[Dict], source_label: str = "NUS Campus") -> str:
    rows = ""
    for ev in sorted(events, key=lambda e: e.get("start") or datetime.max.replace(tzinfo=timezone.utc)):
        etype = ev.get("event_type", "other")
        emoji = TYPE_EMOJI.get(etype, "📅")
        color = TYPE_COLOR.get(etype, "#6b7280")
        rows += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #f3f4f6">
            <span style="background:{color};color:white;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600">{emoji} {etype.upper()}</span>
          </td>
          <td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;font-weight:500;color:#111827">{ev['title']}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;color:#6b7280;font-size:13px">{_format_dt(ev.get('start'))}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #f3f4f6;font-size:13px">{_days_until(ev.get('start'))}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f9fafb;margin:0;padding:20px">
  <div style="max-width:700px;margin:0 auto">
    <div style="background:linear-gradient(135deg,#002469,#003d99);color:white;padding:24px 28px;border-radius:12px 12px 0 0">
      <div style="font-size:20px;font-weight:700">🎓 NUS Campus Schedule</div>
      <div style="font-size:13px;opacity:0.8;margin-top:4px">Synced by OpenClaw Agent · WaveSpeed AI · {datetime.now(SGT).strftime("%d %b %Y")}</div>
    </div>
    <div style="background:white;border-radius:0 0 12px 12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
      <div style="padding:16px 20px;background:#f8faff;border-bottom:1px solid #e5e7eb;font-size:13px;color:#374151">
        📎 <strong>{len(events)} events</strong> from <strong>{source_label}</strong> —
        <span style="color:#002469">A .ics calendar file is attached. Open it to import all events into your calendar app.</span>
      </div>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#f9fafb">
            <th style="padding:8px 12px;text-align:left;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase">Type</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase">Event</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase">Date & Time</th>
            <th style="padding:8px 12px;text-align:left;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase">Countdown</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <div style="padding:16px 20px;font-size:12px;color:#9ca3af;border-top:1px solid #f3f4f6">
        Reminders are embedded in the .ics file: 24h before (email) + 1h before (popup).<br>
        Powered by NUS Campus Intelligent Assistant
      </div>
    </div>
  </div>
</body>
</html>"""


async def send_schedule_email(
    to_email: str,
    events: List[Dict],
    ics_bytes: bytes,
    source_label: str = "NUS Campus",
) -> Dict:
    """
    发送包含 .ics 附件的日程提醒邮件
    Returns: {"success": bool, "error": str | None}
    """
    if not settings.smtp_user or not settings.smtp_password:
        return {"success": False, "error": "SMTP not configured in .env"}

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"📅 NUS Schedule: {len(events)} events synced — {datetime.now(SGT).strftime('%d %b %Y')}"
    msg["From"] = f"NUS Campus Assistant <{settings.smtp_user}>"
    msg["To"] = to_email

    # HTML body
    html_body = build_email_html(events, source_label)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # .ics 附件
    ics_part = MIMEBase("text", "calendar", method="PUBLISH", charset="utf-8")
    ics_part.set_payload(ics_bytes)
    encoders.encode_base64(ics_part)
    ics_part.add_header("Content-Disposition", 'attachment; filename="nus_schedule.ics"')
    ics_part.add_header("Content-Type", 'text/calendar; method=PUBLISH; charset="UTF-8"')
    msg.attach(ics_part)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to_email, msg.as_bytes())
        return {"success": True, "error": None}
    except Exception as e:
        return {"success": False, "error": str(e)}
