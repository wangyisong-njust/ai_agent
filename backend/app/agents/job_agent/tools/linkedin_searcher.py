# -*- coding: utf-8 -*-
"""
LinkedIn 职位搜索工具
使用 Playwright 搜索 LinkedIn Jobs，返回职位列表（无需登录即可搜索）
"""
import asyncio
import random
from typing import List, Dict
from playwright.async_api import async_playwright


async def _random_delay(min_s: float = 0.5, max_s: float = 1.5):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def search_linkedin_jobs(
    keywords: str,
    location: str = "Singapore",
    max_results: int = 10,
) -> List[Dict]:
    """
    搜索 LinkedIn Jobs，返回职位列表
    每个职位包含: title, company, location, url, jd_text
    无需登录，使用公开搜索页面
    """
    jobs = []
    search_url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={keywords.replace(' ', '%20')}"
        f"&location={location.replace(' ', '%20')}"
        f"&f_AL=true"  # Easy Apply only
        f"&sortBy=R"   # Most recent
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(2, 3)

            # 滚动加载更多职位
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await _random_delay(0.8, 1.5)

            # 获取职位卡片
            job_cards = await page.query_selector_all(".jobs-search__results-list > li, .base-card")

            for card in job_cards[:max_results]:
                try:
                    title_el = await card.query_selector(".base-search-card__title, h3.base-search-card__title")
                    company_el = await card.query_selector(".base-search-card__subtitle, h4.base-search-card__subtitle")
                    location_el = await card.query_selector(".job-search-card__location")
                    link_el = await card.query_selector("a.base-card__full-link, a[href*='/jobs/view/']")

                    title = (await title_el.inner_text()).strip() if title_el else ""
                    company = (await company_el.inner_text()).strip() if company_el else ""
                    loc = (await location_el.inner_text()).strip() if location_el else location
                    url = await link_el.get_attribute("href") if link_el else ""

                    if title and url:
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": loc,
                            "url": url.split("?")[0],  # 去掉追踪参数
                            "jd_text": "",
                        })
                except Exception:
                    continue

            # 获取每个职位的 JD 文本
            for job in jobs:
                try:
                    await page.goto(job["url"], wait_until="domcontentloaded", timeout=20000)
                    await _random_delay(1, 2)
                    # 尝试多个可能的 JD 选择器（LinkedIn 会频繁改 class）
                    jd_el = await page.query_selector(
                        ".description__text, "
                        ".show-more-less-html__markup, "
                        ".jobs-description__content, "
                        "[class*='description'] .jobs-box__html-content, "
                        "article.jobs-description"
                    )
                    if jd_el:
                        job["jd_text"] = (await jd_el.inner_text()).strip()[:3000]
                    else:
                        # 降级：用页面全部可见文本中截取职位相关部分
                        body_text = await page.evaluate("document.body.innerText")
                        job["jd_text"] = body_text[:2000] if body_text else ""
                except Exception:
                    # 最低限度：用标题+公司名构造伪 JD 供 AI 分析
                    job["jd_text"] = f"Position: {job['title']}\nCompany: {job['company']}\nLocation: {job['location']}"

        finally:
            await browser.close()

    return jobs
