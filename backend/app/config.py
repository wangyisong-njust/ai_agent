# -*- coding: utf-8 -*-
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # WaveSpeed AI - 赞助商 LLM 入口
    wavespeed_api_key: str = ""
    wavespeed_base_url: str = "https://api.wavespeed.ai/api/v3"
    wavespeed_llm_model: str = "google/gemini-2.5-flash"

    # OpenClaw
    openclaw_gateway_url: str = "http://localhost:3000"
    openclaw_api_key: str = ""

    # Canvas LMS
    canvas_base_url: str = "https://nus.instructure.com"
    canvas_access_token: str = ""

    # Google Calendar
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/canvas/oauth2callback"
    google_gcal_redirect_uri: str = "http://localhost:8000/api/schedule/gcal/callback"

    # App
    secret_key: str = "change-this-in-production"
    database_url: str = "sqlite:///./data/app.db"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
