# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.database import Base


class SyllabusEvent(Base):
    __tablename__ = "syllabus_events"

    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(500))
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, default="")
    event_type = Column(String(50), default="other")   # exam / deadline / quiz / project / other
    source_image = Column(String(500), default="")     # 原始图片路径
    gcal_event_id = Column(String(200), default="")    # Google Calendar event ID
    confirmed = Column(Boolean, default=False)          # 用户已确认
    created_at = Column(DateTime, server_default=func.now())
