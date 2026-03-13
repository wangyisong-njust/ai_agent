# -*- coding: utf-8 -*-
"""
简历解析工具
PDF → 结构化 JSON（通过 WaveSpeed AI）
"""
import pdfplumber
import fitz  # PyMuPDF
from pathlib import Path
from app.services.wavespeed_service import parse_resume


async def extract_text_from_pdf(file_path: str) -> str:
    """从 PDF 提取纯文本"""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception:
        # 备用方案：PyMuPDF
        try:
            doc = fitz.open(file_path)
            for page in doc:
                text += page.get_text() + "\n"
        except Exception as e:
            raise ValueError(f"Cannot parse PDF: {e}")
    return text.strip()


async def parse_resume_file(file_path: str) -> dict:
    """解析简历文件，返回结构化数据"""
    text = await extract_text_from_pdf(file_path)
    if not text:
        raise ValueError("Resume is empty or unreadable")
    result = await parse_resume(text)
    result["raw_text"] = text[:500]  # 保留前500字符供调试
    return result
