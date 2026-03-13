# -*- coding: utf-8 -*-
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from app.database import Base


class CanvasCourse(Base):
    __tablename__ = "canvas_courses"

    id = Column(Integer, primary_key=True)
    canvas_id = Column(Integer, unique=True, index=True)
    name = Column(String(300))
    course_code = Column(String(100))
    semester = Column(String(50))
    synced_at = Column(DateTime, server_default=func.now())


class CanvasAssignment(Base):
    __tablename__ = "canvas_assignments"

    id = Column(Integer, primary_key=True)
    canvas_id = Column(Integer, unique=True, index=True)
    course_id = Column(Integer)
    course_name = Column(String(300))
    name = Column(String(500))
    due_at = Column(DateTime, nullable=True)
    points_possible = Column(Integer, default=0)
    description = Column(Text, default="")
    gcal_event_id = Column(String(200), default="")  # Google Calendar event ID
    synced_at = Column(DateTime, server_default=func.now())


class CanvasAnnouncement(Base):
    __tablename__ = "canvas_announcements"

    id = Column(Integer, primary_key=True)
    canvas_id = Column(Integer, unique=True, index=True)
    course_id = Column(Integer)
    course_name = Column(String(300))
    title = Column(String(500))
    message = Column(Text, default="")
    summary = Column(Text, default="")   # WaveSpeed AI 生成的摘要
    posted_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False)
    synced_at = Column(DateTime, server_default=func.now())
