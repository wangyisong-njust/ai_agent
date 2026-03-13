# -*- coding: utf-8 -*-
"""
LinkedIn Easy Apply 自动化工具
使用 Playwright 模拟浏览器操作
注意：仅用于授权的求职自动化，用户需确认每次提交
"""
import asyncio
import random
from typing import Dict, Optional
from playwright.async_api import async_playwright, Page, Browser


async def _random_delay(min_s: float = 0.5, max_s: float = 2.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _human_type(page: Page, selector: str, text: str):
    """模拟人工逐字输入"""
    await page.click(selector)
    await page.fill(selector, "")
    for char in text:
        await page.type(selector, char, delay=random.randint(30, 100))


class LinkedInApplicator:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
        self._page = None  # BUG-03 fix: 显式初始化，防止 login() 未调用时 AttributeError

    async def start(self, headless: bool = False):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def login(self, email: str = "", password: str = "", li_at_cookie: str = "") -> bool:
        """
        登录 LinkedIn，支持两种方式：
        1. li_at_cookie: 直接注入 session cookie（推荐，适合 Google 账号登录用户）
        2. email + password: 传统账密登录
        """
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        if li_at_cookie:
            # Cookie 登录：直接注入 li_at session cookie
            await context.add_cookies([{
                "name": "li_at",
                "value": li_at_cookie.strip(),
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }])
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            await _random_delay(2, 3)
        else:
            # 账密登录
            await page.goto("https://www.linkedin.com/login")
            await _random_delay(1, 2)
            await _human_type(page, "#username", email)
            await _random_delay(0.3, 0.8)
            await _human_type(page, "#password", password)
            await _random_delay(0.5, 1.0)
            await page.click('[type="submit"]')
            await _random_delay(2, 4)

        if "feed" in page.url or "mynetwork" in page.url or "linkedin.com/in/" in page.url:
            self._page = page
            return True
        return False

    async def apply_easy_apply(self, job_url: str, resume_data: dict) -> Dict:
        """
        对单个 LinkedIn Easy Apply 职位进行申请
        返回申请结果
        """
        # BUG-03 fix: 检查 login() 是否已成功调用
        if self._page is None:
            raise RuntimeError("Must call login() before apply_easy_apply()")
        page = self._page
        await page.goto(job_url)
        await _random_delay(2, 3)

        result = {
            "url": job_url,
            "status": "failed",
            "company": "",
            "role": "",
            "error": "",
        }

        try:
            # 提取职位信息
            result["role"] = await page.text_content(".job-details-jobs-unified-top-card__job-title") or ""
            result["company"] = await page.text_content(".job-details-jobs-unified-top-card__company-name") or ""

            # 获取 JD 文本
            jd_text = await page.text_content(".jobs-description__content") or ""

            # 检查是否有 Easy Apply 按钮
            easy_apply_btn = page.locator(".jobs-apply-button--top-card")
            if not await easy_apply_btn.is_visible():
                result["error"] = "No Easy Apply button"
                result["status"] = "skipped"
                return result

            await easy_apply_btn.click()
            await _random_delay(1, 2)

            # 处理申请表单（多步骤）
            max_steps = 10
            for step in range(max_steps):
                # 上传简历（如果出现文件上传）
                file_input = page.locator('input[type="file"]')
                if await file_input.count() > 0:
                    resume_path = resume_data.get("file_path", "")
                    if resume_path:
                        await file_input.set_input_files(resume_path)
                        await _random_delay(1, 2)

                # 填写联系方式
                phone_input = page.locator('input[id*="phone"]')
                if await phone_input.count() > 0 and resume_data.get("phone"):
                    await phone_input.fill(resume_data["phone"])
                    await _random_delay(0.3, 0.8)

                # 检查是否有 "Submit application" 按钮
                submit_btn = page.locator('button[aria-label="Submit application"]')
                review_btn = page.locator('button[aria-label="Review your application"]')
                next_btn = page.locator('button[aria-label="Continue to next step"]')

                if await submit_btn.is_visible():
                    await submit_btn.click()
                    await _random_delay(2, 3)
                    result["status"] = "applied"
                    break
                elif await review_btn.is_visible():
                    await review_btn.click()
                    await _random_delay(1, 2)
                elif await next_btn.is_visible():
                    await next_btn.click()
                    await _random_delay(1, 2)
                else:
                    break

        except Exception as e:
            result["error"] = str(e)

        return result


class NUSTalentConnectApplicator:
    """NUS TalentConnect 申请自动化（Symplicity CSM）"""

    async def login_and_apply(self, username: str, password: str, job_id: str) -> Dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            await page.goto("https://nus-csm.symplicity.com/students/")
            await _random_delay(1, 2)

            # NUS SSO login
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await _random_delay(2, 4)

            result = {"status": "pending", "job_id": job_id}

            try:
                # 导航到职位页面
                await page.goto(f"https://nus-csm.symplicity.com/students/app/jobs/detail/{job_id}")
                await _random_delay(1, 2)

                apply_btn = page.locator('a:has-text("Apply"), button:has-text("Apply")')
                if await apply_btn.is_visible():
                    await apply_btn.click()
                    await _random_delay(1, 2)
                    result["status"] = "applied"
                else:
                    result["status"] = "no_apply_button"
            except Exception as e:
                result["status"] = "failed"
                result["error"] = str(e)
            finally:
                await browser.close()

            return result
