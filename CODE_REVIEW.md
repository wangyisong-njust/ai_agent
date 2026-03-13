# Code Review Report — NUS Campus Intelligent Assistant

> 审查日期：2026-03-13
> 审查范围：`backend/` 全部 Python 代码
> 审查人：Claude Code（测试工程师 / Code Reviewer）
> 总体评分：**7.5 / 10**

架构设计清晰，三 Agent 分工合理，流式 RAG 实现是亮点。但存在若干逻辑 Bug 和安全隐患，需在上线前修复。

---

## 目录

- [严重 Bug（P0/P1）](#严重-bugp0p1)
- [中等问题（P2/P3）](#中等问题p2p3)
- [做得好的地方](#做得好的地方)
- [修复优先级汇总](#修复优先级汇总)

---

## 严重 Bug（P0/P1）

### BUG-01 · `canvas_fetcher.py` — 同步 API 调用阻塞异步事件循环

**优先级：** 🔴 P0
**文件：** `backend/app/agents/canvas_agent/tools/canvas_fetcher.py:19-34`

**问题描述：**
`canvasapi` 是**同步库**，但被放在 `async def` 函数中直接调用，没有使用 `asyncio.to_thread()` 包装。这会**阻塞整个 FastAPI 事件循环**，导致触发 Canvas 同步时所有其他 API 请求均无法响应。

```python
# 问题代码
async def fetch_active_courses(token: str | None = None) -> List[Dict]:
    canvas = get_canvas_client(token)
    user = canvas.get_current_user()          # ← 同步阻塞调用！
    for course in user.get_courses(...):      # ← 同步迭代！
        ...
```

**同样受影响的函数：**
- `fetch_upcoming_assignments()` (line 37)
- `fetch_announcements()` (line 64)
- `gcal_pusher.py` 中 `service.events().insert().execute()` (同步 HTTP 调用)

**修复建议：**
```python
import asyncio

async def fetch_active_courses(token: str | None = None) -> List[Dict]:
    def _sync_fetch():
        canvas = get_canvas_client(token)
        user = canvas.get_current_user()
        courses = []
        for course in user.get_courses(enrollment_state="active", include=["total_scores"]):
            courses.append({...})
        return courses

    return await asyncio.to_thread(_sync_fetch)
```

---

### BUG-02 · `rag_service.py` — `_hybrid_merge` 中 lambda 变量名遮蔽外层参数

**优先级：** 🔴 P0
**文件：** `backend/app/agents/knowledge_agent/rag_service.py:66-67`

**问题描述：**
`sorted()` 的 `lambda k:` 中参数名 `k` 与外层函数参数 `k: int = 5` 同名，导致作用域遮蔽。最后一行 `sorted_keys[:k]` 中的 `k` 已经是 lambda 的局部变量，行为未定义，实际上 RAG 返回的文档数量不受 `k=5` 控制。

```python
# 问题代码
def _hybrid_merge(semantic_results, bm25_results, k: int = 5) -> List[Dict]:
    ...
    sorted_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)
    #                                         ↑ 遮蔽外层参数 k=5
    return [doc_map[k] for k in sorted_keys[:k]]
    #                                       ↑ 此 k 已被污染
```

**修复建议：**
```python
sorted_keys = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
return [doc_map[key] for key in sorted_keys[:k]]
```

---

### BUG-03 · `linkedin_browser.py` — `self._page` 未初始化防护

**优先级：** 🔴 P1
**文件：** `backend/app/agents/job_agent/tools/linkedin_browser.py:73`

**问题描述：**
`_page` 属性只在 `login()` 成功时被赋值（`self._page = page`），`__init__` 中没有初始化。若 `login()` 未调用或登录失败，直接调用 `apply_easy_apply()` 会抛出 `AttributeError: 'LinkedInApplicator' object has no attribute '_page'`，且该错误在 `agent.py` 中没有被捕获。

```python
# 问题代码
class LinkedInApplicator:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
        # ← 没有 self._page = None

async def apply_easy_apply(self, job_url: str, resume_data: dict) -> Dict:
    page = self._page  # ← 若 login() 未调用，AttributeError
```

**修复建议：**
```python
def __init__(self):
    self.browser: Optional[Browser] = None
    self.playwright = None
    self._page = None  # 显式初始化

async def apply_easy_apply(self, job_url: str, resume_data: dict) -> Dict:
    if self._page is None:
        raise RuntimeError("Must call login() before apply_easy_apply()")
    page = self._page
```

---

### BUG-04 · `canvas_agent/agent.py` — 并发摘要无异常隔离，无限速

**优先级：** 🔴 P1
**文件：** `backend/app/agents/canvas_agent/agent.py:47`

**问题描述：**
所有公告并发调用 WaveSpeed AI 进行摘要，存在两个问题：
1. `asyncio.gather()` 没有 `return_exceptions=True`，任意一条公告摘要失败都会让整个 Canvas 同步抛出异常，已存入数据库的课程和作业数据不会回滚（因 `db.commit()` 在 gather 之后）。
2. 若用户有 50+ 条公告，会同时发起 50+ 个 API 请求，极易触发 WaveSpeed 限流（rate limit）。

```python
# 问题代码
announcements = await asyncio.gather(*[summarize(ann) for ann in announcements])
# ← 无 return_exceptions=True，无并发限制
```

**修复建议：**
```python
import asyncio

# 方案一：使用 return_exceptions=True 隔离失败
results = await asyncio.gather(*[summarize(ann) for ann in announcements], return_exceptions=True)
announcements = [r for r in results if not isinstance(r, Exception)]

# 方案二：使用 Semaphore 限制并发数（推荐同时使用）
sem = asyncio.Semaphore(5)
async def summarize_limited(ann):
    async with sem:
        return await summarize(ann)
announcements = await asyncio.gather(*[summarize_limited(ann) for ann in announcements], return_exceptions=True)
```

---

## 中等问题（P2/P3）

### BUG-05 · `routers/jobs.py` — 文件路径遍历漏洞

**优先级：** 🟡 P2
**文件：** `backend/app/routers/jobs.py:22`

**问题描述：**
`file.filename` 由客户端控制，若传入 `../../etc/passwd.pdf` 或 `../config/.env`，上传文件会被写入任意路径，造成文件覆盖或信息泄露。

```python
# 问题代码
file_path = f"{UPLOAD_DIR}/{file.filename}"  # ← 未过滤路径
```

**修复建议：**
```python
import os
safe_filename = os.path.basename(file.filename)  # 去除路径前缀
file_path = os.path.join(UPLOAD_DIR, safe_filename)
```

---

### BUG-06 · `routers/jobs.py` — LinkedIn 密码明文在请求体传输

**优先级：** 🟡 P2
**文件：** `backend/app/routers/jobs.py:52-67`

**问题描述：**
LinkedIn 密码作为 JSON 字段通过 POST 请求体传入 FastAPI，明文存储在 `ApplyRequest` 对象中，并直接传递到 agent 层。若日志系统打印请求体、或请求被中间人截获，密码会泄露。

```python
# 问题代码
class ApplyRequest(BaseModel):
    linkedin_password: Optional[str] = None  # ← 明文密码字段
```

**修复建议：**
- 短期：确保 HTTPS 强制使用，禁止将 `ApplyRequest` 对象整体打印到日志。
- 长期：改用 OAuth2 Authorization Code Flow 替代密码，或通过前端 Session 管理凭证，后端不持有密码。

---

### BUG-07 · `wavespeed_service.py` — JSON 提取使用贪婪匹配，易解析失败

**优先级：** 🟡 P2
**文件：** `backend/app/services/wavespeed_service.py:94` 和 `148`

**问题描述：**
使用 `re.search(r'\{.*\}', result, re.DOTALL)` 提取 LLM 输出中的 JSON。`.*` 为贪婪匹配，若 LLM 在 JSON 外附带说明文字（如 `Here is the result: {...} Note: ...`），正则会尝试匹配从第一个 `{` 到最后一个 `}` 的最长字符串，可能包含多余内容导致 `json.loads` 失败。LLM 还可能返回 ` ```json {...} ``` ` 格式，正则无法正确提取。

```python
# 问题代码（analyze_jd_resume 和 parse_resume 均有此问题）
json_match = re.search(r'\{.*\}', result, re.DOTALL)
```

**修复建议：**
```python
# 先尝试直接解析，再 fallback 到正则（非贪婪）
import json, re

def extract_json(text: str) -> dict:
    # 去除 markdown 代码块
    text = re.sub(r'```(?:json)?\s*', '', text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*?\}', text, re.DOTALL)  # 非贪婪
        if match:
            return json.loads(match.group())
    return {}
```

---

### BUG-08 · `chroma_client.py` — 嵌入模型维度注释错误

**优先级：** 🟡 P3
**文件：** `backend/app/agents/knowledge_agent/vectorstore/chroma_client.py:12`

**问题描述：**
注释称 `all-MiniLM-L6-v2` 为 768 维，但该模型实际输出 **384 维**向量。768 维对应的是 `all-mpnet-base-v2`。虽然不影响运行（ChromaDB 自动适配），但错误注释会误导后续维护者在选择模型或配置向量数据库时做出错误决策。

```python
# 问题代码
EMBED_MODEL = "all-MiniLM-L6-v2"  # 本地免费模型，768维  ← 错误，实际为 384 维
```

**修复建议：**
```python
EMBED_MODEL = "all-MiniLM-L6-v2"  # 本地免费模型，384 维
```

---

### BUG-09 · `rag_service.py` — BM25 索引无失效机制

**优先级：** 🟡 P3
**文件：** `backend/app/agents/knowledge_agent/rag_service.py:16-27`

**问题描述：**
BM25 索引在首次调用时构建并缓存为全局变量，此后永不更新。当用户通过 `POST /api/knowledge/ingest` 触发知识库更新后，新入库的文档不会被 BM25 检索到，直到服务重启。语义检索（ChromaDB）不受影响，但混合检索的关键词侧会持续返回过时结果。

```python
# 问题代码
_bm25_cache = None  # 全局缓存，一旦构建永不失效

def _get_bm25():
    global _bm25_cache, _bm25_corpus
    if _bm25_cache is None:  # ← 只检查是否为 None，不检查是否过期
        ...
```

**修复建议：**
```python
_bm25_cache = None
_bm25_corpus = None
_bm25_doc_count = 0  # 记录构建时的文档数

def invalidate_bm25_cache():
    """知识库更新后调用此函数使缓存失效"""
    global _bm25_cache, _bm25_corpus, _bm25_doc_count
    _bm25_cache = None
    _bm25_corpus = None
    _bm25_doc_count = 0
```

在 `routers/knowledge.py` 的 `trigger_ingestion()` 完成后调用 `invalidate_bm25_cache()`。

---

### BUG-10 · `canvas_agent/agent.py` — Google Calendar 事件 ID 查询做全表扫描

**优先级：** 🟡 P3
**文件：** `backend/app/agents/canvas_agent/agent.py:98-99`

**问题描述：**
每次同步都查询 `CanvasAssignment` 全表来构建 `existing_event_ids` 字典，当历史作业积累到数百条时，性能会随数据量线性下降。实际上只需查询本次同步批次中涉及的 `canvas_id` 即可。

```python
# 问题代码
existing = await db.scalars(select(CanvasAssignment))  # ← 全表扫描
existing_event_ids = {a.canvas_id: a.gcal_event_id for a in existing.all()}
```

**修复建议：**
```python
current_ids = [a["id"] for a in assignments]
existing = await db.scalars(
    select(CanvasAssignment).where(CanvasAssignment.canvas_id.in_(current_ids))
)
existing_event_ids = {a.canvas_id: a.gcal_event_id for a in existing.all()}
```

---

## 做得好的地方

| # | 亮点 | 说明 |
|---|------|------|
| ✅ 1 | **RRF 混合检索** | 语义 + BM25 结合，是现代 RAG 的最佳实践，方向完全正确 |
| ✅ 2 | **异步 DB 操作** | 正确使用 `AsyncSessionLocal` + `async with`，数据库层异步设计良好 |
| ✅ 3 | **Playwright 防检测** | `--disable-blink-features=AutomationControlled` + navigator.webdriver 覆盖 + 随机延迟，反自动化处理较完整 |
| ✅ 4 | **Canvas 数据增量去重** | `if not existing: db.add(...)` 防止重复插入，逻辑正确 |
| ✅ 5 | **WebSocket 流式输出** | `answer_question` 作为异步生成器设计合理，前端 token-by-token 接收体验流畅 |
| ✅ 6 | **资源释放保障** | `run_job_apply` 中 `finally: await applicator.stop()` 确保浏览器总被关闭，无内存泄漏 |
| ✅ 7 | **多层 PDF 解析降级** | `pdfplumber` 失败后自动降级到 `PyMuPDF`，健壮性好 |

---

## 修复优先级汇总

| ID | 文件 | 问题 | 优先级 | 影响 |
|----|------|------|--------|------|
| BUG-01 | `canvas_fetcher.py` | 同步 API 阻塞事件循环 | 🔴 P0 | Canvas 同步冻结整个服务 |
| BUG-02 | `rag_service.py` | lambda 变量遮蔽 `k=5` | 🔴 P0 | RAG 返回文档数量不受控 |
| BUG-03 | `linkedin_browser.py` | `_page` 未初始化防护 | 🔴 P1 | job apply 直接崩溃 |
| BUG-04 | `canvas_agent/agent.py` | 并发摘要无异常隔离 | 🔴 P1 | 一条公告失败导致整批同步失败 |
| BUG-05 | `routers/jobs.py` | 路径遍历漏洞 | 🟡 P2 | 任意文件写入，安全风险 |
| BUG-06 | `routers/jobs.py` | 密码明文传输 | 🟡 P2 | 凭证泄露风险 |
| BUG-07 | `wavespeed_service.py` | JSON 贪婪正则解析 | 🟡 P2 | LLM 解析偶发失败，返回空结果 |
| BUG-08 | `chroma_client.py` | 嵌入维度注释错误 | 🟡 P3 | 误导维护者，不影响运行 |
| BUG-09 | `rag_service.py` | BM25 缓存不失效 | 🟡 P3 | 知识库更新后关键词检索不刷新 |
| BUG-10 | `canvas_agent/agent.py` | GCal 查询全表扫描 | 🟡 P3 | 数据量大时性能下降 |
